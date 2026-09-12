import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATABASE_PATH = BASE_DIR / "hospital_credit_bill.db"

class Config:
    APP_VERSION = "1.0.0"
    SECRET_KEY = os.getenv("SECRET_KEY", "hospital-credit-billing-secret-key-2026-secure")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ITEMS_PER_PAGE = 20


