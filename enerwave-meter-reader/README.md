# Enerwave Meter Reader

Flask/Railway web app για ανάγνωση φωτογραφιών ψηφιακού μετρητή Holley DTSD545.

## Τι κάνει
- Ανέβασμα πολλών φωτογραφιών μετρητή.
- Προεπεξεργασία εικόνας στον server.
- OCR στον browser με Tesseract.js.
- Χειροκίνητη διόρθωση ενδείξεων.
- Κανόνες Enerwave/ΔΕΗ:
  - Γ1 ή Γ21: καταχωρίζεις 1.8.0 χωρίς δεκαδικά.
  - Γ1Ν ή Γ23: καταχωρίζεις 1.8.1 ημέρας και 1.8.2 νύχτας χωρίς δεκαδικά.

## Local run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Άνοιξε: http://localhost:8080

## GitHub
```bash
git init
git add .
git commit -m "Initial Enerwave meter reader app"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/enerwave-meter-reader.git
git push -u origin main
```

## Railway
1. New Project → Deploy from GitHub repo.
2. Επίλεξε το repo.
3. Railway θα διαβάσει το Dockerfile.
4. Δεν χρειάζονται environment variables.

## Σημαντικό
Το OCR σε φωτογραφίες LCD πίσω από γυαλί μπορεί να κάνει λάθη λόγω αντανακλάσεων. Το app έχει πεδία χειροκίνητης διόρθωσης πριν από το τελικό αποτέλεσμα.
