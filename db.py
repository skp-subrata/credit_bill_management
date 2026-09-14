import sqlite3
import os
from pathlib import Path
from werkzeug.security import generate_password_hash

DATABASE = Path(os.getenv("CREDIT_BILL_DB", Path(__file__).parent / "credit_bill.db"))

def get_db():
    """Open a row-producing SQLite connection with foreign keys enabled."""
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

def init_db():
    """Initialize database tables and seed default admin user."""
    with get_db() as conn:
        # Users table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                email TEXT DEFAULT '',
                role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Credit Cards table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS credit_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                card_name TEXT NOT NULL,
                bank_name TEXT NOT NULL,
                card_number_last4 TEXT NOT NULL,
                credit_limit REAL NOT NULL,
                billing_cycle_day INTEGER NOT NULL,
                due_date_day INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Bills table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER NOT NULL REFERENCES credit_cards(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                bill_amount REAL NOT NULL,
                minimum_due REAL DEFAULT 0,
                due_date TEXT NOT NULL,
                billing_date TEXT NOT NULL,
                status TEXT DEFAULT 'unpaid' CHECK (status IN ('unpaid', 'paid', 'partially_paid')),
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Payments table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bill_id INTEGER NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                amount_paid REAL NOT NULL,
                payment_date TEXT DEFAULT CURRENT_TIMESTAMP,
                payment_method TEXT DEFAULT 'Bank Transfer',
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Seed initial admin user if not exists
        if not conn.execute("SELECT 1 FROM users WHERE username = ?", ("admin",)).fetchone():
            conn.execute(
                "INSERT INTO users (username, password_hash, full_name, email, role) VALUES (?, ?, ?, ?, ?)",
                ("admin", generate_password_hash("admin123"), "System Administrator", "admin@example.com", "admin")
            )
            conn.commit()

