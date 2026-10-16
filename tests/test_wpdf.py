"""Test di base: python -m unittest discover -s tests"""
import sys
import unittest
from pathlib import Path

import pymupdf as fitz

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wpdf import app  # noqa: E402


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

    def test_edit_original_becomes_app(self):
        it = [i for i in app.objects(0)["orig"] if i["text"] == "Etichetta originale"][0]
        app.apply_edit({"page": 0, "covers": it["covers"], "origin": it["origin"], "text": "Nuova",
                        "size": 10, "color": "#000000"})
        o = app.objects(0)
        self.assertNotIn("Etichetta originale", texts(o["orig"]))
        self.assertIn("Nuova", texts(o["app"]))

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

    def test_page_png_out_of_range(self):
        self.assertIsNone(app.page_png(1, 2))
        self.assertTrue(app.page_png(0, 2).startswith(b"\x89PNG"))

    def test_page_png_zoom_is_clamped(self):
        w = fitz.open(stream=app.page_png(0, 1000), filetype="png")[0].rect.width
        self.assertLessEqual(w, app.State.doc[0].rect.width * 8 + 1)


if __name__ == "__main__":
    unittest.main()
