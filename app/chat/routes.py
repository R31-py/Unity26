# -*- coding: utf-8 -*-
import bleach
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import (
    RoleEnum, StaffPermission, ChatRoom, ChatRoomType, ChatMessage, ChatBlock, log_action,
)

bp = Blueprint("chat", __name__, template_folder="../templates/chat")


def _can_access_room(user, room: ChatRoom) -> bool:
    if user.is_superuser:
        return False  # superuser sheh vetëm nga paneli i vet, jo këtu
    if user.role == RoleEnum.ADMIN:
        return True
    if room.room_type == ChatRoomType.STAFF:
        return user.role == RoleEnum.STAFF
    if room.room_type == ChatRoomType.GROUP:
        if user.role == RoleEnum.STAFF:
            return True  # stafi mund të shohë çdo chat grupi (moderim/mbikëqyrje)
        profile = user.camper_profile
        return bool(profile and profile.group_id == room.group_id)
    return False


def _can_moderate(user) -> bool:
    if user.role == RoleEnum.ADMIN:
        return True
    if user.role == RoleEnum.STAFF:
        return user.has_permission(StaffPermission.MODERATE_CHAT)
    return False


@bp.route("/dhoma/<int:room_id>")
@login_required
def view_room(room_id):
    room = ChatRoom.query.get_or_404(room_id)
    if not _can_access_room(current_user, room):
        abort(403)

    can_moderate = _can_moderate(current_user)
    blocked = ChatBlock.query.filter_by(room_id=room.id, user_id=current_user.id).first() is not None
    # Stafi/admin që s'janë pjesë e vetë grupit shohin vetëm-lexim (mbikëqyrje).
    read_only = current_user.role == RoleEnum.STAFF and not (
        current_user.camper_profile
    ) and room.room_type == ChatRoomType.GROUP and not can_moderate

    messages = room.messages
    return render_template(
        "chat/room.html", room=room, messages=messages,
        can_moderate=can_moderate, blocked=blocked, read_only=read_only,
    )


@bp.route("/dhoma/<int:room_id>/dergo", methods=["POST"])
@login_required
def send_message(room_id):
    room = ChatRoom.query.get_or_404(room_id)
    if not _can_access_room(current_user, room):
        abort(403)
    if ChatBlock.query.filter_by(room_id=room.id, user_id=current_user.id).first():
        flash("Je bllokuar nga ky chat.", "danger")
        return redirect(url_for("chat.view_room", room_id=room.id))

    body = bleach.clean(request.form.get("body", "").strip(), tags=[], strip=True)
    if not body:
        return redirect(url_for("chat.view_room", room_id=room.id))
    if len(body) > 2000:
        body = body[:2000]

    msg = ChatMessage(room_id=room.id, sender_id=current_user.id, body=body)
    db.session.add(msg)
    db.session.commit()
    return redirect(url_for("chat.view_room", room_id=room.id))


@bp.route("/mesazhi/<int:message_id>/fshij", methods=["POST"])
@login_required
def delete_message(message_id):
    msg = ChatMessage.query.get_or_404(message_id)
    if not _can_moderate(current_user):
        abort(403)
    msg.is_deleted = True
    msg.body = "[Mesazhi u fshi nga një moderator]"
    msg.deleted_by_id = current_user.id
    db.session.commit()
    log_action(current_user.id, "chat_message_deleted", "ChatMessage", msg.id)
    return redirect(url_for("chat.view_room", room_id=msg.room_id))


@bp.route("/dhoma/<int:room_id>/blloko/<int:user_id>", methods=["POST"])
@login_required
def block_user(room_id, user_id):
    if not _can_moderate(current_user):
        abort(403)
    room = ChatRoom.query.get_or_404(room_id)
    if not ChatBlock.query.filter_by(room_id=room.id, user_id=user_id).first():
        db.session.add(ChatBlock(room_id=room.id, user_id=user_id, blocked_by_id=current_user.id))
        db.session.commit()
        log_action(current_user.id, "chat_user_blocked", "ChatRoom", room.id, details=str(user_id))
    flash("Përdoruesi u bllokua nga ky chat.", "success")
    return redirect(url_for("chat.view_room", room_id=room.id))
