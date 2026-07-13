from flask import Blueprint, render_template, request
from flask_login import login_required, current_user

from app.decorators import role_required
from app.models import Role
from app.dashboard_data import (
    get_points_summary,
    get_room_summary,
    get_messages_for,
    get_weekly_schedule,
    get_unread_message_count,
    get_next_event,
    get_group_leaderboard,
)

user_bp = Blueprint("user", __name__, url_prefix="/dashboard")


@user_bp.route("/")
@login_required
@role_required(Role.USER)
def dashboard():
    from app.live import compute_signal

    points = get_points_summary(current_user)
    room = get_room_summary(current_user)
    messages = get_messages_for(current_user)
    next_event, next_event_relative = get_next_event()
    return render_template(
        "user/dashboard.html",
        user=current_user,
        points=points,
        room=room,
        messages=messages,
        unread_message_count=get_unread_message_count(current_user),
        next_event=next_event,
        next_event_relative=next_event_relative,
        messages_version=compute_signal("messages", current_user),
        points_version=compute_signal("points", current_user),
    )


# ---------------------------------------------------------------------------
# Detail pages — one per carousel tab (nav redesign). Light theme (base.html
# sidebar layout), except Messages which stays in the dark carousel style
# per spec ("same style as the main dashboard").
# ---------------------------------------------------------------------------
@user_bp.route("/points")
@login_required
@role_required(Role.USER)
def points_detail():
    from app.live import compute_signal

    points = get_points_summary(current_user)
    leaderboard = get_group_leaderboard(highlight_group_id=current_user.group_id)
    return render_template(
        "user/points_detail.html",
        points=points,
        leaderboard=leaderboard,
        points_version=compute_signal("points", current_user),
    )


@user_bp.route("/room")
@login_required
@role_required(Role.USER)
def room_detail():
    room = get_room_summary(current_user)
    return render_template("user/room_detail.html", room=room)


@user_bp.route("/messages")
@login_required
@role_required(Role.USER)
def messages_detail():
    from app.live import compute_signal

    messages = get_messages_for(current_user)
    return render_template(
        "user/messages_detail.html",
        messages=messages,
        messages_version=compute_signal("messages", current_user),
    )


@user_bp.route("/schedule")
@login_required
@role_required(Role.USER)
def schedule_detail():
    week_offset = request.args.get("week", default=0, type=int)
    schedule = get_weekly_schedule(week_offset=week_offset)
    return render_template("user/schedule_detail.html", schedule=schedule)
