"""Rigenera gli screenshot del README: python tools/make_preview.py

Crea un modulo PDF d'esempio (dati inventati), lo apre in WPdf su una porta libera e lo
fotografa con Chrome/Edge headless in tema chiaro e scuro -> docs/preview-light.png, docs/preview-dark.png
"""
import os, socket, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from wpdf.app import APP_TITLE, APP_SUBJECT  # noqa: E402

BROWSERS = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "/usr/bin/google-chrome", "/usr/bin/chromium",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]


def typed(page, rect, text, title="Mario", subject="Macchina da scrivere", size=10):
    a = page.add_freetext_annot(pymupdf.Rect(rect), text, fontsize=size, fontname="helv",
                                text_color=(0.05, 0.1, 0.45), fill_color=None)
    a.set_info(title=title, subject=subject, content=text)
    a.set_flags(pymupdf.PDF_ANNOT_IS_PRINT)


def sample_pdf(path):
    d = pymupdf.open()
    p = d.new_page()   # A4
    ink, grey = (0.1, 0.1, 0.12), (0.45, 0.45, 0.5)
    p.insert_text((56, 70), "COMUNE DI ESEMPIO", fontname="hebo", fontsize=9, color=grey)
    p.insert_text((56, 98), "Domanda di iscrizione al servizio mensa scolastica", fontname="hebo", fontsize=15, color=ink)
    p.insert_text((56, 116), "Anno scolastico 2026/2027 - modulo da compilare in stampatello", fontname="helv", fontsize=9, color=grey)
    p.draw_line((56, 128), (539, 128), color=grey, width=0.6)
    y = 160
    fields = [("Cognome del genitore", "ROSSI"), ("Nome", "MARIO"), ("Indirizzo", "Via delle Rose 12, 00100 Esempio"),
              ("Telefono", "333 000 0000")]
    for label, value in fields:
        p.insert_text((56, y), label, fontname="helv", fontsize=9, color=grey)
        p.draw_line((180, y + 3), (539, y + 3), color=grey, width=0.5)
        typed(p, (182, y - 12, 520, y + 4), value)
        y += 30
    p.insert_text((56, y), "Codice fiscale", fontname="helv", fontsize=9, color=grey)
    cf = "RSSMRA80A01H501U"   # codice d'esempio, non appartiene a nessuno
    for i, ch in enumerate(cf):
        x = 180 + i * 18
        p.draw_rect((x, y - 12, x + 16, y + 5), color=grey, width=0.5)
        typed(p, (x + 3, y - 11, x + 15, y + 4), ch, size=10)
    y += 40
    p.insert_text((56, y), "Alunno/a", fontname="hebo", fontsize=11, color=ink)
    y += 24
    for label, value in [("Cognome e nome", "ROSSI GIULIA"), ("Classe e sezione", "3B"), ("Plesso", "Scuola primaria Centro")]:
        p.insert_text((56, y), label, fontname="helv", fontsize=9, color=grey)
        p.draw_line((180, y + 3), (539, y + 3), color=grey, width=0.5)
        typed(p, (182, y - 12, 520, y + 4), value)
        y += 30
    y += 6
    p.insert_text((56, y), "Diete speciali (allegare certificato medico)", fontname="helv", fontsize=9, color=grey)
    p.draw_rect((56, y + 8, 539, y + 58), color=grey, width=0.5)
    typed(p, (62, y + 12, 530, y + 28), "Nessuna", title=APP_TITLE, subject=APP_SUBJECT)
    y += 90
    p.insert_text((56, y), "Data", fontname="helv", fontsize=9, color=grey)
    p.draw_line((90, y + 3), (220, y + 3), color=grey, width=0.5)
    typed(p, (92, y - 12, 218, y + 4), "16/10/2026", title=APP_TITLE, subject=APP_SUBJECT)
    p.insert_text((330, y), "Firma", fontname="helv", fontsize=9, color=grey)
    p.draw_line((366, y + 3), (539, y + 3), color=grey, width=0.5)
    d.save(path)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    browser = next((b for b in BROWSERS if Path(b).exists()), None)
    if not browser:
        sys.exit("Serve Chrome o Edge per gli screenshot.")
    out = ROOT / "docs"
    out.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    pdf = tmp / "Domanda mensa scolastica.pdf"
    sample_pdf(pdf)
    port = free_port()
    srv = subprocess.Popen([sys.executable, "-m", "wpdf", "--no-browser", "--no-update-check",
                            "--port", str(port), str(pdf)], cwd=ROOT)
    try:
        url = f"http://127.0.0.1:{port}/"
        for _ in range(50):
            try:
                urllib.request.urlopen(url + "info", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        for theme in ("light", "dark"):
            png = out / f"preview-{theme}.png"
            args = [browser, "--headless=new", "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--window-size=1440,900", "--virtual-time-budget=6000", f"--user-data-dir={tmp / theme}",
                    f"--screenshot={png}", f"{url}?theme={theme}"]
            subprocess.run(args, check=True, capture_output=True, timeout=120)
            print(png)
    finally:
        srv.terminate()


if __name__ == "__main__":
    main()
