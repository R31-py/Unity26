# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.decorators import roles_required, permission_required
from app.models import (
    RoleEnum, StaffPermission, Group, Announcement, AnnouncementAudience,
    Poll, PollOption, CamperProfile, log_action, visible_users_query,
)

bp = Blueprint("staff", __name__, template_folder="../templates/staff")


@bp.route("/paneli")
@login_required
@roles_required(RoleEnum.STAFF)
def dashboard():
    my_group = Group.query.filter_by(leader_id=current_user.id).first()
    perms = {p.permission.value for p in current_user.staff_permissions}
    return render_template("staff/dashboard.html", my_group=my_group, perms=perms)


@bp.route("/pikët/<int:group_id>", methods=["POST"])
@login_required
@permission_required(StaffPermission.MANAGE_POINTS)
def manage_points(group_id):
    group = Group.query.get_or_404(group_id)
    delta = request.form.get("delta", type=int, default=0)
    group.points = max(0, group.points + delta)
    db.session.commit()
    log_action(current_user.id, "points_updated", "Group", group.id, details=str(delta))
    flash(f"Pikët e grupit '{group.name}' u përditësuan.", "success")
    return redirect(url_for("staff.dashboard"))


@bp.route("/penalitete/<int:group_id>", methods=["POST"])
@login_required
@permission_required(StaffPermission.MANAGE_PENALTIES)
def manage_penalties(group_id):
    group = Group.query.get_or_404(group_id)
    delta = request.form.get("delta", type=int, default=0)
    group.penalties = max(0, group.penalties + delta)
    db.session.commit()
    log_action(current_user.id, "penalties_updated", "Group", group.id, details=str(delta))
    flash(f"Penalitetet e grupit '{group.name}' u përditësuan.", "success")
    return redirect(url_for("staff.dashboard"))


@bp.route("/njoftim", methods=["POST"])
@login_required
@permission_required(StaffPermission.SEND_ANNOUNCEMENTS)
def send_announcement():
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()
    audience = request.form.get("audience", "all")
    if not title or not body:
        flash("Titulli dhe përmbajtja janë të detyrueshme.", "danger")
        return redirect(url_for("staff.dashboard"))

    ann = Announcement(
        title=title, body=body,
        audience=AnnouncementAudience(audience if audience in [a.value for a in AnnouncementAudience] else "all"),
        created_by_id=current_user.id,
        is_emergency=bool(request.form.get("is_emergency")),
    )
    if ann.audience == AnnouncementAudience.GROUP:
        ann.target_group_id = request.form.get("target_group_id", type=int)
    db.session.add(ann)
    db.session.commit()
    log_action(current_user.id, "announcement_sent", "Announcement", ann.id)
    flash("Njoftimi u dërgua.", "success")
    return redirect(url_for("staff.dashboard"))


@bp.route("/pyetesor/krijo", methods=["POST"])
@login_required
@permission_required(StaffPermission.CREATE_POLLS)
def create_poll():
    question = request.form.get("question", "").strip()
    options = [o.strip() for o in request.form.getlist("option") if o.strip()]
    if not question or len(options) < 2:
        flash("Pyetja dhe të paktën 2 opsione janë të detyrueshme.", "danger")
        return redirect(url_for("staff.dashboard"))

    poll = Poll(question=question, created_by_id=current_user.id)
    db.session.add(poll)
    db.session.flush()
    for opt in options:
        db.session.add(PollOption(poll_id=poll.id, text=opt))
    db.session.commit()
    log_action(current_user.id, "poll_created", "Poll", poll.id)
    flash("Pyetësori u krijua.", "success")
    return redirect(url_for("staff.dashboard"))


@bp.route("/emergjenca")
@login_required
@permission_required(StaffPermission.VIEW_EMERGENCY_INFO)
def emergency_info():
    campers = visible_users_query().join(CamperProfile).filter(
        CamperProfile.id.isnot(None)
    ).all()
    return render_template("staff/emergency.html", campers=campers)


@bp.route("/prania")
@login_required
@permission_required(StaffPermission.MANAGE_ATTENDANCE)
def attendance():
    my_group = Group.query.filter_by(leader_id=current_user.id).first()
    return render_template("staff/attendance.html", my_group=my_group)