"""Shared choice-list builders and cross-role validation for the
group/room/user select fields used by both Admin CRUD (app/admin/routes.py)
and the Staff change-request workflow (app/staff/routes.py, Stage 6).

Pulling these out of app/admin/routes.py means Staff's request forms show
the exact same options an Admin would see filling out the same form
directly, and a request's attribution is checked with the same rule in
both places: when it's submitted, and again at approval time (since a
group's membership may have changed in between).
"""

from app.models import Group, Room, Building, User

NONE_CHOICE = (0, "—")


def group_choices():
    groups = Group.query.order_by(Group.name).all()
    return [NONE_CHOICE] + [(g.group_id, g.name) for g in groups]


def room_choices(current_room_id=None):
    """Rooms available for assignment: not full, or the given room (so
    editing a user doesn't force you off their own room just because it's
    at capacity)."""
    rooms = Room.query.join(Building).order_by(Building.name, Room.number).all()
    choices = [NONE_CHOICE]
    for r in rooms:
        if r.room_id == current_room_id or not r.is_full:
            label = f"{r.building.name} · {r.number} ({r.occupant_count}/{r.capacity})"
            choices.append((r.room_id, label))
    return choices


def user_choices_for_attribution():
    """All users, labelled with their current group, so a Point/Penalty can
    be attributed to a specific member. `validate_attribution` below
    enforces that the chosen member actually belongs to the chosen group."""
    users = User.query.order_by(User.name, User.surname).all()
    choices = [NONE_CHOICE]
    for u in users:
        group_label = u.group.name if u.group else "no group"
        choices.append((u.user_id, f"{u.full_name} ({group_label})"))
    return choices


def audience_choices():
    groups = Group.query.order_by(Group.name).all()
    return [(0, "Everyone (broadcast)")] + [(g.group_id, g.name) for g in groups]


def validate_attribution(group_id, user_id):
    """Returns an error message if `user_id` doesn't belong to `group_id`,
    else None. `user_id` of 0/None means "whole group" and is always fine."""
    if not user_id:
        return None
    user = User.query.get(user_id)
    if user is None:
        return "Selected member no longer exists."
    if user.group_id != group_id:
        return f"{user.full_name} isn't a member of the selected group."
    return None
