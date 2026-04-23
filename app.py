from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
import sqlite3
import random
import os
import io
from datetime import datetime
from dotenv import load_dotenv
from functools import wraps
from reportlab.pdfgen import canvas

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")


# =========================
# LOGIN REQUIRED DECORATOR
# =========================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "admin_logged_in" not in session:
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


# =========================
# DATABASE INIT
# =========================
def init_db():
    conn = sqlite3.connect("queue.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS slots(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time TEXT,
        status TEXT,
        eta TEXT,
        capacity INTEGER,
        booked_count INTEGER
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS bookings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        slot_time TEXT,
        token TEXT
    )
    """)

    count = c.execute("SELECT COUNT(*) FROM slots").fetchone()[0]

    if count == 0:
        sample = [
            ("08:00 AM","Available","5 mins",5,0),
            ("08:15 AM","Available","7 mins",5,1),
            ("08:30 AM","Available","9 mins",5,2),
            ("08:45 AM","Available","11 mins",5,0),
            ("09:00 AM","Available","5 mins",5,0),
            ("09:15 AM","Available","8 mins",5,1),
            ("09:30 AM","Available","10 mins",5,3),
            ("09:45 AM","Available","12 mins",5,4),
            ("10:00 AM","Available","15 mins",5,0),
            ("10:15 AM","Available","18 mins",5,2),
            ("10:30 AM","Available","20 mins",5,1),
            ("10:45 AM","Available","22 mins",5,0)
        ]

        c.executemany("""
        INSERT INTO slots(time,status,eta,capacity,booked_count)
        VALUES(?,?,?,?,?)
        """, sample)

    conn.commit()
    conn.close()

init_db()


# =========================
# PAGES
# =========================
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/booking")
def booking():
    return render_template("booking.html")

@app.route("/queue")
def queue():
    return render_template("queue.html")

@app.route("/departments")
def departments():
    return render_template("departments.html")

@app.route("/doctors")
def doctors():
    return render_template("doctors.html")


# =========================
# ADMIN LOGIN
# =========================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin"))

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@login_required
def admin():
    return render_template("admin.html")


# =========================
# USER APIs
# =========================
@app.route("/api/slots")
def get_slots():

    conn = sqlite3.connect("queue.db")
    c = conn.cursor()

    data = c.execute("""
    SELECT id,time,status,eta,capacity,booked_count
    FROM slots
    """).fetchall()

    result = []

    for row in data:
        sid,time,status,eta,cap,count = row

        if count >= cap:
            status = "Full"
        elif count >= cap-1:
            status = "Filling Fast"
        else:
            status = "Available"

        result.append([sid,time,status,eta,cap,count])

    conn.close()
    return jsonify(result)


@app.route("/api/book", methods=["POST"])
def book():

    data = request.json
    slot_id = data["slot_id"]

    conn = sqlite3.connect("queue.db")
    c = conn.cursor()

    slot = c.execute("""
    SELECT time,capacity,booked_count
    FROM slots WHERE id=?
    """, (slot_id,)).fetchone()

    time, cap, count = slot

    if count >= cap:
        conn.close()
        return jsonify({"success": False})

    new_count = count + 1

    total = c.execute("SELECT COUNT(*) FROM bookings").fetchone()[0] + 1
    token = "NRK-" + str(total).zfill(3)

    c.execute("""
    INSERT INTO bookings(name,phone,slot_time,token)
    VALUES(?,?,?,?)
    """, ("Guest", "Auto", time, token))

    c.execute("""
    UPDATE slots
    SET booked_count=?
    WHERE id=?
    """, (new_count, slot_id))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "token": token,
        "time": time,
        "left": cap - new_count
    })


@app.route("/api/queue")
def live_queue():

    conn = sqlite3.connect("queue.db")
    c = conn.cursor()

    bookings = c.execute("""
    SELECT token FROM bookings ORDER BY id
    """).fetchall()

    conn.close()

    if len(bookings) == 0:
        return jsonify({
            "now": "NRK-000",
            "your": "No Booking",
            "ahead": 0,
            "eta": "0 mins"
        })

    now = bookings[0][0]
    ahead = len(bookings) - 1
    eta = str(ahead * 5) + " mins"

    return jsonify({
        "now": now,
        "ahead": ahead,
        "eta": eta
    })


# =========================
# ADMIN APIs
# =========================
@app.route("/api/admin/stats")
@login_required
def admin_stats():

    conn = sqlite3.connect("queue.db")
    c = conn.cursor()

    total = c.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]

    full = c.execute("""
    SELECT COUNT(*) FROM slots
    WHERE booked_count >= capacity
    """).fetchone()[0]

    conn.close()

    return jsonify({
        "total": total,
        "full": full
    })


@app.route("/api/admin/bookings")
@login_required
def admin_bookings():

    conn = sqlite3.connect("queue.db")
    c = conn.cursor()

    data = c.execute("""
    SELECT token,slot_time FROM bookings
    ORDER BY id
    """).fetchall()

    conn.close()
    return jsonify(data)


@app.route("/api/admin/next", methods=["POST"])
@login_required
def admin_next():

    conn = sqlite3.connect("queue.db")
    c = conn.cursor()

    c.execute("""
    DELETE FROM bookings
    WHERE id = (
        SELECT id FROM bookings
        ORDER BY id LIMIT 1
    )
    """)

    conn.commit()
    conn.close()

    return jsonify({"success": True})


@app.route("/api/admin/reset", methods=["POST"])
@login_required
def admin_reset():

    conn = sqlite3.connect("queue.db")
    c = conn.cursor()

    c.execute("DELETE FROM bookings")
    c.execute("UPDATE slots SET booked_count=0")

    conn.commit()
    conn.close()

    return jsonify({"success": True})


# =========================
# PDF REPORT
# =========================
@app.route("/admin/report")
@login_required
def admin_report():

    conn = sqlite3.connect("queue.db")
    c = conn.cursor()

    total = c.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]

    full = c.execute("""
    SELECT COUNT(*) FROM slots
    WHERE booked_count >= capacity
    """).fetchone()[0]

    bookings = c.execute("""
    SELECT token,slot_time
    FROM bookings
    ORDER BY id
    """).fetchall()

    conn.close()

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)

    y = 800

    p.setFont("Helvetica-Bold", 16)
    p.drawString(180, y, "NRK Hospital Daily Report")

    y -= 30
    p.setFont("Helvetica", 12)
    p.drawString(50, y, "Date: " + str(datetime.now()))

    y -= 30
    p.drawString(50, y, "Total Bookings: " + str(total))

    y -= 25
    p.drawString(50, y, "Full Slots: " + str(full))

    y -= 40
    p.setFont("Helvetica-Bold", 13)
    p.drawString(50, y, "Booking Tokens")

    y -= 25
    p.setFont("Helvetica", 11)

    for row in bookings:
        p.drawString(50, y, f"{row[0]}   -   {row[1]}")
        y -= 20

        if y < 50:
            p.showPage()
            y = 800

    p.save()

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="NRK_Report.pdf",
        mimetype="application/pdf"
    )

@app.route("/admin/analytics")
@login_required
def analytics():
    return render_template("analytics.html")

@app.route("/api/admin/analytics")
@login_required
def admin_analytics():

    conn = sqlite3.connect("queue.db")
    c = conn.cursor()

    slots = c.execute("""
    SELECT time, booked_count
    FROM slots
    ORDER BY id
    """).fetchall()

    labels = []
    values = []

    for row in slots:
        labels.append(row[0])
        values.append(row[1])

    total = c.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]

    conn.close()

    return jsonify({
        "labels": labels,
        "values": values,
        "total": total
    })

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(debug=False)