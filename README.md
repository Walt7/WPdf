<p align="center"><img src="wpdf/assets/logo.png" alt="WPdf" width="128"></p>

# WPdf

Editor PDF **gratuito e locale**: modifichi i testi di un PDF nel browser, senza caricare nulla su internet.
Pensato per moduli compilati (testi, date, codici fiscali nelle caselle) dove prima serviva un editor commerciale.

*English: free, local, browser-based PDF text editor. Everything runs on your own computer (a small Python server on `127.0.0.1`); your files are never uploaded anywhere.*

## Cosa fa
- **Tre livelli distinti**, ognuno con il suo colore:
  - **Originale** (blu): il testo del PDF. Bloccato finche' non lo attivi.
  - **Foxit** (arancione): le annotazioni "Macchina da scrivere" (FreeText) create da altri programmi.
  - **App** (verde): le annotazioni create da WPdf, modificabili anche in seguito.
- **Testi mobili**: crei un testo, lo sposti e lo ridimensioni, poi lo **fissi** sul PDF.
- **Lettere in caselle** (codice fiscale, CAP...): riconosciute come un testo unico, si spostano e ridimensionano insieme.
- Frecce ▲▼ per scorrere tutti gli elementi di un livello, anche su piu' pagine.
- Salvataggio diretto sul file con copia di sicurezza, oppure "Salva copia".
- Annulla / ripristina (ultimi 40 stati).

## Installazione e avvio
Serve Python 3.9 o superiore.

**Direttamente da Git (consigliato)**
```bash
pip install git+https://github.com/<utente>/wpdf
wpdf                # oppure: wpdf mio_file.pdf
```
Con `pipx` o `uv` non serve nemmeno installarlo: `pipx run --spec git+https://github.com/<utente>/wpdf wpdf` / `uvx --from git+https://github.com/<utente>/wpdf wpdf`.

**Da una copia del repository**
```bash
git clone https://github.com/<utente>/wpdf
cd wpdf
pip install -r requirements.txt
python -m wpdf      # Windows: doppio clic su "Avvia WPdf.bat" - Linux/macOS: ./run.sh
```

Si apre il browser su `http://127.0.0.1:8765`. Opzioni: `--port`, `--no-browser`, `--version`. Se la porta e' occupata viene usata la successiva.

## Uso
1. **Apri PDF…** (su Windows e Linux si apre la finestra di scelta file; su macOS inserisci il percorso).
2. **Modifica testo**: clicca un testo. **Area**: trascina un rettangolo per testi non selezionabili. **Aggiungi testo**: clicca dove scrivere.
3. Sposta il testo (trascina o Ctrl+frecce), ridimensionalo (quadratino blu), poi **Fissa** (Invio).
4. **Salva** (Ctrl+S) sovrascrive il file; la prima volta crea `nome (originale).pdf` come copia di sicurezza. **Salva copia…** scarica `nome - modificato.pdf`.

Il cestino scarta il testo mobile senza toccare il PDF; **Cancella dal PDF** rimuove davvero il testo selezionato (annullabile con Annulla finche' non salvi).

## Serve un server / VPS?
No. WPdf gira sul tuo computer. **Non metterlo su un server pubblico**: non ha login ne' sessioni separate, quindi chiunque lo raggiungesse vedrebbe e modificherebbe i tuoi PDF. Per questo ascolta solo su `127.0.0.1` e rifiuta richieste con `Host`/`Origin` diversi. Vedi [SECURITY.md](SECURITY.md).

## Limiti noti
- Il testo dell'originale che modifichi viene coperto e riscritto come annotazione App con font base (Helvetica, Times o Courier): i font originali (es. Calibri) non vengono mantenuti.
- Salvando, le annotazioni Foxit modificate perdono la formattazione interna (testo ricco), restano testo, posizione, dimensione e colore.
- Non gestisce PDF protetti da password.
- Ogni modifica salva una copia in memoria per l'annulla (massimo 40): sconsigliato con PDF molto grandi.

## Sviluppo
```bash
pip install -r requirements.txt
python -m unittest discover -s tests
```
Vedi [CONTRIBUTING.md](CONTRIBUTING.md) e [CHANGELOG.md](CHANGELOG.md). **Non allegare PDF reali a issue e PR**: possono contenere dati personali.

## Licenza
Il codice e' sotto licenza **AGPL-3.0-or-later** (come PyMuPDF, su cui si basa). Vedi `LICENSE`.
Il logo (sigla WR) e' un marchio dell'autore e non e' coperto dalla licenza del codice.
