from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.decorators import role_required
from app.extensions import db
from app.push import notify_new_message
from app.models import (
    Role,
    User,
    Group,
    Room,
    Building,
    GroupEvent,
    GroupEventType,
    Message,
    Event,
    ChangeRequest,
    RequestStatus,
    RequestTargetType,
)
from app.admin.forms import (
    UserForm,
    GroupForm,
    BuildingForm,
    RoomForm,
    GroupEventForm,
    MessageForm,
    EventForm,
    ConfirmDeleteForm,
    ReviewRejectForm,
    NONE_CHOICE,
)
from app.choices import (
    group_choices as _group_choices,
    room_choices as _room_choices,
    user_choices_for_attribution as _user_choices_for_attribution,
    audience_choices as _audience_choices,
    validate_attribution,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@login_required
@role_required(Role.ADMIN)
def dashboard():
    staff_count = User.query.filter_by(role=Role.STAFF.value).count()
    camper_count = User.query.filter_by(role=Role.USER.value).count()
    full_rooms = sum(1 for r in Room.query.all() if len(r.occupants) >= r.capacity)
    pending = ChangeRequest.query.filter_by(status=RequestStatus.PENDING).all()
    pending_by_type = {}
    for r in pending:
        pending_by_type[r.target_type] = pending_by_type.get(r.target_type, 0) + 1
    next_event = (
        Event.query.filter(Event.time >= datetime.utcnow()).order_by(Event.time.asc()).first()
    )
    stats = {
        "user_count": User.query.count(),
        "staff_count": staff_count,
        "camper_count": camper_count,
        "group_count": Group.query.count(),
        "room_count": Room.query.count(),
        "full_room_count": full_rooms,
        "point_entry_count": GroupEvent.query.count(),
        "message_count": Message.query.count(),
        "event_count": Event.query.count(),
        "next_event": next_event,
        "pending_requests": len(pending),
        "pending_by_type": pending_by_type,
    }
    from app.live import compute_signal

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        messages_version=compute_signal("messages", current_user),
        points_version=compute_signal("points", current_user),
        requests_version=compute_signal("requests", current_user),
    )


@admin_bp.route("/notifications/test", methods=["POST"])
@login_required
@role_required(Role.ADMIN)
def notifications_test():
    from app.push import send_test_notification, vapid_configured

    if not vapid_configured():
        flash(
            "Push isn't configured yet — set VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY "
            "(see generate_vapid_keys.py) before test notifications can be sent.",
            "error",
        )
        return redirect(url_for("admin.dashboard"))

    result = send_test_notification(current_user)
    if result["total"] == 0:
        flash(
            "No one has push notifications turned on yet — there's nothing to send to. "
            "Each person needs to enable notifications from their own device first.",
            "error",
        )
    elif result["sent"] == result["total"]:
        flash(f"Test notification sent to all {result['sent']} subscribed device(s).", "success")
    else:
        parts = [f"{result['sent']} of {result['total']} device(s) reached"]
        if result["stale"]:
            parts.append(f"{result['stale']} expired subscription(s) removed")
        if result["failed"]:
            parts.append(f"{result['failed']} failed")
        flash("Test notification sent — " + ", ".join(parts) + ".", "info")
    return redirect(url_for("admin.dashboard"))


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
# NOTE: _group_choices / _room_choices / _user_choices_for_attribution /
# _audience_choices are now imported from app.choices (Stage 6) so Staff's
# change-request forms build their dropdowns identically. See app/choices.py.


def _validate_attribution(form):
    """Returns an error message if the chosen member doesn't belong to the
    chosen group, else None."""
    return validate_attribution(form.group_id.data, form.user_id.data)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
@admin_bp.route("/users")
@login_required
@role_required(Role.ADMIN)
def users():
    all_users = User.query.order_by(User.role, User.name).all()
    delete_form = ConfirmDeleteForm()
    return render_template("admin/users.html", users=all_users, delete_form=delete_form)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN)
def user_new():
    form = UserForm(is_create=True)
    form.group_id.choices = _group_choices()
    form.room_id.choices = _room_choices()

    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data.strip()).first():
            flash("That username is already taken.", "error")
            return render_template("admin/user_form.html", form=form, mode="new")

        room = Room.query.get(form.room_id.data) if form.room_id.data else None
        if room and room.is_full:
            flash(f"Room {room.number} is already at capacity.", "error")
            return render_template("admin/user_form.html", form=form, mode="new")

        user = User(
            name=form.name.data.strip(),
            surname=(form.surname.data or "").strip() or None,
            username=form.username.data.strip(),
            role=form.role.data,
            group_id=form.group_id.data or None,
            room_id=form.room_id.data or None,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(f"Created {Role(user.role).name.title()} account for {user.full_name}.", "success")
        return redirect(url_for("admin.users"))

    return render_template("admin/user_form.html", form=form, mode="new")


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN)
def user_edit(user_id):
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user, is_create=False)
    form.group_id.choices = _group_choices()
    form.room_id.choices = _room_choices(current_room_id=user.room_id)

    if request.method == "GET":
        form.group_id.data = user.group_id or 0
        form.room_id.data = user.room_id or 0
        form.password.data = ""

    if form.validate_on_submit():
        clash = User.query.filter(
            User.username == form.username.data.strip(), User.user_id != user.user_id
        ).first()
        if clash:
            flash("That username is already taken.", "error")
            return render_template("admin/user_form.html", form=form, mode="edit", user=user)

        room = Room.query.get(form.room_id.data) if form.room_id.data else None
        if room and room.is_full and room.room_id != user.room_id:
            flash(f"Room {room.number} is already at capacity.", "error")
            return render_template("admin/user_form.html", form=form, mode="edit", user=user)

        if user.is_admin and form.role.data != Role.ADMIN.value:
            remaining_admins = User.query.filter(
                User.role == Role.ADMIN.value, User.user_id != user.user_id
            ).count()
            if remaining_admins == 0:
                flash("Can't demote the last remaining Admin.", "error")
                return render_template("admin/user_form.html", form=form, mode="edit", user=user)

        user.name = form.name.data.strip()
        user.surname = (form.surname.data or "").strip() or None
        user.username = form.username.data.strip()
        user.role = form.role.data
        user.group_id = form.group_id.data or None
        user.room_id = form.room_id.data or None
        if form.password.data:
            user.set_password(form.password.data)

        db.session.commit()
        flash(f"Updated {user.full_name}.", "success")
        return redirect(url_for("admin.users"))

    return render_template("admin/user_form.html", form=form, mode="edit", user=user)


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@role_required(Role.ADMIN)
def user_delete(user_id):
    form = ConfirmDeleteForm()
    if not form.validate_on_submit():
        abort(400)

    user = User.query.get_or_404(user_id)
    if user.user_id == current_user.user_id:
        flash("You can't delete your own account while logged in as it.", "error")
        return redirect(url_for("admin.users"))

    if user.is_admin:
        remaining_admins = User.query.filter(
            User.role == Role.ADMIN.value, User.user_id != user.user_id
        ).count()
        if remaining_admins == 0:
            flash("Can't delete the last remaining Admin.", "error")
            return redirect(url_for("admin.users"))

    name = user.full_name
    db.session.delete(user)
    db.session.commit()
    flash(f"Deleted {name}.", "info")
    return redirect(url_for("admin.users"))


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------
@admin_bp.route("/groups")
@login_required
@role_required(Role.ADMIN)
def groups():
    from app.dashboard_data import get_group_leaderboard

    leaderboard = get_group_leaderboard()
    delete_form = ConfirmDeleteForm()
    return render_template("admin/groups.html", leaderboard=leaderboard, delete_form=delete_form)


@admin_bp.route("/groups/new", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN)
def group_new():
    form = GroupForm()
    if form.validate_on_submit():
        group = Group(name=form.name.data.strip(), color=(form.color.data or "").strip() or None)
        db.session.add(group)
        db.session.commit()
        flash(f"Created group {group.name}.", "success")
        return redirect(url_for("admin.groups"))
    return render_template("admin/group_form.html", form=form, mode="new")


@admin_bp.route("/groups/<int:group_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN)
def group_edit(group_id):
    group = Group.query.get_or_404(group_id)
    form = GroupForm(obj=group)
    if form.validate_on_submit():
        group.name = form.name.data.strip()
        group.color = (form.color.data or "").strip() or None
        db.session.commit()
        flash(f"Updated group {group.name}.", "success")
        return redirect(url_for("admin.groups"))
    return render_template("admin/group_form.html", form=form, mode="edit", group=group)


@admin_bp.route("/groups/<int:group_id>/delete", methods=["POST"])
@login_required
@role_required(Role.ADMIN)
def group_delete(group_id):
    form = ConfirmDeleteForm()
    if not form.validate_on_submit():
        abort(400)
    group = Group.query.get_or_404(group_id)
    name = group.name
    db.session.delete(group)
    db.session.commit()
    flash(f"Deleted group {name}. Members were kept, just unassigned from it.", "info")
    return redirect(url_for("admin.groups"))


# ---------------------------------------------------------------------------
# Rooms & Buildings
# ---------------------------------------------------------------------------
@admin_bp.route("/rooms")
@login_required
@role_required(Role.ADMIN)
def rooms():
    all_buildings = Building.query.order_by(Building.name).all()
    delete_form = ConfirmDeleteForm()
    return render_template(
        "admin/rooms.html", buildings=all_buildings, delete_form=delete_form
    )


@admin_bp.route("/buildings/new", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN)
def building_new():
    form = BuildingForm()
    if form.validate_on_submit():
        building = Building(name=form.name.data.strip())
        db.session.add(building)
        db.session.commit()
        flash(f"Created building {building.name}.", "success")
        return redirect(url_for("admin.rooms"))
    return render_template("admin/building_form.html", form=form, mode="new")


@admin_bp.route("/buildings/<int:building_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN)
def building_edit(building_id):
    building = Building.query.get_or_404(building_id)
    form = BuildingForm(obj=building)
    if form.validate_on_submit():
        building.name = form.name.data.strip()
        db.session.commit()
        flash(f"Updated building {building.name}.", "success")
        return redirect(url_for("admin.rooms"))
    return render_template("admin/building_form.html", form=form, mode="edit", building=building)


@admin_bp.route("/buildings/<int:building_id>/delete", methods=["POST"])
@login_required
@role_required(Role.ADMIN)
def building_delete(building_id):
    form = ConfirmDeleteForm()
    if not form.validate_on_submit():
        abort(400)
    building = Building.query.get_or_404(building_id)
    name = building.name
    db.session.delete(building)
    db.session.commit()
    flash(f"Deleted building {name} and its rooms.", "info")
    return redirect(url_for("admin.rooms"))


@admin_bp.route("/rooms/new", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN)
def room_new():
    form = RoomForm()
    form.building_id.choices = [
        (b.building_id, b.name) for b in Building.query.order_by(Building.name).all()
    ]
    if not form.building_id.choices:
        flash("Create a building first before adding rooms.", "error")
        return redirect(url_for("admin.rooms"))

    if form.validate_on_submit():
        room = Room(
            building_id=form.building_id.data,
            number=form.number.data.strip(),
            capacity=form.capacity.data,
        )
        db.session.add(room)
        db.session.commit()
        flash(f"Created room {room.number}.", "success")
        return redirect(url_for("admin.rooms"))
    return render_template("admin/room_form.html", form=form, mode="new")


@admin_bp.route("/rooms/<int:room_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN)
def room_edit(room_id):
    room = Room.query.get_or_404(room_id)
    form = RoomForm(obj=room)
    form.building_id.choices = [
        (b.building_id, b.name) for b in Building.query.order_by(Building.name).all()
    ]

    if form.validate_on_submit():
        if form.capacity.data < room.occupant_count:
            flash(
                f"Can't set capacity below the current occupant count "
                f"({room.occupant_count}).",
                "error",
            )
            return render_template("admin/room_form.html", form=form, mode="edit", room=room)

        room.building_id = form.building_id.data
        room.number = form.number.data.strip()
        room.capacity = form.capacity.data
        db.session.commit()
        flash(f"Updated room {room.number}.", "success")
        return redirect(url_for("admin.rooms"))
    return render_template("admin/room_form.html", form=form, mode="edit", room=room)


@admin_bp.route("/rooms/<int:room_id>/delete", methods=["POST"])
@login_required
@role_required(Role.ADMIN)
def room_delete(room_id):
    form = ConfirmDeleteForm()
    if not form.validate_on_submit():
        abort(400)
    room = Room.query.get_or_404(room_id)
    name = room.number
    db.session.delete(room)
    db.session.commit()
    flash(f"Deleted room {name}. Occupants were kept, just unassigned from it.", "info")
    return redirect(url_for("admin.rooms"))


# ---------------------------------------------------------------------------
# Points & Penalties (group_events)
# ---------------------------------------------------------------------------
@admin_bp.route("/points")
@login_required
@role_required(Role.ADMIN)
def points():
    all_events = GroupEvent.query.order_by(GroupEvent.created_at.desc()).all()
    delete_form = ConfirmDeleteForm()
    return render_template("admin/points.html", events=all_events, delete_form=delete_form)


@admin_bp.route("/points/new", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN)
def point_new():
    form = GroupEventForm()
    form.group_id.choices = _group_choices()[1:]  # group is required here, drop "—"
    form.user_id.choices = _user_choices_for_attribution()

    if not form.group_id.choices:
        flash("Create a group first before adding points or penalties.", "error")
        return redirect(url_for("admin.groups"))

    if form.validate_on_submit():
        error = _validate_attribution(form)
        if error:
            flash(error, "error")
            return render_template("admin/point_form.html", form=form, mode="new")

        event = GroupEvent(
            group_id=form.group_id.data,
            user_id=form.user_id.data or None,
            type=form.type.data,
            name=form.name.data.strip(),
            description=(form.description.data or "").strip() or None,
            value=form.value.data,
        )
        db.session.add(event)
        group = Group.query.get(form.group_id.data)
        group.recompute_points()
        db.session.commit()
        sign = "+" if event.type == GroupEventType.POINT.value else "-"
        flash(f"Added {sign}{event.value} ({event.name}) to {group.name}.", "success")
        return redirect(url_for("admin.points"))

    return render_template("admin/point_form.html", form=form, mode="new")


@admin_bp.route("/points/<int:group_event_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN)
def point_edit(group_event_id):
    event = GroupEvent.query.get_or_404(group_event_id)
    form = GroupEventForm(obj=event)
    form.group_id.choices = _group_choices()[1:]
    form.user_id.choices = _user_choices_for_attribution()

    if request.method == "GET":
        form.user_id.data = event.user_id or 0

    if form.validate_on_submit():
        error = _validate_attribution(form)
        if error:
            flash(error, "error")
            return render_template("admin/point_form.html", form=form, mode="edit", event=event)

        old_group_id = event.group_id
        event.group_id = form.group_id.data
        event.user_id = form.user_id.data or None
        event.type = form.type.data
        event.name = form.name.data.strip()
        event.description = (form.description.data or "").strip() or None
        event.value = form.value.data
        db.session.flush()

        Group.query.get(old_group_id).recompute_points()
        if form.group_id.data != old_group_id:
            Group.query.get(form.group_id.data).recompute_points()
        db.session.commit()
        flash(f"Updated {event.name}.", "success")
        return redirect(url_for("admin.points"))

    return render_template("admin/point_form.html", form=form, mode="edit", event=event)


@admin_bp.route("/points/<int:group_event_id>/delete", methods=["POST"])
@login_required
@role_required(Role.ADMIN)
def point_delete(group_event_id):
    form = ConfirmDeleteForm()
    if not form.validate_on_submit():
        abort(400)

    event = GroupEvent.query.get_or_404(group_event_id)
    name, group_id = event.name, event.group_id
    db.session.delete(event)
    db.session.flush()
    Group.query.get(group_id).recompute_points()
    db.session.commit()
    flash(f"Deleted {name}.", "info")
    return redirect(url_for("admin.points"))


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------
def _audience_choices():
    groups = Group.query.order_by(Group.name).all()
    return [(0, "Everyone (broadcast)")] + [(g.group_id, g.name) for g in groups]


@admin_bp.route("/messages")
@login_required
@role_required(Role.ADMIN)
def messages():
    from app.live import compute_signal

    all_messages = Message.query.order_by(Message.time.desc()).all()
    delete_form = ConfirmDeleteForm()
    return render_template(
        "admin/messages.html",
        messages=all_messages,
        delete_form=delete_form,
        messages_version=compute_signal("messages", current_user),
    )


@admin_bp.route("/messages/new", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN)
def message_new():
    form = MessageForm()
    form.target_group_id.choices = _audience_choices()

    if form.validate_on_submit():
        message = Message(
            title=form.title.data.strip(),
            content=form.content.data.strip(),
            user_id=current_user.user_id,
            target_group_id=form.target_group_id.data or None,
        )
        db.session.add(message)
        db.session.commit()
        notify_new_message(message)
        flash(f"Posted \"{message.title}\".", "success")
        return redirect(url_for("admin.messages"))

    return render_template("admin/message_form.html", form=form, mode="new")


@admin_bp.route("/messages/<int:message_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN)
def message_edit(message_id):
    message = Message.query.get_or_404(message_id)
    form = MessageForm(obj=message)
    form.target_group_id.choices = _audience_choices()

    if request.method == "GET":
        form.target_group_id.data = message.target_group_id or 0

    if form.validate_on_submit():
        message.title = form.title.data.strip()
        message.content = form.content.data.strip()
        message.target_group_id = form.target_group_id.data or None
        db.session.commit()
        flash(f"Updated \"{message.title}\".", "success")
        return redirect(url_for("admin.messages"))

    return render_template("admin/message_form.html", form=form, mode="edit", message=message)


@admin_bp.route("/messages/<int:message_id>/delete", methods=["POST"])
@login_required
@role_required(Role.ADMIN)
def message_delete(message_id):
    form = ConfirmDeleteForm()
    if not form.validate_on_submit():
        abort(400)
    message = Message.query.get_or_404(message_id)
    title = message.title
    db.session.delete(message)
    db.session.commit()
    flash(f"Deleted \"{title}\".", "info")
    return redirect(url_for("admin.messages"))


# ---------------------------------------------------------------------------
# Events (schedule)
# ---------------------------------------------------------------------------
@admin_bp.route("/events")
@login_required
@role_required(Role.ADMIN)
def events():
    all_events = Event.query.order_by(Event.time.asc()).all()
    delete_form = ConfirmDeleteForm()
    return render_template("admin/events.html", events=all_events, delete_form=delete_form)


@admin_bp.route("/events/new", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN)
def event_new():
    form = EventForm()
    if form.validate_on_submit():
        event = Event(
            name=form.name.data.strip(),
            description=(form.description.data or "").strip() or None,
            time=form.time.data,
        )
        db.session.add(event)
        db.session.commit()
        flash(f"Added \"{event.name}\" to the schedule.", "success")
        return redirect(url_for("admin.events"))
    return render_template("admin/event_form.html", form=form, mode="new")


@admin_bp.route("/events/<int:event_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(Role.ADMIN)
def event_edit(event_id):
    event = Event.query.get_or_404(event_id)
    form = EventForm(obj=event)
    if form.validate_on_submit():
        event.name = form.name.data.strip()
        event.description = (form.description.data or "").strip() or None
        event.time = form.time.data
        db.session.commit()
        flash(f"Updated \"{event.name}\".", "success")
        return redirect(url_for("admin.events"))
    return render_template("admin/event_form.html", form=form, mode="edit", event=event)


@admin_bp.route("/events/<int:event_id>/delete", methods=["POST"])
@login_required
@role_required(Role.ADMIN)
def event_delete(event_id):
    form = ConfirmDeleteForm()
    if not form.validate_on_submit():
        abort(400)
    event = Event.query.get_or_404(event_id)
    name = event.name
    db.session.delete(event)
    db.session.commit()
    flash(f"Removed \"{name}\" from the schedule.", "info")
    return redirect(url_for("admin.events"))


@admin_bp.route("/events/run-reminder-check", methods=["POST"])
@login_required
@role_required(Role.ADMIN)
def event_run_reminder_check():
    """Manually runs the same check Vercel Cron hits on a schedule in
    production (spec §5, §2.2.6) — since nothing triggers that
    automatically in local dev, this lets you try Stage 8 without waiting
    for a real event's start time or standing up a cron job."""
    form = ConfirmDeleteForm()
    if not form.validate_on_submit():
        abort(400)

    from app.reminders import check_and_send_reminders

    result = check_and_send_reminders()
    sent = result["twenty_min_reminders_sent"] + result["start_reminders_sent"]
    if sent:
        flash(
            f"Reminder check: sent {result['twenty_min_reminders_sent']} "
            f"twenty-minute and {result['start_reminders_sent']} start-time "
            f"reminder(s).",
            "success",
        )
    else:
        flash(
            f"Reminder check: nothing due right now "
            f"(checked {result['candidates_checked']} upcoming/recent event(s)).",
            "info",
        )
    return redirect(url_for("admin.events"))


# ---------------------------------------------------------------------------
# Requests (Staff change-request review queue)
# ---------------------------------------------------------------------------
class _RequestApplyError(Exception):
    """Raised when an approved request's payload can no longer be applied —
    e.g. a group or member it referenced was deleted after the request was
    submitted. Caught in request_approve() to show a friendly flash instead
    of a 500, leaving the request untouched (still pending) so an Admin can
    edit the payload's assumptions out of the picture and reject it, or ask
    Staff to resubmit."""


def _apply_message_request(payload, submitted_by_user_id):
    target_group_id = payload.get("target_group_id") or None
    if target_group_id and Group.query.get(target_group_id) is None:
        raise _RequestApplyError("the target group no longer exists.")

    message = Message(
        title=(payload.get("title") or "").strip(),
        content=(payload.get("content") or "").strip(),
        user_id=submitted_by_user_id,
        target_group_id=target_group_id,
    )
    db.session.add(message)
    return message


def _apply_group_event_request(payload):
    group_id = payload.get("group_id")
    group = Group.query.get(group_id) if group_id else None
    if group is None:
        raise _RequestApplyError("the target group no longer exists.")

    user_id = payload.get("user_id") or None
    error = validate_attribution(group_id, user_id)
    if error:
        raise _RequestApplyError(error)

    event = GroupEvent(
        group_id=group_id,
        user_id=user_id,
        type=payload.get("type"),
        name=(payload.get("name") or "").strip(),
        description=payload.get("description"),
        value=payload.get("value"),
    )
    db.session.add(event)
    db.session.flush()
    group.recompute_points()


def _apply_event_request(payload):
    time_str = payload.get("time")
    try:
        event_time = datetime.fromisoformat(time_str) if time_str else None
    except ValueError:
        event_time = None
    if event_time is None:
        raise _RequestApplyError("the event's date/time couldn't be read.")

    event = Event(
        name=(payload.get("name") or "").strip(),
        description=payload.get("description"),
        time=event_time,
    )
    db.session.add(event)


@admin_bp.route("/requests")
@login_required
@role_required(Role.ADMIN)
def requests_list():
    status_filter = request.args.get("status", default="pending")
    query = ChangeRequest.query
    if status_filter in (RequestStatus.PENDING, RequestStatus.APPROVED, RequestStatus.REJECTED):
        query = query.filter_by(status=status_filter)
    else:
        status_filter = "all"

    all_requests = query.order_by(ChangeRequest.created_at.desc()).all()
    pending_count = ChangeRequest.query.filter_by(status=RequestStatus.PENDING).count()
    reject_form = ReviewRejectForm()
    approve_form = ConfirmDeleteForm()  # CSRF-only, reused as a generic "confirm" form
    from app.live import compute_signal

    return render_template(
        "admin/requests.html",
        requests=all_requests,
        requests_version=compute_signal("requests", current_user),
        status_filter=status_filter,
        pending_count=pending_count,
        reject_form=reject_form,
        approve_form=approve_form,
    )


@admin_bp.route("/requests/<int:request_id>/approve", methods=["POST"])
@login_required
@role_required(Role.ADMIN)
def request_approve(request_id):
    form = ConfirmDeleteForm()
    if not form.validate_on_submit():
        abort(400)

    cr = ChangeRequest.query.get_or_404(request_id)
    if cr.status != RequestStatus.PENDING:
        flash("That request has already been reviewed.", "error")
        return redirect(url_for("admin.requests_list"))

    payload = cr.payload or {}
    applied_message = None
    try:
        if cr.target_type == RequestTargetType.MESSAGE:
            applied_message = _apply_message_request(payload, cr.submitted_by_user_id)
        elif cr.target_type == RequestTargetType.GROUP_EVENT:
            _apply_group_event_request(payload)
        elif cr.target_type == RequestTargetType.EVENT:
            _apply_event_request(payload)
        else:
            raise _RequestApplyError("this request's type isn't recognized.")
    except _RequestApplyError as exc:
        db.session.rollback()
        flash(f"Couldn't approve — {exc}", "error")
        return redirect(url_for("admin.requests_list"))

    cr.status = RequestStatus.APPROVED
    cr.reviewed_by_user_id = current_user.user_id
    cr.reviewed_at = datetime.utcnow()
    db.session.commit()
    if applied_message is not None:
        notify_new_message(applied_message)
    flash("Request approved — the change is now live.", "success")
    return redirect(url_for("admin.requests_list"))


@admin_bp.route("/requests/<int:request_id>/reject", methods=["POST"])
@login_required
@role_required(Role.ADMIN)
def request_reject(request_id):
    form = ReviewRejectForm()
    if not form.validate_on_submit():
        abort(400)

    cr = ChangeRequest.query.get_or_404(request_id)
    if cr.status != RequestStatus.PENDING:
        flash("That request has already been reviewed.", "error")
        return redirect(url_for("admin.requests_list"))

    cr.status = RequestStatus.REJECTED
    cr.reviewed_by_user_id = current_user.user_id
    cr.reviewed_at = datetime.utcnow()
    cr.review_reason = (form.reason.data or "").strip() or None
    db.session.commit()
    flash("Request rejected.", "info")
    return redirect(url_for("admin.requests_list"))
