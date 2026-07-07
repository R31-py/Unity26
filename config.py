"""
Konfigurimi i aplikacionit "Youth Summer Camp: Unity".

Të gjitha vlerat sensitive vijnë nga variablat e mjedisit (.env) - asnjëherë
mos i vendos çelësat direkt në kod (kërkesë sigurie).
"""
import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


def _bool(env_val, default=False):
    if env_val is None:
        return default
    return env_val.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    # --- Bazë ---
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        # Vetëm për zhvillim lokal - në prodhim DUHET vendosur SECRET_KEY.
        SECRET_KEY = "dev-only-insecure-key-change-me"

    CAMP_NAME = "Youth Summer Camp: Unity"
    CAMP_SLOGAN = "Together as one"

    # --- Bazë të dhënash ---
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'instance', 'camp_dev.db')}"
    )
    # Render/Heroku japin URL me prefix postgres:// ose postgresql:// (pa drejtues).
    # Përdorim psycopg (v3), jo psycopg2, sepse psycopg2 s'ka build të përputhshëm
    # me versionet e reja të Python (p.sh. 3.13/3.14) te platformat si Render.
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://", "postgresql+psycopg://", 1
        )
    elif SQLALCHEMY_DATABASE_URI.startswith("postgresql://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgresql://", "postgresql+psycopg://", 1
        )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- Cookies & sesione (siguri) ---
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = _bool(os.environ.get("SESSION_COOKIE_SECURE"), True)
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = _bool(os.environ.get("SESSION_COOKIE_SECURE"), True)

    # --- CSRF (Flask-WTF) ---
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    # --- Ngarkim skedarësh ---
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB
    UPLOAD_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
    UPLOAD_FOLDER = os.path.join(basedir, "app", "static", "uploads")

    # --- Rate limiting ---
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

    # --- Web Push (VAPID) ---
    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
    VAPID_CLAIM_EMAIL = os.environ.get("VAPID_CLAIM_EMAIL", "mailto:admin@example.com")

    # --- Superuser i fshehur ---
    # Rruga e panelit superuser NUK duhet të jetë e parashikueshme (ndrysho në prodhim!).
    SUPERUSER_PANEL_SLUG = os.environ.get("SUPERUSER_PANEL_SLUG", "system-x9k2-portal")


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}