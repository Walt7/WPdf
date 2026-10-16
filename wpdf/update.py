"""Aggiornamenti: controllo dell'ultima Release su GitHub e sostituzione dell'eseguibile.

Il controllo parte solo quando l'interfaccia lo chiede (si puo' disattivare) e invia a GitHub
una sola richiesta anonima di versione: nessun dato dei documenti esce dal computer.
"""
import hashlib, json, os, re, subprocess, sys, tempfile
from pathlib import Path
from urllib.request import Request, urlopen

from . import __version__

REPO = "Walt7/WPdf"
API = os.environ.get("WPDF_UPDATE_URL", f"https://api.github.com/repos/{REPO}/releases/latest")
ASSET = "WPdf.exe"
TIMEOUT = 6


def parse_version(v):
    """'v1.2.3' -> (1, 2, 3); parti non numeriche ignorate."""
    return tuple(int(n) for n in re.findall(r"\d+", v or "")[:3]) or (0,)


def is_newer(latest, current=__version__):
    return parse_version(latest) > parse_version(current)


def frozen_exe():
    """Percorso dell'eseguibile se WPdf gira come WPdf.exe (PyInstaller), altrimenti None."""
    return Path(sys.executable).resolve() if getattr(sys, "frozen", False) and sys.platform == "win32" else None


def _get(url, accept="application/vnd.github+json"):
    req = Request(url, headers={"Accept": accept, "User-Agent": f"WPdf/{__version__}"})
    return urlopen(req, timeout=TIMEOUT)


def summarize(rel, current=__version__):
    """Dalla risposta dell'API GitHub ai soli dati che servono all'interfaccia."""
    asset = next((a for a in rel.get("assets", []) if a.get("name") == ASSET), None)
    latest = rel.get("tag_name", "")
    return {
        "current": current,
        "latest": latest.lstrip("v"),
        "newer": is_newer(latest, current),
        "url": rel.get("html_url", f"https://github.com/{REPO}/releases"),
        "notes": (rel.get("body") or "")[:4000],
        "asset": None if not asset else {"url": asset["browser_download_url"], "size": asset.get("size"),
                                         "sha256": (asset.get("digest") or "").removeprefix("sha256:") or None},
        "canInstall": bool(asset and frozen_exe()),
        "pip": f"pip install -U git+https://github.com/{REPO}",
    }


_cache = None


def check(force=False):
    """Ultima Release (una richiesta per avvio, salvo force)."""
    global _cache
    if _cache is None or force:
        with _get(API) as r:
            _cache = summarize(json.load(r))
    return _cache


def download(asset, dest_dir):
    """Scarica il nuovo exe accanto a quello attuale e ne verifica dimensione e SHA-256."""
    fd, tmp = tempfile.mkstemp(prefix="WPdf-", suffix=".download", dir=dest_dir)
    h, n = hashlib.sha256(), 0
    try:
        with os.fdopen(fd, "wb") as f, _get(asset["url"], "application/octet-stream") as r:
            while chunk := r.read(1 << 16):
                f.write(chunk)
                h.update(chunk)
                n += len(chunk)
        if asset.get("size") and n != asset["size"]:
            raise ValueError(f"download incompleto ({n} di {asset['size']} byte)")
        if asset.get("sha256") and h.hexdigest() != asset["sha256"].lower():
            raise ValueError("il file scaricato non corrisponde (SHA-256 diverso)")
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return Path(tmp)


def swap(exe, new):
    """Mette `new` al posto di `exe`. Windows non cancella un exe in uso ma lo lascia rinominare:
    il vecchio diventa WPdf.old.exe e viene eliminato al prossimo avvio (cleanup_old)."""
    old = exe.with_name(exe.stem + ".old" + exe.suffix)
    old.unlink(missing_ok=True)
    exe.replace(old)
    try:
        new.replace(exe)
    except BaseException:
        old.replace(exe)   # rimetti a posto l'exe originale
        raise
    return old


def cleanup_old():
    exe = frozen_exe()
    if exe:
        try:
            exe.with_name(exe.stem + ".old" + exe.suffix).unlink(missing_ok=True)
        except OSError:
            pass   # ancora in uso (vecchia copia non ancora chiusa): riprova al prossimo avvio


def relaunch(exe, args):
    """Avvia il nuovo exe in una console sua. PYINSTALLER_RESET_ENVIRONMENT: il figlio non deve
    riusare la cartella temporanea del processo che sta per chiudersi."""
    env = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    # l'exe a file singolo gira in un job di Windows che alla chiusura termina anche i figli:
    # il nuovo processo deve uscirne, altrimenti muore insieme al vecchio
    breakaway = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
    try:
        subprocess.Popen([str(exe), *args], env=env, close_fds=True, creationflags=flags | breakaway)
    except OSError:   # job che non consente l'uscita
        subprocess.Popen([str(exe), *args], env=env, close_fds=True, creationflags=flags)
