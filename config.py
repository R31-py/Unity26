import os
from datetime import timedelta

from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))


class Config:
    # --- Core ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    # --- Database ---
    # In production (Vercel) this MUST be set to a hosted Postgres URL
    # (Neon, Supabase, or Vercel Postgres — spec §2.3). Providers hand out
    # "postgres://" or "postgresql://" URLs; SQLAlchemy needs the dialect
    # to explicitly say "+psycopg" to use psycopg v3 (not the old,
    # incompatible-with-newer-Python psycopg2), so that gets patched in
    # here regardless of which prefix the provider gave you.
    # For local development we default to a SQLite file so the app runs
    # out of the box with zero external setup.
    _db_url = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'instance', 'camp.db')}"
    )
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif _db_url.startswith("postgresql://") and "+psycopg" not in _db_url:
        _db_url = _db_url.replace("postgresql://", "postgresql+psycopg://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Sessions / cookies ---
    # Signed cookies only (Flask's default session backend) — no server-side
    # session storage, since Vercel functions are stateless (see spec §5).
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Set SESSION_COOKIE_SECURE = True once served over HTTPS (Vercel deploy).
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"

    # --- CSRF (Flask-WTF) ---
    WTF_CSRF_ENABLED = True

    # --- Web Push (VAPID) — generate with generate_vapid_keys.py.
    # Blank means push is simply off: the frontend disables the
    # "Enable notifications" button instead of erroring. ---
    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
    VAPID_CLAIM_EMAIL = os.environ.get("VAPID_CLAIM_EMAIL", "mailto:admin@example.com")

    # --- Admin seed (used by seed.py) ---
    SEED_ADMIN_USERNAME = os.environ.get("SEED_ADMIN_USERNAME", "admin")
    SEED_ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "admin123")

    # --- Manual reminder-check auth (Stage 8) ---
    # /api/cron/check-reminders is now just a manual/debug trigger — the
    # real checking runs via before_request (app/reminders.py) piggybacked
    # on normal traffic, not a Vercel Cron job. If you set this to a long
    # random string (as a Vercel/local env var), the route requires
    # `Authorization: Bearer <value>` to be hit. Left blank, it runs
    # unauthenticated — fine for local dev only.
    CRON_SECRET = os.environ.get("CRON_SECRET", "")
