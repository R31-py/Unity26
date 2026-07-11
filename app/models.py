from datetime import datetime
from enum import IntEnum

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class Role(IntEnum):
    """Explicit role encoding (spec §2.2.7) — never compare raw ints elsewhere."""
    ADMIN = 1
    STAFF = 2
    USER = 3

    @classmethod
    def choices(cls):
        return [(r.value, r.name.title()) for r in cls]


class RequestStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RequestTargetType:
    MESSAGE = "message"
    GROUP_EVENT = "group_event"
    EVENT = "event"


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------
class Group(db.Model):
    __tablename__ = "groups"

    group_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(10))
    points = db.Column(db.Integer, default=0, nullable=False)

    users = db.relationship("User", back_populates="group")
    group_events = db.relationship(
        "GroupEvent", back_populates="group", cascade="all, delete-orphan"
    )
    messages = db.relationship("Message", back_populates="target_group")

    def recompute_points(self):
        """Recalculate the cached `points` total from this group's ledger
        of group_events (spec §2.2.2 attribution, §3 "group's total").
        Called by Admin points CRUD after any create/edit/delete so the
        stored column never drifts from the itemized entries that back it.
        Does not commit — caller is responsible for that.
        """
        total = 0
        for e in self.group_events:
            total += e.value if e.type == GroupEventType.POINT.value else -e.value
        self.points = total
        return self.points

    def __repr__(self):
        return f"<Group {self.name}>"


# ---------------------------------------------------------------------------
# Buildings & Rooms (spec §2.4)
# ---------------------------------------------------------------------------
class Building(db.Model):
    __tablename__ = "buildings"

    building_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)

    rooms = db.relationship(
        "Room", back_populates="building", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Building {self.name}>"


class Room(db.Model):
    __tablename__ = "rooms"

    room_id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(
        db.Integer, db.ForeignKey("buildings.building_id", ondelete="CASCADE"),
        nullable=False,
    )
    number = db.Column(db.String(20), nullable=False)
    capacity = db.Column(db.Integer, default=4, nullable=False)

    building = db.relationship("Building", back_populates="rooms")
    occupants = db.relationship("User", back_populates="room")

    @property
    def occupant_count(self):
        return len(self.occupants)

    @property
    def is_full(self):
        return self.occupant_count >= self.capacity

    def __repr__(self):
        return f"<Room {self.number} @ building {self.building_id}>"


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), nullable=False)
    surname = db.Column(db.String(30))
    role = db.Column(db.Integer, nullable=False, default=Role.USER.value)

    # --- login credentials (spec §2.2.1 — not in the original schema) ---
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    group_id = db.Column(
        db.Integer, db.ForeignKey("groups.group_id", ondelete="SET NULL"), nullable=True
    )
    room_id = db.Column(
        db.Integer, db.ForeignKey("rooms.room_id", ondelete="SET NULL"), nullable=True
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    group = db.relationship("Group", back_populates="users")
    room = db.relationship("Room", back_populates="occupants")

    messages_authored = db.relationship(
        "Message", back_populates="author", foreign_keys="Message.user_id"
    )
    push_subscriptions = db.relationship(
        "PushSubscription", back_populates="user", cascade="all, delete-orphan"
    )
    change_requests_submitted = db.relationship(
        "ChangeRequest",
        back_populates="submitted_by",
        foreign_keys="ChangeRequest.submitted_by_user_id",
    )

    # --- password helpers ---
    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    # --- Flask-Login required id ---
    def get_id(self):
        return str(self.user_id)

    # --- role helpers ---
    @property
    def role_enum(self):
        return Role(self.role)

    @property
    def is_admin(self):
        return self.role == Role.ADMIN.value

    @property
    def is_staff(self):
        return self.role == Role.STAFF.value

    @property
    def is_plain_user(self):
        return self.role == Role.USER.value

    @property
    def full_name(self):
        return f"{self.name} {self.surname}".strip() if self.surname else self.name

    def __repr__(self):
        return f"<User {self.username} ({self.role_enum.name})>"


# ---------------------------------------------------------------------------
# Points & Penalties
# ---------------------------------------------------------------------------
class GroupEventType(IntEnum):
    PENALTY = 0
    POINT = 1


class GroupEvent(db.Model):
    """A points/penalty ledger entry — group-wide by default, or attributed
    to one member when `user_id` is set (spec §2.2.2)."""

    __tablename__ = "group_events"

    group_event_id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(
        db.Integer, db.ForeignKey("groups.group_id", ondelete="CASCADE")
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    type = db.Column(db.Integer, nullable=False, default=GroupEventType.POINT.value)
    name = db.Column(db.String(30))
    description = db.Column(db.Text)
    value = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    group = db.relationship("Group", back_populates="group_events")
    user = db.relationship("User", foreign_keys=[user_id])

    @property
    def signed_value(self):
        """Value with the sign implied by `type` — points add, penalties
        subtract. `value` itself is always stored as a positive magnitude."""
        return self.value if self.type == GroupEventType.POINT.value else -self.value

    def __repr__(self):
        return f"<GroupEvent {self.name} value={self.value}>"


# ---------------------------------------------------------------------------
# Schedule events
# ---------------------------------------------------------------------------
class Event(db.Model):
    __tablename__ = "events"

    event_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    description = db.Column(db.Text)
    time = db.Column(db.DateTime)

    # de-duplication for reminder pushes (spec §2.2.6) — wired in Stage 8
    sent_20min_at = db.Column(db.DateTime, nullable=True)
    sent_start_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Event {self.name} @ {self.time}>"


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------
class Message(db.Model):
    __tablename__ = "messages"

    message_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    content = db.Column(db.Text)
    time = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )

    # NULL = broadcast to everyone, else scoped to one group (spec §2.2.5)
    target_group_id = db.Column(
        db.Integer, db.ForeignKey("groups.group_id", ondelete="CASCADE"), nullable=True
    )

    author = db.relationship(
        "User", back_populates="messages_authored", foreign_keys=[user_id]
    )
    target_group = db.relationship("Group", back_populates="messages")

    def __repr__(self):
        return f"<Message {self.title!r}>"


# ---------------------------------------------------------------------------
# Push subscriptions (Web Push / VAPID) — wired up in Stage 7
# ---------------------------------------------------------------------------
class PushSubscription(db.Model):
    __tablename__ = "push_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    endpoint = db.Column(db.String(500), nullable=False, unique=True)
    p256dh = db.Column(db.String(255), nullable=False)
    auth = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="push_subscriptions")


# ---------------------------------------------------------------------------
# Staff change requests — wired up in Stage 6
# ---------------------------------------------------------------------------
class ChangeRequest(db.Model):
    __tablename__ = "change_requests"

    request_id = db.Column(db.Integer, primary_key=True)
    submitted_by_user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    target_type = db.Column(db.String(20), nullable=False)  # message/group_event/event
    payload = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=RequestStatus.PENDING)
    reviewed_by_user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    review_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    submitted_by = db.relationship(
        "User",
        back_populates="change_requests_submitted",
        foreign_keys=[submitted_by_user_id],
    )
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_user_id])
