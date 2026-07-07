# -*- coding: utf-8 -*-
import os
import click
from flask import Flask, render_template
from flask_login import current_user

from config import config_by_name
from app.extensions import db, migrate, login_manager, csrf, limiter


def create_app(config_name=None):
    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_by_name[config_name])

    os.makedirs(os.path.join(app.root_path, "..", "instance"), exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # --- Blueprints ---
    from app.auth.routes import bp as auth_bp
    from app.kampist.routes import bp as kampist_bp
    from app.staff.routes import bp as staff_bp
    from app.admin.routes import bp as admin_bp
    from app.superuser.routes import bp as superuser_bp
    from app.chat.routes import bp as chat_bp
    from app.api.routes import bp as api_bp

    app.register_blueprint(auth_bp, url_prefix="")
    app.register_blueprint(kampist_bp, url_prefix="/kampist")
    app.register_blueprint(staff_bp, url_prefix="/staf")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(chat_bp, url_prefix="/chat")
    app.register_blueprint(api_bp, url_prefix="/api")
    # Rruga e superuser-it është e fshehur pas një "slug" të konfigurueshëm dhe
    # nuk lidhet askund në navigim/UI publike.
    app.register_blueprint(superuser_bp, url_prefix=f"/{app.config['SUPERUSER_PANEL_SLUG']}")

    # --- Faqet publike / PWA ---
    @app.route("/")
    def home():
        if current_user.is_authenticated:
            from app.auth.routes import redirect_for_role
            return redirect_for_role(current_user)
        return render_template("public_home.html")

    @app.route("/manifest.json")
    def manifest():
        return app.send_static_file("manifest.json")

    @app.route("/sw.js")
    def service_worker():
        resp = app.send_static_file("sw.js")
        # Service worker duhet të shërbehet nga rrënja me scope të gjerë
        resp.headers["Service-Worker-Allowed"] = "/"
        resp.headers["Content-Type"] = "application/javascript"
        return resp

    @app.route("/offline")
    def offline():
        return render_template("offline.html")

    # --- Context processors ---
    @app.context_processor
    def inject_camp_info():
        return {
            "CAMP_NAME": app.config["CAMP_NAME"],
            "CAMP_SLOGAN": app.config["CAMP_SLOGAN"],
            "VAPID_PUBLIC_KEY": app.config.get("VAPID_PUBLIC_KEY", ""),
        }

    # --- Error handlers ---
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def ratelimited(e):
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    # --- Security headers baze (mbrojtje shtesë përveç HTTPS te Render) ---
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self';",
        )
        return response

    register_cli_commands(app)
    return app


def register_cli_commands(app):
    @app.cli.command("seed-superuser")
    @click.argument("email")
    @click.argument("password")
    def seed_superuser(email, password):
        """Krijon (ose përditëson) llogarinë e fshehur të superuser-it.

        Përdorim: flask seed-superuser "ti@example.com" "fjalekalim-shume-i-forte"
        """
        from app.models import User, RoleEnum
        from app.extensions import db

        user = User.query.filter_by(email=email.lower().strip()).first()
        if user:
            user.set_password(password)
            user.is_superuser = True
            user.is_active_account = True
            click.echo(f"U përditësua llogaria ekzistuese si superuser: {email}")
        else:
            user = User(email=email.lower().strip(), role=RoleEnum.ADMIN, is_superuser=True)
            user.set_password(password)
            db.session.add(user)
            click.echo(f"U krijua llogaria e re superuser: {email}")
        db.session.commit()
        click.echo(
            "Kujdes: kjo llogari nuk shfaqet në asnjë listë/UI publike. "
            f"Hyr te /{app.config['SUPERUSER_PANEL_SLUG']}/ pasi të kyçesh normalisht te /kycu."
        )

    @app.cli.command("seed-demo-data")
    def seed_demo_data():
        """Mbush bazën e zhvillimit me të dhëna shembull (grupe, dhoma, admin)."""
        from app.extensions import db
        from app.models import User, RoleEnum, Group, Building, Room, ChatRoom, ChatRoomType

        if not User.query.filter_by(role=RoleEnum.ADMIN, is_superuser=False).first():
            admin = User(email="admin@eaglesofhope.local", role=RoleEnum.ADMIN)
            admin.set_password("NderroKetePassword123!")
            db.session.add(admin)
            click.echo("Admin demo: admin@eaglesofhope.local / NderroKetePassword123!")

        if not Group.query.first():
            for name, color in [("Shqiponjat e Verdha", "#F0A93A"),
                                 ("Shqiponjat Blu", "#4A90C4"),
                                 ("Shqiponjat e Gjelbra", "#3E7C5A")]:
                g = Group(name=name, color=color)
                db.session.add(g)
                db.session.flush()
                db.session.add(ChatRoom(name=f"Chat - {name}", room_type=ChatRoomType.GROUP, group_id=g.id))
            db.session.add(ChatRoom(name="Chat i Stafit", room_type=ChatRoomType.STAFF))

        if not Building.query.first():
            b1 = Building(name="Ndërtesa A")
            db.session.add(b1)
            db.session.flush()
            for n in ["A101", "A102", "A103"]:
                db.session.add(Room(building_id=b1.id, number=n, capacity=4))

        db.session.commit()
        click.echo("Të dhënat demo u shtuan me sukses.")
