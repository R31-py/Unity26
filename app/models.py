"""
Modelet e bazës së të dhënave.

Shënim sigurie: fjalëkalimet ruhen VETËM si hash (Argon2). Asnjë fjalëkalim
nuk ruhet ose transmetohet në tekst të thjeshtë.
"""
import enum
import secrets
from datetime import datetime

from flask_login import UserMixin
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.extensions import db

_ph = PasswordHasher()


def gen_token(n=24):
    return secrets.token_urlsafe(n)


class RoleEnum(str, enum.Enum):
    KAMPIST = "kampist"
    STAFF = "staff"
    ADMIN = "admin"
    # SUPERUSER nuk është një "rol" i shfaqur askund në UI publike; përdoret
    # vetëm nëpërmjet flamurit `is_superuser` më poshtë, jo si vlerë e listuar
    # në dropdown-e apo forma të administratorit.


class StaffPermission(str, enum.Enum):
    MANAGE_POINTS = "manage_points"
    MANAGE_PENALTIES = "manage_penalties"
    MANAGE_OWN_GROUP = "manage_own_group"
    SEND_ANNOUNCEMENTS = "send_announcements"
    CREATE_POLLS = "create_polls"
    MODERATE_CHAT = "moderate_chat"
    MANAGE_ATTENDANCE = "manage_attendance"
    VIEW_EMERGENCY_INFO = "view_emergency_info"


# ---------------------------------------------------------------------------
# Përdoruesi
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(50))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(RoleEnum), nullable=False, default=RoleEnum.KAMPIST)

    # --- Superuser i fshehur ---
    # Këta llogari NUK shfaqen në asnjë listë përdoruesish, grupi, dhome apo
    # chat-i të dukshme për admin/staf/kampistë. Shiko app/superuser/routes.py
    # dhe filtrat `visible_users()` / `visible_query()` më poshtë.
    is_superuser = db.Column(db.Boolean, default=False, nullable=False)

    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime)

    # Lidhje me profilin e kampistit (nëse roli = kampist)
    camper_profile = db.relationship(
        "CamperProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    staff_permissions = db.relationship(
        "StaffPermissionGrant", back_populates="user", cascade="all, delete-orphan",
        foreign_keys="StaffPermissionGrant.user_id",
    )
    push_subscriptions = db.relationship(
        "PushSubscription", back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, raw_password: str):
        self.password_hash = _ph.hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        try:
            return _ph.verify(self.password_hash, raw_password)
        except VerifyMismatchError:
            return False
        except Exception:
            return False

    def has_permission(self, perm: "StaffPermission") -> bool:
        if self.role == RoleEnum.ADMIN or self.is_superuser:
            return True
        if self.role != RoleEnum.STAFF:
            return False
        return any(g.permission == perm for g in self.staff_permissions)

    @property
    def full_name(self):
        if self.camper_profile:
            return f"{self.camper_profile.first_name} {self.camper_profile.last_name}"
        return self.email

    def __repr__(self):
        return f"<User {self.email} role={self.role}>"


class StaffPermissionGrant(db.Model):
    __tablename__ = "staff_permission_grants"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    permission = db.Column(db.Enum(StaffPermission), nullable=False)
    granted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    granted_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="staff_permissions", foreign_keys=[user_id])

    __table_args__ = (db.UniqueConstraint("user_id", "permission", name="uq_user_permission"),)


# ---------------------------------------------------------------------------
# Grupe & Dhoma
# ---------------------------------------------------------------------------
class Group(db.Model):
    __tablename__ = "groups"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    color = db.Column(db.String(7), default="#3E7C5A")  # hex
    leader_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    points = db.Column(db.Integer, default=0)
    penalties = db.Column(db.Integer, default=0)
    achievements = db.Column(db.Text)  # JSON string i thjeshtë me arritjet

    leader = db.relationship("User", foreign_keys=[leader_id])
    members = db.relationship("CamperProfile", back_populates="group")
    chat_room = db.relationship(
        "ChatRoom", uselist=False, back_populates="group", cascade="all, delete-orphan"
    )


class Building(db.Model):
    __tablename__ = "buildings"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    rooms = db.relationship("Room", back_populates="building", cascade="all, delete-orphan")


class Room(db.Model):
    __tablename__ = "rooms"
    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), nullable=False)
    number = db.Column(db.String(20), nullable=False)
    capacity = db.Column(db.Integer, default=4)

    building = db.relationship("Building", back_populates="rooms")
    occupants = db.relationship("CamperProfile", back_populates="room")


# ---------------------------------------------------------------------------
# Profili i kampistit (formulari i regjistrimit)
# ---------------------------------------------------------------------------
class CamperProfile(db.Model):
    __tablename__ = "camper_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    # Informacion Personal
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(30))
    address = db.Column(db.String(255))
    city = db.Column(db.String(100))

    # Kontakt emergjence
    emergency_contact_name = db.Column(db.String(150))
    emergency_contact_phone = db.Column(db.String(50))

    # Përvoja në kamp
    attended_before = db.Column(db.Boolean, default=False)
    times_attended = db.Column(db.Integer)
    last_year_attended = db.Column(db.Integer)

    # Gjendja shëndetësore
    has_allergies = db.Column(db.Boolean, default=False)
    allergies_description = db.Column(db.Text)
    health_notes = db.Column(db.Text)
    takes_medication = db.Column(db.Boolean, default=False)
    medication_name = db.Column(db.String(255))
    medication_instructions = db.Column(db.Text)

    # Informacion shtesë
    dietary_requirement = db.Column(db.String(50))  # asnjë/vegjetarian/vegan/pa gluten/tjetër
    dietary_other = db.Column(db.String(255))
    talent_description = db.Column(db.Text)
    shirt_size = db.Column(db.String(5))

    # Të mitur (< 18)
    is_minor = db.Column(db.Boolean, default=False)
    guardian_name = db.Column(db.String(150))
    guardian_phone = db.Column(db.String(50))
    guardian_email = db.Column(db.String(255))
    guardian_address = db.Column(db.String(255))
    guardian_signature = db.Column(db.String(150))
    guardian_consent_date = db.Column(db.Date)

    # Deklarata finale (checkboxes)
    accepted_info_accurate = db.Column(db.Boolean, default=False)
    accepted_rules = db.Column(db.Boolean, default=False)
    accepted_safety_notice = db.Column(db.Boolean, default=False)
    accepted_media_release = db.Column(db.Boolean, default=False)
    accepted_privacy_policy = db.Column(db.Boolean, default=False)
    rules_read_at = db.Column(db.DateTime)

    # Caktimet e kampit
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"))
    room_id = db.Column(db.Integer, db.ForeignKey("rooms.id"))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="camper_profile")
    group = db.relationship("Group", back_populates="members")
    room = db.relationship("Room", back_populates="occupants")


# ---------------------------------------------------------------------------
# Njoftime
# ---------------------------------------------------------------------------
class AnnouncementAudience(str, enum.Enum):
    ALL = "all"
    GROUP = "group"
    STAFF_ONLY = "staff_only"
    SINGLE_USER = "single_user"


class Announcement(db.Model):
    __tablename__ = "announcements"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    audience = db.Column(db.Enum(AnnouncementAudience), default=AnnouncementAudience.ALL)
    target_group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=True)
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    is_emergency = db.Column(db.Boolean, default=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    created_by = db.relationship("User", foreign_keys=[created_by_id])


# ---------------------------------------------------------------------------
# Pyetësorë (Polls)
# ---------------------------------------------------------------------------
class Poll(db.Model):
    __tablename__ = "polls"
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(255), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    is_open = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    options = db.relationship("PollOption", back_populates="poll", cascade="all, delete-orphan")


class PollOption(db.Model):
    __tablename__ = "poll_options"
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey("polls.id"), nullable=False)
    text = db.Column(db.String(255), nullable=False)

    poll = db.relationship("Poll", back_populates="options")
    votes = db.relationship("PollVote", back_populates="option", cascade="all, delete-orphan")


class PollVote(db.Model):
    __tablename__ = "poll_votes"
    id = db.Column(db.Integer, primary_key=True)
    option_id = db.Column(db.Integer, db.ForeignKey("poll_options.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    voted_at = db.Column(db.DateTime, default=datetime.utcnow)

    option = db.relationship("PollOption", back_populates="votes")

    __table_args__ = (db.UniqueConstraint("option_id", "user_id", name="uq_one_vote_per_option"),)


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
class ChatRoomType(str, enum.Enum):
    GROUP = "group"
    STAFF = "staff"


class ChatRoom(db.Model):
    __tablename__ = "chat_rooms"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    room_type = db.Column(db.Enum(ChatRoomType), nullable=False, default=ChatRoomType.GROUP)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), unique=True, nullable=True)

    group = db.relationship("Group", back_populates="chat_room")
    messages = db.relationship(
        "ChatMessage", back_populates="room", cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("chat_rooms.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    room = db.relationship("ChatRoom", back_populates="messages")
    sender = db.relationship("User", foreign_keys=[sender_id])


class ChatBlock(db.Model):
    """Bllokim përdoruesi nga një chat i caktuar (moderim)."""
    __tablename__ = "chat_blocks"
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("chat_rooms.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    blocked_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    blocked_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("room_id", "user_id", name="uq_block_room_user"),)


# ---------------------------------------------------------------------------
# Push notifications
# ---------------------------------------------------------------------------
class PushSubscription(db.Model):
    __tablename__ = "push_subscriptions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    endpoint = db.Column(db.Text, nullable=False, unique=True)
    p256dh = db.Column(db.String(255), nullable=False)
    auth = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="push_subscriptions")


# ---------------------------------------------------------------------------
# Audit log (kërkesë sigurie)
# ---------------------------------------------------------------------------
class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(120), nullable=False)
    target_type = db.Column(db.String(80))
    target_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


def log_action(actor_id, action, target_type=None, target_id=None, details=None, ip_address=None):
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
        ip_address=ip_address,
    )
    db.session.add(entry)
    db.session.commit()


# ---------------------------------------------------------------------------
# Orari ditor i kampit
# ---------------------------------------------------------------------------
class ScheduleItem(db.Model):
    __tablename__ = "schedule_items"
    id = db.Column(db.Integer, primary_key=True)
    day_label = db.Column(db.String(50), nullable=False)   # p.sh. "E Hënë" ose "Dita 1"
    time_label = db.Column(db.String(20), nullable=False)  # p.sh. "08:00"
    title = db.Column(db.String(200), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Ndihmës: gjithmonë përjashto superuser-at nga pamjet e zakonshme
# ---------------------------------------------------------------------------
def visible_users_query():
    """Query e User që PËRJASHTON superuser-at - përdoret nga çdo listë
    përdoruesish e dukshme për admin/staf/kampistë."""
    return User.query.filter(User.is_superuser.is_(False))