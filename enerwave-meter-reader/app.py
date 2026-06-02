import base64
import csv
import json
import os
import re
import uuid
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from PIL import Image

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me")

raw_db_url = os.getenv("DATABASE_URL", "sqlite:///local.db")
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = raw_db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024

db = SQLAlchemy(app)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


class Reading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    supply_type = db.Column(db.String(20), nullable=False, default="Γ1Ν")
    supply_number = db.Column(db.String(80), nullable=True)
    meter_no = db.Column(db.String(80), nullable=True)
    meter_model = db.Column(db.String(80), nullable=True, default="Holley DTSD545")
    image_filename = db.Column(db.String(255), nullable=True)

    code_180_total = db.Column(db.Integer, nullable=True)
    code_181_day = db.Column(db.Integer, nullable=True)
    code_182_night = db.Column(db.Integer, nullable=True)
    code_280_export = db.Column(db.Integer, nullable=True)
    code_091_time = db.Column(db.String(20), nullable=True)
    code_092_date = db.Column(db.String(20), nullable=True)

    notes = db.Column(db.Text, nullable=True)
    extraction_json = db.Column(db.Text, nullable=True)

    def as_dict(self):
        previous = find_previous_reading(self)
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "supply_type": self.supply_type,
            "supply_number": self.supply_number,
            "meter_no": self.meter_no,
            "meter_model": self.meter_model,
            "image_filename": self.image_filename,
            "1.8.0_total": self.code_180_total,
            "1.8.1_day": self.code_181_day,
            "1.8.2_night": self.code_182_night,
            "2.8.0_export": self.code_280_export,
            "0.9.1_time": self.code_091_time,
            "0.9.2_date": self.code_092_date,
            "consumption_since_previous": calculate_consumption(self, previous),
        }


def create_tables():
    with app.app_context():
        db.create_all()


create_tables()


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def clean_integer(value):
    if value in (None, ""):
        return None
    text = str(value)
    text = text.replace(" ", "").replace(".", "").replace(",", "")
    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    return int(digits)


def resize_for_ai(path: Path) -> Path:
    img = Image.open(path).convert("RGB")
    img.thumbnail((1600, 1600))
    out = path.with_name(path.stem + "_ai.jpg")
    img.save(out, "JPEG", quality=86)
    return out


def ai_extract_meter(path: Path) -> dict:
    """Optional OpenAI Vision extraction. Returns empty values if no API key exists."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return {
            "enabled": False,
            "message": "Δεν υπάρχει OPENAI_API_KEY. Συμπλήρωσε χειροκίνητα τις ενδείξεις."
        }

    client = OpenAI(api_key=api_key)
    image_path = resize_for_ai(path)
    b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    prompt = """
You read Greek electricity meter photos. Extract only visible values from a Holley DTSD545 digital meter.
Codes:
0.9.1 = current time, 0.9.2 = date, 1.8.0 = total import kWh, 1.8.1 = day kWh, 1.8.2 = night kWh, 2.8.0 = export kWh.
Important: omit decimals for kWh readings. If uncertain, use null and add a warning.
Return strict JSON with keys: meter_model, meter_no, supply_number, code_180_total, code_181_day, code_182_night, code_280_export, code_091_time, code_092_date, confidence, warnings.
"""
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Return JSON only."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ],
                },
            ],
        )
        return json.loads(response.choices[0].message.content)
    except Exception as exc:
        return {"enabled": True, "error": str(exc), "warnings": ["AI extraction failed"]}


def find_previous_reading(reading):
    if not reading.supply_number:
        return None
    return (
        Reading.query.filter(
            Reading.id != reading.id,
            Reading.supply_number == reading.supply_number,
            Reading.created_at < reading.created_at,
        )
        .order_by(Reading.created_at.desc())
        .first()
    )


def calculate_consumption(current, previous):
    if previous is None:
        return None
    result = {}
    for field, label in [
        ("code_180_total", "total"),
        ("code_181_day", "day"),
        ("code_182_night", "night"),
    ]:
        cur = getattr(current, field)
        prev = getattr(previous, field)
        if cur is not None and prev is not None and cur >= prev:
            result[label] = cur - prev
    return result or None


def recommended_fields(supply_type: str, reading: Reading):
    st = (supply_type or "").upper().replace(" ", "")
    if st in {"Γ1", "G1", "Γ21", "G21"}:
        return {"main": reading.code_180_total}
    if st in {"Γ1Ν", "Γ1N", "G1N", "Γ23", "G23"}:
        return {"day": reading.code_181_day, "night": reading.code_182_night}
    return {"total": reading.code_180_total, "day": reading.code_181_day, "night": reading.code_182_night}


@app.route("/")
def index():
    latest = Reading.query.order_by(Reading.created_at.desc()).limit(10).all()
    return render_template("index.html", latest=latest)


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("photo")
    if not file or file.filename == "":
        return redirect(url_for("index"))
    if not allowed_file(file.filename):
        return "Unsupported file type", 400

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.{ext}"
    path = UPLOAD_DIR / filename
    file.save(path)

    extracted = ai_extract_meter(path)
    return render_template("review.html", image_filename=filename, extracted=extracted)


@app.route("/save", methods=["POST"])
def save():
    extraction_json = request.form.get("extraction_json") or "{}"
    reading = Reading(
        supply_type=request.form.get("supply_type") or "Γ1Ν",
        supply_number=request.form.get("supply_number") or None,
        meter_no=request.form.get("meter_no") or None,
        meter_model=request.form.get("meter_model") or "Holley DTSD545",
        image_filename=request.form.get("image_filename") or None,
        code_180_total=clean_integer(request.form.get("code_180_total")),
        code_181_day=clean_integer(request.form.get("code_181_day")),
        code_182_night=clean_integer(request.form.get("code_182_night")),
        code_280_export=clean_integer(request.form.get("code_280_export")),
        code_091_time=request.form.get("code_091_time") or None,
        code_092_date=request.form.get("code_092_date") or None,
        notes=request.form.get("notes") or None,
        extraction_json=extraction_json,
    )
    db.session.add(reading)
    db.session.commit()
    return redirect(url_for("reading_detail", reading_id=reading.id))


@app.route("/reading/<int:reading_id>")
def reading_detail(reading_id):
    reading = Reading.query.get_or_404(reading_id)
    previous = find_previous_reading(reading)
    consumption = calculate_consumption(reading, previous)
    recommended = recommended_fields(reading.supply_type, reading)
    return render_template("detail.html", reading=reading, previous=previous, consumption=consumption, recommended=recommended)


@app.route("/readings")
def readings():
    items = Reading.query.order_by(Reading.created_at.desc()).all()
    return render_template("readings.html", items=items)


@app.route("/api/readings")
def api_readings():
    items = Reading.query.order_by(Reading.created_at.desc()).all()
    return jsonify([item.as_dict() for item in items])


@app.route("/export.csv")
def export_csv():
    items = Reading.query.order_by(Reading.created_at.desc()).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["created_at", "supply_type", "supply_number", "meter_no", "1.8.0", "1.8.1", "1.8.2", "2.8.0", "0.9.1", "0.9.2", "notes"])
    for r in items:
        writer.writerow([r.created_at, r.supply_type, r.supply_number, r.meter_no, r.code_180_total, r.code_181_day, r.code_182_night, r.code_280_export, r.code_091_time, r.code_092_date, r.notes])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=enerwave_readings.csv"})


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
