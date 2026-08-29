"""Configuration for Humisense AI Operations Workforce."""
import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "humisense-expo-demo-key")

    # Database
    DB_HOST = os.getenv("DB_HOST", "").strip()
    DB_PORT = int(os.getenv("DB_PORT", "3306") or 3306)
    DB_NAME = os.getenv("DB_NAME", "humisense")
    DB_USER = os.getenv("DB_USER", "")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    # AI Gateway
    AI_PROVIDER = os.getenv("AI_PROVIDER", "mock").strip().lower() or "mock"
    AI_BASE_URL = os.getenv("AI_BASE_URL", "").strip()
    AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
    AI_MODEL = os.getenv("AI_MODEL", "").strip()

    DEMO_MODE = os.getenv("DEMO_MODE", "true").strip().lower() in ("1", "true", "yes")

    # Reconciliation
    DATE_TOLERANCE_DAYS = int(os.getenv("DATE_TOLERANCE_DAYS", "1") or 1)

    # Paths
    DEMO_DIR = os.path.join(BASE_DIR, "demo")
    STATIC_DIR = os.path.join(BASE_DIR, "static")

    # Whether MySQL is available
    @property
    def USE_MYSQL(self):
        return bool(self.DB_HOST)

    @property
    def SQLITE_PATH(self):
        return os.path.join(BASE_DIR, "humisense.db")


config = Config()
