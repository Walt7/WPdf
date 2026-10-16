"""WPdf - editor PDF locale: server stdlib + PyMuPDF. Avvio: python -m wpdf [file.pdf]

Livelli:
  orig  = testo del contenuto pagina (modulo originale, anche testo appiattito)
  foxit = annotazioni FreeText non create da questa app (es. Macchina da scrivere di Foxit)
  app   = annotazioni FreeText create da questa app (title "WPdfEditor")
"""
import argparse, json, os, re, sys, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote

import pymupdf as fitz

from . import __version__

HERE = Path(__file__).parent
PORT = int(os.environ.get("EDITOR_PORT", 8765))
LOCK = threading.Lock()
APP_TITLE = "WPdfEditor"
APP_SUBJECT = "Modifica WPdfEditor"
ASSETS = {"logo.svg": "image/svg+xml", "favicon.svg": "image/svg+xml", "favicon.ico": "image/x-icon",
          "apple-touch-icon.png": "image/png"}   # file serviti da /assets/ (elenco chiuso)


class State:
    doc = None
    name = "documento.pdf"
    path = None    # percorso su disco, se noto (per salvataggio diretto)
    history = []   # bytes per ogni stato
    idx = -1
    _plain = None  # (idx, doc senza annotazioni) cache per leggere il livello orig

    @classmethod
    def load(cls, data, name, path=None):
        doc = fitz.open(stream=data, filetype="pdf")   # prima di toccare lo stato: un file non valido non cambia nulla
        cls.path = str(path) if path else None
        cls.doc = doc
        cls.name = name
        cls.history = [data]
        cls.idx = 0
        cls._plain = None

    MAX_HISTORY = 40   # stati conservati per annulla/ripristina (ognuno e' una copia del PDF)

    @classmethod
    def push(cls):
        data = cls.doc.tobytes(garbage=0)
        cls.history = cls.history[: cls.idx + 1] + [data]
        cls.idx += 1
        if len(cls.history) > cls.MAX_HISTORY:
            del cls.history[0]
            cls.idx -= 1
        cls._plain = None

    @classmethod
    def goto(cls, idx):
        cls.idx = idx
        cls.doc = fitz.open(stream=cls.history[idx], filetype="pdf")
        cls._plain = None

    @classmethod
    def plain(cls):
        """Copia del documento senza annotazioni: il testo estratto è solo del contenuto pagina."""
        if cls._plain is None or cls._plain[0] != cls.idx:
            d = fitz.open(stream=cls.history[cls.idx], filetype="pdf")
            for pg in d:
                for a in list(pg.annots() or []):
                    pg.delete_annot(a)
            cls._plain = (cls.idx, d)
        return cls._plain[1]


def rgb(c):
    return ((c >> 16) & 255) / 255, ((c >> 8) & 255) / 255, (c & 255) / 255


def pick_font(font, bold, italic):
    f = (font or "").lower()
    bold = bold or "bold" in f
    italic = italic or "italic" in f or "oblique" in f
    if "times" in f or "serif" in f and "sans" not in f:
        return {(0, 0): "tiro", (1, 0): "tibo", (0, 1): "tiit", (1, 1): "tibi"}[(bold, italic)]
    if "courier" in f or "mono" in f:
        return {(0, 0): "cour", (1, 0): "cobo", (0, 1): "coit", (1, 1): "cobi"}[(bold, italic)]
    return {(0, 0): "helv", (1, 0): "hebo", (0, 1): "heit", (1, 1): "hebi"}[(bold, italic)]


# ---------------------------------------------------------------- annotazioni
def _calibrate():
    """Distanza tra angolo del rettangolo FreeText e origine (baseline) del testo, per pt di corpo."""
    d = fitz.open()
    p = d.new_page()
    a = p.add_freetext_annot(fitz.Rect(100, 100, 300, 160), "H", fontsize=20, fontname="helv",
                             text_color=(0, 0, 0), fill_color=None)
    for b in p.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                return (s["origin"][0] - a.rect.x0) / 20, (s["origin"][1] - a.rect.y0) / 20
    return 0.0, 0.8


KX, KY = _calibrate()


def make_annot(page, text, ox, oy, size, color, fn, title, subject, width=None, align=0):
    """FreeText con baseline in (ox, oy). width fisso + align=1 per centrare (lettere in caselle)."""
    tw = fitz.get_text_length(text, fontname=fn, fontsize=size)
    if width is None:
        w = tw * 1.1 + 2 * KX * size + 6   # margine: evita l'a-capo automatico
        x0 = ox - KX * size
    else:
        w = width
        x0 = ox
    y0 = oy - KY * size
    a = page.add_freetext_annot(fitz.Rect(x0, y0, x0 + w, y0 + size * 1.5), text, fontsize=size,
                                fontname=fn, text_color=color, fill_color=None, align=align)
    a.set_info(title=title, subject=subject, content=text)
    a.set_flags(fitz.PDF_ANNOT_IS_PRINT)
    return a


def annot_items(page):
    """Annotazioni FreeText della pagina come oggetti editabili (con stile letto dal testo reso)."""
    spans = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            spans.extend(l["spans"])
    out = []
    for a in page.annots() or []:
        if a.type[0] != fitz.PDF_ANNOT_FREE_TEXT:
            continue
        txt = a.info.get("content", "")
        if not txt.strip():
            continue
        r = a.rect
        inside = [s for s in spans
                  if r.x0 - 1 <= (s["bbox"][0] + s["bbox"][2]) / 2 <= r.x1 + 1
                  and r.y0 - 1 <= (s["bbox"][1] + s["bbox"][3]) / 2 <= r.y1 + 1]
        title = a.info.get("title", "")
        layer = "app" if title == APP_TITLE else "foxit"
        if inside:
            s = inside[0]
            bb = list(s["bbox"])
            it = {"origin": [round(v, 2) for v in s["origin"]], "font": s["font"], "size": round(s["size"], 2),
                  "color": "#%06x" % s["color"], "bold": bool(s["flags"] & 16), "italic": bool(s["flags"] & 2)}
        else:
            bb = [r.x0, r.y0, r.x1, r.y1]
            it = {"origin": [round(r.x0 + KX * 7, 2), round(r.y0 + KY * 7, 2)], "font": "Helvetica", "size": 7,
                  "color": "#000000", "bold": False, "italic": False}
        out.append({**it, "bbox": [round(v, 2) for v in bb], "text": txt, "layer": layer,
                    "xrefs": [a.xref], "hide": [[round(v, 2) for v in (r.x0, r.y0, r.x1, r.y1)]],
                    "title": title, "subject": a.info.get("subject", "")})
    return out


def orig_items(page_no):
    page = State.plain()[page_no]
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if not s["text"].strip():
                    continue
                bb = [round(v, 2) for v in s["bbox"]]
                out.append({
                    "bbox": bb, "origin": [round(v, 2) for v in s["origin"]],
                    "text": s["text"], "font": s["font"],
                    "size": round(s["size"], 2), "color": "#%06x" % s["color"],
                    "bold": bool(s["flags"] & 16), "italic": bool(s["flags"] & 2),
                    "layer": "orig", "covers": [[bb[0] - .5, bb[1] - .5, bb[2] + .5, bb[3] + .5]],
                })
    return out


def group_singles(items):
    """Caratteri singoli allineati e spaziati (es. codice fiscale nelle caselle) -> un unico testo."""
    multi = [i for i in items if len(i["text"].strip()) != 1]
    singles = sorted((i for i in items if len(i["text"].strip()) == 1), key=lambda i: i["origin"][1])
    rows, row = [], []
    for it in singles:
        if row and it["origin"][1] - row[0]["origin"][1] > 1.5:
            rows.append(row)
            row = []
        row.append(it)
    if row:
        rows.append(row)
    out = multi
    for row in rows:
        row.sort(key=lambda i: i["origin"][0])
        run = []
        for it in row:
            if run:
                p = run[-1]
                gap = it["bbox"][0] - p["bbox"][2]
                if (it["layer"] == p["layer"] and it["font"] == p["font"] and it["size"] == p["size"]
                        and -1 < gap < 3 * it["size"]):
                    run.append(it)
                    continue
                _flush(run, out)
                run = []
            run.append(it)
        _flush(run, out)
    return out


def _flush(run, out):
    if len(run) >= 3:
        out.append(_group(run))
    else:
        out.extend(run)


def _group(run):
    cx = [(i["bbox"][0] + i["bbox"][2]) / 2 for i in run]
    steps = sorted(b - a for a, b in zip(cx, cx[1:]))
    pitch = steps[len(steps) // 2]
    first = run[0]
    g = {
        **first,
        "text": "".join(i["text"].strip() for i in run),
        "origin": [round(cx[0], 2), round(sum(i["origin"][1] for i in run) / len(run), 2)],
        "bbox": [min(i["bbox"][0] for i in run), min(i["bbox"][1] for i in run),
                 max(i["bbox"][2] for i in run), max(i["bbox"][3] for i in run)],
        "pitch": round(pitch, 3),
    }
    if "covers" in first:
        g["covers"] = [c for i in run for c in i["covers"]]
    if "xrefs" in first:
        g["xrefs"] = [x for i in run for x in i["xrefs"]]
        g["hide"] = [h for i in run for h in i["hide"]]
    return g


def objects(pno):
    page = State.doc[pno]
    ann = group_singles(annot_items(page))
    orig = group_singles(orig_items(pno))
    return {"orig": orig,
            "foxit": [i for i in ann if i["layer"] == "foxit"],
            "app": [i for i in ann if i["layer"] == "app"]}


# ---------------------------------------------------------------- modifica
def _find_annot(page, xref):
    for a in page.annots() or []:
        if a.xref == xref:
            return a
    return None


def _write(page, p, text):
    size = float(p.get("size", 8))
    fn = pick_font(p.get("font"), p.get("bold"), p.get("italic"))
    color = rgb(int(p.get("color", "#000000").lstrip("#"), 16))
    ox, oy = p["origin"]
    title = p.get("title") or APP_TITLE
    subject = p.get("subject") or APP_SUBJECT
    pitch = p.get("pitch")
    made = []
    if pitch:   # una annotazione per casella, lettera centrata
        for i, ch in enumerate(text):
            if ch.strip():
                made.append(make_annot(page, ch, ox + i * pitch - pitch / 2, oy, size, color, fn, title,
                                       subject, width=pitch, align=1))
    else:
        made.append(make_annot(page, text, ox, oy, size, color, fn, title, subject))
    return [a.xref for a in made]


def apply_edit(p):
    try:
        return _apply_edit(p)
    except Exception:
        State.goto(State.idx)   # scarta modifiche a metà: il documento torna all'ultimo stato valido
        raise


def _apply_edit(p):
    page = State.doc[p["page"]]
    xrefs = set(p.get("xrefs") or [])
    covers = p.get("covers") or []
    remap = {}   # vecchio xref -> nuovo, per le annotazioni ricreate dopo la copertura
    # annotazioni sostituite: via
    for x in xrefs:
        a = _find_annot(page, x)
        if a:
            page.delete_annot(a)
    # copertura del contenuto originale: la redazione cancella anche le annotazioni sovrapposte,
    # quindi le altre vengono salvate e ricreate
    if covers:
        rects = [fitz.Rect(r) for r in covers]
        keep = [i for i in annot_items(page) if any(fitz.Rect(i["hide"][0]).intersects(r) for r in rects)]
        for r in rects:
            page.add_redact_annot(r, fill=(1, 1, 1))
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
        present = {i["xrefs"][0] for i in annot_items(page)}
        for i in keep:
            if i["xrefs"][0] in present:
                continue
            remap[i["xrefs"][0]] = _write(page, {**i, "pitch": None}, i["text"])[0]
    text = p.get("text", "")
    if text:
        _write(page, p, text)
    State.push()
    return remap


def delete_annots(page_no, xrefs):  # usata da /delete
    page = State.doc[page_no]
    for x in xrefs:
        a = _find_annot(page, x)
        if a:
            page.delete_annot(a)
    State.push()


class NoPicker(Exception):
    pass


def pick_file():
    if sys.platform not in ("win32", "linux"):   # tkinter fuori dal thread principale non e' affidabile su macOS
        raise NoPicker
    try:
        import tkinter as tk
    except ImportError:
        raise NoPicker
    from tkinter import filedialog
    try:
        root = tk.Tk()
    except tk.TclError:   # nessun display
        raise NoPicker
    root.withdraw()
    root.attributes("-topmost", True)
    p = filedialog.askopenfilename(title="Apri PDF", filetypes=[("PDF", "*.pdf")])
    root.destroy()
    return p


def page_png(pno, z):
    """Immagine della pagina, o None se non esiste. Zoom limitato: evita immagini enormi."""
    if not State.doc or not 0 <= pno < len(State.doc):
        return None
    z = min(8.0, max(0.25, z))
    return State.doc[pno].get_pixmap(matrix=fitz.Matrix(z, z), alpha=False).tobytes("png")


def save_in_place():
    if not State.path:
        raise ValueError("nopath")
    p = Path(State.path)
    bak = p.with_name(p.stem + " (originale).pdf")
    if not bak.exists():      # copia di sicurezza, una sola volta
        bak.write_bytes(p.read_bytes())
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_bytes(State.history[State.idx])
    tmp.replace(p)
    return str(p)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def allowed(self):
        """Solo pagine servite da questo programma: blocca richieste di altri siti (CSRF/DNS rebinding)."""
        ok_hosts = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
        if self.headers.get("Host") not in ok_hosts:
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin.split("://", 1)[-1] in ok_hosts

    def info(self):
        d = State.doc
        return {"open": d is not None, "name": State.name, "path": State.path, "version": __version__,
                "pages": len(d) if d else 0,
                "sizes": [[p.rect.width, p.rect.height] for p in d] if d else [],
                "canUndo": State.idx > 0, "canRedo": State.idx < len(State.history) - 1,
                "rev": State.idx}

    def do_GET(self):
        if not self.allowed():
            return self.send(403, {"error": "forbidden"})
        u = urlparse(self.path)
        q = parse_qs(u.query)
        with LOCK:
            if u.path == "/":
                return self.send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
            asset = "favicon.ico" if u.path == "/favicon.ico" else u.path.removeprefix("/assets/")
            if asset in ASSETS:
                return self.send(200, (HERE / "assets" / asset).read_bytes(), ASSETS[asset])
            if u.path == "/info":
                return self.send(200, self.info())
            m = re.fullmatch(r"/page/(\d+)\.png", u.path)
            if m:
                try:
                    z = float(q.get("z", ["2"])[0])
                except ValueError:
                    return self.send(400, {"error": "bad zoom"})
                png = page_png(int(m[1]), z)
                if png is not None:
                    return self.send(200, png, "image/png")
            m = re.fullmatch(r"/objects/(\d+)", u.path)
            if m and State.doc and int(m[1]) < len(State.doc):
                return self.send(200, objects(int(m[1])))
            if u.path == "/download" and State.doc:
                name = State.name
                if not name.lower().endswith("- modificato.pdf"):
                    name = re.sub(r"\.pdf$", "", name, flags=re.I) + " - modificato.pdf"
                return self.send(200, State.history[State.idx], "application/pdf",
                                 {"Content-Disposition": "attachment; filename*=UTF-8''" + quote(name)})
        self.send(404, {"error": "not found"})

    def do_POST(self):
        if not self.allowed():
            return self.send(403, {"error": "forbidden"})
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        if u.path == "/pick":
            try:
                p = pick_file()
            except NoPicker:
                return self.send(200, {"nopicker": True})
            if not p:
                return self.send(200, {"cancelled": True})
            body = json.dumps({"path": p}).encode()
            u = urlparse("/open-path")
        with LOCK:
            try:
                if u.path == "/open":
                    name = parse_qs(u.query).get("name", ["documento.pdf"])[0]
                    State.load(body, name)
                elif u.path == "/open-path":
                    p = Path(json.loads(body)["path"])
                    State.load(p.read_bytes(), p.name, p)
                elif u.path == "/save":
                    saved = save_in_place()
                    return self.send(200, {**self.info(), "saved": saved})
                elif u.path == "/edit":
                    remap = apply_edit(json.loads(body))
                    return self.send(200, {**self.info(), "remap": remap})
                elif u.path == "/delete":
                    j = json.loads(body)
                    delete_annots(j["page"], j["xrefs"])
                elif u.path == "/undo" and State.idx > 0:
                    State.goto(State.idx - 1)
                elif u.path == "/redo" and State.idx < len(State.history) - 1:
                    State.goto(State.idx + 1)
                else:
                    return self.send(404, {"error": "not found"})
                return self.send(200, self.info())
            except Exception as e:
                return self.send(400, {"error": str(e)})


def main():
    global PORT
    ap = argparse.ArgumentParser(description="WPdf - editor PDF locale nel browser")
    ap.add_argument("file", nargs="?", help="PDF da aprire subito")
    ap.add_argument("--port", type=int, default=PORT, help="porta di partenza (default %(default)s)")
    ap.add_argument("--no-browser", action="store_true", help="non aprire il browser")
    ap.add_argument("--version", action="version", version=f"WPdf {__version__}")
    args = ap.parse_args()
    if args.file:
        p = Path(args.file)
        State.load(p.read_bytes(), p.name, p.resolve())
    srv = None
    for port in range(args.port, args.port + 20):   # porta occupata (altra copia aperta): prova la successiva
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", port), H)
            PORT = port
            break
        except OSError:
            continue
    if srv is None:
        sys.exit("Nessuna porta libera trovata.")
    url = f"http://127.0.0.1:{PORT}/"
    print(f"WPdf {__version__} su {url} (Ctrl+C per uscire)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
