"""Web Push (VAPID) sending — Stage 7.

Wraps `pywebpush` so the rest of the app can just call
`notify_new_message(message)` after a Message is created (either directly
by Admin, or via an approved Staff request) without worrying about VAPID
config, per-subscription errors, or cleaning up dead subscriptions.

Event reminders (spec §4, "20 minutes before / at start") are Stage 8 —
this module only handles the "new Admin message" push for now, but
`send_push_to_users` is generic and Stage 8 reuses it as-is.
"""

import json

from flask import current_app

from app.extensions import db
from app.models import PushSubscription, User, Role


def vapid_configured():
    return bool(
        current_app.config.get("VAPID_PRIVATE_KEY")
        and current_app.config.get("VAPID_PUBLIC_KEY")
    )


def _vapid_claims():
    return {"sub": current_app.config["VAPID_CLAIM_EMAIL"]}


def send_push_to_users(users, payload):
    """Send `payload` (a JSON-serializable dict) to every push subscription
    belonging to any of `users`. Silently no-ops if VAPID isn't configured
    yet (Stage 7 works fine without keys — the button just stays unusable
    client-side). Subscriptions the push service reports as gone (410/404)
    are deleted so future sends don't keep retrying them.

    Returns a summary dict: {"configured": bool, "total": int, "sent": int,
    "failed": int, "stale": int} so callers can report back to the user
    (e.g. the admin "send test notification" button) instead of this being
    a fire-and-forget best-effort call.
    """
    if not vapid_configured():
        current_app.logger.info("Push skipped: VAPID keys not configured.")
        return {"configured": False, "total": 0, "sent": 0, "failed": 0, "stale": 0}

    user_ids = [u.user_id for u in users]
    if not user_ids:
        return {"configured": True, "total": 0, "sent": 0, "failed": 0, "stale": 0}

    # Imported lazily: pywebpush pulls in `cryptography`/`py_vapid`, which
    # are only needed once push is actually configured and used.
    from pywebpush import webpush, WebPushException

    subscriptions = PushSubscription.query.filter(
        PushSubscription.user_id.in_(user_ids)
    ).all()
    data = json.dumps(payload)
    stale_ids = []
    sent = 0
    failed = 0

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=data,
                vapid_private_key=current_app.config["VAPID_PRIVATE_KEY"],
                vapid_claims=_vapid_claims(),
            )
            sent += 1
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (404, 410):
                # Browser/OS says this subscription is gone for good.
                stale_ids.append(sub.id)
            else:
                failed += 1
                current_app.logger.warning("Push send failed (%s): %s", status, exc)
        except Exception as exc:  # pragma: no cover - defensive, push must never 500 a request
            failed += 1
            current_app.logger.warning("Unexpected push error: %s", exc)

    if stale_ids:
        PushSubscription.query.filter(PushSubscription.id.in_(stale_ids)).delete(
            synchronize_session=False
        )
        db.session.commit()

    return {
        "configured": True,
        "total": len(subscriptions),
        "sent": sent,
        "failed": failed,
        "stale": len(stale_ids),
    }


def audience_for_message(message):
    """Accounts that should be notified for this message: matches the same
    visibility rule as `dashboard_data.get_messages_for` (broadcast, or
    scoped to one group), minus Admins — an Admin doesn't have a Messages
    tab and shouldn't get a push for their own announcement."""
    query = User.query.filter(User.role != Role.ADMIN.value)
    if message.target_group_id:
        query = query.filter(User.group_id == message.target_group_id)
    return query.all()


def notify_new_message(message):
    """Fire a push to everyone who should see `message`. Safe to call
    right after commit; never raises — a push failure should never turn a
    successful message post into an error page."""
    try:
        audience = audience_for_message(message)
        payload = {
            "title": message.title or "New message",
            "body": (message.content or "").strip()[:180],
            "url": "/",
        }
        send_push_to_users(audience, payload)
    except Exception as exc:  # pragma: no cover - defensive
        current_app.logger.warning("notify_new_message failed: %s", exc)


def send_test_notification(sender):
    """Admin "send test notification" button: pushes a test payload to
    every account's push subscriptions (Admin, Staff, and User), so the
    person testing can confirm push actually reaches devices end-to-end
    before relying on it for real messages/reminders. Returns the same
    summary dict as `send_push_to_users`."""
    payload = {
        "title": "Test notification",
        "body": f"Sent by {sender.name} from the admin console — if you can see this, push is working.",
        "url": "/",
    }
    return send_push_to_users(User.query.all(), payload)
