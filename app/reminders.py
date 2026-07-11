"""Event reminder checks — Stage 8 (spec §4, §2.2.6).

Designed to be called from a scheduled HTTP hit (Vercel Cron) rather than
an in-process scheduler, since Vercel Functions can't run a persistent
background process (spec §5). Because Cron timing isn't exact — Vercel
may invoke anywhere within the scheduled window depending on plan, and
the interval between checks itself varies by plan (see README §Stage 8)
— this doesn't look for events starting in *exactly* 20 minutes. Instead
it treats "due" as a window: any event whose 20-minutes-before mark has
already passed but whose start hasn't, gets the reminder, once
(`sent_20min_at`). Same idea for the start-time push (`sent_start_at`),
with a cutoff so a long cron outage doesn't dump a pile of very stale
"starting now" pushes once checks resume.
"""

from datetime import datetime, timedelta

from flask import current_app

from app.extensions import db
from app.models import Event, User, Role
from app.push import send_push_to_users

REMINDER_LEAD = timedelta(minutes=20)

# If checks were down for a while (e.g. a quiet Hobby-plan cron, or a
# deploy issue) and come back late, don't fire "starting now" for an
# event that started hours ago — it's no longer a useful reminder.
STALE_CUTOFF = timedelta(hours=3)


def _audience():
    """Same audience as new-message pushes: Users + Staff, not Admin
    (events aren't group-scoped in this schema, so it's everyone)."""
    return User.query.filter(User.role != Role.ADMIN.value).all()


def check_and_send_reminders(now=None):
    """Finds events due for a 20-minute or start-time push, sends them,
    and marks them sent. Returns a small summary dict (also the JSON body
    of the /api/cron/check-reminders response) so a cron run's log line
    on Vercel shows something useful instead of just a 200.
    """
    now = now or datetime.utcnow()

    candidates = Event.query.filter(
        Event.time.isnot(None),
        Event.time >= now - STALE_CUTOFF,
        Event.time <= now + REMINDER_LEAD,
    ).all()

    audience = None  # fetched lazily, only if something's actually due
    twenty_min_sent = 0
    start_sent = 0

    for event in candidates:
        due_20min = (
            event.sent_20min_at is None
            and event.time - REMINDER_LEAD <= now < event.time
        )
        due_start = (
            event.sent_start_at is None
            and now >= event.time
            and (now - event.time) <= STALE_CUTOFF
        )

        if not due_20min and not due_start:
            continue

        if audience is None:
            audience = _audience()

        if due_20min:
            send_push_to_users(
                audience,
                {
                    "title": f"Starting in 20 minutes: {event.name}",
                    "body": (event.description or "").strip()[:180],
                    "url": "/",
                },
            )
            event.sent_20min_at = now
            twenty_min_sent += 1

        if due_start:
            send_push_to_users(
                audience,
                {
                    "title": f"Starting now: {event.name}",
                    "body": (event.description or "").strip()[:180],
                    "url": "/",
                },
            )
            event.sent_start_at = now
            start_sent += 1

    if twenty_min_sent or start_sent:
        db.session.commit()

    return {
        "checked_at": now.isoformat(),
        "candidates_checked": len(candidates),
        "twenty_min_reminders_sent": twenty_min_sent,
        "start_reminders_sent": start_sent,
    }
