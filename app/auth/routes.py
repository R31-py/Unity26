from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from app.auth.forms import LoginForm
from app.models import User, Role

auth_bp = Blueprint("auth", __name__)


def _dashboard_url_for(user):
    if user.role == Role.ADMIN.value:
        return url_for("admin.dashboard")
    if user.role == Role.STAFF.value:
        return url_for("staff.dashboard")
    return url_for("user.dashboard")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_dashboard_url_for(current_user))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password.", "error")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=form.remember_me.data)
        next_url = request.args.get("next")
        # Never trust an open 'next' redirect target
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect(_dashboard_url_for(user))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You've been logged out.", "info")
    return redirect(url_for("auth.login"))
