"""
Creates all tables and seeds the single Admin account.

Admins are never self-registered (spec §1) — this script is the only way
the first Admin account comes into existence. Safe to re-run: it won't
duplicate the Admin if one already exists.

Usage:
    python seed.py

Reads SEED_ADMIN_USERNAME / SEED_ADMIN_PASSWORD from the environment
(defaults: admin / admin123 — change these before deploying anywhere real).
"""
from app import create_app
from app.extensions import db
from app.models import User, Role

app = create_app()

with app.app_context():
    db.create_all()

    existing = User.query.filter_by(role=Role.ADMIN.value).first()
    if existing:
        print(f"Admin already exists: {existing.username!r} — nothing to do.")
    else:
        username = app.config["SEED_ADMIN_USERNAME"]
        password = app.config["SEED_ADMIN_PASSWORD"]
        admin = User(
            name="Camp",
            surname="Admin",
            role=Role.ADMIN.value,
            username=username,
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"Seeded Admin account -> username: {username!r}  password: {password!r}")
        print("Change SEED_ADMIN_PASSWORD / log in and rotate this before real use.")
