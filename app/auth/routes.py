# -*- coding: utf-8 -*-
from datetime import datetime, date

from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db, limiter
from app.forms import LoginForm, RegistrationForm
from app.models import User, RoleEnum, CamperProfile, log_action

bp = Blueprint("auth", __name__, template_folder="../templates/auth")


def redirect_for_role(user: User):
    """Ridrejton përdoruesin te paneli i duhur sipas rolit të tij."""
    if user.is_superuser:
        return redirect(url_for("superuser.dashboard"))
    if user.role == RoleEnum.ADMIN:
        return redirect(url_for("admin.dashboard"))
    if user.role == RoleEnum.STAFF:
        return redirect(url_for("staff.dashboard"))
    return redirect(url_for("kampist.dashboard"))


@bp.route("/kycu", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect_for_role(current_user)

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.is_active_account and user.check_password(form.password.data):
            login_user(user, remember=False)
            user.last_login_at = datetime.utcnow()
            db.session.commit()
            log_action(user.id, "login", ip_address=request.remote_addr)
            return redirect_for_role(user)
        flash("Email ose fjalëkalim i gabuar.", "danger")
    return render_template("auth/login.html", form=form)


@bp.route("/dil")
@login_required
def logout():
    log_action(current_user.id, "logout")
    logout_user()
    session.pop("rules_accepted", None)
    flash("U çkyçe me sukses.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/rregullat")
def rules():
    """Faqja e rregullave. Duhet lexuar deri në fund para se të vazhdohet
    te regjistrimi (kontrolli i plotë kryhet edhe në backend te register())."""
    return render_template("auth/rules.html")


@bp.route("/rregullat/prano", methods=["POST"])
def accept_rules():
    session["rules_accepted"] = True
    session["rules_accepted_at"] = datetime.utcnow().isoformat()
    return {"ok": True}


@bp.route("/regjistrohu", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def register():
    # Kërkesë e detyrueshme: rregullat duhen pranuar përpara regjistrimit.
    if not session.get("rules_accepted"):
        flash("Duhet të lexosh dhe pranosh rregullat e kampit para regjistrimit.", "info")
        return redirect(url_for("auth.rules"))

    form = RegistrationForm()
    if request.method == "GET":
        form.rules_accepted.data = "yes"

    if form.validate_on_submit():
        existing = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if existing:
            flash("Ky email është regjistruar tashmë.", "danger")
            return render_template("auth/register.html", form=form)

        age = getattr(form, "_computed_age", None)
        is_minor = bool(age is not None and age < 18)

        user = User(email=form.email.data.lower().strip(), phone=form.phone.data, role=RoleEnum.KAMPIST)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()

        profile = CamperProfile(
            user_id=user.id,
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
            birth_date=form.birth_date.data,
            age=age if age is not None else 0,
            gender=form.gender.data,
            address=form.address.data,
            city=form.city.data,
            emergency_contact_name=form.emergency_contact_name.data,
            emergency_contact_phone=form.emergency_contact_phone.data,
            attended_before=(form.attended_before.data == "po"),
            times_attended=form.times_attended.data,
            last_year_attended=form.last_year_attended.data,
            has_allergies=(form.has_allergies.data == "po"),
            allergies_description=form.allergies_description.data,
            health_notes=form.health_notes.data,
            takes_medication=(form.takes_medication.data == "po"),
            medication_name=form.medication_name.data,
            medication_instructions=form.medication_instructions.data,
            dietary_requirement=form.dietary_requirement.data,
            dietary_other=form.dietary_other.data,
            talent_description=form.talent_description.data,
            shirt_size=form.shirt_size.data,
            is_minor=is_minor,
            guardian_name=form.guardian_name.data if is_minor else None,
            guardian_phone=form.guardian_phone.data if is_minor else None,
            guardian_email=form.guardian_email.data if is_minor else None,
            guardian_address=form.guardian_address.data if is_minor else None,
            guardian_signature=form.guardian_signature.data if is_minor else None,
            guardian_consent_date=form.guardian_consent_date.data if is_minor else None,
            accepted_info_accurate=form.accepted_info_accurate.data,
            accepted_rules=form.accepted_rules.data,
            accepted_safety_notice=form.accepted_safety_notice.data,
            accepted_media_release=form.accepted_media_release.data,
            accepted_privacy_policy=form.accepted_privacy_policy.data,
            rules_read_at=datetime.utcnow(),
        )
        db.session.add(profile)
        db.session.commit()
        log_action(user.id, "registered", "User", user.id, ip_address=request.remote_addr)

        session.pop("rules_accepted", None)
        login_user(user)
        flash("Regjistrimi u krye me sukses! Mirë se erdhe në Eagles of Hope.", "success")
        return redirect(url_for("kampist.dashboard"))

    return render_template("auth/register.html", form=form)
