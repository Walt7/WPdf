# Contribuire

Segnalazioni e pull request sono benvenute.

## Segnalare un problema
Apri una issue da [questa pagina](https://github.com/Walt7/WPdf/issues/new/choose) (oppure dal link **Segnala un problema** in basso nell'app) e scegli il modello:
- **Segnala un problema**: indica versione, come usi WPdf (exe o pip) e i passi per riprodurlo.
- **Proponi una funzione**: descrivi cosa vuoi fare, prima ancora di come.

Regole:
- Una issue per problema; cerca prima tra quelle esistenti.
- Controlla che il problema ci sia anche con l'[ultima versione](https://github.com/Walt7/WPdf/releases/latest).
- **Non allegare PDF reali** né schermate con dati personali: usa PDF di prova con testi inventati.
- Le vulnerabilità di sicurezza vanno segnalate in privato (vedi `SECURITY.md`), non in una issue.

## Sviluppo

- Avvio in sviluppo: `pip install -r requirements.txt && python -m wpdf`
- Test: `python -m unittest discover -s tests`
- Il codice e' volutamente minimo: un solo `wpdf/app.py` (server + PyMuPDF) e un solo `wpdf/index.html` (nessuna build, nessuna dipendenza JavaScript).
- **Non allegare PDF reali** a issue o PR: possono contenere dati personali. Usa PDF sintetici (vedi `tests/test_wpdf.py`).
