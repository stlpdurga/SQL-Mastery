# SQL Mastery

A local-first SQL learning platform built with Flask and SQLite. It includes account registration and login, hashed passwords, protected learning pages, a 64-lesson curriculum, a read-only SQL practice sandbox, quizzes, progress tracking, and activity-based streaks.

## Run locally

1. Install Python 3.10 or newer.
2. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies and start the app:

   ```powershell
   python -m pip install -r requirements.txt
   python app.py
   ```

4. Open http://127.0.0.1:5000/login to sign in or create an account.

The account/progress database is created automatically as `sql_mastery.db` on first start. Set `SQL_MASTERY_DATABASE` to move it elsewhere. Set `SQL_MASTERY_PRACTICE_DATABASE` to choose another path for the separately stored practice database. Set `SQL_MASTERY_SECRET_KEY` to a stable random secret for deployments; local development generates a new secret when the process starts. Set `SQL_MASTERY_HTTPS=1` when serving over HTTPS so session cookies use the Secure flag. Never expose the Flask development server to the public internet; deploy behind a production WSGI server and HTTPS.

## Learning activity

Completing a lesson, running a valid read-only practice query, or submitting a quiz counts as activity for that calendar day. Opening the site or signing in does not. A separate SQLite practice database is seeded automatically with 20 employees and six departments. The `/practice` route opens the built-in SQL editor; `/progress` shows lesson completion, quiz average, activity streaks, and the last learning activity. Practice queries are read-only and never execute against account or progress data.
