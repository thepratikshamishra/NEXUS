# NEXUS — A Personal Learning Intelligence and Skill-Planning System

NEXUS is a local Flask web application prototype for organizing a learner's career goal, current skills, skill gaps, roadmap tasks, study logs, and hypothetical study-time plans.

## Features included

- Registration and login with Werkzeug password hashing
- Session-based access protection and logout
- SQLite database initialized automatically
- Learning profile: name, target career role, current skills, weekly study hours
- Role-based skill gap analysis using editable JSON data
- Skill progress status: Planned, In progress, Completed; confidence rating and notes
- Personal learning roadmap: add tasks, set due dates, update status, delete tasks
- Study log: record topic, date, minutes, notes; see totals and topic summaries
- What-if study simulator: estimate study hours over a chosen number of months and allocate time across DSA, AI/ML, CS fundamentals, and projects
- Responsive dashboard and user interface
- Sample roles and skills in `data/roles_skills.json`

## Run on Windows

1. Extract the ZIP.
2. Install Python 3.10 or newer from https://www.python.org/downloads/ (enable PATH during installation).
3. Double-click `run_windows.bat`, or open a terminal in this folder and run:

```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

4. Open http://127.0.0.1:5000 in your browser.
5. Register a new account.

## Run on macOS / Linux

```bash
chmod +x run_mac_linux.sh
./run_mac_linux.sh
```

Then open http://127.0.0.1:5000.

## Data storage

The app creates `nexus.db` in the project folder on first run. Your account, profile, progress, roadmap, and study-log data are stored locally in this SQLite database. Keep a backup if the data matters to you.

## Configure before deployment

This project is intended as a local academic prototype, not a hardened public service. Before deploying it:
- Set a long random `NEXUS_SECRET_KEY` environment variable.
- Set `FLASK_DEBUG=0`.
- Use HTTPS and a production WSGI server.
- Add CSRF protection, rate limiting, stricter validation, logging, and deployment-specific security settings.
- Review privacy and backup requirements.

For Windows PowerShell, set the key for the current terminal session:

```powershell
$env:NEXUS_SECRET_KEY = "replace-with-a-long-random-secret"
python app.py
```

## Current scope and honest limitations

The role-skill comparison and simulator are transparent rule-based estimates. They do not train an AI/ML model, predict job offers, or guarantee career outcomes. The hours estimate uses 4.345 weeks per month. Skill gaps are based on matching skill names against the local role dataset, so use consistent names in the profile.

The prototype uses a development server for local use. It is not production-ready without the security improvements above.
