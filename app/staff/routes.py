from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.decorators import role_required
from app.extensions import db
from app.models import Role, ChangeRequest, RequestTargetType
from app.dashboard_data import (
    get_points_summary,
    get_room_summary,
    get_messages_for,
    get_weekly_schedule,
    get_unread_message_count,
    get_next_event,
    get_group_leaderboard,
)
from app.choices import group_choices, user_choices_for_attribution, audience_choices, validate_attribution
from app.staff.forms import RequestMessageForm, RequestGroupEventForm, RequestEventForm

staff_bp = Blueprint("staff", __name__, url_prefix="/staff")


@staff_bp.route("/")
@login_required
@role_required(Role.STAFF)
def dashboard():
    points = get_points_summary(current_user)
    room = get_room_summary(current_user)
    messages = get_messages_for(current_user)
    next_event, next_event_relative = get_next_event()
    pending_own_requests = ChangeRequest.query.filter_by(
        submitted_by_user_id=current_user.user_id, status="pending"
    ).count()
    return render_template(
        "staff/dashboard.html",
        user=current_user,
        points=points,
        room=room,
        messages=messages,
        unread_message_count=get_unread_message_count(current_user),
        next_event=next_event,
        next_event_relative=next_event_relative,
        pending_own_requests=pending_own_requests,
    )


# ---------------------------------------------------------------------------
# Detail pages — same pattern as the User role (nav redesign).
# ---------------------------------------------------------------------------
@staff_bp.route("/points")
@login_required
@role_required(Role.STAFF)
def points_detail():
    points = get_points_summary(current_user)
    leaderboard = get_group_leaderboard(highlight_group_id=current_user.group_id)
    return render_template("staff/points_detail.html", points=points, leaderboard=leaderboard)


@staff_bp.route("/room")
@login_required
@role_required(Role.STAFF)
def room_detail():
    room = get_room_summary(current_user)
    return render_template("staff/room_detail.html", room=room)


@staff_bp.route("/messages")
@login_required
@role_required(Role.STAFF)
def messages_detail():
    messages = get_messages_for(current_user)
    return render_template("staff/messages_detail.html", messages=messages)


@staff_bp.route("/schedule")
@login_required
@role_required(Role.STAFF)
def schedule_detail():
    week_offset = request.args.get("week", default=0, type=int)
    schedule = get_weekly_schedule(week_offset=week_offset)
    return render_template("staff/schedule_detail.html", schedule=schedule)


# ---------------------------------------------------------------------------
# Requests — Staff submits, Admin reviews (spec §3 Staff dashboard)
# ---------------------------------------------------------------------------
@staff_bp.route("/requests")
@login_required
@role_required(Role.STAFF)
def requests_list():
    own_requests = (
        ChangeRequest.query.filter_by(submitted_by_user_id=current_user.user_id)
        .order_by(ChangeRequest.created_at.desc())
        .all()
    )
    return render_template("staff/requests.html", requests=own_requests)


@staff_bp.route("/requests/new/message", methods=["GET", "POST"])
@login_required
@role_required(Role.STAFF)
def request_message_new():
    form = RequestMessageForm()
    form.target_group_id.choices = audience_choices()

    if form.validate_on_submit():
        payload = {
            "title": form.title.data.strip(),
            "content": form.content.data.strip(),
            "target_group_id": form.target_group_id.data or None,
        }
        cr = ChangeRequest(
            submitted_by_user_id=current_user.user_id,
            target_type=RequestTargetType.MESSAGE,
            payload=payload,
        )
        db.session.add(cr)
        db.session.commit()
        flash("Message submitted for Admin approval.", "success")
        return redirect(url_for("staff.requests_list"))

    return render_template("staff/request_message_form.html", form=form)


@staff_bp.route("/requests/new/point", methods=["GET", "POST"])
@login_required
@role_required(Role.STAFF)
def request_point_new():
    form = RequestGroupEventForm()
    form.group_id.choices = group_choices()[1:]  # group is required, drop "—"
    form.user_id.choices = user_choices_for_attribution()

    if not form.group_id.choices:
        flash("No groups exist yet — ask an Admin to create one first.", "error")
        return redirect(url_for("staff.requests_list"))

    if form.validate_on_submit():
        error = validate_attribution(form.group_id.data, form.user_id.data)
        if error:
            flash(error, "error")
            return render_template("staff/request_point_form.html", form=form)

        payload = {
            "group_id": form.group_id.data,
            "user_id": form.user_id.data or None,
            "type": form.type.data,
            "name": form.name.data.strip(),
            "description": (form.description.data or "").strip() or None,
            "value": form.value.data,
        }
        cr = ChangeRequest(
            submitted_by_user_id=current_user.user_id,
            target_type=RequestTargetType.GROUP_EVENT,
            payload=payload,
        )
        db.session.add(cr)
        db.session.commit()
        flash("Points/penalty entry submitted for Admin approval.", "success")
        return redirect(url_for("staff.requests_list"))

    return render_template("staff/request_point_form.html", form=form)


@staff_bp.route("/requests/new/event", methods=["GET", "POST"])
@login_required
@role_required(Role.STAFF)
def request_event_new():
    form = RequestEventForm()

    if form.validate_on_submit():
        payload = {
            "name": form.name.data.strip(),
            "description": (form.description.data or "").strip() or None,
            "time": form.time.data.isoformat(),
        }
        cr = ChangeRequest(
            submitted_by_user_id=current_user.user_id,
            target_type=RequestTargetType.EVENT,
            payload=payload,
        )
        db.session.add(cr)
        db.session.commit()
        flash("Event submitted for Admin approval.", "success")
        return redirect(url_for("staff.requests_list"))

    return render_template("staff/request_event_form.html", form=form)
