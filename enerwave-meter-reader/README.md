# Enerwave Meter Reader

Flask + PostgreSQL app για ανάγνωση και αποθήκευση ενδείξεων ψηφιακού μετρητή Holley DTSD545.

## Τι κάνει

- Upload φωτογραφίας μετρητή
- Optional OpenAI Vision extraction με `OPENAI_API_KEY`
- Χειροκίνητη επιβεβαίωση/διόρθωση ενδείξεων
- Αποθήκευση σε PostgreSQL μέσω `DATABASE_URL`
- Ιστορικό μετρήσεων
- Υπολογισμός κατανάλωσης από προηγούμενη μέτρηση ίδιας παροχής
- CSV export
- Railway-ready Docker deploy

## Κωδικοί μετρητή

- `0.9.1` Ώρα
- `0.9.2` Ημερομηνία
- `1.8.0` Συνολική κατανάλωση
- `1.8.1` Ημερήσια κατανάλωση
- `1.8.2` Νυχτερινή κατανάλωση
- `2.8.0` Εξαγωγή ενέργειας, όπου υπάρχει

## Railway Deploy

1. Ανέβασε το project στο GitHub.
2. Στο Railway κάνε New Project from GitHub Repo.
3. Πρόσθεσε PostgreSQL plugin.
4. Το Railway θα δώσει αυτόματα `DATABASE_URL`.
5. Προαιρετικά πρόσθεσε Variables:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
SECRET_KEY=some-random-secret
```

## Σημαντικό για το PORT

Δεν υπάρχει `Procfile` και δεν υπάρχει `startCommand` στο `railway.json`.
Το Dockerfile ξεκινά σωστά με:

```dockerfile
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8080} app:app"]
```

Έτσι δεν θα ξαναβγάλει:

```text
Error: '$PORT' is not a valid port number.
```

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Άνοιξε: http://localhost:8080

## Local PostgreSQL

```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/enerwave"
python app.py
```

Αν δεν υπάρχει `DATABASE_URL`, χρησιμοποιεί local SQLite για δοκιμές.
