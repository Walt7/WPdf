"""Test di base: python -m unittest discover -s tests"""
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

import pymupdf as fitz

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wpdf import app, signatures, update, vault  # noqa: E402


def sample_pdf():
    """PDF sintetico: testo di pagina + annotazioni FreeText 'di terzi' (stile Foxit)."""
    d = fitz.open()
    p = d.new_page()
    p.insert_text((72, 100), "Etichetta originale", fontname="helv", fontsize=10)
    p.insert_text((72, 140), "Altro testo", fontname="helv", fontsize=10)
    a = p.add_freetext_annot(fitz.Rect(200, 90, 320, 110), "NOME", fontsize=8, fontname="helv",
                             text_color=(0, 0, 0), fill_color=None)
    a.set_info(title="Altro Autore", subject="Macchina da scrivere", content="NOME")
    for i, ch in enumerate("ABCDE"):   # una lettera per casella
        c = p.add_freetext_annot(fitz.Rect(72 + i * 14, 200, 72 + i * 14 + 9, 212), ch, fontsize=8,
                                 fontname="helv", text_color=(0, 0, 0), fill_color=None)
        c.set_info(title="Altro Autore", subject="Macchina da scrivere", content=ch)
    return d.tobytes()


def texts(items):
    return [i["text"] for i in items]


class Layers(unittest.TestCase):
    def setUp(self):
        app.State.load(sample_pdf(), "t.pdf")

    def test_layers_are_separated(self):
        o = app.objects(0)
        self.assertIn("Etichetta originale", texts(o["orig"]))
        self.assertNotIn("NOME", texts(o["orig"]))
        self.assertIn("NOME", texts(o["foxit"]))
        self.assertEqual(o["app"], [])

    def test_single_chars_are_grouped(self):
        g = [i for i in app.objects(0)["foxit"] if i["text"] == "ABCDE"]
        self.assertEqual(len(g), 1)
        self.assertEqual(len(g[0]["xrefs"]), 5)
        self.assertAlmostEqual(g[0]["pitch"], 14, delta=0.5)

    def test_edit_original_stays_page_text(self):
        it = [i for i in app.objects(0)["orig"] if i["text"] == "Etichetta originale"][0]
        app.apply_edit({"page": 0, "covers": it["covers"], "origin": it["origin"], "text": "Nuova",
                        "size": 10, "color": "#000000"})
        o = app.objects(0)
        self.assertNotIn("Etichetta originale", texts(o["orig"]))
        new = [i for i in o["orig"] if i["text"] == "Nuova"]
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0]["origin"], it["origin"])          # stessa posizione
        self.assertEqual(o["app"], [])                             # nessuna annotazione
        page = app.State.plain()[0]                                # come lo vede un lettore senza annotazioni
        self.assertIn("Nuova", page.get_text())

    def test_original_letter_boxes_stay_page_text(self):
        d = fitz.open()
        p = d.new_page()
        for i, ch in enumerate("ABCDE"):
            p.insert_text((72 + i * 14, 200), ch, fontsize=8, fontname="helv")
        app.State.load(d.tobytes(), "c.pdf")
        g = [i for i in app.objects(0)["orig"] if i.get("pitch")][0]
        app.apply_edit({"page": 0, "covers": g["covers"], "origin": g["origin"], "pitch": g["pitch"],
                        "text": "VWXYZ", "size": g["size"], "color": "#000000"})
        o = app.objects(0)
        self.assertEqual(texts(o["orig"]), ["VWXYZ"])
        self.assertAlmostEqual([i for i in o["orig"] if i.get("pitch")][0]["pitch"], g["pitch"], delta=0.3)
        self.assertEqual(o["app"], [])

    def test_edit_foxit_stays_foxit(self):
        it = [i for i in app.objects(0)["foxit"] if i["text"] == "NOME"][0]
        app.apply_edit({"page": 0, "xrefs": it["xrefs"], "title": it["title"], "subject": it["subject"],
                        "origin": it["origin"], "text": "COGNOME", "size": it["size"], "color": it["color"]})
        o = app.objects(0)
        self.assertIn("COGNOME", texts(o["foxit"]))
        self.assertNotIn("NOME", texts(o["foxit"]))
        self.assertEqual(o["app"], [])

    def test_group_edit_keeps_one_annotation_per_char(self):
        g = [i for i in app.objects(0)["foxit"] if i["text"] == "ABCDE"][0]
        app.apply_edit({"page": 0, "xrefs": g["xrefs"], "title": g["title"], "subject": g["subject"],
                        "pitch": g["pitch"], "origin": g["origin"], "text": "VWXYZ", "size": g["size"],
                        "color": g["color"]})
        self.assertIn("VWXYZ", texts(app.objects(0)["foxit"]))

    def test_delete_with_empty_text(self):
        it = [i for i in app.objects(0)["foxit"] if i["text"] == "NOME"][0]
        app.apply_edit({"page": 0, "xrefs": it["xrefs"], "origin": it["origin"], "text": ""})
        self.assertNotIn("NOME", texts(app.objects(0)["foxit"]))

    def test_cover_keeps_overlapping_annotations(self):
        it = [i for i in app.objects(0)["foxit"] if i["text"] == "NOME"][0]
        x0, y0, x1, y1 = it["bbox"]
        res = app.apply_edit({"page": 0, "covers": [[x0 - 30, y0, x0 + 3, y1]], "origin": [x0 - 28, y1 - 2],
                              "text": "X", "size": 8, "color": "#000000"})
        self.assertIn("NOME", texts(app.objects(0)["foxit"]))   # ricreata
        self.assertEqual(len(res), 1)                           # mappa vecchio->nuovo xref

    def test_failed_edit_rolls_back(self):
        rev = app.State.idx
        with self.assertRaises(Exception):
            app.apply_edit({"page": 0, "covers": [[0, 0, 5, 5]], "origin": [1, 1], "text": "x", "color": "zz"})
        self.assertEqual(app.State.idx, rev)

    def test_history_is_capped(self):
        for i in range(app.State.MAX_HISTORY + 5):
            app.apply_edit({"page": 0, "origin": [72, 300], "text": str(i), "size": 8, "color": "#000000"})
        self.assertLessEqual(len(app.State.history), app.State.MAX_HISTORY)
        self.assertEqual(app.State.idx, len(app.State.history) - 1)


def rotated_pdf(rot):
    """Pagina 300x200 con /Rotate rot: un testo nel verso del PDF e uno dritto come mostrato."""
    d = fitz.open()
    p = d.new_page(width=300, height=200)
    p.set_rotation(rot)
    p.insert_text((72, 100), "Etichetta originale", fontname="helv", fontsize=10)
    p.insert_text(fitz.Point(40, 75) * p.derotation_matrix, "Dritto", fontname="helv", fontsize=10, rotate=rot)
    a = p.add_freetext_annot(fitz.Rect(150, 150, 260, 170), "NOME", fontsize=8, fontname="helv",
                             text_color=(0, 0, 0), fill_color=None)
    a.set_info(title="Altro Autore", subject="Macchina da scrivere", content="NOME")
    return d.tobytes()


def ink(page, clip):
    """Riquadro dei pixel scuri della pagina resa (coordinate visualizzate, 1 px = 1 pt) dentro clip."""
    pix = page.get_pixmap(alpha=False)
    x0, y0, x1, y1 = (int(v) for v in fitz.Rect(clip) & fitz.Rect(0, 0, pix.width, pix.height))
    pts = [(x, y) for y in range(y0, y1) for x in range(x0, x1) if pix.pixel(x, y)[0] < 128]
    return fitz.Rect(min(x for x, _ in pts), min(y for _, y in pts), max(x for x, _ in pts) + 1,
                     max(y for _, y in pts) + 1) if pts else None


class RotatedPages(unittest.TestCase):
    """Il browser vede la pagina ruotata: /objects e /edit usano coordinate visualizzate."""

    def item(self, layer, text):
        return [i for i in app.objects(0)[layer] if i["text"] == text][0]

    def assertCovers(self, bbox, rot):
        """Il riquadro inviato al browser contiene il testo come appare nell'immagine della pagina."""
        found = ink(app.State.doc[0], fitz.Rect(bbox) + (-6, -6, 6, 6))
        self.assertIsNotNone(found, rot)
        self.assertTrue(fitz.Rect(bbox) + (-1.5, -1.5, 1.5, 1.5) in found or
                        found in fitz.Rect(bbox) + (-1.5, -1.5, 1.5, 1.5), (rot, bbox, found))

    def test_boxes_match_rendered_text(self):
        for rot in (0, 90, 180, 270):
            app.State.load(rotated_pdf(rot), "r.pdf")
            for layer, text in (("orig", "Etichetta originale"), ("orig", "Dritto"), ("foxit", "NOME")):
                self.assertCovers(self.item(layer, text)["bbox"], rot)
            self.assertEqual(self.item("orig", "Dritto")["dir"], [1, 0], rot)

    def test_edit_original_keeps_position_and_direction(self):
        for rot in (0, 90, 180, 270):
            for text in ("Etichetta originale", "Dritto"):
                app.State.load(rotated_pdf(rot), "r.pdf")
                it = self.item("orig", text)
                app.apply_edit({"page": 0, "covers": it["covers"], "origin": it["origin"], "dir": it["dir"],
                                "text": "Nuova", "size": 10, "color": "#000000"})
                o = app.objects(0)
                self.assertNotIn(text, texts(o["orig"]), rot)
                new = self.item("orig", "Nuova")
                self.assertEqual(new["dir"], it["dir"], (rot, text))
                for a, b in zip(new["origin"], it["origin"]):
                    self.assertAlmostEqual(a, b, delta=0.05, msg=(rot, text))
                self.assertCovers(new["bbox"], rot)
                self.assertEqual(o["app"], [])

    def test_edit_annotation_keeps_position(self):
        for rot in (0, 90, 180, 270):
            app.State.load(rotated_pdf(rot), "r.pdf")
            it = self.item("foxit", "NOME")
            app.apply_edit({"page": 0, "xrefs": it["xrefs"], "title": it["title"], "subject": it["subject"],
                            "origin": it["origin"], "dir": it["dir"], "text": "COGNOME", "size": it["size"],
                            "color": it["color"]})
            new = self.item("foxit", "COGNOME")
            self.assertEqual(new["dir"], it["dir"], rot)
            for a, b in zip(new["origin"], it["origin"]):
                self.assertAlmostEqual(a, b, delta=0.5, msg=rot)
            self.assertCovers(new["bbox"], rot)

    def test_added_text_is_upright_where_clicked(self):
        for rot in (0, 90, 180, 270):
            app.State.load(rotated_pdf(rot), "r.pdf")
            app.apply_edit({"page": 0, "origin": [120, 185], "text": "Aggiunto", "size": 10, "color": "#000000"})
            new = self.item("app", "Aggiunto")
            self.assertEqual(new["dir"], [1, 0], rot)
            for a, b in zip(new["origin"], [120, 185]):
                self.assertAlmostEqual(a, b, delta=0.5, msg=rot)
            self.assertCovers(new["bbox"], rot)

    def test_area_covers_displayed_rect(self):
        for rot in (0, 90, 180, 270):
            app.State.load(rotated_pdf(rot), "r.pdf")
            x0, y0, x1, y1 = self.item("orig", "Dritto")["bbox"]
            app.apply_edit({"page": 0, "covers": [[x0 - 1, y0 - 1, x1 + 1, y1 + 1]], "origin": [x0, y1 - 2],
                            "text": "Area", "size": 8, "color": "#000000"})
            o = app.objects(0)
            self.assertNotIn("Dritto", texts(o["orig"]), rot)
            self.assertIn("Etichetta originale", texts(o["orig"]), rot)
            self.assertEqual(self.item("orig", "Area")["dir"], [1, 0], rot)

    def test_letter_boxes_on_rotated_page(self):
        for rot in (90, 270):
            d = fitz.open()
            p = d.new_page(width=300, height=200)
            p.set_rotation(rot)
            for i, ch in enumerate("ABCDE"):   # dritte come mostrate
                p.insert_text(fitz.Point(40 + i * 14, 60) * p.derotation_matrix, ch, fontsize=8,
                              fontname="helv", rotate=rot)
            app.State.load(d.tobytes(), "c.pdf")
            g = [i for i in app.objects(0)["orig"] if i.get("pitch")][0]
            app.apply_edit({"page": 0, "covers": g["covers"], "origin": g["origin"], "pitch": g["pitch"],
                            "dir": g["dir"], "text": "VWXYZ", "size": g["size"], "color": "#000000"})
            n = [i for i in app.objects(0)["orig"] if i.get("pitch")][0]
            self.assertEqual(n["text"], "VWXYZ", rot)
            self.assertAlmostEqual(n["pitch"], g["pitch"], delta=0.3)
            self.assertAlmostEqual(n["origin"][0], g["origin"][0], delta=0.5)


class Robustness(unittest.TestCase):
    def setUp(self):
        app.State.load(sample_pdf(), "t.pdf", "C:/dati/t.pdf")

    def test_invalid_file_leaves_state_untouched(self):
        doc, path, name = app.State.doc, app.State.path, app.State.name
        with self.assertRaises(Exception):
            app.State.load(b"non e' un pdf", "altro.pdf", "C:/dati/altro.pdf")
        # altrimenti 'Salva' scriverebbe il documento aperto sopra altro.pdf
        self.assertIs(app.State.doc, doc)
        self.assertEqual((app.State.path, app.State.name), (path, name))

    def test_served_assets_exist(self):
        for name in app.ASSETS:
            self.assertTrue((app.HERE / "assets" / name).is_file(), name)
        ico = (app.HERE / "assets" / "favicon.ico").read_bytes()
        self.assertEqual(ico[:4], b"\0\0\1\0")   # intestazione ICO

    def test_page_png_out_of_range(self):
        self.assertIsNone(app.page_png(1, 2))
        self.assertTrue(app.page_png(0, 2).startswith(b"\x89PNG"))

    def test_page_png_zoom_is_clamped(self):
        w = fitz.open(stream=app.page_png(0, 1000), filetype="png")[0].rect.width
        self.assertLessEqual(w, app.State.doc[0].rect.width * 8 + 1)


class Updates(unittest.TestCase):
    def test_version_compare(self):
        self.assertTrue(update.is_newer("v1.0.1", "1.0.0"))
        self.assertTrue(update.is_newer("1.10.0", "1.9.9"))
        self.assertFalse(update.is_newer("v1.0.0", "1.0.0"))
        self.assertFalse(update.is_newer("0.9.0", "1.0.0"))

    def test_summarize_release(self):
        rel = {"tag_name": "v9.0.0", "html_url": "https://example/rel", "body": "note",
               "assets": [{"name": "WPdf.exe", "size": 3, "digest": "sha256:ABC",
                           "browser_download_url": "https://example/WPdf.exe"}]}
        r = update.summarize(rel, "1.0.0")
        self.assertTrue(r["newer"])
        self.assertEqual(r["latest"], "9.0.0")
        self.assertEqual(r["asset"]["sha256"], "ABC")
        self.assertFalse(r["canInstall"])          # i test non girano come WPdf.exe
        self.assertIsNone(update.summarize({"tag_name": "v9", "assets": []})["asset"])

    def _asset(self, d, data, **over):
        src = Path(d) / "nuovo.bin"
        src.write_bytes(data)
        return {"url": src.as_uri(), "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), **over}

    def test_download_is_verified(self):
        with tempfile.TemporaryDirectory() as d:
            got = update.download(self._asset(d, b"exe nuovo"), d)
            self.assertEqual(got.read_bytes(), b"exe nuovo")
            for bad in ({"sha256": "0" * 64}, {"size": 999}):
                with self.assertRaises(ValueError):
                    update.download(self._asset(d, b"exe nuovo", **bad), d)
            self.assertEqual(len(list(Path(d).glob("*.download"))), 1)   # gli scaricamenti falliti non restano

    def test_swap_keeps_old_copy(self):
        with tempfile.TemporaryDirectory() as d:
            exe, new = Path(d) / "WPdf.exe", Path(d) / "x.download"
            exe.write_bytes(b"vecchio")
            new.write_bytes(b"nuovo")
            old = update.swap(exe, new)
            self.assertEqual((exe.read_bytes(), old.read_bytes()), (b"nuovo", b"vecchio"))
            self.assertEqual(old.name, "WPdf.old.exe")


class Dirty(unittest.TestCase):
    def test_unsaved_changes_are_tracked(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "t.pdf"
            f.write_bytes(sample_pdf())
            app.State.load(f.read_bytes(), f.name, f)
            self.assertEqual(app.State.idx, app.State.saved_idx)
            app.apply_edit({"page": 0, "origin": [72, 300], "text": "x", "size": 8, "color": "#000000"})
            self.assertNotEqual(app.State.idx, app.State.saved_idx)
            app.save_in_place()
            self.assertEqual(app.State.idx, app.State.saved_idx)


def sig_png(w=40, h=20):
    """Firma di prova: sfondo trasparente, quadrato rosso in alto a sinistra."""
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, w, h), 1)
    pix.set_rect(pix.irect, (0, 0, 0, 0))
    pix.set_rect(fitz.IRect(0, 0, 10, 10), (200, 0, 0, 255))
    return pix.tobytes("png")


class Signatures(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        os.environ["WPDF_SIGNATURES_DIR"] = self.dir.name
        signatures._vault = None   # nuova cartella, nuova chiave

    def tearDown(self):
        signatures._vault = None
        os.environ.pop("WPDF_SIGNATURES_DIR", None)
        self.dir.cleanup()

    def test_store_rename_delete(self):
        g = signatures.add(sig_png(), "Firma completa")
        self.assertEqual([i["name"] for i in signatures.listing()], ["Firma completa"])
        self.assertEqual(signatures.png(g["id"]), sig_png())
        signatures.rename(g["id"], "Sigla")
        self.assertEqual(signatures.listing()[0]["name"], "Sigla")
        signatures.delete(g["id"])
        self.assertEqual(signatures.listing(), [])

    def test_files_are_encrypted(self):
        g = signatures.add(sig_png(), "Mario Rossi")
        files = {f.name: f.read_bytes() for f in Path(self.dir.name).iterdir()}
        self.assertNotIn(b"\x89PNG", files[g["id"] + ".sig"])
        self.assertNotIn(b"Mario", files["firme.dat"])
        if sys.platform == "win32":   # chiave protetta con DPAPI, non i 32 byte grezzi
            self.assertNotEqual(len(files["chiave.bin"]), 32)

    def test_tampered_file_is_rejected(self):
        g = signatures.add(sig_png(), "x")
        f = Path(self.dir.name) / (g["id"] + ".sig")
        b = bytearray(f.read_bytes())
        b[30] ^= 1
        f.write_bytes(bytes(b))
        with self.assertRaises(ValueError):
            signatures.png(g["id"])

    def test_vault_roundtrip_and_key_reuse(self):
        v = vault.Vault(self.dir.name)
        blob = v.encrypt(b"dati della firma")
        self.assertEqual(vault.Vault(self.dir.name).decrypt(blob), b"dati della firma")   # stessa chiave su disco

    def test_rejects_non_transparent_or_bad_images(self):
        opaque = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 20), 0).tobytes("png")
        for bad in (opaque, b"non e' un'immagine"):
            with self.assertRaises(ValueError):
                signatures.add(bad, "x")
        with self.assertRaises(KeyError):
            signatures.png("../chiave")

    def test_place_keeps_transparency_on_rotated_pages(self):
        g = signatures.add(sig_png(), "x")
        for rot in (0, 90, 180, 270):
            d = fitz.open()
            p = d.new_page(width=300, height=200)
            p.set_rotation(rot)
            p.draw_rect(p.rect * p.derotation_matrix, color=None, fill=(0, 0.6, 0))   # sfondo verde
            signatures.place(p, g["id"], (10, 10, 90, 50))
            pix = p.get_pixmap(alpha=False)
            self.assertEqual(pix.pixel(14, 14), (200, 0, 0), rot)   # in alto a sinistra come mostrato
            self.assertEqual(pix.pixel(70, 40), (0, 153, 0), rot)   # zona vuota: si vede sotto

    def test_sign_through_server_state(self):
        g = signatures.add(sig_png(), "x")
        app.State.load(sample_pdf(), "t.pdf")
        rev = app.State.idx
        signatures.place(app.State.doc[0], g["id"], (100, 100, 180, 140))
        app.State.push()
        self.assertEqual(app.State.idx, rev + 1)
        self.assertEqual(len(app.State.doc[0].get_images()), 1)


if __name__ == "__main__":
    unittest.main()
