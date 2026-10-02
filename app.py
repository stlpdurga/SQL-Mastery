import os
import re
import secrets
import sqlite3
import threading
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import HTTPException

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
IS_VERCEL = os.environ.get("VERCEL") == "1"
DATA_ROOT = Path(os.environ.get("TMPDIR") or "/tmp") / "sql-mastery" if IS_VERCEL else ROOT


def configured_database_path(environment_name, default_name):
    value = os.environ.get(environment_name)
    path = Path(value).expanduser() if value else Path(default_name)
    return path if path.is_absolute() else DATA_ROOT / path


DATABASE = configured_database_path("SQL_MASTERY_DATABASE", "sql_mastery.db")
PRACTICE_DATABASE = configured_database_path("SQL_MASTERY_PRACTICE_DATABASE", "sql_mastery_practice.db")
CONFIGURED_SECRET_KEY = os.environ.get("SECRET_KEY") or os.environ.get("SQL_MASTERY_SECRET_KEY")
app = Flask(__name__)
app.secret_key = CONFIGURED_SECRET_KEY or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=IS_VERCEL or os.environ.get("SQL_MASTERY_HTTPS", "0") == "1",
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

QUIZ_BANK = {
    "What is SQL?": ("What is SQL primarily used for?", "Querying and managing relational data", "Designing web page layouts", "Compressing image files", "Controlling a computer's operating system"),
    "What is a Database?": ("What is a database?", "An organized collection of data", "A single spreadsheet formula", "A programming language", "A network cable"),
    "Tables, Rows and Columns": ("In a relational table, what does a row usually represent?", "One record", "One field name", "The whole database", "A relationship rule"),
    "SQL Syntax Basics": ("What commonly separates clauses in a basic SELECT statement?", "Keywords such as SELECT, FROM, and WHERE", "Curly braces around every clause", "A comma between every keyword", "A required slash at the end"),
    "SELECT": ("Which statement retrieves every column from employees?", "SELECT * FROM employees;", "GET ALL employees;", "READ employees.*;", "SHOW employees COLUMNS;"),
    "SELECT DISTINCT": ("What does SELECT DISTINCT do?", "Removes duplicate result rows", "Sorts rows alphabetically", "Filters rows with a condition", "Limits results to one row"),
    "WHERE": ("When does WHERE filter rows?", "Before grouping and aggregation", "After ORDER BY", "Only after LIMIT", "Only when a table has a primary key"),
    "Comparison Operators": ("Which operator means 'not equal to' in SQLite?", "<>", "=>", "=!", "><"),
    "AND / OR / NOT": ("A WHERE condition joined with AND is true when...", "Both conditions are true", "Either condition is true", "Both conditions are false", "The first condition is omitted"),
    "ORDER BY": ("How do you sort salary from highest to lowest?", "ORDER BY salary DESC", "ORDER salary HIGH", "SORT BY salary DOWN", "GROUP BY salary DESC"),
    "LIMIT": ("What does LIMIT 5 do in SQLite?", "Returns at most five result rows", "Skips the first five rows", "Keeps rows with values above five", "Creates five copies of each row"),
    "INSERT": ("Which command adds a new row to a table?", "INSERT INTO", "ADD ROW", "UPDATE INTO", "CREATE VALUE"),
    "UPDATE": ("What should usually accompany UPDATE to change only selected rows?", "A WHERE clause", "A GROUP BY clause", "A CREATE clause", "A second table name"),
    "DELETE": ("What does DELETE FROM employees WHERE id = 3 do?", "Removes matching employee rows", "Removes the employees table", "Sets every salary to 3", "Creates a backup row"),
    "NULL Values": ("How should SQL test whether a value is missing?", "column_name IS NULL", "column_name = NULL", "column_name EQUALS EMPTY", "column_name == BLANK"),
    "Aliases": ("Which keyword gives a result column a temporary label?", "AS", "TO", "LABEL", "RENAME"),
    "Aggregate Functions": ("What do aggregate functions generally calculate?", "A summary value from multiple rows", "A new table for each row", "A sort order only", "A database connection"),
    "COUNT()": ("What does COUNT(*) count?", "All rows in the result", "Only non-NULL values in the first column", "Only distinct tables", "The number of columns"),
    "SUM()": ("What does SUM(salary) return?", "The total of the non-NULL salary values", "The average salary", "The largest salary", "The number of salaries"),
    "AVG()": ("What does AVG(salary) calculate?", "The arithmetic mean of non-NULL salaries", "The middle salary by rank", "The total salary", "The number of departments"),
    "MIN()": ("What does MIN(salary) return?", "The smallest non-NULL salary", "The most frequent salary", "The average salary", "The number of salary values"),
    "MAX()": ("What does MAX(salary) return?", "The largest non-NULL salary", "The sum of salaries", "The median salary", "The first salary inserted"),
    "GROUP BY": ("What does GROUP BY department do?", "Creates one group for each department value", "Sorts departments in alphabetical order", "Deletes duplicate departments from the table", "Filters rows before SELECT"),
    "HAVING": ("Which clause filters groups after GROUP BY?", "HAVING", "WHERE", "ORDER BY", "LIMIT"),
    "LIKE": ("In LIKE patterns, what does % match?", "Zero or more characters", "Exactly one character", "Only numeric digits", "A NULL value"),
    "IN": ("What does department IN ('IT', 'HR') test?", "Whether department matches either listed value", "Whether department contains both words", "Whether department is between IT and HR", "Whether department is NULL"),
    "BETWEEN": ("In SQLite, BETWEEN 10 AND 20 includes which boundaries?", "Both 10 and 20", "Neither 10 nor 20", "10 but not 20", "20 but not 10"),
    "CASE": ("What does a CASE expression return?", "A value selected by the first matching WHEN branch", "A new database table", "A sorted copy of the input rows", "A count of all matching rows"),
    "String Functions": ("What does UPPER('sql') return in SQLite?", "SQL", "sql", "Sql", "NULL"),
    "Date Functions": ("What does SQLite date('2025-01-02', '+1 day') return?", "2025-01-03", "2025-01-01", "2025-02-02", "2026-01-02"),
    "INNER JOIN": ("Which rows does an INNER JOIN return?", "Rows with matching join keys in both inputs", "Every row from the left input, matched or not", "Every row from the right input, matched or not", "Only rows with NULL join keys"),
    "LEFT JOIN": ("What does a LEFT JOIN preserve?", "Every row from the left table", "Every row from the right table only", "Only rows that match in both tables", "Only rows with duplicate keys"),
    "RIGHT JOIN": ("What does a RIGHT JOIN preserve?", "Every row from the right table", "Every row from the left table only", "Only matching rows from both tables", "Only rows with NULL values"),
    "FULL OUTER JOIN": ("What does a FULL OUTER JOIN preserve?", "Matched rows plus unmatched rows from both sides", "Only matching rows", "All left rows and no right-only rows", "Only rows with identical column names"),
    "Self JOIN": ("Why would a query join a table to itself?", "To relate rows within the same table, such as employees and managers", "To remove every duplicate row", "To combine two databases permanently", "To sort rows without ORDER BY"),
    "UNION": ("What does UNION do by default?", "Combines compatible result sets and removes duplicate rows", "Combines tables side by side", "Keeps all duplicates", "Updates matching rows"),
    "UNION ALL": ("How does UNION ALL differ from UNION?", "It keeps duplicate rows", "It sorts each input automatically", "It requires matching primary keys", "It updates the first result set"),
    "Subqueries": ("What is a subquery?", "A query nested inside another SQL statement", "A query that can only read system tables", "A synonym for an index", "A table with no columns"),
    "EXISTS": ("What does EXISTS test?", "Whether its subquery returns at least one row", "Whether a column contains no NULL values", "Whether two tables have equal row counts", "Whether a table has an index"),
    "Common Table Expressions (CTEs)": ("How long is a non-recursive CTE available?", "For the single statement immediately following WITH", "Until the database is closed", "For every user session", "Until it is manually dropped"),
    "Recursive CTEs": ("What are the two conceptual parts of a recursive CTE?", "An initial query and a recursive query", "A primary key and a foreign key", "A trigger and an index", "A SELECT and a mandatory DELETE"),
    "Window Functions": ("Unlike GROUP BY, a window function usually...", "Calculates across related rows while keeping each input row", "Collapses each group into one row", "Deletes rows outside a partition", "Creates a permanent view"),
    "ROW_NUMBER()": ("What does ROW_NUMBER() assign within its window?", "A unique sequential number to each row", "The same rank to all tied rows", "A count of distinct columns", "A permanent employee ID"),
    "RANK()": ("When two rows tie under RANK(), what happens to later ranks?", "The next rank contains a gap", "The next rank always increments by exactly one", "All following rows receive NULL", "The tied rows are removed"),
    "DENSE_RANK()": ("When two rows tie under DENSE_RANK(), what happens to the next rank?", "It increments by one without a gap", "It skips a rank", "It restarts at one", "It becomes NULL"),
    "LEAD()": ("What does LEAD(value) access by default?", "A value from a following row in the window", "A value from the previous row", "The first value in the whole database", "The highest value in the group"),
    "LAG()": ("What does LAG(value) access by default?", "A value from a preceding row in the window", "A value from the next row", "The lowest value in the group", "The row count"),
    "PARTITION BY": ("What does PARTITION BY do inside OVER()?", "Divides rows into groups for a window calculation", "Sorts the final query result", "Filters rows before joins", "Creates a physical table partition"),
    "Advanced CASE Statements": ("In a searched CASE expression, which matching WHEN branch is used?", "The first WHEN condition that evaluates true", "The last WHEN condition that evaluates true", "Every matching branch is combined", "The branch with the largest numeric result"),
    "Advanced Subqueries": ("What makes a subquery correlated?", "It refers to a column from its outer query", "It contains the UNION keyword", "It returns exactly one row", "It is stored as a view"),
    "Views": ("What is a typical SQL view?", "A saved query that can be queried like a virtual table", "A copied database file", "A required index on every column", "A transaction that cannot be rolled back"),
    "Stored Procedures": ("What is a stored procedure in database systems that support them?", "A named set of SQL statements stored for later execution", "A row-level constraint", "A temporary query alias", "A type of foreign key"),
    "Functions": ("What does a SQL scalar function typically return per invocation?", "A single value", "A complete database", "A set of table definitions", "A transaction log"),
    "Triggers": ("What commonly causes a database trigger to run?", "A configured table event such as INSERT, UPDATE, or DELETE", "Opening the dashboard", "Creating a SELECT alias", "Reading a query result"),
    "Transactions": ("What is the purpose of a database transaction?", "Treat related operations as a unit that can be committed or rolled back", "Sort query results consistently", "Make every query read-only", "Create a view automatically"),
    "COMMIT": ("What does COMMIT do?", "Makes the current transaction's changes permanent", "Undoes the current transaction", "Starts a new database", "Locks every table permanently"),
    "ROLLBACK": ("What does ROLLBACK do before a transaction is committed?", "Undoes the transaction's pending changes", "Saves the pending changes", "Creates a savepoint automatically", "Deletes the transaction log"),
    "Indexes": ("What is a common tradeoff of adding an index?", "Faster lookups can cost storage and slow some writes", "Every query becomes faster with no cost", "It removes the need for keys", "It permanently sorts the underlying table"),
    "Query Optimization": ("What is a useful first step when investigating a slow query?", "Inspect its execution plan and identify expensive operations", "Add an index to every column", "Remove all WHERE clauses", "Replace every JOIN with a subquery"),
    "Database Normalization": ("What is a common goal of normalization?", "Reduce unnecessary duplication and update anomalies", "Store every value in one giant text column", "Make every query use a window function", "Duplicate each row for backup"),
    "Primary Keys": ("What must a primary key identify?", "Each row uniquely, without NULL values", "A group of duplicate rows", "The database server's network address", "Only optional descriptive text"),
    "Foreign Keys": ("What does a foreign key typically enforce?", "A reference to a valid key in a related table", "A required sort order", "A unique value in every column", "A saved query definition"),
    "Constraints": ("What is the purpose of a database constraint?", "Enforce rules on values or relationships in stored data", "Format query output colors", "Choose which rows a SELECT returns", "Rename a result column"),
    "Advanced SQL Interview Questions": ("Which function numbers employees by salary within each department without collapsing rows?", "ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC)", "COUNT(*) GROUP BY department", "DELETE FROM employees ORDER BY salary", "DISTINCT department ORDER BY salary"),
}


def build_quiz(title, number):
    question, correct_option, *distractors = QUIZ_BANK[title]
    correct_index = 0
    options = list(distractors)
    options.insert(correct_index, correct_option)
    return {
        "quiz_question": question,
        "options": options,
        "correct_answer": "ABCD"[correct_index],
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
            quiz = build_quiz(title, number)
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
                **quiz,
            })
    return lessons


LESSONS = build_curriculum()
LESSON_BY_ID = {lesson["id"]: lesson for lesson in LESSONS}
PRACTICE_DEPARTMENTS = [
    (1, "IT", "Hyderabad"),
    (2, "HR", "Vijayawada"),
    (3, "Finance", "Bengaluru"),
    (4, "Sales", "Chennai"),
    (5, "Marketing", "Hyderabad"),
    (6, "Operations", "Visakhapatnam"),
]
PRACTICE_EMPLOYEES = [
    (1, "Aditi Sharma", 29, "Female", "IT", "Software Developer", 82000, "2018-05-12", "Hyderabad"),
    (2, "Vikram Iyer", 34, "Male", "Finance", "Financial Analyst", 76000, "2017-08-22", "Bengaluru"),
    (3, "Pooja Reddy", 27, "Female", "HR", "HR Executive", 54000, "2021-02-15", "Vijayawada"),
    (4, "Rahul Nair", 31, "Male", "Sales", "Sales Executive", 69000, "2019-11-04", "Chennai"),
    (5, "Sneha Kulkarni", 26, "Female", "Marketing", "Marketing Specialist", 58000, "2022-01-19", "Hyderabad"),
    (6, "Karthik Rao", 38, "Male", "Operations", "Operations Manager", 94000, "2015-06-30", "Visakhapatnam"),
    (7, "Meera Joshi", 32, "Female", "IT", "Data Analyst", 78000, "2019-07-11", "Hyderabad"),
    (8, "Nikhil Das", 29, "Male", "Finance", "Accountant", 62000, "2020-09-20", "Bengaluru"),
    (9, "Ananya Verma", 33, "Female", "Sales", "Business Development Manager", 88000, "2016-10-14", "Chennai"),
    (10, "Rohan Shah", 41, "Male", "IT", "Project Manager", 115000, "2013-04-05", "Hyderabad"),
    (11, "Divya Babu", 30, "Female", "HR", "Recruitment Specialist", 57000, "2021-03-28", "Vijayawada"),
    (12, "Sanjay Menon", 35, "Male", "Marketing", "Content Strategist", 67000, "2018-12-02", "Hyderabad"),
    (13, "Ishita Gopal", 28, "Female", "Operations", "Logistics Coordinator", 61000, "2022-06-09", "Visakhapatnam"),
    (14, "Arjun Singh", 37, "Male", "Sales", "Regional Sales Lead", 98000, "2014-08-17", "Chennai"),
    (15, "Tejaswini Patil", 31, "Female", "IT", "Business Analyst", 79000, "2017-02-21", "Hyderabad"),
    (16, "Harish Kumar", 36, "Male", "Finance", "Senior Analyst", 87000, "2016-03-12", "Bengaluru"),
    (17, "Nandini Raju", 29, "Female", "Marketing", "Marketing Analyst", 63000, "2020-04-10", "Hyderabad"),
    (18, "Siddharth Rao", 40, "Male", "Operations", "Operations Analyst", 72000, "2015-11-27", "Visakhapatnam"),
    (19, "Manisha Sen", 27, "Female", "HR", "HR Analyst", 51000, "2023-01-08", "Vijayawada"),
    (20, "Deepak Nair", 33, "Male", "IT", "Senior Software Developer", 98000, "2018-09-15", "Hyderabad"),
]
PRACTICE_TASKS = [
    {"title": "Display all employees.", "query": "SELECT * FROM employees;"},
    {"title": "Display employee names and salaries.", "query": "SELECT name, salary FROM employees;"},
    {"title": "Find employees whose salary is greater than 50000.", "query": "SELECT name, department, salary FROM employees WHERE salary > 50000 ORDER BY salary DESC;"},
    {"title": "Find employees working in the IT department.", "query": "SELECT name, job_title FROM employees WHERE department = 'IT';"},
    {"title": "Sort employees by salary from highest to lowest.", "query": "SELECT name, salary FROM employees ORDER BY salary DESC;"},
    {"title": "Find employees from a particular city.", "query": "SELECT name, city FROM employees WHERE city = 'Hyderabad';"},
    {"title": "Count the number of employees.", "query": "SELECT COUNT(*) AS total_employees FROM employees;"},
    {"title": "Find the average salary.", "query": "SELECT AVG(salary) AS average_salary FROM employees;"},
    {"title": "Group employees by department.", "query": "SELECT department, COUNT(*) AS employee_count FROM employees GROUP BY department ORDER BY employee_count DESC;"},
    {"title": "Find departments having more than 3 employees.", "query": "SELECT department, COUNT(*) AS employee_count FROM employees GROUP BY department HAVING COUNT(*) > 3 ORDER BY employee_count DESC;"},
    {"title": "Find the highest salary.", "query": "SELECT MAX(salary) AS highest_salary FROM employees;"},
    {"title": "Find the lowest salary.", "query": "SELECT MIN(salary) AS lowest_salary FROM employees;"},
    {"title": "Use CASE to categorize salaries.", "query": "SELECT name, salary, CASE WHEN salary >= 80000 THEN 'High' WHEN salary >= 60000 THEN 'Mid' ELSE 'Entry' END AS salary_band FROM employees ORDER BY salary DESC;"},
    {"title": "Use GROUP BY and aggregate functions.", "query": "SELECT department, AVG(salary) AS avg_salary, COUNT(*) AS employee_count FROM employees GROUP BY department ORDER BY avg_salary DESC;"},
    {"title": "Show total salary by department.", "query": "SELECT d.department_name, SUM(e.salary) AS total_salary FROM employees e JOIN departments d ON e.department_id = d.department_id GROUP BY d.department_id ORDER BY total_salary DESC;"},
    {"title": "Find the highest-paid employee.", "query": "SELECT first_name, last_name, salary FROM employees ORDER BY salary DESC LIMIT 1;"},
    {"title": "Find the average salary for each department.", "query": "SELECT d.department_name, AVG(e.salary) AS average_salary FROM employees e JOIN departments d ON e.department_id = d.department_id GROUP BY d.department_id ORDER BY average_salary DESC;"},
    {"title": "Use JOIN with the departments table.", "query": "SELECT e.first_name, e.last_name, d.department_name, d.location FROM employees e INNER JOIN departments d ON e.department_id = d.department_id ORDER BY e.last_name, e.first_name;"},
]


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
                current_lesson_id TEXT,
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
        user_columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
        if "current_lesson_id" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN current_lesson_id TEXT")


def get_practice_db():
    if "practice_db" not in g:
        PRACTICE_DATABASE.parent.mkdir(parents=True, exist_ok=True)
        g.practice_db = sqlite3.connect(PRACTICE_DATABASE)
        g.practice_db.row_factory = sqlite3.Row
    return g.practice_db


def initialize_practice_db():
    PRACTICE_DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(PRACTICE_DATABASE) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                department_id INTEGER PRIMARY KEY,
                department_name TEXT NOT NULL UNIQUE,
                location TEXT NOT NULL
            );
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL,
                department TEXT NOT NULL,
                job_title TEXT NOT NULL,
                salary INTEGER NOT NULL,
                hire_date TEXT NOT NULL,
                city TEXT NOT NULL
            );
        """)
        connection.executemany(
            "INSERT OR IGNORE INTO departments (department_id, department_name, location) VALUES (?, ?, ?)",
            PRACTICE_DEPARTMENTS,
        )
        connection.executemany(
            "INSERT OR IGNORE INTO employees (id, name, age, gender, department, job_title, salary, hire_date, city) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            PRACTICE_EMPLOYEES,
        )
        employee_columns = {row[1] for row in connection.execute("PRAGMA table_info(employees)")}
        required_columns = {
            "employee_id": "INTEGER",
            "first_name": "TEXT",
            "last_name": "TEXT",
            "email": "TEXT",
            "department_id": "INTEGER",
            "manager_id": "INTEGER",
        }
        for column, sql_type in required_columns.items():
            if column not in employee_columns:
                connection.execute(f"ALTER TABLE employees ADD COLUMN {column} {sql_type}")
        department_ids = {
            row[1]: row[0]
            for row in connection.execute("SELECT department_id, department_name FROM departments")
        }
        for employee in connection.execute("SELECT id, name, department FROM employees"):
            parts = employee[1].split(maxsplit=1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""
            email = f"{first_name}.{last_name}@sqlmastery.example".strip(".").lower()
            manager_id = None if employee[0] in (6, 10) else (6 if employee[2] == "Operations" else 10 if employee[2] == "IT" else 1)
            connection.execute(
                "UPDATE employees SET employee_id = ?, first_name = ?, last_name = ?, email = ?, department_id = ?, manager_id = ? WHERE id = ?",
                (employee[0], first_name, last_name, email, department_ids.get(employee[2]), manager_id, employee[0]),
            )
        connection.commit()


_DATABASES_INITIALIZED = False
_DATABASE_INITIALIZATION_LOCK = threading.Lock()


def initialize_databases():
    global _DATABASES_INITIALIZED
    if _DATABASES_INITIALIZED:
        return
    with _DATABASE_INITIALIZATION_LOCK:
        if _DATABASES_INITIALIZED:
            return
        initialize_db()
        initialize_practice_db()
        _DATABASES_INITIALIZED = True


@app.teardown_appcontext
def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()
    practice_connection = g.pop("practice_db", None)
    if practice_connection is not None:
        practice_connection.close()


@app.context_processor
def csrf_context():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return {"csrf_token": session["csrf_token"]}


@app.before_request
def prepare_runtime():
    if request.endpoint == "health":
        return None
    if IS_VERCEL and not CONFIGURED_SECRET_KEY:
        app.logger.error("SECRET_KEY must be configured for authenticated Vercel routes.")
        return jsonify(success=False, error="Server configuration missing: set SECRET_KEY in Vercel environment variables."), 503
    try:
        initialize_databases()
    except (OSError, sqlite3.Error):
        app.logger.exception("Database initialization failed.")
        if request.path.startswith("/api/"):
            return jsonify(success=False, error="Unable to initialize application storage."), 500
        abort(500, "Unable to initialize application storage. Check the server logs.")


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
        user = get_db().execute("SELECT 1 FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        if user is None:
            session.clear()
            flash("Your session expired. Please sign in again.", "error")
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
    last_activity = connection.execute(
        "SELECT MAX(activity_date) AS last_activity FROM activity_dates WHERE user_id = ?",
        (user_id,),
    ).fetchone()["last_activity"]
    enriched = [{**lesson, "completed": lesson["id"] in completed} for lesson in LESSONS]
    current_lesson = next(
        (lesson for lesson in enriched if lesson["id"] == user["current_lesson_id"] and not lesson["completed"]),
        None,
    )
    next_lesson = current_lesson or next((lesson for lesson in enriched if not lesson["completed"]), enriched[-1])
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
        "last_activity": last_activity,
        "next_lesson": next_lesson,
    }


def get_practice_snapshot():
    connection = get_practice_db()
    employees = [dict(row) for row in connection.execute("SELECT * FROM employees ORDER BY id").fetchall()]
    departments = [dict(row) for row in connection.execute("SELECT * FROM departments ORDER BY department_id").fetchall()]
    return {"employees": employees, "departments": departments}


@app.route("/")
def home():
    return redirect(url_for("dashboard") if signed_in() else url_for("login"))


@app.get("/health")
@app.get("/api/health")
def health():
    if request.path == "/health":
        return jsonify(status="ok")
    return jsonify(status="success", message="SQL Mastery API is running")


@app.route("/login.html", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
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
            session.permanent = bool(request.form.get("remember"))
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
    return redirect("/login")


@app.get("/dashboard.html")
@login_required
def dashboard():
    return render_template("dashboard.html", **dashboard_data(session["user_id"]))


@app.get("/progress.html")
@app.get("/progress")
@login_required
def progress():
    return render_template("progress.html", **dashboard_data(session["user_id"]))


@app.get("/practice")
@login_required
def practice():
    return redirect(f"{url_for('lesson', id='select')}#practice")


@app.get("/lesson.html")
@login_required
def lesson():
    lesson_item = LESSON_BY_ID.get(request.args.get("id", ""))
    if lesson_item is None:
        abort(404)
    connection = get_db()
    connection.execute("UPDATE users SET current_lesson_id = ? WHERE id = ?", (lesson_item["id"], session["user_id"]))
    connection.commit()
    enriched = dashboard_data(session["user_id"])
    item = {**lesson_item, "completed": lesson_item["id"] in {x["id"] for x in enriched["lessons"] if x["completed"]}}
    next_item = next((x for x in LESSONS if x["number"] > lesson_item["number"]), None)
    practice_snapshot = get_practice_snapshot()
    return render_template(
        "lesson.html",
        lesson=item,
        next_lesson=next_item,
        username=session.get("username"),
        practice_snapshot=practice_snapshot,
        practice_tasks=PRACTICE_TASKS,
    )


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
    if lesson_item is None or not isinstance(answer, str) or answer not in "ABCD":
        return jsonify(error="Choose one of the quiz answers."), 400
    correct = answer == lesson_item["correct_answer"]
    correct_option = lesson_item["options"][ord(lesson_item["correct_answer"]) - ord("A")]
    score = 100 if correct else 0
    connection = get_db()
    connection.execute("INSERT INTO quiz_attempts (user_id, lesson_id, score) VALUES (?, ?, ?)", (session["user_id"], lesson_item["id"], score))
    record_activity(session["user_id"])
    connection.commit()
    return jsonify(ok=True, correct=correct, score=score, correct_answer=correct_option)


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
        with sqlite3.connect(PRACTICE_DATABASE) as practice_connection:
            practice_connection.row_factory = sqlite3.Row
            practice_connection.execute("PRAGMA query_only = ON")
            cursor = practice_connection.execute(normalized)
            columns = [item[0] for item in cursor.description or []]
            rows = [
                [value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value for value in row]
                for row in cursor.fetchmany(100)
            ]
    except sqlite3.Error as error:
        message = "SQL syntax error. Check your query and try again." if "syntax" in str(error).lower() or "incomplete" in str(error).lower() else "Query error. Check your table names, column names, and SQL, then try again."
        return jsonify(error=message), 400
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


@app.errorhandler(Exception)
def unhandled_error(error):
    if isinstance(error, HTTPException):
        return error
    app.logger.error(
        "Unhandled error during %s %s",
        request.method,
        request.path,
        exc_info=(type(error), error, error.__traceback__),
    )
    if request.path.startswith("/api/") or request.is_json:
        return jsonify(success=False, error="Unable to process the request."), 500
    return render_template(
        "error.html",
        code=500,
        message="The server couldn't complete this request. The error has been logged.",
    ), 500


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1", port=int(os.environ.get("PORT", "5000")))
