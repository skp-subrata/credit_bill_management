import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db, init_db

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "credit-bill-secret-key-2026")

# Initialize database tables
init_db()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in as Administrator.", "error")
            return redirect(url_for("admin_login"))
        if session.get("role") != "admin":
            flash("Access denied. Administrator privileges required.", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function


@app.context_processor
def inject_user():
    return dict(
        user=session.get("username"),
        role=session.get("role"),
        full_name=session.get("full_name")
    )


@app.route("/")
@login_required
def index():
    user_id = session["user_id"]
    with get_db() as conn:
        cards_count = conn.execute("SELECT COUNT(*) as cnt FROM credit_cards WHERE user_id = ?", (user_id,)).fetchone()["cnt"]
        total_limit = conn.execute("SELECT COALESCE(SUM(credit_limit), 0) as total FROM credit_cards WHERE user_id = ?", (user_id,)).fetchone()["total"]
        
        unpaid_row = conn.execute("""
            SELECT COUNT(*) as count, COALESCE(SUM(bill_amount), 0) as total 
            FROM bills WHERE user_id = ? AND status != 'paid'
        """, (user_id,)).fetchone()
        
        bills = conn.execute("""
            SELECT b.*, c.card_name, c.bank_name, c.card_number_last4
            FROM bills b
            JOIN credit_cards c ON b.card_id = c.id
            WHERE b.user_id = ?
            ORDER BY b.due_date ASC LIMIT 10
        """, (user_id,)).fetchall()

    metrics = {
        "total_cards": cards_count,
        "total_limit": total_limit,
        "unpaid_count": unpaid_row["count"],
        "total_unpaid": unpaid_row["total"]
    }
    return render_template("index.html", metrics=metrics, bills=bills)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]
            flash(f"Welcome back, {user['full_name']}!", "success")
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("index"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            if user["role"] != "admin":
                flash("Access denied. Account is not registered as an administrator.", "error")
                return render_template("admin_login.html")
            
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]
            flash(f"Administrator access granted. Welcome, {user['full_name']}!", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Invalid administrator credentials.", "error")

    return render_template("admin_login.html")


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    with get_db() as conn:
        total_users = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()["cnt"]
        total_cards = conn.execute("SELECT COUNT(*) as cnt FROM credit_cards").fetchone()["cnt"]
        total_bills = conn.execute("SELECT COUNT(*) as cnt FROM bills").fetchone()["cnt"]
        total_paid_amount = conn.execute("SELECT COALESCE(SUM(amount_paid), 0) as total FROM payments").fetchone()["total"]

        users = conn.execute("SELECT id, username, full_name, email, role, created_at FROM users ORDER BY created_at DESC").fetchall()
        
        all_bills = conn.execute("""
            SELECT b.*, c.card_name, c.bank_name, c.card_number_last4, u.username, u.full_name as user_fullname
            FROM bills b
            JOIN credit_cards c ON b.card_id = c.id
            JOIN users u ON b.user_id = u.id
            ORDER BY b.due_date DESC
        """, ()).fetchall()

    admin_metrics = {
        "total_users": total_users,
        "total_cards": total_cards,
        "total_bills": total_bills,
        "total_paid_amount": total_paid_amount
    }

    return render_template("admin_dashboard.html", admin_metrics=admin_metrics, users=users, all_bills=all_bills)


@app.route("/admin/users/<int:user_id>/toggle-role", methods=["POST"])
@admin_required
def admin_toggle_role(user_id):
    if user_id == session.get("user_id"):
        flash("You cannot alter your own admin role.", "error")
        return redirect(url_for("admin_dashboard"))

    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user:
            new_role = "user" if user["role"] == "admin" else "admin"
            conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
            conn.commit()
            flash(f"User @{user['username']} role updated to {new_role.upper()}.", "success")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    if user_id == session.get("user_id"):
        flash("You cannot delete your own admin account.", "error")
        return redirect(url_for("admin_dashboard"))

    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            flash(f"User @{user['username']} deleted successfully.", "success")

    return redirect(url_for("admin_dashboard"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not username or not password or not full_name:
            flash("Please fill in all required fields.", "error")
            return render_template("register.html")

        password_hash = generate_password_hash(password)

        try:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO users (username, password_hash, full_name, email, role) VALUES (?, ?, ?, ?, 'user')",
                    (username, password_hash, full_name, email)
                )
                conn.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            flash("Username is already taken. Please choose another.", "error")

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/cards")
@login_required
def cards():
    user_id = session["user_id"]
    with get_db() as conn:
        cards_list = conn.execute("SELECT * FROM credit_cards WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    return render_template("cards.html", cards=cards_list)


@app.route("/cards/add", methods=["POST"])
@login_required
def add_card():
    user_id = session["user_id"]
    card_name = request.form.get("card_name", "").strip()
    bank_name = request.form.get("bank_name", "").strip()
    card_number_last4 = request.form.get("card_number_last4", "").strip()
    credit_limit = float(request.form.get("credit_limit", 0))
    billing_cycle_day = int(request.form.get("billing_cycle_day", 1))
    due_date_day = int(request.form.get("due_date_day", 1))

    with get_db() as conn:
        conn.execute("""
            INSERT INTO credit_cards (user_id, card_name, bank_name, card_number_last4, credit_limit, billing_cycle_day, due_date_day)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, card_name, bank_name, card_number_last4, credit_limit, billing_cycle_day, due_date_day))
        conn.commit()

    flash(f"Credit card '{card_name}' added successfully!", "success")
    return redirect(url_for("cards"))


@app.route("/bills")
@login_required
def bills():
    user_id = session["user_id"]
    with get_db() as conn:
        cards_list = conn.execute("SELECT * FROM credit_cards WHERE user_id = ?", (user_id,)).fetchall()
        bills_list = conn.execute("""
            SELECT b.*, c.card_name, c.bank_name, c.card_number_last4
            FROM bills b
            JOIN credit_cards c ON b.card_id = c.id
            WHERE b.user_id = ?
            ORDER BY b.due_date DESC
        """, (user_id,)).fetchall()

    return render_template("bills.html", cards=cards_list, bills=bills_list)


@app.route("/bills/add", methods=["POST"])
@login_required
def add_bill():
    user_id = session["user_id"]
    card_id = int(request.form.get("card_id"))
    bill_amount = float(request.form.get("bill_amount", 0))
    minimum_due = float(request.form.get("minimum_due", 0))
    billing_date = request.form.get("billing_date")
    due_date = request.form.get("due_date")
    notes = request.form.get("notes", "").strip()

    with get_db() as conn:
        conn.execute("""
            INSERT INTO bills (card_id, user_id, bill_amount, minimum_due, billing_date, due_date, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, 'unpaid', ?)
        """, (card_id, user_id, bill_amount, minimum_due, billing_date, due_date, notes))
        conn.commit()

    flash("New bill statement recorded successfully!", "success")
    return redirect(url_for("bills"))


@app.route("/bills/<int:bill_id>/pay", methods=["POST"])
@login_required
def pay_bill(bill_id):
    user_id = session["user_id"]
    with get_db() as conn:
        bill = conn.execute("SELECT * FROM bills WHERE id = ? AND user_id = ?", (bill_id, user_id)).fetchone()
        if bill:
            conn.execute("UPDATE bills SET status = 'paid' WHERE id = ?", (bill_id,))
            conn.execute("""
                INSERT INTO payments (bill_id, user_id, amount_paid, payment_method, notes)
                VALUES (?, ?, ?, 'Online Payment', 'Paid in full via web app')
            """, (bill_id, user_id, bill["bill_amount"]))
            conn.commit()
            flash("Bill status updated to Paid!", "success")
        else:
            flash("Bill statement not found.", "error")

    return redirect(request.referrer or url_for("bills"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)

