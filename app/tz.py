"""Local-time display helper.

Every timestamp column in models.py (`Message.time`, `Event.time`,
`GroupEvent.created_at`, `ChangeRequest.reviewed_at`, ...) is stored as
**naive UTC** — that's correct and deliberate, so ordering/comparisons
(`datetime.utcnow()` in reminders.py and dashboard_data.py) never have to
think about timezones at all.

The bug this file fixes: nothing was ever converting those UTC values
back to the camp's local timezone before displaying them, so every
template was just formatting raw UTC as if it were local time. Route
that formatting through `to_local()` (or the `local_time` Jinja filter
registered in app/__init__.py) instead of calling `.strftime()` directly
on a stored datetime.
"""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app

UTC = ZoneInfo("UTC")


def _camp_zone():
    """Resolve CAMP_TIMEZONE to a ZoneInfo, falling back to UTC (and
    logging a warning) if it's missing/misspelled — e.g. "Albania/Tirana"
    isn't a real IANA key, the correct one is "Europe/Tirane" — so a typo'd
    env var degrades to "times are in UTC" instead of a 500 on every page
    that displays one."""
    tz_name = current_app.config.get("CAMP_TIMEZONE", "UTC")
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        current_app.logger.warning(
            "CAMP_TIMEZONE=%r is not a valid IANA timezone name — falling back to UTC. "
            "Check https://en.wikipedia.org/wiki/List_of_tz_database_time_zones for the correct key.",
            tz_name,
        )
        return UTC


def to_local(dt):
    """Convert a naive-UTC datetime (as stored in the DB) to the camp's
    configured local timezone (CAMP_TIMEZONE). Returns None unchanged so
    this is safe to call on optional fields like `sent_20min_at`."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(_camp_zone())


def local_date(dt):
    """The calendar date `dt` falls on in the camp's local timezone —
    NOT the same as `dt.date()`, which is whatever date it happened to be
    in UTC. Use this for any "which day does this belong on" grouping
    (schedule/message day headings) instead of `.date()` directly."""
    local = to_local(dt)
    return local.date() if local else None


def local_naive_to_utc_naive(local_dt):
    """The admin/staff Event form uses an HTML `<input type="datetime-local">`,
    which WTForms' DateTimeLocalField parses into a naive datetime holding
    exactly the wall-clock numbers that were typed — e.g. typing "8:00 PM"
    produces `datetime(..., 20, 0)` with no timezone attached at all. The
    person typing it means camp-local time ("campfire at 8pm"), not UTC.

    Call this at the point an Event is created/edited to convert that
    local wall-clock value into the naive-UTC form the `time` column
    actually stores — mirroring `local_midnight_to_utc_naive` above, just
    for an arbitrary time-of-day instead of midnight."""
    if local_dt is None:
        return None
    aware_local = local_dt.replace(tzinfo=_camp_zone())
    return aware_local.astimezone(UTC).replace(tzinfo=None)


def local_midnight_to_utc_naive(local_date_value):
    """The inverse direction: given a local calendar date, return
    midnight of that date in the camp's timezone, converted to naive UTC
    — i.e. the right value to compare against a stored (naive-UTC)
    DateTime column in a query, such as "give me all events on this
    local day"."""
    from datetime import datetime as _datetime

    local_midnight = _datetime.combine(local_date_value, _datetime.min.time(), tzinfo=_camp_zone())
    return local_midnight.astimezone(UTC).replace(tzinfo=None)
