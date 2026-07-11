"""Shared read-only dashboard data for the User and Staff roles — both see
the same Points & Penalties, Room & Roommates, Messages, and Schedule
cards (spec §3)."""

from datetime import datetime, timedelta

from app.models import GroupEvent, Message, Event


def get_points_summary(user):
    """Returns None if the user has no group yet, else a dict with the
    group, its current total (kept in sync by Admin CRUD — see
    Group.recompute_points), and the itemized ledger, newest first."""
    if not user.group:
        return None
    events = (
        GroupEvent.query.filter_by(group_id=user.group_id)
        .order_by(GroupEvent.created_at.desc())
        .all()
    )
    return {"group": user.group, "total": user.group.points, "events": events}


def get_room_summary(user):
    """Returns None if the user has no room yet, else the room and the
    other occupants assigned to it (roommates, not including the user)."""
    if not user.room:
        return None
    roommates = [u for u in user.room.occupants if u.user_id != user.user_id]
    return {"room": user.room, "roommates": roommates}


def get_messages_for(user):
    """Messages visible to this user: broadcasts (target_group_id IS NULL)
    plus anything scoped to their own group, newest first (spec §2.2.5)."""
    from sqlalchemy import or_

    query = Message.query.filter(
        or_(Message.target_group_id.is_(None), Message.target_group_id == user.group_id)
    )
    return query.order_by(Message.time.desc()).all()


# Events have no explicit duration in the schema (spec §2), so "current"
# treats each event as occupying a 1-hour block from its start time — just
# for the past/current/upcoming visual distinction, not stored anywhere.
_ASSUMED_EVENT_DURATION = timedelta(hours=1)


def get_weekly_schedule(week_offset=0, now=None):
    """Builds a Monday-Sunday timetable for the requested week (0 = this
    week, -1 = last week, +1 = next week), with each event classified as
    past / current / upcoming relative to `now`."""
    now = now or datetime.utcnow()
    today = now.date()
    monday = today - timedelta(days=today.weekday())
    week_start = monday + timedelta(weeks=week_offset)
    week_end = week_start + timedelta(days=7)

    events = (
        Event.query.filter(
            Event.time >= datetime.combine(week_start, datetime.min.time()),
            Event.time < datetime.combine(week_end, datetime.min.time()),
        )
        .order_by(Event.time.asc())
        .all()
    )

    days = []
    for i in range(7):
        day_date = week_start + timedelta(days=i)
        day_events = []
        for e in events:
            if e.time is None or e.time.date() != day_date:
                continue
            ends_at = e.time + _ASSUMED_EVENT_DURATION
            if now < e.time:
                status = "upcoming"
            elif now < ends_at:
                status = "current"
            else:
                status = "past"
            day_events.append({"event": e, "status": status})
        days.append(
            {
                "date": day_date,
                "is_today": day_date == today,
                "events": day_events,
            }
        )

    return {
        "week_start": week_start,
        "week_end": week_end - timedelta(days=1),
        "week_offset": week_offset,
        "is_current_week": week_offset == 0,
        "days": days,
    }


# ---------------------------------------------------------------------------
# Carousel-dashboard helpers (nav redesign) — no new persisted state, just
# small derived values for the home-screen cards.
# ---------------------------------------------------------------------------
def get_unread_message_count(user, now=None):
    """Heuristic "new" indicator: messages visible to this user created in
    the last 24h. There's no persisted read-state table (out of scope per
    the spec), so this is a time-based approximation, not a true unread
    count — good enough for a small attention-getting dot on the tab."""
    now = now or datetime.utcnow()
    cutoff = now - timedelta(hours=24)
    return sum(1 for m in get_messages_for(user) if m.time and m.time >= cutoff)


def get_next_event(now=None):
    """The single next upcoming event (any group — events aren't scoped),
    plus a short human-relative label for its card."""
    now = now or datetime.utcnow()
    event = (
        Event.query.filter(Event.time >= now).order_by(Event.time.asc()).first()
    )
    if not event:
        return None, None

    delta = event.time - now
    minutes = int(delta.total_seconds() // 60)
    if minutes <= 0:
        label = "Starting now"
    elif minutes < 60:
        label = f"Starting in {minutes} min"
    elif minutes < 60 * 24:
        label = f"In {minutes // 60} hr"
    else:
        label = f"In {delta.days} day{'s' if delta.days != 1 else ''}"
    return event, label


def get_group_leaderboard(highlight_group_id=None):
    """All groups ranked by points, highest first, with each group's
    reward/penalty counts (spec: "current group ranks") and a flag for
    whichever group should be visually highlighted (the viewer's own)."""
    from app.models import Group, GroupEvent, GroupEventType

    groups = Group.query.order_by(Group.points.desc(), Group.name.asc()).all()
    rows = []
    for rank, g in enumerate(groups, start=1):
        reward_count = sum(1 for e in g.group_events if e.type == GroupEventType.POINT.value)
        penalty_count = sum(1 for e in g.group_events if e.type == GroupEventType.PENALTY.value)
        rows.append({
            "rank": rank,
            "group": g,
            "reward_count": reward_count,
            "penalty_count": penalty_count,
            "is_mine": g.group_id == highlight_group_id,
        })
    return rows
