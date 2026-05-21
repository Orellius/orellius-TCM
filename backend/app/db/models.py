"""SQLAlchemy database models."""

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ── Multi-tenancy: Organizations & Users ──────────────────────


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    plan = Column(String, nullable=False, default="free")  # free|pro|enterprise
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())

    users = relationship("User", back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, nullable=False, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    org_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    role = Column(String, nullable=False, default="viewer")  # admin|editor|viewer
    is_superadmin = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    last_login = Column(DateTime, nullable=True)

    organization = relationship("Organization", back_populates="users")


# ── Billing ───────────────────────────────────────────────────


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True)
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    plan = Column(String, nullable=False, default="free")
    status = Column(String, nullable=False, default="active")  # active|past_due|canceled
    current_period_end = Column(DateTime, nullable=True)
    messages_used_today = Column(Integer, default=0)
    messages_reset_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())


# ── Audit Log ─────────────────────────────────────────────────


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_org_timestamp", "org_id", "timestamp"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String, nullable=False, index=True)
    resource_type = Column(String, nullable=True)
    resource_id = Column(String, nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)
    ip_address = Column(String, nullable=True)
    timestamp = Column(DateTime, server_default=func.now(), index=True)


# ── Webhooks ──────────────────────────────────────────────────


class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    url = Column(String, nullable=False)
    events = Column(JSON, default=list)  # ["message.published", "alert.hfc", ...]
    secret = Column(String, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_source_channel_created_at", "source_channel", "created_at"),
        Index("ix_messages_status_created_at", "status", "created_at"),
    )

    id = Column(String, primary_key=True)
    source_channel = Column(
        String,
        ForeignKey("channels.name", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    original_text = Column(Text, nullable=False)
    translated_text = Column(Text, default="")
    status = Column(String, nullable=False, default="ingested", index=True)
    media_items = Column(JSON, default=list)
    review_notes = Column(Text, default="")
    human_edited = Column(Boolean, default=False)
    extracted_facts = Column(JSON, default=list)
    auto_tags = Column(JSON, nullable=True)
    applied_template_id = Column(String, nullable=True)
    formatted_output = Column(Text, default="")
    published = Column(Boolean, default=False)
    publish_error = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    channel = relationship("Channel", back_populates="messages", foreign_keys=[source_channel])


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    channel_type = Column(String, nullable=False, default="source")
    is_active = Column(Boolean, default=True)
    last_scraped_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    messages = relationship("Message", back_populates="channel", foreign_keys=[Message.source_channel])


class GlossaryEntry(Base):
    __tablename__ = "glossary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_term = Column(String, nullable=False, index=True)
    source_language = Column(String, default="ar")
    hebrew_translation = Column(String, nullable=False)
    context = Column(Text, default="")
    embedding = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class SourceTrust(Base):
    __tablename__ = "source_trust"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(String, nullable=False, unique=True, index=True)
    trust_level = Column(String, nullable=False, default="neutral")
    accuracy_score = Column(Float, default=0.5)
    total_posts = Column(Integer, default=0)
    corroborated_posts = Column(Integer, default=0)
    content_consistency = Column(Float, default=0.5)
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime, server_default=func.now())
