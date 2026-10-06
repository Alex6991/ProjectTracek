from flask import Flask, render_template, request, redirect, url_for, Response
import csv
import io
import sqlite3
from datetime import datetime


app = Flask(__name__)
DB_NAME = "expenses.db"


# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            comment TEXT,
            date TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'expense'
        )
    """)
    try:
        cursor.execute("ALTER TABLE expenses ADD COLUMN type TEXT NOT NULL DEFAULT 'expense'")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# --- ГЛАВНАЯ ---
@app.route("/")
def index():
    selected_month = request.args.get("month", "")
    conn = get_db()

    if selected_month:
        expenses = conn.execute(
            "SELECT * FROM expenses WHERE substr(date, 1, 7) = ? ORDER BY date DESC",
            (selected_month,)
        ).fetchall()
    else:
        expenses = conn.execute("SELECT * FROM expenses ORDER BY date DESC").fetchall()

    months = conn.execute(
        "SELECT DISTINCT substr(date, 1, 7) AS month FROM expenses ORDER BY month DESC"
    ).fetchall()
    conn.close()

    total_income = sum(e["amount"] for e in expenses if e["type"] == "income")
    total_expense = sum(e["amount"] for e in expenses if e["type"] == "expense")
    balance = total_income - total_expense

    # --- Категории отдельно для расходов и доходов ---
    expense_categories = {}
    income_categories = {}
    for e in expenses:
        if e["type"] == "expense":
            expense_categories[e["category"]] = expense_categories.get(e["category"], 0) + e["amount"]
        else:
            income_categories[e["category"]] = income_categories.get(e["category"], 0) + e["amount"]

    return render_template(
        "index.html",
        expenses=expenses,
        total_income=total_income,
        total_expense=total_expense,
        balance=balance,
        expense_categories=expense_categories,
        income_categories=income_categories,
        months=months,
        selected_month=selected_month,
        expense_labels=list(expense_categories.keys()),
        expense_values=[round(v, 2) for v in expense_categories.values()],
        income_labels=list(income_categories.keys()),
        income_values=[round(v, 2) for v in income_categories.values()],
    )
@app.route("/export")
def export_csv():
    """Экспорт расходов и доходов в CSV-файл."""
    selected_month = request.args.get("month", "")
    conn = get_db()

    if selected_month:
        expenses = conn.execute(
            "SELECT * FROM expenses WHERE substr(date, 1, 7) = ? ORDER BY date DESC",
            (selected_month,)
        ).fetchall()
    else:
        expenses = conn.execute("SELECT * FROM expenses ORDER BY date DESC").fetchall()

    conn.close()

    # Формируем CSV в памяти
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')  # ; — чтобы Excel понял русский разделитель

    # Заголовки
    writer.writerow(["Дата", "Тип", "Категория", "Сумма", "Комментарий"])

    # Данные
    for e in expenses:
        type_label = "Доход" if e["type"] == "income" else "Расход"
        writer.writerow([
            e["date"],
            type_label,
            e["category"],
            f"{e['amount']:.2f}",
            e["comment"] or "",
        ])

    # BOM (\ufeff) — чтобы Excel корректно открыл русские буквы
    csv_data = "\ufeff" + output.getvalue()

    # Имя файла
    filename = f"budget_{selected_month}.csv" if selected_month else "budget_all.csv"

    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# --- ДОБАВЛЕНИЕ / РЕДАКТИРОВАНИЕ ---
@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        amount = request.form.get("amount")
        category = request.form.get("category")
        comment = request.form.get("comment")
        date = request.form.get("date") or datetime.now().strftime("%Y-%m-%d")
        type_ = request.form.get("type", "expense")

        if not amount or not category:
            return "Ошибка: сумма и категория обязательны", 400

        conn = get_db()
        conn.execute(
            "INSERT INTO expenses (amount, category, comment, date, type) VALUES (?, ?, ?, ?, ?)",
            (float(amount), category, comment, date, type_)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("index"))

    return render_template("add.html", expense=None)


@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
def edit(expense_id):
    conn = get_db()
    expense = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()

    if expense is None:
        conn.close()
        return "Запись не найдена", 404

    if request.method == "POST":
        amount = request.form.get("amount")
        category = request.form.get("category")
        comment = request.form.get("comment")
        date = request.form.get("date") or datetime.now().strftime("%Y-%m-%d")
        type_ = request.form.get("type", "expense")

        conn.execute(
            "UPDATE expenses SET amount = ?, category = ?, comment = ?, date = ?, type = ? WHERE id = ?",
            (float(amount), category, comment, date, type_, expense_id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("index"))

    conn.close()
    return render_template("add.html", expense=expense)


@app.route("/delete/<int:expense_id>")
def delete(expense_id):
    conn = get_db()
    conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)