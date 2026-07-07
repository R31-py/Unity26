# -*- coding: utf-8 -*-
import json
import logging

from flask import current_app
from pywebpush import webpush, WebPushException

from app.extensions import db
from app.models import PushSubscription

logger = logging.getLogger(__name__)


def _send_to_subscription(sub: PushSubscription, payload: dict):
    try:
        webpush(
            subscription_info={
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            },
            data=json.dumps(payload),
            vapid_private_key=current_app.config["VAPID_PRIVATE_KEY"],
            vapid_claims={"sub": current_app.config["VAPID_CLAIM_EMAIL"]},
        )
        return True
    except WebPushException as exc:
        logger.warning("Push dështoi për endpoint %s: %s", sub.endpoint[:40], exc)
        # 404/410 = abonimi nuk vlen më, fshije
        if exc.response is not None and exc.response.status_code in (404, 410):
            db.session.delete(sub)
            db.session.commit()
        return False


def send_push_to_user(user, title, body, url="/"):
    if not current_app.config.get("VAPID_PRIVATE_KEY"):
        return  # push i çaktivizuar nëse s'ka çelësa VAPID të konfiguruar
    payload = {"title": title, "body": body, "url": url}
    for sub in list(user.push_subscriptions):
        _send_to_subscription(sub, payload)


def send_push_to_users(users, title, body, url="/"):
    for u in users:
        send_push_to_user(u, title, body, url=url)