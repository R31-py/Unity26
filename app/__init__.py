import os

from flask import Flask, render_template, current_app, request

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

    # --- template context ---
    _asset_hash_cache = {}

    @app.context_processor
    def inject_asset_url():
        """`asset_url('css/style.css')` — like `url_for('static', ...)` but
        appends `?v=<hash of the file's contents>`. Static files are served
        with a normal long-lived Cache-Control by default (see the
        no-cache hook below, which deliberately skips /static/), which is
        good for performance but means a CSS/JS fix can sit invisible in
        everyone's browser cache under the old URL until it expires. Since
        the query string changes whenever the file's contents change, the
        browser sees a new URL and re-fetches immediately — no manual
        cache-busting or hard-refresh needed after a deploy."""
        import hashlib
        from flask import url_for as _url_for

        def asset_url(filename):
            if filename not in _asset_hash_cache:
                path = os.path.join(app.static_folder, filename)
                try:
                    with open(path, "rb") as f:
                        digest = hashlib.md5(f.read()).hexdigest()[:8]
                except OSError:
                    digest = "0"
                _asset_hash_cache[filename] = digest
            return _url_for("static", filename=filename) + "?v=" + _asset_hash_cache[filename]

        return {"asset_url": asset_url}

    # --- prevent stale authenticated pages from surviving logout via the
    # browser's back/forward cache ---
    # Without an explicit no-store, hitting Back after logging out (or
    # after logging in as someone else on a shared device) can redisplay
    # the previous page straight from the browser's cache/bfcache, without
    # a new request ever reaching the server's @login_required checks —
    # it just *looks* like you're still logged in (or logged in as the
    # other account) until you interact with the page and it re-fetches.
    @app.after_request
    def _no_cache_for_dynamic_pages(response):
        if request.path.startswith("/static/"):
            return response
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        return response

    # --- error handlers ---
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    return app
