"""Live-update polling support (Stage 9).

Pages were fully server-rendered with zero refresh logic, so nothing ever
updated until the user navigated or hit reload. This module fixes that
without websockets/SSE (Vercel's serverless functions don't hold those open
well): any page with a `data-live-key="X"` container polls `/live/version`
every few seconds; when the signal for X changes, the client re-fetches the
*current page* and swaps in the fresh `[data-live-key="X"]` markup in
place — no full reload, no flicker. See static/js/live.js for the client.

`compute_signal` is the single source of truth for "did X change" — it's
called both by the polling endpoint below and by every route that renders
a `data-live-key` container (so the version baked into the initial page
load always matches what a poll would compute right after, and the very
first poll doesn't spuriously think something changed).

Signals are short strings, not booleans — "changed" is just "does the
string differ from what the client already has", so the exact format
doesn't matter as long as it changes whenever the underlying data does.
"""

from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, or_

from app.models import Message, Group, GroupEvent, ChangeRequest, RequestStatus, Role

live_bp = Blueprint("live", __name__, url_prefix="/live")


def _messages_signal(user):
    """Admin sees every message (their own admin/messages.html list is
    unfiltered); User/Staff only see broadcasts + their own group's, same
    scope as dashboard_data.get_messages_for."""
    query = Message.query
    if user.role != Role.ADMIN.value:
        query = query.filter(
            or_(Message.target_group_id.is_(None), Message.target_group_id == user.group_id)
        )
    count, max_time = query.with_entities(
        func.count(Message.message_id), func.max(Message.time)
    ).one()
    return f"{count or 0}:{max_time.isoformat() if max_time else ''}"


def _points_signal(user):
    """Global, not per-user: the points/leaderboard page shows every
    group's rank, so any group's points changing should refresh it for
    everyone looking, not just that group's own members."""
    total_points = Group.query.with_entities(
        func.coalesce(func.sum(Group.points), 0)
    ).scalar()
    events_count = GroupEvent.query.with_entities(
        func.count(GroupEvent.group_event_id)
    ).scalar()
    return f"{total_points}:{events_count or 0}"


def _requests_signal(user):
    """Admin: global pending queue (what admin/requests.html + the
    dashboard card show). Staff: just their own pending submissions (the
    badge on staff/dashboard.html). Plain Users have no concept of
    requests, so this signal doesn't apply to them."""
    if user.role == Role.ADMIN.value:
        base = ChangeRequest.query.filter_by(status=RequestStatus.PENDING)
    elif user.role == Role.STAFF.value:
        base = ChangeRequest.query.filter_by(
            submitted_by_user_id=user.user_id, status=RequestStatus.PENDING
        )
    else:
        return None
    count, max_id = base.with_entities(
        func.count(ChangeRequest.request_id), func.max(ChangeRequest.request_id)
    ).one()
    return f"{count or 0}:{max_id or 0}"


_SIGNALS = {
    "messages": _messages_signal,
    "points": _points_signal,
    "requests": _requests_signal,
}


def compute_signal(key, user):
    """Used both by /live/version and by page routes seeding the initial
    `data-live-version` attribute. Returns None for signals that don't
    apply to this user's role (e.g. "requests" for a plain User) — the
    client just never polls a key whose baseline was None/absent."""
    fn = _SIGNALS.get(key)
    return fn(user) if fn else None


@live_bp.route("/version")
@login_required
def version():
    return jsonify({key: compute_signal(key, current_user) for key in _SIGNALS})
