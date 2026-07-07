# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.models import PushSubscription

bp = Blueprint("api", __name__)


@bp.route("/push/vapid-public-key")
@login_required
def vapid_public_key():
    return jsonify({"publicKey": current_app.config.get("VAPID_PUBLIC_KEY", "")})


@bp.route("/push/subscribe", methods=["POST"])
@login_required
def push_subscribe():
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")
    keys = data.get("keys") or {}
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")

    if not endpoint or not p256dh or not auth:
        return jsonify({"ok": False, "error": "Të dhëna abonimi jo të plota."}), 400

    existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if existing:
        existing.user_id = current_user.id
        existing.p256dh = p256dh
        existing.auth = auth
    else:
        db.session.add(PushSubscription(
            user_id=current_user.id, endpoint=endpoint, p256dh=p256dh, auth=auth,
        ))
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/push/unsubscribe", methods=["POST"])
@login_required
def push_unsubscribe():
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")
    if endpoint:
        PushSubscription.query.filter_by(endpoint=endpoint, user_id=current_user.id).delete()
        db.session.commit()
    return jsonify({"ok": True})
