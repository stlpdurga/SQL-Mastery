import os
import re
import secrets
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("SQL_MASTERY_DATABASE", ROOT / "sql_mastery.db"))
app = Flask(__name__)
app.secret_key = os.environ.get("SQL_MASTERY_SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SQL_MASTERY_HTTPS", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(days=14),
)

LEVELS = [
    ("beginner", "Beginner", "Build a strong foundation, one query at a time.", "#e1f4e9"),
    ("intermediate", "Intermediate", "Ask better questions of your data.", "#e5efff"),
    ("advanced", "Advanced", "Write powerful, efficient SQL with confidence.", "#f5e8f3"),
]
TOPICS = {
    "beginner": [
        "What is SQL?", "What is a Database?", "Tables, Rows and Columns", "SQL Syntax Basics", "SELECT", "SELECT DISTINCT", "WHERE", "Comparison Operators", "AND / OR / NOT", "ORDER BY", "LIMIT", "INSERT", "UPDATE", "DELETE", "NULL Values", "Aliases",
    ],
    "intermediate": [
        "Aggregate Functions", "COUNT()", "SUM()", "AVG()", "MIN()", "MAX()", "GROUP BY", "HAVING", "LIKE", "IN", "BETWEEN", "CASE", "String Functions", "Date Functions", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL OUTER JOIN", "Self JOIN", "UNION", "UNION ALL", "Subqueries", "EXISTS",
    ],
    "advanced": [
        "Common Table Expressions (CTEs)", "Recursive CTEs", "Window Functions", "ROW_NUMBER()", "RANK()", "DENSE_RANK()", "LEAD()", "LAG()", "PARTITION BY", "Advanced CASE Statements", "Advanced Subqueries", "Views", "Stored Procedures", "Functions", "Triggers", "Transactions", "COMMIT", "ROLLBACK", "Indexes", "Query Optimization", "Database Normalization", "Primary Keys", "Foreign Keys", "Constraints", "Advanced SQL Interview Questions",
    ],
}

EXAMPLES = {
    "SELECT": ("SELECT column_name\nFROM table_name;", "SELECT name, department\nFROM employees;", "Returns the name and department columns for every employee.", "Use * to select every column, but name columns explicitly in real queries.", "Forgetting FROM means SQL does not know which table to read.", "Show the names of everyone in the Sales department.", "SELECT name FROM employees WHERE department = 'Sales';"),
    "SELECT DISTINCT": ("SELECT DISTINCT column_name\nFROM table_name;", "SELECT DISTINCT department\nFROM employees;", "Returns each department once, even if many employees share it.", "DISTINCT applies to the complete set of selected columns.", "Adding another column can make rows distinct again.", "List each department only once.", "SELECT DISTINCT department FROM employees;"),
    "WHERE": ("SELECT columns\nFROM table_name\nWHERE condition;", "SELECT name, salary\nFROM employees\nWHERE salary > 70000;", "Keeps only rows that match the condition.", "Text values need quotes; numeric values do not.", "WHERE filters rows before grouping.", "Find employees earning under 60000.", "SELECT name FROM employees WHERE salary < 60000;"),
    "ORDER BY": ("SELECT columns\nFROM table_name\nORDER BY column_name [ASC | DESC];", "SELECT name, salary\nFROM employees\nORDER BY salary DESC;", "Sorts the results from highest salary to lowest.", "ASC is the default. Add a second column to break ties.", "Without ORDER BY, row order is not guaranteed.", "Show employees from highest to lowest salary.", "SELECT name, salary FROM employees ORDER BY salary DESC;"),
    "LIMIT": ("SELECT columns\nFROM table_name\nLIMIT number;", "SELECT name\nFROM employees\nORDER BY salary DESC\nLIMIT 3;", "Returns just the first three rows after sorting.", "Pair LIMIT with ORDER BY when you need predictable results.", "LIMIT before a meaningful sort may return arbitrary rows.", "Show the two highest-paid employees.", "SELECT name FROM employees ORDER BY salary DESC LIMIT 2;"),
    "COUNT()": ("SELECT COUNT(column_name)\nFROM table_name;", "SELECT COUNT(*) AS employee_count\nFROM employees;", "Counts the number of employee rows.", "COUNT(*) includes all rows; COUNT(column) skips NULL values.", "COUNT(*) does not count distinct values unless you add DISTINCT.", "Count all employees.", "SELECT COUNT(*) FROM employees;"),
    "GROUP BY": ("SELECT group_column, aggregate_function(value)\nFROM table_name\nGROUP BY group_column;", "SELECT department, COUNT(*) AS people\nFROM employees\nGROUP BY department;", "Makes one result row per department, with a headcount for each.", "Every selected non-aggregate column should appear in GROUP BY.", "Filtering grouped totals uses HAVING, not WHERE.", "Count employees in each department.", "SELECT department, COUNT(*) FROM employees GROUP BY department;"),
    "HAVING": ("SELECT group_column, aggregate_function(value)\nFROM table_name\nGROUP BY group_column\nHAVING aggregate_condition;", "SELECT department, AVG(salary) AS average_salary\nFROM employees\nGROUP BY department\nHAVING AVG(salary) > 70000;", "Filters groups after their averages have been calculated.", "WHERE filters input rows; HAVING filters grouped results.", "Do not use HAVING as a substitute for a simple WHERE filter.", "Show departments with more than one employee.", "SELECT department FROM employees GROUP BY department HAVING COUNT(*) > 1;"),
    "INNER JOIN": ("SELECT columns\nFROM first_table\nINNER JOIN second_table ON first_table.key = second_table.key;", "SELECT employees.name, departments.location\nFROM employees\nINNER JOIN departments ON employees.department = departments.name;", "Combines matching employee and department rows.", "Qualify columns when both tables could contain the same name.", "Missing or incorrect join conditions can multiply rows.", "List each employee beside their department location.", "SELECT e.name, d.location FROM employees e INNER JOIN departments d ON e.department = d.name;"),
    "LEFT JOIN": ("SELECT columns\nFROM first_table\nLEFT JOIN second_table ON join_condition;", "SELECT e.name, d.location\nFROM employees e\nLEFT JOIN departments d ON e.department = d.name;", "Keeps every employee; unmatched department columns become NULL.", "A LEFT JOIN preserves all rows from the table on its left.", "A WHERE filter on the right table can accidentally remove unmatched rows.", "Show every employee and their department location when available.", "SELECT e.name, d.location FROM employees e LEFT JOIN departments d ON e.department = d.name;"),
    "Common Table Expressions (CTEs)": ("WITH cte_name AS (\n    SELECT ...\n)\nSELECT ... FROM cte_name;", "WITH high_earners AS (\n  SELECT name, salary FROM employees WHERE salary > 70000\n)\nSELECT name FROM high_earners;", "Names a temporary result so a longer query is easier to read.", "A CTE exists only for the single statement immediately after WITH.", "A CTE is a readability tool, not automatically a performance improvement.", "Create a CTE of employees in Engineering, then select their names.", "WITH engineers AS (SELECT name FROM employees WHERE department = 'Engineering') SELECT name FROM engineers;"),
    "Window Functions": ("function_name() OVER (\n    PARTITION BY group_column\n    ORDER BY sort_column\n)\n", "SELECT name, department,\n  ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) AS rank\nFROM employees;", "Adds a calculation beside each row without collapsing rows into groups.", "The OVER clause defines which rows the calculation can see.", "Unlike GROUP BY, window functions preserve individual rows.", "Number employees within each department by salary.", "SELECT name, ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) FROM employees;"),
    "Transactions": ("BEGIN;\nUPDATE ...;\nCOMMIT; -- or ROLLBACK;", "BEGIN;\nUPDATE employees SET salary = salary + 1000 WHERE id = 1;\nCOMMIT;", "Groups changes so they can be saved together or undone together.", "A transaction is useful when several changes must succeed as a unit.", "Forgetting to commit may leave changes unsaved, depending on the client.", "In a transaction, increase the salary of employee 1 by 500.", "BEGIN; UPDATE employees SET salary = salary + 500 WHERE id = 1; COMMIT;"),
    "Indexes": ("CREATE INDEX index_name\nON table_name (column_name);", "CREATE INDEX idx_employees_department\nON employees (department);", "Creates a lookup structure that can speed up searches on department.", "Indexes trade extra storage and slower writes for faster reads.", "Adding indexes to every column can make updates unnecessarily expensive.", "Write the SQL statement that indexes the employees department column.", "CREATE INDEX idx_department ON employees (department);"),
}


def slugify(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def build_curriculum():
    lessons = []
    number = 0
    for level_id, level_name, _, _ in LEVELS:
        for title in TOPICS[level_id]:
            number += 1
            slug = slugify(title)
            syntax, example, output, notes, mistakes, task, answer = EXAMPLES.get(
                title,
                (f"-- {title}\nSELECT ...\nFROM table_name;",
                 f"SELECT name\nFROM employees; -- {title}",
                 f"This query demonstrates where {title} fits into a SQL statement.",
                 f"Use {title} when it makes the intent of your query clearer.",
                 "Check the clause order and make sure each column belongs to the table you are querying.",
                 f"Write a query that returns employee names using {title}.",
                 "SELECT name FROM employees;"),
            )
            lessons.append({
                "id": slug, "title": title, "level": level_id, "level_name": level_name,
                "number": number, "syntax": syntax, "example": example, "output": output,
                "notes": notes, "mistakes": mistakes, "task": task, "answer": answer,
                "explanation": f"{title} is one of the building blocks of SQL. Think of a database as a set of organized spreadsheets: this idea helps you ask for, shape, or manage the information stored in them.",
                "quiz_question": f"Which statement best describes {title}?",
                "options": [f"A SQL concept used to work with data: {title}", "A type of computer hardware", "A web browser setting"],
                "correct": 0,
            })
    return lessons


LESSONS = build_curriculum()
LESSON_BY_ID = {lesson["id"]: lesson for lesson in LESSONS}
SAMPLE_SCHEMA = """CREATE TABLE employees (id INTEGER, name TEXT, department TEXT, salary INTEGER, hire_date TEXT);
INSERT INTO employees VALUES
  (1, 'Ava Chen', 'Engineering', 92000, '2021-03-14'),
  (2, 'Noah Patel', 'Design', 74000, '2022-06-02'),
  (3, 'Mia Brooks', 'Engineering', 85000, '2020-11-19'),
  (4, 'Leo Martin', 'Sales', 61000, '2023-01-09'),
  (5, 'Zoe Kim', 'Sales', 68000, '2022-09-27');
CREATE TABLE departments (name TEXT, location TEXT);
INSERT INTO departments VALUES ('Engineering', 'Seattle'), ('Design', 'Portland'), ('Sales', 'Austin');"""


def get_db():
    if "db" not in g:
        DATABASE.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


def initialize_db():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE) as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                longest_streak INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS completions (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                lesson_id TEXT NOT NULL,
                completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, lesson_id)
            );
            CREATE TABLE IF NOT EXISTS quiz_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                lesson_id TEXT NOT NULL,
                score INTEGER NOT NULL,
                attempted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS activity_dates (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                activity_date TEXT NOT NULL,
                PRIMARY KEY (user_id, activity_date)
            );
        """)


initialize_db()


@app.teardown_appcontext
def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


@app.context_processor
def csrf_context():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return {"csrf_token": session["csrf_token"]}


@app.before_request
def enforce_csrf():
    if request.method == "POST":
        submitted = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
        if not submitted or not secrets.compare_digest(submitted, session.get("csrf_token", "")):
            if request.is_json:
                return jsonify(error="Your session expired. Refresh the page and try again."), 400
            abort(400, "Invalid or expired form token.")


def signed_in():
    return session.get("user_id") is not None


def login_required(view):
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not signed_in():
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def activity_today(user_id):
    today = date.today()
    rows = get_db().execute(
        "SELECT activity_date FROM activity_dates WHERE user_id = ? ORDER BY activity_date DESC LIMIT 400",
        (user_id,),
    ).fetchall()
    active_dates = {date.fromisoformat(row["activity_date"]) for row in rows}
    last_day = max(active_dates, default=None)
    if last_day not in (today, today - timedelta(days=1)):
        current = 0
    else:
        cursor = last_day
        current = 0
        while cursor in active_dates:
            current += 1
            cursor -= timedelta(days=1)
    return current


def record_activity(user_id):
    connection = get_db()
    connection.execute(
        "INSERT OR IGNORE INTO activity_dates (user_id, activity_date) VALUES (?, ?)",
        (user_id, date.today().isoformat()),
    )
    user_streak = activity_today(user_id)
    connection.execute("UPDATE users SET longest_streak = MAX(longest_streak, ?) WHERE id = ?", (user_streak, user_id))


def dashboard_data(user_id):
    connection = get_db()
    completed = {row["lesson_id"] for row in connection.execute("SELECT lesson_id FROM completions WHERE user_id = ?", (user_id,))}
    scores = connection.execute("SELECT AVG(score) AS average FROM quiz_attempts WHERE user_id = ?", (user_id,)).fetchone()["average"]
    user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    enriched = [{**lesson, "completed": lesson["id"] in completed} for lesson in LESSONS]
    next_lesson = next((lesson for lesson in enriched if not lesson["completed"]), enriched[-1])
    levels = []
    for level_id, name, description, color in LEVELS:
        items = [lesson for lesson in enriched if lesson["level"] == level_id]
        count = sum(item["completed"] for item in items)
        levels.append({"id": level_id, "name": name, "description": description, "color": color, "lessons": items, "done": count, "total": len(items), "percent": round(count * 100 / len(items))})
    return {
        "user": user, "lessons": enriched, "levels": levels, "completed": len(completed),
        "total": len(LESSONS), "percent": round(len(completed) * 100 / len(LESSONS)),
        "streak": activity_today(user_id), "longest": user["longest_streak"],
        "quiz_score": round(scores) if scores is not None else 0,
        "next_lesson": next_lesson,
    }


@app.route("/")
def home():
    return redirect(url_for("dashboard") if signed_in() else url_for("login"))


@app.route("/login.html", methods=["GET", "POST"])
def login():
    if signed_in():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        identity = request.form.get("identity", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE username = ? OR email = ?", (identity, identity)).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            flash("That username, email, or password doesn't match.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["csrf_token"] = secrets.token_urlsafe(32)
            target = request.args.get("next", "")
            return redirect(target if target.startswith("/") and not target.startswith("//") else url_for("dashboard"))
    return render_template("login.html")


@app.route("/register.html", methods=["GET", "POST"])
def register():
    if signed_in():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        error = None
        if not all((full_name, email, username, password, confirm)):
            error = "Please complete every field."
        elif not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            error = "Enter a valid email address."
        elif not re.fullmatch(r"[A-Za-z0-9_]{3,24}", username):
            error = "Username must be 3–24 characters: letters, numbers, or underscores."
        elif len(password) < 8:
            error = "Use a password with at least 8 characters."
        elif password != confirm:
            error = "Passwords do not match."
        elif get_db().execute("SELECT 1 FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone():
            error = "That username is already taken."
        elif get_db().execute("SELECT 1 FROM users WHERE email = ? COLLATE NOCASE", (email,)).fetchone():
            error = "An account with that email already exists."
        if error:
            flash(error, "error")
        else:
            get_db().execute(
                "INSERT INTO users (full_name, username, email, password_hash) VALUES (?, ?, ?, ?)",
                (full_name, username, email, generate_password_hash(password)),
            )
            get_db().commit()
            flash("Your account is ready. Sign in to start learning.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.post("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/dashboard.html")
@login_required
def dashboard():
    return render_template("dashboard.html", **dashboard_data(session["user_id"]))


@app.get("/lesson.html")
@login_required
def lesson():
    lesson_item = LESSON_BY_ID.get(request.args.get("id", ""))
    if lesson_item is None:
        abort(404)
    enriched = dashboard_data(session["user_id"])
    item = {**lesson_item, "completed": lesson_item["id"] in {x["id"] for x in enriched["lessons"] if x["completed"]}}
    next_item = next((x for x in LESSONS if x["number"] > lesson_item["number"]), None)
    return render_template("lesson.html", lesson=item, next_lesson=next_item, username=session.get("username"))


@app.post("/api/lesson/complete")
@login_required
def complete_lesson():
    payload = request.get_json(silent=True) or {}
    lesson_id = payload.get("lesson_id", "")
    if lesson_id not in LESSON_BY_ID:
        return jsonify(error="Lesson not found."), 404
    connection = get_db()
    connection.execute("INSERT OR IGNORE INTO completions (user_id, lesson_id) VALUES (?, ?)", (session["user_id"], lesson_id))
    record_activity(session["user_id"])
    connection.commit()
    stats = dashboard_data(session["user_id"])
    return jsonify(ok=True, progress=stats["percent"], current_streak=stats["streak"])


@app.post("/api/quiz")
@login_required
def submit_quiz():
    payload = request.get_json(silent=True) or {}
    lesson_item = LESSON_BY_ID.get(payload.get("lesson_id", ""))
    answer = payload.get("answer")
    if lesson_item is None or not isinstance(answer, int) or answer not in range(len(lesson_item["options"])):
        return jsonify(error="Choose one of the quiz answers."), 400
    score = 100 if answer == lesson_item["correct"] else 0
    connection = get_db()
    connection.execute("INSERT INTO quiz_attempts (user_id, lesson_id, score) VALUES (?, ?, ?)", (session["user_id"], lesson_item["id"], score))
    record_activity(session["user_id"])
    connection.commit()
    return jsonify(ok=True, correct=score == 100, score=score, correct_answer=lesson_item["options"][lesson_item["correct"]])


@app.post("/api/practice")
@login_required
def run_practice():
    payload = request.get_json(silent=True) or {}
    query = payload.get("query", "")
    lesson_id = payload.get("lesson_id", "")
    if lesson_id not in LESSON_BY_ID or not isinstance(query, str) or len(query) > 4000:
        return jsonify(error="Enter a query for this lesson."), 400
    normalized = query.strip()
    if not re.match(r"^(SELECT|WITH)\b", normalized, re.IGNORECASE) or re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|PRAGMA|VACUUM)\b", normalized, re.IGNORECASE):
        return jsonify(error="Practice mode is read-only. Start with a SELECT query."), 400
    try:
        with sqlite3.connect(":memory:") as sandbox:
            sandbox.row_factory = sqlite3.Row
            sandbox.executescript(SAMPLE_SCHEMA)
            sandbox.execute("PRAGMA query_only = ON")
            cursor = sandbox.execute(normalized)
            columns = [item[0] for item in cursor.description or []]
            rows = [list(row) for row in cursor.fetchmany(100)]
    except sqlite3.Error as error:
        return jsonify(error=f"SQL error: {error}"), 400
    connection = get_db()
    connection.execute("INSERT OR IGNORE INTO completions (user_id, lesson_id) VALUES (?, ?)", (session["user_id"], lesson_id))
    record_activity(session["user_id"])
    connection.commit()
    return jsonify(ok=True, columns=columns, rows=rows, row_count=len(rows))


@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html", code=400, message=getattr(error, "description", "Please try again.")), 400


@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", code=404, message="We couldn't find that page."), 404


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1", port=int(os.environ.get("PORT", "5000")))
