# Contribuire

Segnalazioni e pull request sono benvenute.

- Avvio in sviluppo: `pip install -r requirements.txt && python -m wpdf`
- Test: `python -m unittest discover -s tests`
- Il codice e' volutamente minimo: un solo `wpdf/app.py` (server + PyMuPDF) e un solo `wpdf/index.html` (nessuna build, nessuna dipendenza JavaScript).
- **Non allegare PDF reali** a issue o PR: possono contenere dati personali. Usa PDF sintetici (vedi `tests/test_wpdf.py`).
