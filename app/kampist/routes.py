# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.decorators import roles_required
from app.models import (
    RoleEnum, Poll, PollVote, Announcement, AnnouncementAudience, User, ScheduleItem, log_action,
)
from app.utils import verse_of_the_day

bp = Blueprint("kampist", __name__, template_folder="../templates/kampist")


@bp.route("/paneli")
@login_required
@roles_required(RoleEnum.KAMPIST)
def dashboard():
    profile = current_user.camper_profile
    group = profile.group if profile else None
    room = profile.room if profile else None

    roommates = []
    if room:
        roommates = [p for p in room.occupants if p.id != (profile.id if profile else None)]

    open_polls = Poll.query.filter_by(is_open=True).order_by(Poll.created_at.desc()).limit(5).all()
    answered_poll_ids = {
        v.option.poll_id
        for v in PollVote.query.filter_by(user_id=current_user.id).all()
    }

    announcements = (
        Announcement.query.filter(
            db.or_(
                Announcement.audience == AnnouncementAudience.ALL,
                db.and_(
                    Announcement.audience == AnnouncementAudience.GROUP,
                    Announcement.target_group_id == (group.id if group else -1),
                ),
                db.and_(
                    Announcement.audience == AnnouncementAudience.SINGLE_USER,
                    Announcement.target_user_id == current_user.id,
                ),
            )
        )
        .order_by(Announcement.created_at.desc())
        .limit(10)
        .all()
    )

    admins = User.query.filter_by(role=RoleEnum.ADMIN, is_superuser=False, is_active_account=True).all()
    schedule_items = ScheduleItem.query.order_by(ScheduleItem.day_label, ScheduleItem.sort_order).all()

    verse_ref, verse_text = verse_of_the_day()

    return render_template(
        "kampist/dashboard.html",
        profile=profile,
        group=group,
        room=room,
        roommates=roommates,
        open_polls=open_polls,
        answered_poll_ids=answered_poll_ids,
        announcements=announcements,
        admins=admins,
        schedule_items=schedule_items,
        verse_ref=verse_ref,
        verse_text=verse_text,
    )


@bp.route("/pyetesor/<int:poll_id>/voto", methods=["POST"])
@login_required
@roles_required(RoleEnum.KAMPIST)
def vote_poll(poll_id):
    from flask import request
    from app.models import PollOption

    poll = Poll.query.get_or_404(poll_id)
    if not poll.is_open:
        flash("Ky pyetësor është mbyllur.", "info")
        return redirect(url_for("kampist.dashboard"))

    already = PollVote.query.join(PollOption).filter(
        PollOption.poll_id == poll.id, PollVote.user_id == current_user.id
    ).first()
    if already:
        flash("Ke përgjigjur tashmë këtë pyetësor.", "info")
        return redirect(url_for("kampist.dashboard"))

    option_id = request.form.get("option_id", type=int)
    option = PollOption.query.filter_by(id=option_id, poll_id=poll.id).first()
    if not option:
        flash("Opsion i pavlefshëm.", "danger")
        return redirect(url_for("kampist.dashboard"))

    db.session.add(PollVote(option_id=option.id, user_id=current_user.id))
    db.session.commit()
    log_action(current_user.id, "poll_voted", "Poll", poll.id)
    flash("Përgjigja u ruajt. Faleminderit!", "success")
    return redirect(url_for("kampist.dashboard"))
