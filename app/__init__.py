import os

from flask import Flask, render_template, current_app

from config import Config
from app.extensions import db, login_manager, csrf


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # Make sure instance/ exists (holds the local SQLite file in dev)
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    # --- init extensions ---
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # --- user loader (Flask-Login) ---
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # --- blueprints ---
    from app.auth.routes import auth_bp
    from app.admin.routes import admin_bp
    from app.staff.routes import staff_bp
    from app.user.routes import user_bp
    from app.main.routes import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(user_bp)

    from app.live import live_bp

    app.register_blueprint(live_bp)

    # --- reminder checks, piggybacked on traffic instead of Vercel Cron ---
    # (Hobby plan only allows daily crons — see app/reminders.py docstring.)
    @app.before_request
    def _maybe_run_reminder_check():
        from app.reminders import maybe_check_reminders

        try:
            maybe_check_reminders()
        except Exception:
            # Never let a reminder-check hiccup break the actual page/
            # request the user is waiting on.
            current_app.logger.exception("maybe_check_reminders() failed")

    # --- template context ---
    @app.context_processor
    def inject_pending_requests_count():
        """Powers the small badge on the Admin sidebar's Requests link.
        Cheap enough to run on every request at this app's scale; only
        queries when an Admin is actually logged in."""
        from flask_login import current_user as _current_user

        if _current_user.is_authenticated and _current_user.is_admin:
            from app.models import ChangeRequest, RequestStatus

            count = ChangeRequest.query.filter_by(status=RequestStatus.PENDING).count()
            return {"pending_requests_count": count}
        return {"pending_requests_count": 0}

    # --- error handlers ---
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    return app
