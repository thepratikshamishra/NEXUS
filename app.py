import os
import json
import sqlite3
from functools import wraps
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "nexus.db")
ROLE_DATA = os.path.join(BASE_DIR, "data", "roles_skills.json")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("NEXUS_SECRET_KEY", "dev-only-change-this-before-deployment")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


def connect_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with connect_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            full_name TEXT NOT NULL DEFAULT '',
            target_role TEXT NOT NULL DEFAULT 'Data Scientist',
            current_skills TEXT NOT NULL DEFAULT '',
            weekly_hours REAL NOT NULL DEFAULT 10,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS skill_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            skill TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Planned',
            confidence INTEGER NOT NULL DEFAULT 1,
            notes TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, skill),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            study_date TEXT NOT NULL,
            topic TEXT NOT NULL,
            minutes INTEGER NOT NULL CHECK(minutes > 0),
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS roadmap_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            skill TEXT NOT NULL DEFAULT '',
            due_date TEXT,
            status TEXT NOT NULL DEFAULT 'Not started',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        # Backfill profile for accounts created by older project versions.
        db.execute("""INSERT OR IGNORE INTO profiles(user_id, full_name, target_role, current_skills)
                      SELECT id, name, 'Data Scientist', '' FROM users""")
        db.commit()


@app.before_request
def before_request():
    g.user = None
    if session.get("user_id"):
        with connect_db() as db:
            g.user = db.execute("SELECT id, name, email FROM users WHERE id = ?",
                                (session["user_id"],)).fetchone()
        if g.user is None:
            session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def get_roles():
    try:
        with open(ROLE_DATA, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def get_profile(user_id):
    with connect_db() as db:
        return db.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()


def parse_skills(raw):
    return sorted({s.strip() for s in (raw or "").replace("\n", ",").split(",") if s.strip()},
                  key=str.casefold)


@app.route("/")
def index():
    if g.user:
        return redirect(url_for("dashboard"))
    return render_template("index.html", roles=get_roles())


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not name or not email or not password:
            flash("Please complete all required fields.", "danger")
        elif len(password) < 8:
            flash("Use a password with at least 8 characters.", "danger")
        elif password != confirm:
            flash("The passwords do not match.", "danger")
        else:
            try:
                with connect_db() as db:
                    cur = db.execute(
                        "INSERT INTO users(name, email, password_hash) VALUES (?, ?, ?)",
                        (name, email, generate_password_hash(password)))
                    user_id = cur.lastrowid
                    db.execute(
                        "INSERT INTO profiles(user_id, full_name, target_role, current_skills) VALUES (?, ?, ?, '')",
                        (user_id, name, "Data Scientist"))
                    db.commit()
                session.clear()
                session["user_id"] = user_id
                flash("Account created. Welcome to NEXUS!", "success")
                return redirect(url_for("dashboard"))
            except sqlite3.IntegrityError:
                flash("An account with that email already exists.", "danger")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with connect_db() as db:
            user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash("You're logged in.", "success")
            return redirect(url_for("dashboard"))
        flash("Email or password is incorrect.", "danger")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    profile = get_profile(g.user["id"])
    roles = get_roles()
    role = profile["target_role"] if profile else "Data Scientist"
    required = roles.get(role, [])
    current = parse_skills(profile["current_skills"] if profile else "")
    current_lower = {s.casefold() for s in current}
    missing = [s for s in required if s.casefold() not in current_lower]
    with connect_db() as db:
        study_total = db.execute("SELECT COALESCE(SUM(minutes),0) AS total FROM study_sessions WHERE user_id=?",
                                 (g.user["id"],)).fetchone()["total"]
        session_count = db.execute("SELECT COUNT(*) AS n FROM study_sessions WHERE user_id=?",
                                    (g.user["id"],)).fetchone()["n"]
        done = db.execute("SELECT COUNT(*) AS n FROM roadmap_items WHERE user_id=? AND status='Completed'",
                          (g.user["id"],)).fetchone()["n"]
        roadmap_total = db.execute("SELECT COUNT(*) AS n FROM roadmap_items WHERE user_id=?",
                                   (g.user["id"],)).fetchone()["n"]
        recent = db.execute("SELECT * FROM study_sessions WHERE user_id=? ORDER BY study_date DESC, id DESC LIMIT 5",
                            (g.user["id"],)).fetchall()
    return render_template("dashboard.html", profile=profile, required=required, current=current,
                           missing=missing, study_total=study_total, session_count=session_count,
                           done=done, roadmap_total=roadmap_total, recent=recent)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    roles = get_roles()
    existing = get_profile(g.user["id"])
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        target_role = request.form.get("target_role", "").strip()
        current_skills = ", ".join(parse_skills(request.form.get("current_skills", "")))
        try:
            weekly_hours = float(request.form.get("weekly_hours", "10"))
        except ValueError:
            weekly_hours = 10
        if not full_name:
            flash("Please enter your name.", "danger")
        elif target_role not in roles:
            flash("Choose a valid target role.", "danger")
        elif not (1 <= weekly_hours <= 100):
            flash("Weekly study hours must be between 1 and 100.", "danger")
        else:
            with connect_db() as db:
                db.execute("""UPDATE profiles SET full_name=?, target_role=?, current_skills=?,
                              weekly_hours=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?""",
                           (full_name, target_role, current_skills, weekly_hours, g.user["id"]))
                db.commit()
            flash("Your learning profile has been saved.", "success")
            return redirect(url_for("profile"))
    existing = get_profile(g.user["id"])
    return render_template("profile.html", profile=existing, roles=roles, skill_list=parse_skills(existing["current_skills"]))


@app.route("/skills")
@login_required
def skills():
    profile = get_profile(g.user["id"])
    roles = get_roles()
    role = profile["target_role"]
    required = roles.get(role, [])
    current = parse_skills(profile["current_skills"])
    current_lower = {s.casefold() for s in current}
    gaps = [s for s in required if s.casefold() not in current_lower]
    with connect_db() as db:
        progress_rows = db.execute("SELECT * FROM skill_progress WHERE user_id=? ORDER BY skill",
                                   (g.user["id"],)).fetchall()
    progress = {r["skill"].casefold(): r for r in progress_rows}
    return render_template("skills.html", role=role, current=current, required=required,
                           gaps=gaps, progress=progress)


@app.route("/skills/progress", methods=["POST"])
@login_required
def update_skill_progress():
    skill = request.form.get("skill", "").strip()
    status = request.form.get("status", "Planned")
    confidence = request.form.get("confidence", "1")
    notes = request.form.get("notes", "").strip()
    allowed = {"Planned", "In progress", "Completed"}
    try:
        confidence = max(1, min(5, int(confidence)))
    except ValueError:
        confidence = 1
    if not skill or status not in allowed:
        flash("Please provide a valid skill and status.", "danger")
    else:
        with connect_db() as db:
            db.execute("""INSERT INTO skill_progress(user_id, skill, status, confidence, notes, updated_at)
                          VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                          ON CONFLICT(user_id, skill) DO UPDATE SET status=excluded.status,
                          confidence=excluded.confidence, notes=excluded.notes, updated_at=CURRENT_TIMESTAMP""",
                       (g.user["id"], skill, status, confidence, notes))
            db.commit()
        flash(f"Progress saved for {skill}.", "success")
    return redirect(url_for("skills"))


@app.route("/roadmap", methods=["GET", "POST"])
@login_required
def roadmap():
    profile = get_profile(g.user["id"])
    roles = get_roles()
    required = roles.get(profile["target_role"], [])
    current_lower = {s.casefold() for s in parse_skills(profile["current_skills"])}
    gaps = [s for s in required if s.casefold() not in current_lower]
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        skill = request.form.get("skill", "").strip()
        due_date = request.form.get("due_date", "").strip() or None
        if title:
            with connect_db() as db:
                db.execute("""INSERT INTO roadmap_items(user_id, title, description, skill, due_date)
                              VALUES (?, ?, ?, ?, ?)""",
                           (g.user["id"], title, description, skill, due_date))
                db.commit()
            flash("Roadmap task added.", "success")
            return redirect(url_for("roadmap"))
        flash("A task title is required.", "danger")
    with connect_db() as db:
        items = db.execute("SELECT * FROM roadmap_items WHERE user_id=? ORDER BY CASE status WHEN 'Not started' THEN 0 WHEN 'In progress' THEN 1 ELSE 2 END, due_date",
                           (g.user["id"],)).fetchall()
    return render_template("roadmap.html", items=items, gaps=gaps)


@app.route("/roadmap/<int:item_id>/status", methods=["POST"])
@login_required
def roadmap_status(item_id):
    status = request.form.get("status", "Not started")
    if status not in {"Not started", "In progress", "Completed"}:
        flash("Invalid task status.", "danger")
    else:
        with connect_db() as db:
            db.execute("UPDATE roadmap_items SET status=? WHERE id=? AND user_id=?",
                       (status, item_id, g.user["id"]))
            db.commit()
        flash("Roadmap updated.", "success")
    return redirect(url_for("roadmap"))


@app.route("/roadmap/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_roadmap_item(item_id):
    with connect_db() as db:
        db.execute("DELETE FROM roadmap_items WHERE id=? AND user_id=?", (item_id, g.user["id"]))
        db.commit()
    flash("Task deleted.", "info")
    return redirect(url_for("roadmap"))


@app.route("/study-log", methods=["GET", "POST"])
@login_required
def study_log():
    if request.method == "POST":
        study_date = request.form.get("study_date", date.today().isoformat())
        topic = request.form.get("topic", "").strip()
        notes = request.form.get("notes", "").strip()
        try:
            minutes = int(request.form.get("minutes", "0"))
            datetime.strptime(study_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            minutes = 0
        if not topic or minutes <= 0 or minutes > 1440:
            flash("Enter a topic and a duration between 1 and 1440 minutes.", "danger")
        else:
            with connect_db() as db:
                db.execute("INSERT INTO study_sessions(user_id, study_date, topic, minutes, notes) VALUES (?, ?, ?, ?, ?)",
                           (g.user["id"], study_date, topic, minutes, notes))
                db.commit()
            flash("Study session logged.", "success")
            return redirect(url_for("study_log"))
    with connect_db() as db:
        logs = db.execute("SELECT * FROM study_sessions WHERE user_id=? ORDER BY study_date DESC, id DESC LIMIT 50",
                          (g.user["id"],)).fetchall()
        summary = db.execute("""SELECT COALESCE(SUM(minutes),0) AS total,
                                 COUNT(*) AS count FROM study_sessions WHERE user_id=?""",
                              (g.user["id"],)).fetchone()
        by_topic = db.execute("""SELECT topic, SUM(minutes) AS minutes FROM study_sessions
                                 WHERE user_id=? GROUP BY topic ORDER BY minutes DESC LIMIT 6""",
                              (g.user["id"],)).fetchall()
    return render_template("study_log.html", logs=logs, summary=summary, by_topic=by_topic,
                           today=date.today().isoformat())


@app.route("/study-log/<int:log_id>/delete", methods=["POST"])
@login_required
def delete_study_log(log_id):
    with connect_db() as db:
        db.execute("DELETE FROM study_sessions WHERE id=? AND user_id=?", (log_id, g.user["id"]))
        db.commit()
    flash("Study entry deleted.", "info")
    return redirect(url_for("study_log"))


@app.route("/simulator", methods=["GET", "POST"])
@login_required
def simulator():
    profile = get_profile(g.user["id"])
    roles = get_roles()
    role = profile["target_role"]
    required = roles.get(role, [])
    current_lower = {s.casefold() for s in parse_skills(profile["current_skills"])}
    gaps = [s for s in required if s.casefold() not in current_lower]
    result = None
    if request.method == "POST":
        try:
            hours = float(request.form.get("hours_per_day", "2"))
            days = int(request.form.get("days_per_week", "5"))
            months = int(request.form.get("months", "6"))
            dsa_pct = int(request.form.get("dsa_pct", "30"))
            ai_pct = int(request.form.get("ai_pct", "40"))
            cs_pct = int(request.form.get("cs_pct", "20"))
            project_pct = int(request.form.get("project_pct", "10"))
            values = [dsa_pct, ai_pct, cs_pct, project_pct]
            if not (0.25 <= hours <= 16 and 1 <= days <= 7 and 1 <= months <= 36):
                raise ValueError
            if any(v < 0 for v in values) or sum(values) != 100:
                flash("Allocation percentages must be non-negative and add up to exactly 100%.", "danger")
            else:
                total = hours * days * 4.345 * months
                result = {
                    "total_hours": round(total, 1),
                    "total_weeks": round(months * 4.345, 1),
                    "dsa": round(total * dsa_pct / 100, 1),
                    "ai": round(total * ai_pct / 100, 1),
                    "cs": round(total * cs_pct / 100, 1),
                    "projects": round(total * project_pct / 100, 1),
                    "gaps": gaps,
                    "months": months,
                    "hours": hours,
                    "days": days,
                    "percentages": values
                }
        except (ValueError, TypeError):
            flash("Enter valid numbers for your simulation.", "danger")
    return render_template("simulator.html", result=result, gaps=gaps, role=role)


@app.route("/about")
def about():
    return render_template("about.html")


@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", code=404, message="That page could not be found."), 404


@app.errorhandler(500)
def server_error(error):
    return render_template("error.html", code=500, message="Something went wrong. Please try again."), 500


init_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
