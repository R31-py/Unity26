# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.decorators import roles_required
from app.models import (
    RoleEnum, StaffPermission, StaffPermissionGrant, User, Group, Building, Room,
    CamperProfile, Announcement, AnnouncementAudience, ChatRoom, ChatRoomType,
    ScheduleItem, log_action, visible_users_query,
)

bp = Blueprint("admin", __name__, template_folder="../templates/admin")


def _require_admin():
    """Aplikohet te çdo route më poshtë nëpërmjet dekoratorit roles_required."""


@bp.route("/paneli")
@login_required
@roles_required(RoleEnum.ADMIN)
def dashboard():
    stats = {
        "total_campers": visible_users_query().filter_by(role=RoleEnum.KAMPIST).count(),
        "total_staff": visible_users_query().filter_by(role=RoleEnum.STAFF).count(),
        "total_groups": Group.query.count(),
        "total_rooms": Room.query.count(),
        "unassigned_campers": CamperProfile.query.filter(CamperProfile.group_id.is_(None)).count(),
    }
    from app.models import AuditLog
    recent_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(10).all()
    return render_template("admin/dashboard.html", stats=stats, recent_logs=recent_logs)


# ---------------------------------------------------------------------------
# Përdoruesit
# ---------------------------------------------------------------------------
@bp.route("/perdorues")
@login_required
@roles_required(RoleEnum.ADMIN)
def users():
    q = visible_users_query().order_by(User.created_at.desc())
    role_filter = request.args.get("role")
    if role_filter in [r.value for r in RoleEnum]:
        q = q.filter(User.role == RoleEnum(role_filter))
    all_users = q.all()
    all_permissions = list(StaffPermission)
    return render_template("admin/users.html", users=all_users, all_permissions=all_permissions)


@bp.route("/perdorues/<int:user_id>/bej-staf", methods=["POST"])
@login_required
@roles_required(RoleEnum.ADMIN)
def make_staff(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_superuser:
        flash("Nuk mund të ndryshosh këtë llogari.", "danger")
        return redirect(url_for("admin.users"))
    user.role = RoleEnum.STAFF
    db.session.commit()
    log_action(current_user.id, "user_promoted_to_staff", "User", user.id)
    flash(f"{user.full_name} u bë staf.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/perdorues/<int:user_id>/leje", methods=["POST"])
@login_required
@roles_required(RoleEnum.ADMIN)
def update_permissions(user_id):
    user = User.query.get_or_404(user_id)
    if user.role != RoleEnum.STAFF:
        flash("Vetëm anëtarëve të stafit mund t'u caktohen leje.", "danger")
        return redirect(url_for("admin.users"))

    selected = set(request.form.getlist("permissions"))
    current = {g.permission.value: g for g in user.staff_permissions}

    # Shto lejet e reja
    for perm in StaffPermission:
        if perm.value in selected and perm.value not in current:
            db.session.add(StaffPermissionGrant(user_id=user.id, permission=perm, granted_by_id=current_user.id))
    # Hiq lejet e hequra
    for perm_value, grant in current.items():
        if perm_value not in selected:
            db.session.delete(grant)

    db.session.commit()
    log_action(current_user.id, "permissions_updated", "User", user.id, details=",".join(selected))
    flash(f"Lejet e {user.full_name} u përditësuan.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/perdorues/<int:user_id>/aktivizim", methods=["POST"])
@login_required
@roles_required(RoleEnum.ADMIN)
def toggle_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_superuser or user.id == current_user.id:
        flash("Nuk mund të ndryshosh këtë llogari.", "danger")
        return redirect(url_for("admin.users"))
    user.is_active_account = not user.is_active_account
    db.session.commit()
    log_action(current_user.id, "user_active_toggled", "User", user.id, details=str(user.is_active_account))
    flash(f"Llogaria e {user.full_name} u {'aktivizua' if user.is_active_account else 'çaktivizua'}.", "success")
    return redirect(url_for("admin.users"))


# ---------------------------------------------------------------------------
# Grupet
# ---------------------------------------------------------------------------
@bp.route("/grupet")
@login_required
@roles_required(RoleEnum.ADMIN)
def groups():
    all_groups = Group.query.order_by(Group.name).all()
    staff_members = visible_users_query().filter_by(role=RoleEnum.STAFF).all()
    unassigned = CamperProfile.query.filter(CamperProfile.group_id.is_(None)).all()
    return render_template(
        "admin/groups.html", groups=all_groups, staff_members=staff_members, unassigned=unassigned
    )


@bp.route("/grupet/krijo", methods=["POST"])
@login_required
@roles_required(RoleEnum.ADMIN)
def create_group():
    name = request.form.get("name", "").strip()
    color = request.form.get("color", "#3E7C5A")
    if not name:
        flash("Emri i grupit është i detyrueshëm.", "danger")
        return redirect(url_for("admin.groups"))

    group = Group(name=name, color=color)
    db.session.add(group)
    db.session.flush()
    db.session.add(ChatRoom(name=f"Chat - {name}", room_type=ChatRoomType.GROUP, group_id=group.id))
    db.session.commit()
    log_action(current_user.id, "group_created", "Group", group.id)
    flash(f"Grupi '{name}' u krijua me chat automatik.", "success")
    return redirect(url_for("admin.groups"))


@bp.route("/grupet/<int:group_id>/drejtues", methods=["POST"])
@login_required
@roles_required(RoleEnum.ADMIN)
def set_group_leader(group_id):
    group = Group.query.get_or_404(group_id)
    leader_id = request.form.get("leader_id", type=int)
    group.leader_id = leader_id or None
    db.session.commit()
    log_action(current_user.id, "group_leader_set", "Group", group.id, details=str(leader_id))
    flash(f"Drejtuesi i grupit '{group.name}' u përditësua.", "success")
    return redirect(url_for("admin.groups"))


@bp.route("/grupet/anetar", methods=["POST"])
@login_required
@roles_required(RoleEnum.ADMIN)
def assign_member():
    profile_id = request.form.get("profile_id", type=int)
    group_id = request.form.get("group_id", type=int)
    profile = CamperProfile.query.get_or_404(profile_id)
    profile.group_id = group_id or None
    db.session.commit()
    log_action(current_user.id, "member_assigned_group", "CamperProfile", profile.id, details=str(group_id))
    flash(f"{profile.first_name} u caktua në grup.", "success")
    return redirect(url_for("admin.groups"))


# ---------------------------------------------------------------------------
# Dhomat
# ---------------------------------------------------------------------------
@bp.route("/dhomat")
@login_required
@roles_required(RoleEnum.ADMIN)
def rooms():
    buildings = Building.query.order_by(Building.name).all()
    unassigned = CamperProfile.query.filter(CamperProfile.room_id.is_(None)).all()
    return render_template("admin/rooms.html", buildings=buildings, unassigned=unassigned)


@bp.route("/dhomat/ndertese", methods=["POST"])
@login_required
@roles_required(RoleEnum.ADMIN)
def create_building():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Emri i ndërtesës është i detyrueshëm.", "danger")
        return redirect(url_for("admin.rooms"))
    building = Building(name=name)
    db.session.add(building)
    db.session.commit()
    log_action(current_user.id, "building_created", "Building", building.id)
    flash(f"Ndërtesa '{name}' u krijua.", "success")
    return redirect(url_for("admin.rooms"))


@bp.route("/dhomat/krijo", methods=["POST"])
@login_required
@roles_required(RoleEnum.ADMIN)
def create_room():
    building_id = request.form.get("building_id", type=int)
    number = request.form.get("number", "").strip()
    capacity = request.form.get("capacity", type=int, default=4)
    if not building_id or not number:
        flash("Ndërtesa dhe numri i dhomës janë të detyrueshme.", "danger")
        return redirect(url_for("admin.rooms"))
    room = Room(building_id=building_id, number=number, capacity=capacity or 4)
    db.session.add(room)
    db.session.commit()
    log_action(current_user.id, "room_created", "Room", room.id)
    flash(f"Dhoma '{number}' u krijua.", "success")
    return redirect(url_for("admin.rooms"))


@bp.route("/dhomat/cakto", methods=["POST"])
@login_required
@roles_required(RoleEnum.ADMIN)
def assign_room():
    profile_id = request.form.get("profile_id", type=int)
    room_id = request.form.get("room_id", type=int)
    profile = CamperProfile.query.get_or_404(profile_id)

    if room_id:
        room = Room.query.get_or_404(room_id)
        current_occupancy = len(room.occupants)
        if current_occupancy >= room.capacity:
            flash(f"Dhoma '{room.number}' është plot.", "danger")
            return redirect(url_for("admin.rooms"))

    profile.room_id = room_id or None
    db.session.commit()
    log_action(current_user.id, "member_assigned_room", "CamperProfile", profile.id, details=str(room_id))
    flash(f"{profile.first_name} u caktua në dhomë.", "success")
    return redirect(url_for("admin.rooms"))


# ---------------------------------------------------------------------------
# Njoftimet
# ---------------------------------------------------------------------------
@bp.route("/njoftimet")
@login_required
@roles_required(RoleEnum.ADMIN)
def announcements():
    all_groups = Group.query.order_by(Group.name).all()
    history = Announcement.query.order_by(Announcement.created_at.desc()).limit(30).all()
    return render_template("admin/announcements.html", groups=all_groups, history=history)


@bp.route("/njoftimet/dergo", methods=["POST"])
@login_required
@roles_required(RoleEnum.ADMIN)
def send_announcement():
    from app.push_utils import send_push_to_users

    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()
    audience = request.form.get("audience", "all")
    if not title or not body:
        flash("Titulli dhe përmbajtja janë të detyrueshme.", "danger")
        return redirect(url_for("admin.announcements"))

    audience_enum = AnnouncementAudience(
        audience if audience in [a.value for a in AnnouncementAudience] else "all"
    )
    ann = Announcement(
        title=title, body=body, audience=audience_enum,
        created_by_id=current_user.id,
        is_emergency=bool(request.form.get("is_emergency")),
    )
    recipients = []
    if audience_enum == AnnouncementAudience.GROUP:
        ann.target_group_id = request.form.get("target_group_id", type=int)
        group = Group.query.get(ann.target_group_id)
        if group:
            recipients = [m.user for m in group.members]
    elif audience_enum == AnnouncementAudience.STAFF_ONLY:
        recipients = visible_users_query().filter_by(role=RoleEnum.STAFF).all()
    else:
        recipients = visible_users_query().filter(User.role != RoleEnum.ADMIN).all()

    db.session.add(ann)
    db.session.commit()
    log_action(current_user.id, "announcement_sent", "Announcement", ann.id)

    if recipients:
        send_push_to_users(recipients, title, body, url="/kampist/paneli")

    flash("Njoftimi u dërgua.", "success")
    return redirect(url_for("admin.announcements"))


# ---------------------------------------------------------------------------
# Raportet & Cilësimet
# ---------------------------------------------------------------------------
@bp.route("/raportet")
@login_required
@roles_required(RoleEnum.ADMIN)
def reports():
    all_groups = Group.query.order_by(Group.name).all()
    dietary_counts = {}
    for p in CamperProfile.query.all():
        key = p.dietary_requirement or "asnje"
        dietary_counts[key] = dietary_counts.get(key, 0) + 1
    allergy_count = CamperProfile.query.filter_by(has_allergies=True).count()
    medication_count = CamperProfile.query.filter_by(takes_medication=True).count()
    return render_template(
        "admin/reports.html",
        groups=all_groups,
        dietary_counts=dietary_counts,
        allergy_count=allergy_count,
        medication_count=medication_count,
    )


@bp.route("/cilesimet")
@login_required
@roles_required(RoleEnum.ADMIN)
def settings():
    return render_template("admin/settings.html")


# ---------------------------------------------------------------------------
# Orari
# ---------------------------------------------------------------------------
@bp.route("/orari")
@login_required
@roles_required(RoleEnum.ADMIN)
def schedule():
    items = ScheduleItem.query.order_by(ScheduleItem.day_label, ScheduleItem.sort_order).all()
    return render_template("admin/schedule.html", items=items)


@bp.route("/orari/krijo", methods=["POST"])
@login_required
@roles_required(RoleEnum.ADMIN)
def create_schedule_item():
    day_label = request.form.get("day_label", "").strip()
    time_label = request.form.get("time_label", "").strip()
    title = request.form.get("title", "").strip()
    if not day_label or not time_label or not title:
        flash("Dita, ora dhe titulli janë të detyrueshme.", "danger")
        return redirect(url_for("admin.schedule"))
    item = ScheduleItem(
        day_label=day_label, time_label=time_label, title=title,
        created_by_id=current_user.id,
    )
    db.session.add(item)
    db.session.commit()
    log_action(current_user.id, "schedule_item_created", "ScheduleItem", item.id)
    flash("Aktiviteti u shtua në orar.", "success")
    return redirect(url_for("admin.schedule"))


@bp.route("/orari/<int:item_id>/fshij", methods=["POST"])
@login_required
@roles_required(RoleEnum.ADMIN)
def delete_schedule_item(item_id):
    item = ScheduleItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    log_action(current_user.id, "schedule_item_deleted", "ScheduleItem", item_id)
    flash("Aktiviteti u hoq nga orari.", "success")
    return redirect(url_for("admin.schedule"))
