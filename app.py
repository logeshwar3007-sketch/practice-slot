"""
Front page for entering the slots you want booked.
Run this first: python app.py
Then open http://127.0.0.1:5000 in your browser.

Add as many slots as you want (hall, timing, type). They're saved to
slots_wanted.json, which bot.py reads and watches for.
"""
import json
from pathlib import Path
from flask import Flask, request, redirect, render_template, url_for

app = Flask(__name__)
WANTED_PATH = Path(__file__).parent / "slots_wanted.json"


def load_wanted():
    if WANTED_PATH.exists():
        return json.loads(WANTED_PATH.read_text())
    return []


def save_wanted(items):
    WANTED_PATH.write_text(json.dumps(items, indent=2))


@app.route("/api/slots", methods=["GET"])
def api_slots():
    return {"slots": load_wanted()}


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", slots=load_wanted())


@app.route("/add", methods=["POST"])
def add():
    items = load_wanted()

    items.append({
        "hall": request.form.get("hall", "").strip(),
        "date": request.form.get("date", "").strip(),
        "timing": request.form.get("timing", "").strip(),
        "type": request.form.get("type", "").strip(),
        "purpose": request.form.get("purpose", "").strip(),
        "status": "waiting",
        "message": ""
    })

    save_wanted(items)
    return redirect(url_for("index"))


@app.route("/delete/<int:idx>", methods=["POST"])
def delete(idx):
    items = load_wanted()
    if 0 <= idx < len(items):
        items.pop(idx)
        save_wanted(items)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
