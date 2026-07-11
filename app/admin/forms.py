from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SelectField,
    IntegerField,
    SubmitField,
    TextAreaField,
    DateTimeLocalField,
)
from wtforms.validators import DataRequired, Optional, Length, NumberRange, ValidationError

from app.models import Role, GroupEventType


# A shared "no selection" sentinel for optional SelectFields backed by
# integer FKs (group_id / room_id). WTForms SelectField coerce=int needs a
# real int choice, so we use 0 and translate 0 <-> None in the route.
NONE_CHOICE = (0, "—")


class UserForm(FlaskForm):
    name = StringField("First name", validators=[DataRequired(), Length(max=30)])
    surname = StringField("Surname", validators=[Optional(), Length(max=30)])
    username = StringField("Username", validators=[DataRequired(), Length(max=50)])
    password = PasswordField(
        "Password",
        validators=[Optional(), Length(min=4, message="Password must be at least 4 characters.")],
    )
    role = SelectField("Role", choices=Role.choices(), coerce=int, validators=[DataRequired()])
    group_id = SelectField("Group", coerce=int, validators=[Optional()])
    room_id = SelectField("Room", coerce=int, validators=[Optional()])
    submit = SubmitField("Save")

    def __init__(self, *args, is_create=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_create = is_create

    def validate_password(self, field):
        if self.is_create and not field.data:
            raise ValidationError("Password is required for a new account.")


class GroupForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=50)])
    color = StringField(
        "Color",
        validators=[Optional(), Length(max=10)],
        render_kw={"placeholder": "#2f7a4f or leave blank"},
    )
    submit = SubmitField("Save")


class BuildingForm(FlaskForm):
    name = StringField("Building name", validators=[DataRequired(), Length(max=50)])
    submit = SubmitField("Save")


class RoomForm(FlaskForm):
    building_id = SelectField("Building", coerce=int, validators=[DataRequired()])
    number = StringField("Room number", validators=[DataRequired(), Length(max=20)])
    capacity = IntegerField(
        "Capacity", validators=[DataRequired(), NumberRange(min=1, max=50)], default=4
    )
    submit = SubmitField("Save")


class GroupEventForm(FlaskForm):
    """A points/penalties ledger entry (spec §2.2.2 / §3). Group-wide by
    default; optionally attributed to one member of that same group."""

    group_id = SelectField("Group", coerce=int, validators=[DataRequired()])
    user_id = SelectField(
        "Attribute to a member (optional)", coerce=int, validators=[Optional()]
    )
    type = SelectField(
        "Type",
        choices=[
            (GroupEventType.POINT.value, "Point (+)"),
            (GroupEventType.PENALTY.value, "Penalty (−)"),
        ],
        coerce=int,
        validators=[DataRequired()],
    )
    name = StringField("Name", validators=[DataRequired(), Length(max=30)])
    description = TextAreaField(
        "Reason / description", validators=[Optional(), Length(max=2000)]
    )
    value = IntegerField(
        "Value",
        validators=[DataRequired(), NumberRange(min=1, max=10000)],
        render_kw={"placeholder": "Enter as a positive number — sign comes from Type above"},
    )
    submit = SubmitField("Save")


class MessageForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=100)])
    content = TextAreaField("Content", validators=[DataRequired(), Length(max=4000)])
    target_group_id = SelectField(
        "Audience", coerce=int, validators=[Optional()]
    )
    submit = SubmitField("Post")


class EventForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=100)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])
    time = DateTimeLocalField(
        "Date & time", format="%Y-%m-%dT%H:%M", validators=[DataRequired()]
    )
    submit = SubmitField("Save")


class ConfirmDeleteForm(FlaskForm):
    """CSRF-only form backing every delete button (spec: no bare GET deletes)."""

    submit = SubmitField("Delete")


class ReviewRejectForm(FlaskForm):
    """Backs the "Reject" action on a pending Staff change request
    (Stage 6). The reason is optional but shown back to the submitting
    Staff member on their Requests page."""

    reason = TextAreaField(
        "Reason (optional)", validators=[Optional(), Length(max=1000)]
    )
    submit = SubmitField("Reject")
