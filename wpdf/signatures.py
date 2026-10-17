"""Firme salvate: immagini PNG con sfondo trasparente, conservate solo sul computer dell'utente.

Cartella: %APPDATA%\\WPdf\\firme su Windows, ~/.config/wpdf/firme altrove (WPDF_SIGNATURES_DIR per cambiarla).
Ogni firma e' <id>.sig, l'elenco con i nomi e' firme.dat: entrambi cifrati (vedi vault.py).
"""
import json, os, re, secrets, sys, threading, time
from pathlib import Path

import pymupdf

from .vault import Vault

MAX_BYTES = 5 * 1024 * 1024
MAX_SIDE = 2000
_lock = threading.Lock()
_vault = None


def folder():
    if os.environ.get("WPDF_SIGNATURES_DIR"):
        d = Path(os.environ["WPDF_SIGNATURES_DIR"])
    elif sys.platform == "win32" and os.environ.get("APPDATA"):
        d = Path(os.environ["APPDATA"]) / "WPdf" / "firme"
    else:
        d = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "wpdf" / "firme"
    d.mkdir(parents=True, exist_ok=True)
    return d


def vault():
    global _vault
    if _vault is None:
        _vault = Vault(folder())
    return _vault


def _index_path():
    return folder() / "firme.dat"


def _file(sid):
    return folder() / f"{sid}.sig"


def _save(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(vault().encrypt(data))
    tmp.replace(path)


def _read():
    try:
        items = json.loads(vault().decrypt(_index_path().read_bytes()))
    except FileNotFoundError:
        items = []
    return [i for i in items if _valid_id(i.get("id")) and _file(i["id"]).is_file()]


def _write(items):
    _save(_index_path(), json.dumps(items, ensure_ascii=False).encode())


def _valid_id(sid):
    return isinstance(sid, str) and re.fullmatch(r"[0-9a-f]{16}", sid) is not None


def listing():
    return _read()


def png(sid):
    if not _valid_id(sid):
        raise KeyError(sid)
    return vault().decrypt(_file(sid).read_bytes())


def _check_png(data):
    if len(data) > MAX_BYTES:
        raise ValueError("immagine troppo grande (massimo 5 MB)")
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("la firma deve essere un'immagine PNG")
    pix = pymupdf.Pixmap(data)
    if not pix.alpha:
        raise ValueError("la firma deve avere lo sfondo trasparente")
    if pix.width > MAX_SIDE or pix.height > MAX_SIDE or pix.width < 4 or pix.height < 4:
        raise ValueError("dimensioni dell'immagine non valide")
    return pix.width, pix.height


def add(data, name):
    w, h = _check_png(data)
    sid = secrets.token_hex(8)
    name = (name or "").strip()[:60] or time.strftime("Firma del %d/%m/%Y")
    with _lock:
        _save(_file(sid), data)
        items = _read()
        items.insert(0, {"id": sid, "name": name, "w": w, "h": h, "created": int(time.time())})
        _write(items)
    return items[0]


def rename(sid, name):
    name = (name or "").strip()[:60]
    if not name:
        raise ValueError("il nome non puo' essere vuoto")
    with _lock:
        items = _read()
        for i in items:
            if i["id"] == sid:
                i["name"] = name
                _write(items)
                return i
    raise KeyError(sid)


def delete(sid):
    if not _valid_id(sid):
        raise KeyError(sid)
    with _lock:
        _write([i for i in _read() if i["id"] != sid])
        _file(sid).unlink(missing_ok=True)


def place(page, sid, rect):
    """Disegna la firma nel contenuto della pagina, trasparenza compresa.
    rect e' in coordinate di pagina come le mostra il visualizzatore (pagina gia' ruotata)."""
    r = pymupdf.Rect(rect)
    if r.is_empty or r.width < 2 or r.height < 2:
        raise ValueError("area della firma non valida")
    r = r * page.derotation_matrix   # dalle coordinate visualizzate a quelle del PDF
    page.insert_image(r, stream=png(sid), keep_proportion=False, overlay=True, rotate=page.rotation)
