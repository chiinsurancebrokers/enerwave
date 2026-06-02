from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request, send_from_directory
from PIL import Image, ImageOps, ImageEnhance

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "20"))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-me")

CODES = {
    "0.9.1": "Ώρα",
    "0.9.2": "Ημερομηνία",
    "1.8.0": "Συνολική κατανάλωση ενέργειας",
    "1.8.1": "Ημερήσια κατανάλωση ενέργειας",
    "1.8.2": "Νυχτερινή κατανάλωση ενέργειας",
    "2.8.0": "Συνολική εξαγόμενη ενέργεια / παραγωγή",
    "E.E.0": "Alarm & Error Register",
    "0.2.2": "Setup code",
}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def normalize_digits(value: str) -> str:
    """Keep digits only and remove leading zeros for kWh submission."""
    digits = re.sub(r"\D", "", value or "")
    return str(int(digits)) if digits else ""


def preprocess_image(path: Path) -> Path:
    """Create a lighter, high-contrast copy that helps browser OCR."""
    output = path.with_name(path.stem + "_processed.jpg")
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    img.thumbnail((1800, 1800))
    img = ImageEnhance.Contrast(img).enhance(1.8)
    img = ImageEnhance.Sharpness(img).enhance(1.6)
    img = ImageEnhance.Brightness(img).enhance(1.08)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.save(output, quality=92, optimize=True)
    return output


def compute_submission(payload: dict[str, Any]) -> dict[str, Any]:
    supply_type = (payload.get("supply_type") or "G1N").upper().replace(" ", "")
    readings = payload.get("readings") or {}
    result: dict[str, Any] = {"supply_type": supply_type, "fields": {}, "warnings": []}

    if supply_type in {"Γ1", "G1", "Γ21", "G21"}:
        main = normalize_digits(readings.get("1.8.0", ""))
        if not main:
            result["warnings"].append("Για Γ1/Γ21 χρειάζεται η ένδειξη 1.8.0 χωρίς δεκαδικά.")
        result["fields"] = {"Ένδειξη κύριου / συνολική (1.8.0)": main}
    elif supply_type in {"Γ1Ν", "Γ1N", "G1N", "Γ23", "G23"}:
        day = normalize_digits(readings.get("1.8.1", ""))
        night = normalize_digits(readings.get("1.8.2", ""))
        if not day:
            result["warnings"].append("Για Γ1Ν/Γ23 χρειάζεται η ένδειξη ημέρας 1.8.1 χωρίς δεκαδικά.")
        if not night:
            result["warnings"].append("Για Γ1Ν/Γ23 χρειάζεται η ένδειξη νύχτας 1.8.2 χωρίς δεκαδικά.")
        result["fields"] = {"Ένδειξη ημέρας (1.8.1)": day, "Ένδειξη νύχτας (1.8.2)": night}
    else:
        result["warnings"].append("Άγνωστος τύπος παροχής. Επιλέξτε Γ1, Γ21, Γ1Ν ή Γ23.")

    return result


@app.route("/")
def index():
    return render_template("index.html", codes=CODES)


@app.post("/upload")
def upload():
    files = request.files.getlist("photos")
    saved = []
    for file in files:
        if not file or not file.filename or not allowed_file(file.filename):
            continue
        ext = file.filename.rsplit(".", 1)[1].lower()
        name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex}.{ext}"
        path = UPLOAD_DIR / name
        file.save(path)
        processed = preprocess_image(path)
        saved.append({
            "original": f"/uploads/{path.name}",
            "processed": f"/uploads/{processed.name}",
            "filename": path.name,
        })
    return jsonify({"files": saved})


@app.post("/calculate")
def calculate():
    return jsonify(compute_submission(request.get_json(silent=True) or {}))


@app.route("/uploads/<path:filename>")
def uploaded_file(filename: str):
    return send_from_directory(UPLOAD_DIR, filename)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=True)
