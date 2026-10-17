"""Cifratura minima dei file delle firme, solo libreria standard.

- Chiave casuale di 32 byte in <cartella>/chiave.bin. Su Windows e' protetta con DPAPI
  (legata all'account Windows: copiata su un altro PC o account non si apre); altrove il file
  e' leggibile solo dal proprio utente.
- Ogni file: "WPF1" + nonce (16) + dati cifrati + tag (32). Cifratura: flusso HMAC-SHA256
  in modalita' contatore; integrita': HMAC-SHA256 su nonce e dati (encrypt-then-MAC).

Protegge le firme se qualcuno copia la cartella o il disco; non da chi usa lo stesso account
gia' aperto.
"""
import hashlib, hmac, os, secrets, sys
from pathlib import Path

MAGIC = b"WPF1"
ENTROPY = b"WPdf firme"


# ---------------------------------------------------------------- DPAPI (Windows)
def _dpapi(data, protect):
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def blob(b):
        buf = ctypes.create_string_buffer(b, len(b))
        return BLOB(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf

    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    src, _keep1 = blob(data)
    ent, _keep2 = blob(ENTROPY)
    out = BLOB()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    desc = "WPdf" if protect else None
    if not fn(ctypes.byref(src), desc, ctypes.byref(ent), None, None, 0x1, ctypes.byref(out)):   # 0x1: nessuna finestra
        raise OSError("DPAPI: chiave delle firme non leggibile con questo account Windows")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


# ---------------------------------------------------------------- chiave
def _load_key(folder):
    path = Path(folder) / "chiave.bin"
    if path.exists():
        raw = path.read_bytes()
        return _dpapi(raw, False) if sys.platform == "win32" else raw
    key = secrets.token_bytes(32)
    stored = _dpapi(key, True) if sys.platform == "win32" else key
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)   # solo l'utente (Linux/macOS)
    with os.fdopen(fd, "wb") as f:
        f.write(stored)
    return key


class Vault:
    def __init__(self, folder):
        master = _load_key(folder)
        self._enc = hmac.new(master, b"cifratura", hashlib.sha256).digest()
        self._mac = hmac.new(master, b"integrita", hashlib.sha256).digest()

    def _stream(self, nonce, n):
        out = bytearray()
        for i in range((n + 31) // 32):
            out += hmac.new(self._enc, nonce + i.to_bytes(8, "big"), hashlib.sha256).digest()
        return bytes(out[:n])

    def encrypt(self, data):
        nonce = secrets.token_bytes(16)
        ct = bytes(a ^ b for a, b in zip(data, self._stream(nonce, len(data))))
        tag = hmac.new(self._mac, nonce + ct, hashlib.sha256).digest()
        return MAGIC + nonce + ct + tag

    def decrypt(self, blob):
        if len(blob) < 52 or not blob.startswith(MAGIC):
            raise ValueError("file della firma non valido")
        nonce, ct, tag = blob[4:20], blob[20:-32], blob[-32:]
        if not hmac.compare_digest(tag, hmac.new(self._mac, nonce + ct, hashlib.sha256).digest()):
            raise ValueError("file della firma danneggiato o cifrato con un'altra chiave")
        return bytes(a ^ b for a, b in zip(ct, self._stream(nonce, len(ct))))
