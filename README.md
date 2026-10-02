# SQL Mastery

A local-first SQL learning platform built with Flask and SQLite. It includes account registration and login, hashed passwords, protected learning pages, a 64-lesson curriculum, a read-only SQL practice sandbox, quizzes, progress tracking, and activity-based streaks.

## Run locally

1. Install Python 3.10 or newer.
2. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Copy `.env.example` to `.env` and set a private `SECRET_KEY` value.
4. Install dependencies and start the app:

   ```powershell
   python -m pip install -r requirements.txt
   python app.py
   ```

5. Open http://127.0.0.1:5000/login to sign in or create an account.

The account/progress and practice databases initialize lazily on the first non-health request. Locally they are created beside `app.py`; `SQL_MASTERY_DATABASE` and `SQL_MASTERY_PRACTICE_DATABASE` can override their paths. The root `app.py` exposes the Flask `app` object directly for Vercel's Flask runtime; no custom `vercel.json` routing is required. `/health` and `/api/health` do not initialize or depend on SQLite.

## Learning activity

For Vercel, configure `SECRET_KEY` in Project Settings → Environment Variables before using login. Serverless SQLite files are placed under `/tmp/sql-mastery`; this storage is temporary and not shared reliably across instances, so account data, progress, and streaks are demo-only on Vercel. Use a persistent external database before relying on deployed user data. The built-in practice data is reproducibly seeded with 20 employees and six departments. Completing a lesson, running a valid read-only practice query, or submitting a quiz counts as activity; opening the site or signing in does not. `/practice` opens the SQL editor and `/progress` shows learning statistics. Never expose the Flask development server publicly; use HTTPS and a production deployment.
