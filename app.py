import os
import io
import uuid
import sqlite3
import requests
from datetime import datetime

import pandas as pd
from flask import (
    Flask, render_template, request,
    redirect, session, flash,
    send_file, url_for
)
from flask_mail import Mail, Message
from dotenv import load_dotenv
from xhtml2pdf import pisa
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

app = Flask(__name__)
app.secret_key = "ai_crop_yield_prediction_secret"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
SOIL_RAW_DIR = os.path.join(BASE_DIR, "data", "soil_raw")
CROP_YIELD_FILE = os.path.join(BASE_DIR, "data", "crop_yield.csv")
PESTICIDE_FILE = os.path.join(BASE_DIR, "pesticides.csv")

app.config.update(
    MAIL_SERVER="smtp.gmail.com",
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=MAIL_USERNAME,
    MAIL_PASSWORD=MAIL_PASSWORD,
    MAIL_DEFAULT_SENDER=MAIL_USERNAME
)
mail = Mail(app)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            email TEXT UNIQUE,
            password TEXT,
            reset_token TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            crop TEXT,
            soil TEXT,
            acres REAL,
            location TEXT,
            yield_kg REAL,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM users WHERE username=?",
            (request.form["username"],)
        )
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user["password"], request.form["password"]):
            session["user_id"] = user["id"]
            return redirect(url_for("index"))

        flash("Invalid username or password")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO users (username, email, password)
                VALUES (?, ?, ?)
            """, (
                request.form["username"],
                request.form["email"],
                generate_password_hash(request.form["password"])
            ))
            conn.commit()
            conn.close()

            flash("Registered successfully. Please login.")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash("Email already registered. Please login or use another email.")
            return redirect(url_for("register"))

    return render_template("register.html")



@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        token = str(uuid.uuid4())
        email = request.form["email"]

        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE users SET reset_token=? WHERE email=?", (token, email))
        conn.commit()
        conn.close()

        link = url_for("reset_password", token=token, _external=True)
        msg = Message("Password Reset", recipients=[email])
        msg.body = f"Reset your password: {link}"
        mail.send(msg)

        flash("Reset link sent to email")

    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if request.method == "POST":
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            UPDATE users
            SET password=?, reset_token=NULL
            WHERE reset_token=?
        """, (generate_password_hash(request.form["password"]), token))
        conn.commit()
        conn.close()
        return redirect(url_for("login"))

    return render_template("reset_password.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

def predict_soil_values(location, soil_type):
    base = abs(hash(location + soil_type)) % 100
    return {
        "type": soil_type.capitalize(),
        "N": round(120 + base * 1.2, 2),
        "P": round(25 + base * 0.6, 2),
        "K": round(150 + base * 2.0, 2),
        "pH": round(5.5 + (base % 20) / 20, 2)
    }


def get_weather(location):
    res = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params={
            "q": location,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric"
        }
    ).json()

    api_condition = res["weather"][0]["main"].lower()

    condition_map = {
        "clear": "clear",
        "clouds": "cloudy",
        "rain": "rainy",
        "mist": "fog",
        "haze": "fog",
        "fog": "fog"
    }

    img_key = condition_map.get(api_condition, "clear")

    return {
        "temp": res["main"]["temp"],
        "humidity": res["main"]["humidity"],
        "condition": res["weather"][0]["main"],
        "image": f"weather/{img_key}.jpg"
    }


def predict_irrigation(soil, weather):
    if weather["humidity"] > 80:
        method = "Flood"
    elif soil["pH"] < 6.5:
        method = "Drip"
    elif weather["humidity"] < 40:
        method = "Sprinkler"
    else:
        method = "Furrow"

    return {
        "method": method,
        "image": f"irrigation/{method.lower()}.jpg",
        "steps": [
            "Prepare land properly",
            "Ensure uniform water flow",
            "Avoid over-irrigation",
            "Monitor soil moisture regularly"
        ]
    }

@app.route("/index")
def index():
    return render_template("index.html")


@app.route("/predict", methods=["POST"])
def predict():
    crop = request.form["crop"]
    soil = request.form["soil"]
    acres = float(request.form["acres"])
    location = request.form["location"]

    df = pd.read_csv(CROP_YIELD_FILE)
    avg = df[df["Item"].str.lower() == crop.lower()]["Value"].mean()
    yield_kg = round(avg * acres, 2)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO predictions
        (user_id, crop, soil, acres, location, yield_kg, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        session["user_id"],
        crop, soil, acres,
        location, yield_kg,
        datetime.now().strftime("%d-%m-%Y %I:%M %p")
    ))
    pid = cur.lastrowid
    conn.commit()
    conn.close()

    return redirect(url_for("result_page", pid=pid))


@app.route("/result/<int:pid>")
def result_page(pid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM predictions WHERE id=?", (pid,))
    prediction = cur.fetchone()
    conn.close()

    return render_template("result.html", prediction=prediction)


@app.route("/soil/<int:pid>")
def soil_page(pid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM predictions WHERE id=?", (pid,))
    p = cur.fetchone()
    conn.close()

    soil = predict_soil_values(p["location"], p["soil"])
    return render_template("soil.html", soil=soil, pid=pid)


@app.route("/weather/<int:pid>")
def weather_page(pid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM predictions WHERE id=?", (pid,))
    p = cur.fetchone()
    conn.close()

    weather = get_weather(p["location"])
    return render_template("weather.html", weather=weather, pid=pid)


@app.route("/irrigation/<int:pid>")
def irrigation_page(pid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM predictions WHERE id=?", (pid,))
    p = cur.fetchone()
    conn.close()

    soil = predict_soil_values(p["location"], p["soil"])
    weather = get_weather(p["location"])
    irrigation = predict_irrigation(soil, weather)

    return render_template(
        "irrigation.html",
        method=irrigation["method"],
        irrigation=irrigation,
        steps=irrigation["steps"],
        pid=pid
    )


@app.route("/pesticide/<int:pid>")
def pesticide_page(pid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM predictions WHERE id=?", (pid,))
    prediction = cur.fetchone()
    conn.close()

    df = pd.read_csv(PESTICIDE_FILE)
    pesticides = df[df["crop"].str.lower() == prediction["crop"].lower()].to_dict("records")

    return render_template(
        "pesticide.html",
        prediction=prediction,
        pesticides=pesticides,
        pid=pid
    )

@app.route("/past-predictions")
def past_predictions():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT created_at, crop, soil, location, acres, yield_kg
        FROM predictions
        WHERE user_id=?
        ORDER BY id DESC
    """, (session["user_id"],))
    records = cur.fetchall()

    cur.execute("""
        SELECT id
        FROM predictions
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 1
    """, (session["user_id"],))
    row = cur.fetchone()

    conn.close()

    pid = row["id"] if row else 1

    return render_template(
        "past_predictions.html",
        records=records,
        pid=pid
    )

@app.route("/download-pdf/<int:pid>")
def download_pdf(pid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM predictions WHERE id=?", (pid,))
    p = cur.fetchone()
    conn.close()

    soil = predict_soil_values(p["location"], p["soil"])
    weather = get_weather(p["location"])
    irrigation = predict_irrigation(soil, weather)

    df = pd.read_csv(PESTICIDE_FILE)
    pesticides = df[df["crop"].str.lower() == p["crop"].lower()].to_dict("records")

    data = {
        "crop": p["crop"],
        "location": p["location"],
        "acres": p["acres"],
        "yield_kg": p["yield_kg"],
        "date": p["created_at"],
        "soil": soil,
        "weather": weather,
        "irrigation": irrigation,
        "pesticides": pesticides
    }

    html = render_template("pdf_template.html", data=data)
    pdf = io.BytesIO()
    pisa.CreatePDF(html, dest=pdf)
    pdf.seek(0)

    return send_file(pdf, download_name="AI_Crop_Report.pdf", as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
