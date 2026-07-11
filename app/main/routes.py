from flask import Blueprint, redirect, url_for, send_from_directory, current_app, request, jsonify, abort
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Role, PushSubscription

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    if current_user.role == Role.ADMIN.value:
        return redirect(url_for("admin.dashboard"))
    if current_user.role == Role.STAFF.value:
        return redirect(url_for("staff.dashboard"))
    return redirect(url_for("user.dashboard"))


# ---------------------------------------------------------------------------
# PWA: service worker served from the root so its scope covers the whole
# app ("/"), not just /static/ (spec §7, Stage 7). manifest.json doesn't
# need root scope, so it's linked straight from /static/ in base.html.
# ---------------------------------------------------------------------------
@main_bp.route("/sw.js")
def service_worker():
    response = send_from_directory(
        current_app.static_folder, "sw.js", mimetype="application/javascript"
    )
    # Belt-and-suspenders: explicitly confirms root scope is allowed even
    # though serving from "/" already implies it.
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


# ---------------------------------------------------------------------------
# Web Push subscription storage (spec §2.2.3 push_subscriptions table).
# Any logged-in role can subscribe — Users and Staff see the Messages tab
# these pushes are for; Admins can too, mostly useful for testing.
# ---------------------------------------------------------------------------
@main_bp.route("/push/subscribe", methods=["POST"])
@login_required
def push_subscribe():
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")
    keys = data.get("keys") or {}
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")

    if not endpoint or not p256dh or not auth:
        return jsonify({"error": "Malformed subscription."}), 400

    existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if existing:
        existing.user_id = current_user.user_id
        existing.p256dh = p256dh
        existing.auth = auth
    else:
        db.session.add(
            PushSubscription(
                user_id=current_user.user_id,
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth,
            )
        )
    db.session.commit()
    return jsonify({"status": "subscribed"})


@main_bp.route("/push/unsubscribe", methods=["POST"])
@login_required
def push_unsubscribe():
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")
    if endpoint:
        PushSubscription.query.filter_by(
            endpoint=endpoint, user_id=current_user.user_id
        ).delete()
        db.session.commit()
    return jsonify({"status": "unsubscribed"})


# ---------------------------------------------------------------------------
# Event reminders (spec §4, §5, §2.2.6) — Stage 8. The actual reminder
# checking now runs automatically via before_request (see
# app/reminders.py: maybe_check_reminders), piggybacked on normal traffic
# instead of a Vercel Cron job (Hobby plan only allows daily crons — too
# coarse for a 20-minutes-before reminder). This route is kept as a manual
# trigger for local testing / debugging (curl, or a browser tab); it
# forces an immediate check regardless of the 5-minute throttle. Guarded
# by CRON_SECRET when one's configured — see config.py for why.
# ---------------------------------------------------------------------------
@main_bp.route("/api/cron/check-reminders")
def cron_check_reminders():
    secret = current_app.config.get("CRON_SECRET")
    if secret:
        auth_header = request.headers.get("Authorization", "")
        if auth_header != f"Bearer {secret}":
            abort(401)
    else:
        current_app.logger.warning(
            "CRON_SECRET is not set — /api/cron/check-reminders is running "
            "unauthenticated. Fine for local dev; set CRON_SECRET before "
            "deploying anywhere public."
        )

    from app.reminders import check_and_send_reminders

    result = check_and_send_reminders()
    return jsonify(result)
