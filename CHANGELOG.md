# Changelog

## Non rilasciato
- **Rotazione delle pagine**: pulsanti per ruotare a sinistra/destra la pagina corrente o tutte le pagine, e su ogni pagina (al passaggio del mouse) per ruotare solo quella. Annullabile, e salvata nel file.
- Corretto: sulle **pagine ruotate** (90/180/270°) i riquadri dei testi, Area e Aggiungi testo cadevano nel punto sbagliato. Il server ora usa le coordinate della pagina come la si vede; i testi modificati mantengono il verso dell'originale e quelli aggiunti sono dritti come mostrati.

## 1.1.0
- **Firme salvate**: archivio locale e cifrato (DPAPI su Windows), firme disegnate, caricate da foto/scansione con sfondo reso trasparente o scritte in corsivo; si inseriscono come firma mobile da spostare e ridimensionare in proporzione, poi si fissano nella pagina mantenendo la trasparenza (anche su pagine ruotate).
- Supporto per **tavoletta grafica**: pressione della penna, tutti i campioni della tavoletta, lato gomma.
- Il testo **Originale** modificato (anche con Area) ora viene riscritto nella pagina invece che come annotazione: resta selezionabile, copiabile e cercabile in Foxit e negli altri lettori, e rimane nel livello Originale. I testi aggiunti e quelli Foxit restano annotazioni.
- Corretto: elementi con l'attributo `hidden` che restavano visibili.

## 1.0.0
- **Aggiornamenti**: avviso quando esce una nuova versione (Novità, Aggiorna e riavvia, Più tardi, Salta questa versione). WPdf.exe si aggiorna da solo verificando dimensione e SHA-256 e riapre il file; con pip mostra il comando. Disattivabile con `--no-update-check`.
- Link **Segnala un problema** nell'app e modelli per le issue su GitHub.
- Eseguibile Windows in un solo file: `build.bat` crea `dist\WPdf.exe` con PyInstaller.
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
