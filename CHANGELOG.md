# Changelog

## Non rilasciato
- Nuova interfaccia: barra su due righe (comandi; livelli, ricerca e zoom), controlli raggruppati, barra di stato con file, modalità di salvataggio e pagine, schermata iniziale con le spiegazioni dei livelli, tema scuro rifinito.
- **Cerca** (Ctrl+F): trova il testo in tutti i livelli, Invio/Maiusc+Invio o frecce per scorrere i risultati.
- Pannello laterale nascondibile (chiuso di default su finestre strette).
- Icone `favicon.ico` (16–256 px) e `apple-touch-icon.png`, generate da `tools/make_icons.py`.
- Corretto: un errore di sintassi bloccava l'intera pagina (anche il drag and drop).
- Corretto: aprire un file non valido poteva far salvare il documento aperto sopra quel file.
- Corretto: se "Fissa tutto" falliva a metà, la pagina non mostrava i testi già fissati.
- Aprire un altro file chiede conferma se ci sono testi non fissati; errori di apertura segnalati.
- Pagine inesistenti e zoom fuori misura gestiti dal server.
- Usa `import pymupdf` (il modulo `fitz` è deprecato).

## 0.1.0
Prima versione pubblica.
- Editor PDF nel browser, in locale (nessun dato lascia il computer).
- Tre livelli distinti: **Originale** (testo della pagina), **Foxit** (annotazioni FreeText di terzi), **App** (annotazioni create da WPdf).
- Testi mobili: crea, sposta, ridimensiona, poi **fissa** sul PDF.
- Lettere in caselle (codice fiscale, CAP...) riconosciute come un testo unico.
- Frecce su/giu per scorrere gli elementi di un livello.
- Salvataggio diretto sul file aperto con copia di sicurezza, oppure "Salva copia".
- Annulla/ripristina (ultimi 40 stati).
