# -*- coding: utf-8 -*-
from flask import Blueprint, render_template

from app.decorators import superuser_required
from app.models import (
    User, RoleEnum, Group, Room, ChatRoom, ChatMessage, Announcement, AuditLog,
)

bp = Blueprint("superuser", __name__, template_folder="../templates/superuser")

# Shënim sigurie: çdo route këtu është VETËM-LEXIM me qëllim. Superuser nuk
# duhet të mund të ndryshojë të dhëna nëpërmjet këtij paneli - shiko
# app/decorators.py::superuser_required (kthen 404, jo 403, nëse s'je superuser
# në mënyrë që as ekzistenca e panelit të mos zbulohet).


@bp.route("/")
@superuser_required
def dashboard():
    stats = {
        "total_users": User.query.count(),
        "campers": User.query.filter_by(role=RoleEnum.KAMPIST).count(),
        "staff": User.query.filter_by(role=RoleEnum.STAFF).count(),
        "admins": User.query.filter_by(role=RoleEnum.ADMIN, is_superuser=False).count(),
        "groups": Group.query.count(),
        "rooms": Room.query.count(),
        "chat_rooms": ChatRoom.query.count(),
        "announcements": Announcement.query.count(),
    }
    return render_template("superuser/dashboard.html", stats=stats)


@bp.route("/perdorues")
@superuser_required
def users():
    all_users = User.query.filter_by(is_superuser=False).order_by(User.created_at.desc()).all()
    return render_template("superuser/users.html", users=all_users)


@bp.route("/grupet")
@superuser_required
def groups():
    all_groups = Group.query.order_by(Group.name).all()
    return render_template("superuser/groups.html", groups=all_groups)


@bp.route("/dhomat")
@superuser_required
def rooms():
    from app.models import Building
    buildings = Building.query.order_by(Building.name).all()
    return render_template("superuser/rooms.html", buildings=buildings)


@bp.route("/chat")
@superuser_required
def chat_overview():
    all_rooms = ChatRoom.query.all()
    message_counts = {r.id: ChatMessage.query.filter_by(room_id=r.id).count() for r in all_rooms}
    return render_template("superuser/chat_overview.html", rooms=all_rooms, message_counts=message_counts)


@bp.route("/njoftimet")
@superuser_required
def announcements():
    all_announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template("superuser/announcements.html", announcements=all_announcements)


@bp.route("/raportet")
@superuser_required
def reports():
    from app.models import CamperProfile
    dietary_counts = {}
    for p in CamperProfile.query.all():
        key = p.dietary_requirement or "asnje"
        dietary_counts[key] = dietary_counts.get(key, 0) + 1
    return render_template(
        "superuser/reports.html",
        dietary_counts=dietary_counts,
        allergy_count=CamperProfile.query.filter_by(has_allergies=True).count(),
        medication_count=CamperProfile.query.filter_by(takes_medication=True).count(),
        total_campers=CamperProfile.query.count(),
    )


@bp.route("/audit-log")
@superuser_required
def audit_log():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template("superuser/audit_log.html", logs=logs)
