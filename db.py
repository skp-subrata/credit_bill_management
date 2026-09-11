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

        # Seed initial admin user if not exists
        if not conn.execute("SELECT 1 FROM users WHERE username = ?", ("admin",)).fetchone():
            conn.execute(
                "INSERT INTO users (username, password_hash, full_name, email, role) VALUES (?, ?, ?, ?, ?)",
                ("admin", generate_password_hash("admin123"), "System Administrator", "admin@example.com", "admin")
            )
            conn.commit()
