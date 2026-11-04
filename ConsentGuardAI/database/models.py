"""SQLAlchemy models for ConsentGuardAI."""

from datetime import datetime, timezone
import uuid

from app import db


class User(db.Model):
    """Stores registered user accounts."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<User id={self.id} email={self.email!r}>"


class ConsentModel(db.Model):
    """Persistent record of a user's purpose-specific consent."""

    __tablename__ = "consents"

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(255), nullable=False, index=True)
    purpose = db.Column(db.String(255), nullable=False, index=True)
    data_categories = db.Column(db.JSON, nullable=False)
    granted = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    withdrawn_at = db.Column(db.DateTime(timezone=True), nullable=True)
    version = db.Column(db.Integer, nullable=False, default=1)


class Conversation(db.Model):
    """Stores separate conversation sessions for ChatGPT-like context isolation."""

    __tablename__ = "conversations"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False, default="New Conversation")
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    messages = db.relationship(
        "ChatMessage",
        backref="conversation",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="ChatMessage.created_at.asc()",
    )

    def __repr__(self):
        return f"<Conversation id={self.id} title={self.title!r}>"


class ChatMessage(db.Model):
    """Stores individual messages within an isolated conversation session."""

    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.String(36),
        db.ForeignKey("conversations.id"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(db.Integer, nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    purpose = db.Column(db.String(255), nullable=True)
    decision = db.Column(db.String(20), nullable=True)  # 'ALLOW', 'WARN', 'BLOCK'
    decision_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return f"<ChatMessage id={self.id} role={self.role!r} decision={self.decision!r}>"


class ProtectedRecord(db.Model):
    """Stores a user's protected data record and its immutable original purpose (Objectives 1 & 2)."""

    __tablename__ = "protected_records"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    conversation_id = db.Column(db.String(36), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    data_classification = db.Column(
        db.String(100),
        nullable=False,
        default="Confidential",
    )
    data_encrypted = db.Column(db.LargeBinary, nullable=False)
    original_purpose = db.Column(db.String(500), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self):
        return f"<ProtectedRecord id={self.id} title={self.title!r}>"


class AuditLog(db.Model):
    """Stores security and authorization events with structured decision history (Objective 4 & Screen E)."""

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True, index=True)
    conversation_id = db.Column(db.String(36), nullable=True, index=True)
    request_ref = db.Column(db.String(64), nullable=True, index=True)
    event_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(1000), nullable=False)
    reuse_detected = db.Column(db.Boolean, nullable=True, default=False)
    matched_record_id = db.Column(db.Integer, nullable=True)
    original_purpose = db.Column(db.String(500), nullable=True)
    requested_purpose = db.Column(db.String(500), nullable=True)
    decision = db.Column(db.String(20), nullable=True)  # 'ALLOW', 'WARN', 'BLOCK'
    decision_reason = db.Column(db.Text, nullable=True)
    sent_to_provider = db.Column(db.Boolean, nullable=True, default=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    previous_hash = db.Column(db.String(64), nullable=True)
    entry_hash = db.Column(db.String(64), nullable=True)

    def __repr__(self):
        return f"<AuditLog id={self.id} event_type={self.event_type!r} decision={self.decision!r}>"
