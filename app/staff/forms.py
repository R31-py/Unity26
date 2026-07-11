from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    SelectField,
    IntegerField,
    SubmitField,
    TextAreaField,
    DateTimeLocalField,
)
from wtforms.validators import DataRequired, Optional, Length, NumberRange

from app.models import GroupEventType


class RequestMessageForm(FlaskForm):
    """Mirrors admin.forms.MessageForm — same fields, but submitting this
    creates a ChangeRequest (target_type=message) instead of a live
    Message. Admin approval is what actually posts it."""

    title = StringField("Title", validators=[DataRequired(), Length(max=100)])
    content = TextAreaField("Content", validators=[DataRequired(), Length(max=4000)])
    target_group_id = SelectField("Audience", coerce=int, validators=[Optional()])
    submit = SubmitField("Submit for approval")


class RequestGroupEventForm(FlaskForm):
    """Mirrors admin.forms.GroupEventForm — same fields, but submitting
    this creates a ChangeRequest (target_type=group_event) instead of a
    live GroupEvent ledger entry."""

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
    submit = SubmitField("Submit for approval")


class RequestEventForm(FlaskForm):
    """Mirrors admin.forms.EventForm — same fields, but submitting this
    creates a ChangeRequest (target_type=event) instead of a live Event."""

    name = StringField("Name", validators=[DataRequired(), Length(max=100)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])
    time = DateTimeLocalField(
        "Date & time", format="%Y-%m-%dT%H:%M", validators=[DataRequired()]
    )
    submit = SubmitField("Submit for approval")
