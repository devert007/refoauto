from __future__ import annotations

import typing
from datetime import datetime, timedelta, timezone
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import FromClause

from app.db.base import Base
from app.db.types import PGCryptoString

__all__ = (
    "DEFAULT_AMO_FIELD_MAPPING",
    "AnalyticsHistory",
    "AuditAction",
    "AuditEntityType",
    "AuditLog",
    "BaseModel",
    "BookingMode",
    "ChatwootConversation",
    "ChatwootMessage",
    "Client",
    "ConversationEpisode",
    "CrmVendor",
    "DiscountType",
    "Location",
    "LocationCrmCredentials",
    "LocationFAQ",
    "Offer",
    "OfferService",
    "Practitioner",
    "PractitionerType",
    "PrepaidType",
    "PriceType",
    "ReactivationAttempt",
    "ReactivationBatch",
    "ReactivationCampaign",
    "ReactivationContact",
    "Resource",
    "ResourceInstance",
    "ResourceRequirementType",
    "RolloutMode",
    "Service",
    "ServiceCategory",
    "ServicePractitioner",
    "ServiceResource",
    "SpecialDate",
    "Staff",
    "SyncLog",
    "SyncLogStatus",
    "TestCase",
    "TestSchedule",
    "ToneOfVoice",
)


class CrmVendor(StrEnum):
    SHORTCUTS = "ShortCuts"
    ALTEGIO = "Altegio"
    SIMPLEX = "Simplex"
    OTHER = "Other"

    @property
    def sync_supported(self) -> bool:
        """Check if this vendor supports catalog sync."""
        return self == CrmVendor.ALTEGIO


class EHRSyncStatus(StrEnum):
    IDLE = "idle"
    IN_PROGRESS = "in_progress"
    FAILED = "failed"


class PriceType(StrEnum):
    """Price type for services."""

    FIXED = "fixed"  # Fixed price (price_min = price_max)
    RANGE = "range"  # Price range (price_min < price_max)
    FROM = "from"  # "From X" (only price_min)
    VARIES = "varies"  # "Price depends on..." (text note)
    UNKNOWN = "unknown"  # Not specified


class BookingMode(StrEnum):
    """How the service can be booked."""

    SLOTS = "slots"  # Via EHR slots
    CALLBACK = "callback"  # Request callback
    DISABLED = "disabled"  # Booking disabled


class PrepaidType(StrEnum):
    """Prepayment requirement for service."""

    FORBIDDEN = "forbidden"  # Prepayment not allowed
    ALLOWED = "allowed"  # Prepayment optional
    REQUIRED = "required"  # Prepayment required


class PractitionerType(StrEnum):
    """Type of practitioner."""

    DOCTOR = "doctor"
    THERAPIST = "therapist"
    SPECIALIST = "specialist"
    OTHER = "other"


class ResourceRequirementType(StrEnum):
    """How resource is required for service."""

    REQUIRED = "required"  # This resource is mandatory
    ALTERNATIVE = "alternative"  # Alternative (OR with other alternatives in same group)


class DiscountType(StrEnum):
    """Type of discount for offer."""

    PERCENTAGE = "percentage"  # Percentage discount (10%, 20%)
    FIXED = "fixed"  # Fixed amount (-100 AED)
    NONE = "none"  # No discount (description only)


class RolloutMode(StrEnum):
    """Rollout mode for Yma AI at a location."""

    INVISIBLE = "invisible"  # AI completely off
    SHADOW = "shadow"  # AI drafts but doesn't send (safe mode on)
    NIGHT_OWL = "night_owl"  # Only after-hours
    CAUTIOUS = "cautious"  # After-hours + ad clients
    GROWING = "growing"  # After-hours + ad clients + new clients
    CONFIDENT = "confident"  # All clients except booking
    AUTONOMOUS = "autonomous"  # Full autonomous including booking
    CUSTOM = "custom"  # Custom feature selection


class ToneOfVoice(StrEnum):
    """AI tone of voice presets."""

    YMA = "yma"
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    CONCISE = "concise"


class BaseModel:
    """Base model class with common methods."""

    __name__: typing.ClassVar[str]
    __table__: FromClause

    def to_dict(self, exclude: set[str] | None = None) -> dict[str, typing.Any]:
        exclude_names: set[str] = {"sa_orm_sentinel", "_sentinel"}
        state: typing.Any = getattr(self, "_sa_instance_state", None)
        if state is not None:
            unloaded: set[str]
            try:
                unloaded = set(getattr(state, "unloaded", set()))
            except Exception:
                unloaded = set()
            exclude_names = exclude_names.union(unloaded)
        if exclude:
            exclude_names = exclude_names.union(exclude)
        return {c.name: getattr(self, c.name) for c in self.__table__.columns if c.name not in exclude_names}


test_clients = Table(
    "test_clients",
    Base.metadata,
    Column("test_id", ForeignKey("tests.id", ondelete="CASCADE"), primary_key=True),
    Column("client_id", ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True),
)


# Default AMO CRM field mapping for TVC
DEFAULT_AMO_FIELD_MAPPING = {
    "contact_phone_field_id": 687721,
    "chat_url_field_id": 952881,
    "chat_id_field_id": 952879,
    "escalation_at_field_id": 952883,
    "escalation_summary_field_id": 952889,
    "utm_field_id": 952891,
    "escalated_to_manager_field_id": 952893,
}


class Client(BaseModel, Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(300))
    website_url: Mapped[str | None] = mapped_column(String(500))
    favicon_url: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)

    # Language settings
    primary_language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    supported_languages: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSONB),
        default=list,
        nullable=False,
    )

    # Business settings
    currency: Mapped[str] = mapped_column(String(3), default="AED", nullable=False)

    # Chatwoot settings (shared across all locations by default)
    chatwoot_base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    chatwoot_api_token: Mapped[str] = mapped_column(PGCryptoString, nullable=False)
    chatwoot_account_id: Mapped[int] = mapped_column(Integer, default=1)  # Default account

    manager_name: Mapped[str | None] = mapped_column(String(200))
    wa_bot_number: Mapped[str | None] = mapped_column(String(64))

    tags: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSONB), default=list)

    comment: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(100), default="active", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    timezone_utc_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    timezone_name: Mapped[str] = mapped_column(String(100), nullable=False, default="Asia/Dubai")

    # e.g. {"whatsapp": 1, "email": 2}
    inbox_id_dict: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)

    escalation_amo_base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_amo_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_amo_field_mapping: Mapped[dict | None] = mapped_column(
        MutableDict.as_mutable(JSONB),
        nullable=True,
        default=None,
    )

    # many-to-many with TestCase
    tests: Mapped[set[TestCase]] = relationship(
        "TestCase",
        secondary=test_clients,
        back_populates="clients",
        lazy="selectin",
        collection_class=set,
    )

    # one-to-many with Location
    locations: Mapped[list[Location]] = relationship(
        "Location",
        back_populates="client",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="Location.id",
    )

    def __repr__(self) -> str:
        return f"Client(id={self.id}, name={self.name}, timezone={self.timezone_name})"

    @property
    def branches_count(self) -> int:
        """Get the number of locations (branches)."""
        return len(self.locations) if self.locations else 0

    @property
    def chatwoot_url(self) -> str:
        """Backward-compatible alias for chatwoot_base_url."""
        return self.chatwoot_base_url

    @property
    def primary_location(self) -> Location | None:
        """Get primary location (or first location if none marked as primary)."""
        if not self.locations:
            return None
        for loc in self.locations:
            if loc.is_primary:
                return loc
        return self.locations[0] if self.locations else None

    @property
    def crm_vendor(self) -> str | None:
        """Backward-compatible: get CRM vendor from primary location."""
        loc = self.primary_location
        return loc.crm_vendor if loc else None

    @property
    def has_crm_integration(self) -> bool:
        """Backward-compatible: check if primary location has CRM integration."""
        loc = self.primary_location
        return loc.has_crm_integration if loc else False

    @property
    def crm_credentials(self) -> LocationCrmCredentials | None:
        """Backward-compatible: get CRM credentials from primary location."""
        loc = self.primary_location
        return loc.crm_credentials if loc else None

    def get_chatwoot_conv_url(self, conv_id: int | None = None, account_id: int | None = None) -> str:
        """Get Chatwoot conversation URL. Uses default account_id if not specified."""
        url = self.chatwoot_base_url.rstrip("/")
        acc_id = account_id or self.chatwoot_account_id
        if conv_id is None:
            return f"{url}/app/accounts/{acc_id}/conversations/"
        return f"{url}/app/accounts/{acc_id}/conversations/{conv_id}"

    def get_timezone(self) -> timezone:
        return timezone(timedelta(hours=self.timezone_utc_offset), name=self.timezone_name)

    def get_inbox_id(self, inbox_name: str) -> int | None:
        return self.inbox_id_dict.get(inbox_name)

    def is_amo_crm_configured(self) -> bool:
        return self.escalation_amo_base_url is not None and self.escalation_amo_token is not None

    def get_amo_field_mapping(self) -> dict[str, int]:
        """Get AMO CRM field mapping, falling back to default TVC mapping."""
        if self.escalation_amo_field_mapping:
            return self.escalation_amo_field_mapping
        return DEFAULT_AMO_FIELD_MAPPING


Index("ix__clients__status", Client.status)
Index("gin__clients__tags", Client.tags, postgresql_using="gin")


class Location(BaseModel, Base):
    """Location (branch/clinic) belonging to a Client."""

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Identification
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(300))  # Public-facing name
    code: Mapped[str | None] = mapped_column(String(50))  # Short code like "JUM"
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))

    # Address (address is required, city is optional)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    google_maps_url: Mapped[str | None] = mapped_column(String(500))
    city: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    currency: Mapped[str | None] = mapped_column(String(3))
    timezone_name: Mapped[str] = mapped_column(String(100), nullable=False, default="Asia/Dubai")
    timezone_utc_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=4)

    whatsapp: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(200))
    website: Mapped[str | None] = mapped_column(String(500))
    instagram: Mapped[str | None] = mapped_column(String(200))
    facebook: Mapped[str | None] = mapped_column(String(500))
    lead_form_wa_template_name: Mapped[str | None] = mapped_column(String(200))

    # Chatwoot settings
    # By default, uses client's chatwoot_base_url and chatwoot_api_token
    # but each location has its own account_id (or can use client's default)
    chatwoot_account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    chatwoot_inbox_id: Mapped[int | None] = mapped_column(Integer)
    # If location needs separate Chatwoot instance
    use_separate_chatwoot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    chatwoot_url: Mapped[str | None] = mapped_column(String(500))
    chatwoot_api_token: Mapped[str | None] = mapped_column(PGCryptoString)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    is_visible_to_ai: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    rollout_mode: Mapped[str] = mapped_column(String(50), default=RolloutMode.INVISIBLE.value, nullable=False)
    rollout_features: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict, nullable=False)
    working_hours: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict, nullable=False)
    escalation_settings: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict, nullable=False)
    reminder_settings: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict, nullable=False)

    ai_assistant_name: Mapped[str] = mapped_column(String(100), default="Yma AI", nullable=False)
    ai_assistant_description: Mapped[str | None] = mapped_column(String(200))
    ai_notify_about_ai: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ai_disclosure_message: Mapped[str | None] = mapped_column(Text)
    ai_tone_of_voice: Mapped[str] = mapped_column(String(50), default=ToneOfVoice.YMA.value, nullable=False)
    ai_custom_instructions: Mapped[str | None] = mapped_column(String(500))
    ai_block_spam: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    client: Mapped[Client] = relationship("Client", back_populates="locations", lazy="selectin")
    crm_credentials: Mapped[LocationCrmCredentials | None] = relationship(
        "LocationCrmCredentials",
        back_populates="location",
        uselist=False,
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"Location(id={self.id}, client_id={self.client_id}, name={self.name})"

    def get_timezone(self) -> timezone:
        return timezone(timedelta(hours=self.timezone_utc_offset), name=self.timezone_name)

    def get_chatwoot_base_url(self) -> str:
        """Get Chatwoot base URL (own or from client)."""
        if self.use_separate_chatwoot and self.chatwoot_url:
            return self.chatwoot_url
        return self.client.chatwoot_base_url

    def get_chatwoot_api_token(self) -> str:
        """Get Chatwoot API token (own or from client)."""
        if self.use_separate_chatwoot and self.chatwoot_api_token:
            return self.chatwoot_api_token
        return self.client.chatwoot_api_token

    def get_chatwoot_conv_url(self, conv_id: int | None = None) -> str:
        """Get Chatwoot conversation URL for this location."""
        url = self.get_chatwoot_base_url().rstrip("/")
        if conv_id is None:
            return f"{url}/app/accounts/{self.chatwoot_account_id}/conversations/"
        return f"{url}/app/accounts/{self.chatwoot_account_id}/conversations/{conv_id}"

    @property
    def has_crm_integration(self) -> bool:
        """Check if location has CRM/EHR integration configured."""
        return self.crm_credentials is not None

    @property
    def crm_vendor(self) -> str | None:
        """Get CRM vendor name if configured."""
        return self.crm_credentials.vendor if self.crm_credentials else None

    def get_currency(self) -> str:
        """Get currency (own or from client)."""
        return self.currency or self.client.currency


Index("ix__locations__client_id", Location.client_id)
Index("ix__locations__status", Location.status)


class SpecialDate(BaseModel, Base):
    """Special dates (holidays, exceptions) for a location's working hours."""

    __tablename__ = "special_dates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Date range (for single day, date_from = date_to)
    date_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Recurring yearly (e.g., Christmas)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Name/label
    name: Mapped[str | None] = mapped_column(String(200))  # "Christmas", "Ramadan"

    # Hours configuration
    is_closed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Custom hours if not closed (JSONB for flexibility)
    # Structure: {"intervals": [{"open": "10:00", "close": "14:00"}]}
    custom_hours: Mapped[dict | None] = mapped_column(JSONB)

    # AI guidance
    yma_response_instruction: Mapped[str | None] = mapped_column(Text)

    # Relationship
    location: Mapped[Location] = relationship("Location")

    def __repr__(self) -> str:
        return f"SpecialDate(id={self.id}, location_id={self.location_id}, name={self.name})"


Index("ix__special_dates__location_date", SpecialDate.location_id, SpecialDate.date_from)


class LocationFAQ(BaseModel, Base):
    """FAQ entries for a location (used by Yma AI)."""

    __tablename__ = "location_faqs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    question: Mapped[str] = mapped_column(String(500), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)

    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationship
    location: Mapped[Location] = relationship("Location")

    def __repr__(self) -> str:
        return f"LocationFAQ(id={self.id}, location_id={self.location_id}, question={self.question[:50]})"


Index("ix__location_faqs__location_active", LocationFAQ.location_id, LocationFAQ.is_active)


class LocationCrmCredentials(BaseModel, Base):
    """CRM/EHR credentials for a Location. One-to-one with Location."""

    __tablename__ = "location_crm_credentials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    vendor: Mapped[str] = mapped_column(String(50), nullable=False)

    # Common fields (used by multiple vendors)
    base_url: Mapped[str | None] = mapped_column(String(500))
    login: Mapped[str | None] = mapped_column(String(200))
    password: Mapped[str | None] = mapped_column(PGCryptoString)
    api_key: Mapped[str | None] = mapped_column(PGCryptoString)

    # Altegio-specific
    partner_token: Mapped[str | None] = mapped_column(PGCryptoString)
    user_token: Mapped[str | None] = mapped_column(PGCryptoString)
    # External location ID in Altegio (single location per our Location)
    external_location_id: Mapped[str | None] = mapped_column(String(100))

    # Sync tracking
    sync_status: Mapped[str] = mapped_column(String(20), default=EHRSyncStatus.IDLE, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_error: Mapped[str | None] = mapped_column(Text)

    # Relationship back to Location
    location: Mapped[Location] = relationship("Location", back_populates="crm_credentials")

    @property
    def is_sync_in_progress(self) -> bool:
        return self.sync_status == EHRSyncStatus.IN_PROGRESS

    def __repr__(self) -> str:
        return f"LocationCrmCredentials(id={self.id}, location_id={self.location_id}, vendor={self.vendor})"


class Staff(BaseModel, Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    slack_username: Mapped[str | None] = mapped_column(String(120))
    slack_user_id: Mapped[str | None] = mapped_column(String(120))
    avatar_url: Mapped[str | None] = mapped_column(String(500))

    def __repr__(self) -> str:
        return f"Staff(id={self.id}, full_name={self.full_name}, email={self.email})"

    __table_args__ = (UniqueConstraint("full_name", name="uq__staff__full_name"),)


class TestSchedule(StrEnum):
    __test__ = False
    EVERY_5_MINUTES = "every_5_minutes"
    HOURLY = "hourly"
    SIX_HOURS = "6h"
    DAILY = "daily"


class TestStatus(StrEnum):
    __test__ = False
    ACTIVE = "active"
    INACTIVE = "inactive"


class TestType(StrEnum):
    __test__ = False
    INSTRUCTION = "instruction"
    ALGORITHM = "algorithm"
    ANALYTICS = "analytics"
    ESCALATION_ANALYTICS = "escalation_analytics"


# --- TestCase ---
class TestCase(BaseModel, Base):
    __test__ = False
    __tablename__ = "tests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    created_user: Mapped[str | None] = mapped_column(String(320))
    updated_user: Mapped[str | None] = mapped_column(String(320))

    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    instruction: Mapped[str] = mapped_column(Text)
    test_type: Mapped[str] = mapped_column(String(200), default=TestType.INSTRUCTION.value)

    tags: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSONB), default=list)

    responsible_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id"))
    responsible: Mapped[Staff | None] = relationship("Staff")

    clients: Mapped[set[Client]] = relationship(
        "Client",
        secondary=test_clients,
        back_populates="tests",
        lazy="selectin",
        collection_class=set,
    )

    notify_slack_on_fail: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    schedule: Mapped[str] = mapped_column(
        String(16),
        default=TestSchedule.DAILY.value,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(100),
        default=TestStatus.ACTIVE.value,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"TestCase(id={self.id}, name={self.name}, status={self.status})"


Index("ix__tests__status", TestCase.status)
Index("ix__tests__schedule", TestCase.schedule)
Index("gin__tests__tags", TestCase.tags, postgresql_using="gin")


class TestRunStatus(StrEnum):
    __test__ = False
    SKIPPED = "skipped"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    QUEUED = "queued"


class RunTrigger(StrEnum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    RETRY = "retry"


class TestRun(BaseModel, Base):
    __test__ = False
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    test_id: Mapped[int] = mapped_column(
        ForeignKey("tests.id", ondelete="CASCADE"),
        index=True,
    )
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        index=True,
    )

    trigger: Mapped[str] = mapped_column(
        String(16),
        default=RunTrigger.SCHEDULE.value,
        nullable=False,
    )
    created_user: Mapped[str | None] = mapped_column(String(320))
    updated_user: Mapped[str | None] = mapped_column(String(320))

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, default=None)

    status: Mapped[str] = mapped_column(
        String(16),
        default=TestRunStatus.QUEUED.value,
        nullable=False,
    )

    params: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)

    test_snapshot: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
    )

    judge_comment: Mapped[str | None] = mapped_column(Text)
    judge_output: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
    )
    comment: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)

    model_name: Mapped[str | None] = mapped_column(String(100))
    cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 4))


Index(
    "ix__test_runs__test_client_created_alive",
    TestRun.test_id,
    TestRun.client_id,
    TestRun.created_at.desc(),
    postgresql_where=TestRun.deleted_at.is_(None),
)
Index(
    "ix__test_runs__client_created_alive",
    TestRun.client_id,
    TestRun.created_at.desc(),
    postgresql_where=TestRun.deleted_at.is_(None),
)
Index(
    "ix__test_runs__status_created_alive",
    TestRun.status,
    TestRun.created_at.desc(),
    postgresql_where=TestRun.deleted_at.is_(None),
)


class GoogleSheetTabInfo(BaseModel, Base):
    """
    Info about a tab in a Google Sheet.
    Each tab in the sheet represents one testing tab scenario.
    For example, the "clinic_info" tab is a scenario for testing clinic information.
    scenario_description - description of the scenario that is manually entered in the UI.
    """

    __tablename__ = "google_sheet_tab_info"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    # Relation to scenario (sheet). One scenario has many tabs
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("e2e_scenarios.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tab_name: Mapped[str] = mapped_column(String(300), nullable=False)
    scenario_description: Mapped[str | None] = mapped_column(Text)
    custom_instructions: Mapped[str | None] = mapped_column(Text)
    columns_map: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
    )  # e.g. {"questions": "A", "criteria": "B", "expected_results": "C"}
    # Relationship back to E2EScenario
    scenario: Mapped[E2EScenario] = relationship("E2EScenario", back_populates="google_sheet_tabs_info")

    def __repr__(self) -> str:
        return f"GoogleSheetTabInfo(id={self.id}, tab_name={self.tab_name}, columns_map={self.columns_map})"

    __table_args__ = (
        Index("ix__gs_tab_info__scenario_tab", "scenario_id", "tab_name"),
        UniqueConstraint("scenario_id", "tab_name", name="uq__gs_tab__scenario_tabname"),
    )


class E2EScenario(BaseModel, Base):
    __tablename__ = "e2e_scenarios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # Scenario info:
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSONB), default=list)
    created_user: Mapped[str | None] = mapped_column(String(320))

    # Google Sheet info:
    spreadsheet_url: Mapped[str] = mapped_column(String(500), nullable=False)
    google_sheet_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    google_sheet_tabs_info: Mapped[list[GoogleSheetTabInfo]] = relationship(
        "GoogleSheetTabInfo",
        back_populates="scenario",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"E2EScenario(id={self.id}, name={self.name}, spreadsheet_url={self.spreadsheet_url})"


class E2EScenarioRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    ESCALATION = "escalation"


class E2EScenarioRun(BaseModel, Base):
    __tablename__ = "e2e_scenario_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    check_availability: Mapped[bool | None] = mapped_column(Boolean, default=None, nullable=True)

    google_sheet_tab_info_id: Mapped[int] = mapped_column(
        ForeignKey("google_sheet_tab_info.id", ondelete="CASCADE"),
        index=True,
    )
    google_sheet_tab_info: Mapped[GoogleSheetTabInfo] = relationship("GoogleSheetTabInfo")

    # target phone (clinic bot), normalized E.164 without '+'
    phone_number: Mapped[str] = mapped_column(String(32), index=True)
    # chat identifier (jid) once known (e.g. after first outbound)
    chat_id: Mapped[str | None] = mapped_column(String(64), index=True, default=None)
    created_user: Mapped[str | None] = mapped_column(String(320))

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        default=E2EScenarioRunStatus.QUEUED.value,
        nullable=False,
        index=True,
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    comment: Mapped[str | None] = mapped_column(Text)

    judge_comment: Mapped[str | None] = mapped_column(Text)
    judge_output: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)

    model_name: Mapped[str | None] = mapped_column(String(100))
    cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 4))
    sub_id: Mapped[str] = mapped_column(String(100), default="n/a", nullable=True)
    last_state: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)

    def is_telegram(self) -> bool:
        return self.phone_number.startswith("@")

    @property
    def is_resume(self) -> bool:
        tab_data = self.last_state.get("tab_data", {})
        return bool(tab_data)

    @property
    def tab_data_dict(self) -> dict:
        return self.last_state.get("tab_data", {})

    @property
    def need_to_update_gs(self) -> bool:
        """If the run is not checked for availability, update the Google Sheet."""
        return self.check_availability is not True

    @property
    def need_to_slack_notification(self) -> bool:
        """If the run is not checked for availability, don't send a slack notification."""
        return self.check_availability is True

    @property
    def scenario(self) -> E2EScenario:
        return self.google_sheet_tab_info.scenario

    @property
    def gs_tab_info(self) -> GoogleSheetTabInfo:
        return self.google_sheet_tab_info

    def __repr__(self) -> str:
        return f"E2EScenarioRun(id={self.id}, phone_number={self.phone_number}, status={self.status})"

    __table_args__ = (
        # enforce single active run per phone_number (for queued/running) via partial unique index
        Index(
            "uq__e2e_runs__active_phone",
            "phone_number",
            unique=True,
            postgresql_where=text("status IN ('running')"),
        ),
        CheckConstraint(
            "(finished_at IS NULL) OR (started_at IS NULL) OR (finished_at >= started_at)",
            name="ck__e2e_runs__time_order",
        ),
        Index("ix__e2e_runs__tab_created", "google_sheet_tab_info_id", "created_at"),
        Index("ix__e2e_runs__status_created", "status", "created_at"),
    )


class E2EScenarioStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"


class E2ERunStep(BaseModel, Base):
    __tablename__ = "e2e_run_steps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    run_id: Mapped[int] = mapped_column(
        ForeignKey("e2e_scenario_runs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    run: Mapped[E2EScenarioRun] = relationship("E2EScenarioRun")

    row_index: Mapped[int] = mapped_column(Integer, nullable=False)

    question: Mapped[str | None] = mapped_column(Text)
    criteria: Mapped[str | None] = mapped_column(Text)
    expected: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False, index=True)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    actual_reply: Mapped[str | None] = mapped_column(Text)
    quality: Mapped[str] = mapped_column(String(16), default="pending", nullable=False, index=True)
    judge_comment: Mapped[str | None] = mapped_column(Text)
    judge_output: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)
    latency_ms: Mapped[int | None] = mapped_column(Integer)

    meta: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)

    def __repr__(self) -> str:
        return f"E2ERunStep(id={self.id}, question={self.question}, status={self.status})"

    __table_args__ = (
        UniqueConstraint("run_id", "row_index", name="uq__e2e_steps__run_row"),
        Index("ix__e2e_steps__run_status", "run_id", "status"),
    )


class MessageDirection(StrEnum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class MessageStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    ERROR = "error"


class Message(BaseModel, Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    channel_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    direction: Mapped[str] = mapped_column(
        String(16),
        default=MessageDirection.OUTBOUND.value,
        nullable=False,
        index=True,
    )
    message_id: Mapped[str | None] = mapped_column(String(128), index=True, unique=True)
    chat_id: Mapped[str | None] = mapped_column(String(64), index=True)

    phone_from: Mapped[str | None] = mapped_column(String(32), index=True)
    phone_to: Mapped[str | None] = mapped_column(String(32), index=True)

    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=MessageStatus.PENDING.value, nullable=False, index=True)
    from_me: Mapped[bool] = mapped_column(nullable=False, default=False)
    is_processed: Mapped[bool] = mapped_column(nullable=False, default=False)

    raw: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)

    run_id: Mapped[int | None] = mapped_column(ForeignKey("e2e_scenario_runs.id", ondelete="SET NULL"), index=True)
    run: Mapped[E2EScenarioRun | None] = relationship("E2EScenarioRun")

    def __repr__(self) -> str:
        return f"Message(id={self.id}, from_me={self.from_me}, status={self.status})"

    __table_args__ = (
        Index("ix__messages__run_created", "run_id", "created_at"),
        Index("ix__messages__chat_ts", "chat_id", "created_at"),
    )


class ConversationEpisode(BaseModel, Base):
    """
    Represents a single episode/journey within a conversation.
    An episode is a focused interaction with one clear intent (e.g., booking, inquiry).
    Multiple episodes can exist for the same contact over time.
    """

    __tablename__ = "conversation_episodes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    client_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    chatwoot_conv_url: Mapped[str] = mapped_column(String(500), nullable=False)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_user_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_from: Mapped[str | None] = mapped_column(String(300), nullable=True)

    message_index_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message_index_end: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    funnel_status: Mapped[str | None] = mapped_column(String(100))
    booking_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    episode_summary: Mapped[str | None] = mapped_column(Text)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    analytics_data: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)
    episode_decision: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)

    separation_reason: Mapped[str | None] = mapped_column(String(100))
    separation_confidence: Mapped[int | None] = mapped_column(Integer)

    def __repr__(self) -> str:
        return f"ConversationEpisode(episode_number={self.episode_number}, status={self.funnel_status})"

    def _format_active_episode(self) -> str:
        started_at_str = self.started_at.strftime("%Y-%m-%d %H:%M:%S")
        ended_at_str = "ongoing"
        status = self.funnel_status or "active"
        summary = self.episode_summary or "This is an active episode without a summary yet."
        header = f"Episode #{self.episode_number} ({started_at_str} - {ended_at_str}, Status: {status})"
        summary = f"Episode Summary:\n{summary}"
        return f"{header}\n{summary}"

    def _format_completed_episode(self) -> str:
        started_at_str = self.started_at.strftime("%Y-%m-%d %H:%M:%S")
        ended_at_str = self.ended_at.strftime("%Y-%m-%d %H:%M:%S") if self.ended_at else "no_info_available"
        status = self.funnel_status or "unknown"
        summary = self.episode_summary or "No summary available."
        separation_reason = self.separation_reason or "There was no separation reason, probably due the error."
        header = f"Episode #{self.episode_number} ({started_at_str} - {ended_at_str}, Status: {status})"
        body = f"Episode was separated from previous because {separation_reason}"
        summary = f"Episode Summary:\n{summary}"
        return f"{header}\n{body}\n{summary}"

    def format_for_llm(self) -> str:
        if self.is_active:
            return self._format_active_episode()
        return self._format_completed_episode()


class ConversationEpisodeTest(BaseModel, Base):
    """
    Test version of ConversationEpisode for verification and Metabase analytics.
    Maps to 'conversation_episodes_test'.
    """

    __tablename__ = "conversation_episodes_test"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    client_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    chatwoot_conv_url: Mapped[str] = mapped_column(String(500), nullable=False)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_user_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_from: Mapped[str | None] = mapped_column(String(300), nullable=True)

    message_index_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message_index_end: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    funnel_status: Mapped[str | None] = mapped_column(String(100))
    booking_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    episode_summary: Mapped[str | None] = mapped_column(Text)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    analytics_data: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)
    episode_decision: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)

    separation_reason: Mapped[str | None] = mapped_column(String(100))
    separation_confidence: Mapped[int | None] = mapped_column(Integer)

    def __repr__(self) -> str:
        return f"ConversationEpisodeTest(episode_number={self.episode_number}, status={self.funnel_status})"


class LeadForm(BaseModel, Base):
    __tablename__ = "lead_forms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), insert_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    campaign_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    inbox_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    client_name: Mapped[str] = mapped_column(String(200), nullable=False)
    user_phone: Mapped[str] = mapped_column(String(200), nullable=False)
    user_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    user_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    merged_information: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)
    is_processed_success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class EscalationAnalytics(BaseModel, Base):
    __tablename__ = "escalation_analytics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), insert_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    client_name: Mapped[str] = mapped_column(String(200), nullable=False)
    chatwoot_conv_id: Mapped[int] = mapped_column(Integer, nullable=False)
    chatwoot_url: Mapped[str] = mapped_column(String(500), nullable=False)
    chatwoot_message_id: Mapped[int] = mapped_column(Integer, nullable=False)

    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalated_at: Mapped[str | None] = mapped_column(String(100), nullable=True)
    escalated_to_manager: Mapped[str | None] = mapped_column(String(100), nullable=True)
    utc_escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user_phone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    user_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    referral: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)


class AnalyticsHistory(BaseModel, Base):
    """
    Historical record of analytics changes for a conversation.
    Tracks how analytics parameters changed over time.
    """

    __tablename__ = "analytics_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )

    client_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    chatwoot_conv_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    chatwoot_url: Mapped[str] = mapped_column(String(500), nullable=False)

    # Current funnel status at the time of this snapshot
    funnel_status: Mapped[str | None] = mapped_column(String(100))

    # Complete analytics snapshot at the time of change
    analytics_snapshot: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)

    # Metadata
    change_type: Mapped[str] = mapped_column(String(50), nullable=False, default="update")  # update, create, etc.
    test_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("test_runs.id", ondelete="SET NULL"),
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"AnalyticsHistory(id={self.id}, client={self.client_name}, "
            f"conv_id={self.chatwoot_conv_id}, status={self.funnel_status})"
        )


Index(
    "ix__analytics_history__client_conv",
    AnalyticsHistory.client_name,
    AnalyticsHistory.chatwoot_conv_id,
)
Index(
    "ix__analytics_history__created",
    AnalyticsHistory.created_at.desc(),
)
Index(
    "ix__analytics_history__funnel_status",
    AnalyticsHistory.funnel_status,
)


# =============================================================================
# Reactivation Models
# =============================================================================


class ReactivationCampaignStatus(StrEnum):
    CONFIGURING = "configuring"
    ACTIVE = "active"
    CANCELLED = "cancelled"


class ReactivationBatchStatus(StrEnum):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReactivationContactStatus(StrEnum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    SKIPPED = "skipped"


class ReactivationAttemptStatus(StrEnum):
    SCHEDULED = "scheduled"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class ReactivationCampaign(BaseModel, Base):
    """
    Reactivation campaign - top level entity.
    A campaign is tied to a specific client and inbox.
    """

    __tablename__ = "reactivation_campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # Basic info
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(50), default="whatsapp", nullable=False)

    # Chatwoot settings (from client)
    inbox_id: Mapped[int] = mapped_column(Integer, nullable=False)
    template_name: Mapped[str | None] = mapped_column(String(200))

    # CSV tracking
    csv_filename: Mapped[str | None] = mapped_column(String(500))
    csv_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_contacts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_contacts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        default=ReactivationCampaignStatus.CONFIGURING.value,
        nullable=False,
        index=True,
    )
    is_test: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Audit
    created_by_user: Mapped[str | None] = mapped_column(String(320))

    # Relationships
    client: Mapped[Client] = relationship("Client", lazy="selectin")
    batches: Mapped[list[ReactivationBatch]] = relationship(
        "ReactivationBatch",
        back_populates="campaign",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    contacts: Mapped[list[ReactivationContact]] = relationship(
        "ReactivationContact",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"ReactivationCampaign(id={self.id}, name={self.name}, status={self.status})"


Index("ix__reactivation_campaigns__client_status", ReactivationCampaign.client_id, ReactivationCampaign.status)


class ReactivationBatch(BaseModel, Base):
    """
    A batch within a campaign - represents a scheduled send to a subset of contacts.
    """

    __tablename__ = "reactivation_batches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("reactivation_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Configuration
    description: Mapped[str | None] = mapped_column(String(500))
    contact_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    custom_instructions: Mapped[str | None] = mapped_column(Text)

    # Runtime tracking
    status: Mapped[str] = mapped_column(
        String(50),
        default=ReactivationBatchStatus.SCHEDULED.value,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Statistics (denormalized for performance)
    contact_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text)

    # Relationships
    campaign: Mapped[ReactivationCampaign] = relationship("ReactivationCampaign", back_populates="batches")
    attempts: Mapped[list[ReactivationAttempt]] = relationship(
        "ReactivationAttempt",
        back_populates="batch",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"ReactivationBatch(id={self.id}, campaign_id={self.campaign_id}, batch_number={self.batch_number})"

    __table_args__ = (
        UniqueConstraint("campaign_id", "batch_number", name="uq__reactivation_batches__campaign_batch"),
        Index("ix__reactivation_batches__scheduled_status", "scheduled_at", "status"),
    )


class ReactivationContact(BaseModel, Base):
    """
    A contact from the uploaded CSV file.
    """

    __tablename__ = "reactivation_contacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("reactivation_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # CSV data
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)  # Normalized E.164
    name: Mapped[str | None] = mapped_column(String(200))
    additional_info: Mapped[str | None] = mapped_column(Text)

    # Batch assignment (NULL until batches are configured)
    assigned_batch_number: Mapped[int | None] = mapped_column(Integer)

    # Validation
    validation_status: Mapped[str] = mapped_column(
        String(50),
        default=ReactivationContactStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    validation_errors: Mapped[list] = mapped_column(MutableList.as_mutable(JSONB), default=list)
    skip_reason: Mapped[str | None] = mapped_column(String(200))

    # Relationships
    campaign: Mapped[ReactivationCampaign] = relationship("ReactivationCampaign", back_populates="contacts")
    attempts: Mapped[list[ReactivationAttempt]] = relationship(
        "ReactivationAttempt",
        back_populates="contact",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"ReactivationContact(id={self.id}, phone={self.phone_number}, status={self.validation_status})"

    __table_args__ = (
        Index("ix__reactivation_contacts__campaign_batch", "campaign_id", "assigned_batch_number"),
        Index("ix__reactivation_contacts__phone", "phone_number"),
    )


class ReactivationAttempt(BaseModel, Base):
    """
    A single send attempt for a contact in a specific batch.
    """

    __tablename__ = "reactivation_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    contact_id: Mapped[int] = mapped_column(
        ForeignKey("reactivation_contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("reactivation_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("reactivation_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Scheduling
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        default=ReactivationAttemptStatus.SCHEDULED.value,
        nullable=False,
        index=True,
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Chatwoot data
    chatwoot_contact_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chatwoot_conv_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chatwoot_conv_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    chatwoot_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Message status verification
    message_status: Mapped[str | None] = mapped_column(String(50))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_answered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_booked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Booking details
    booking_service: Mapped[str | None] = mapped_column(String(200))
    booking_service_doctor_name: Mapped[str | None] = mapped_column(String(200))
    booking_service_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    booking_service_cost: Mapped[float | None] = mapped_column(Numeric(10, 2))

    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text)

    # Metadata (EHR check results, custom attributes sent, etc.)
    attempt_metadata: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)

    # Relationships
    contact: Mapped[ReactivationContact] = relationship("ReactivationContact", back_populates="attempts")
    batch: Mapped[ReactivationBatch] = relationship("ReactivationBatch", back_populates="attempts")

    def __repr__(self) -> str:
        return f"ReactivationAttempt(id={self.id}, contact_id={self.contact_id}, status={self.status})"

    __table_args__ = (
        Index("ix__reactivation_attempts__batch_status", "batch_id", "status"),
        Index("ix__reactivation_attempts__scheduled_status", "scheduled_at", "status"),
    )


# =============================================================================
# Chatwoot Sync Models
# =============================================================================


class ChatwootConversation(BaseModel, Base):
    __tablename__ = "chatwoot_conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chatwoot_conversation_id: Mapped[int] = mapped_column(Integer, nullable=False)
    chatwoot_account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    chatwoot_inbox_id: Mapped[int | None] = mapped_column(Integer)
    uuid: Mapped[str | None] = mapped_column(String(100))

    status: Mapped[str | None] = mapped_column(String(50))
    priority: Mapped[str | None] = mapped_column(String(50))
    labels: Mapped[list] = mapped_column(MutableList.as_mutable(JSONB), default=list)
    custom_attributes: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)
    additional_attributes: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)

    assignee_id: Mapped[int | None] = mapped_column(Integer)
    assignee_name: Mapped[str | None] = mapped_column(String(200))
    contact_id: Mapped[int | None] = mapped_column(Integer)
    contact_name: Mapped[str | None] = mapped_column(String(200))
    channel: Mapped[str | None] = mapped_column(String(100))

    conversation_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    conversation_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_reply_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    chatwoot_conversation_url: Mapped[str] = mapped_column(String(500), unique=True, index=True, nullable=False)
    backfill_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    location: Mapped[Location] = relationship("Location", lazy="selectin")

    def __repr__(self) -> str:
        return f"ChatwootConversation(id={self.id}, chatwoot_id={self.chatwoot_conversation_id})"

    __table_args__ = (
        UniqueConstraint(
            "location_id",
            "chatwoot_conversation_id",
            name="uq__chatwoot_conversations__location_conv",
        ),
        Index("ix__chatwoot_conversations__location_status", "location_id", "status"),
        Index("ix__chatwoot_conversations__last_activity", "location_id", "last_activity_at"),
    )


class ChatwootMessage(BaseModel, Base):
    __tablename__ = "chatwoot_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chatwoot_message_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    chatwoot_conversation_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    chatwoot_account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    chatwoot_inbox_id: Mapped[int | None] = mapped_column(Integer)

    content: Mapped[str | None] = mapped_column(Text)
    message_type: Mapped[int | None] = mapped_column(Integer)
    private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str | None] = mapped_column(String(50))
    content_type: Mapped[str | None] = mapped_column(String(100))

    sender_type: Mapped[str | None] = mapped_column(String(100))
    sender_id: Mapped[int | None] = mapped_column(Integer)
    sender_name: Mapped[str | None] = mapped_column(String(200))

    content_attributes: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)
    additional_attributes: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)
    attachments: Mapped[list] = mapped_column(MutableList.as_mutable(JSONB), default=list)
    external_source_ids: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)

    message_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    message_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"ChatwootMessage(id={self.id}, chatwoot_id={self.chatwoot_message_id})"


Index(
    "ix__chatwoot_messages__location_conv_created",
    ChatwootMessage.location_id,
    ChatwootMessage.chatwoot_conversation_id,
    ChatwootMessage.message_created_at,
)
Index(
    "ix__chatwoot_messages__location_created",
    ChatwootMessage.location_id,
    ChatwootMessage.message_created_at,
)
Index(
    "ix__chatwoot_messages__conv_type",
    ChatwootMessage.chatwoot_conversation_id,
    ChatwootMessage.message_type,
)


# =============================================================================
# Service Catalog Models
# =============================================================================


class ServiceCategory(BaseModel, Base):
    """Service category (Department / Category)."""

    __tablename__ = "service_categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("service_categories.id", ondelete="SET NULL"),
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Audit - who made the last change
    updated_by: Mapped[str | None] = mapped_column(String(255))  # email of the user

    # Data
    name_i18n: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
        nullable=False,
    )  # e.g. {"en": "Massage", "ar": "...", "ru": "..."}
    description_i18n: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
        nullable=False,
    )

    # Hierarchy and sorting
    level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 0 = department (top level), 1 = category, 2 = subcategory
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Visibility
    is_visible_to_ai: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # EHR mapping
    external_id: Mapped[str | None] = mapped_column(String(200), index=True)
    source: Mapped[str] = mapped_column(
        String(50),
        default="manual",
        nullable=False,
    )  # altegio, simplex, shortcuts, manual
    source_data: Mapped[dict | None] = mapped_column(JSONB)  # Raw EHR data
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Overrides - fields manually changed by manager (have priority over EHR sync)
    overridden_fields: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSONB),
        default=list,
        nullable=False,
    )  # ["name_i18n", "description_i18n"] - fields that won't be overwritten by sync

    # Relationships
    location: Mapped[Location] = relationship("Location")
    parent: Mapped[ServiceCategory | None] = relationship(
        "ServiceCategory",
        remote_side="ServiceCategory.id",
        back_populates="children",
    )
    children: Mapped[list[ServiceCategory]] = relationship(
        "ServiceCategory",
        back_populates="parent",
        lazy="selectin",
    )
    services: Mapped[list[Service]] = relationship(
        "Service",
        back_populates="category",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"ServiceCategory(id={self.id}, location_id={self.location_id}, name={self.get_name()})"

    def get_name(self, lang: str = "en") -> str:
        """Get name with fallback to English."""
        return self.name_i18n.get(lang) or self.name_i18n.get("en") or ""

    def get_description(self, lang: str = "en") -> str:
        """Get description with fallback to English."""
        return self.description_i18n.get(lang) or self.description_i18n.get("en") or ""


Index("ix__service_categories__location_parent", ServiceCategory.location_id, ServiceCategory.parent_id)
Index("ix__service_categories__location_archived", ServiceCategory.location_id, ServiceCategory.is_archived)


class Service(BaseModel, Base):
    """Clinic service."""

    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("service_categories.id", ondelete="SET NULL"),
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    # Audit - who made the last change
    updated_by: Mapped[str | None] = mapped_column(String(255))  # email of the user

    # === Core data ===
    name_i18n: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
        nullable=False,
    )
    description_i18n: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
        nullable=False,
    )

    # Aliases for AI matching
    aliases: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSONB),
        default=list,
        nullable=False,
    )  # e.g. ["botox", "botulinum", "filler"]

    # === Parameters ===
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    # Default duration. Per-practitioner duration stored in service_practitioners.

    capacity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # 1 = individual, >1 = group service (yoga, etc.)

    # === Price ===
    price_type: Mapped[str] = mapped_column(
        String(20),
        default=PriceType.UNKNOWN.value,
        nullable=False,
    )
    price_min: Mapped[float | None] = mapped_column(Numeric(10, 2))
    price_max: Mapped[float | None] = mapped_column(Numeric(10, 2))
    # Currency from Location.get_currency()
    price_note_i18n: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
        nullable=False,
    )  # {"en": "Price depends on treatment area"}

    # === Prepayment ===
    prepaid: Mapped[str] = mapped_column(
        String(20),
        default=PrepaidType.FORBIDDEN.value,
        nullable=False,
    )  # forbidden, allowed, required

    # === Booking mode ===
    booking_mode: Mapped[str] = mapped_column(
        String(20),
        default=BookingMode.SLOTS.value,
        nullable=False,
    )

    # === Visibility and status ===
    is_visible_to_ai: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # === EHR mapping ===
    external_id: Mapped[str | None] = mapped_column(String(200), index=True)
    source: Mapped[str] = mapped_column(
        String(50),
        default="manual",
        nullable=False,
    )
    source_data: Mapped[dict | None] = mapped_column(JSONB)  # Raw EHR data
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # === Overrides ===
    # Fields that were manually overridden and should not be updated during sync
    overridden_fields: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSONB),
        default=list,
        nullable=False,
    )  # ["name_i18n", "description_i18n", "price_min"]

    # === Relationships ===
    location: Mapped[Location] = relationship("Location")
    category: Mapped[ServiceCategory | None] = relationship(
        "ServiceCategory",
        back_populates="services",
    )
    practitioner_links: Mapped[list[ServicePractitioner]] = relationship(
        "ServicePractitioner",
        back_populates="service",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    resource_links: Mapped[list[ServiceResource]] = relationship(
        "ServiceResource",
        back_populates="service",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    offer_links: Mapped[list[OfferService]] = relationship(
        "OfferService",
        back_populates="service",
        lazy="noload",  # Not loaded by default
    )

    def __repr__(self) -> str:
        return f"Service(id={self.id}, location_id={self.location_id}, name={self.get_name()})"

    def get_name(self, lang: str = "en") -> str:
        """Get name with fallback to English."""
        return self.name_i18n.get(lang) or self.name_i18n.get("en") or ""

    def get_description(self, lang: str = "en") -> str:
        """Get description with fallback to English."""
        return self.description_i18n.get(lang) or self.description_i18n.get("en") or ""

    @property
    def is_overridden(self) -> bool:
        """Check if service has any manual overrides."""
        return len(self.overridden_fields) > 0

    def is_field_overridden(self, field: str) -> bool:
        """Check if specific field is overridden."""
        return field in self.overridden_fields

    @property
    def is_group_service(self) -> bool:
        """Check if this is a group service."""
        return self.capacity > 1


Index("ix__services__location_category", Service.location_id, Service.category_id)
Index("ix__services__location_archived", Service.location_id, Service.is_archived)
Index("ix__services__external_id", Service.location_id, Service.external_id)


class Practitioner(BaseModel, Base):
    """Doctor, therapist, or specialist."""

    __tablename__ = "practitioners"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    # Audit - who made the last change
    updated_by: Mapped[str | None] = mapped_column(String(255))  # email of the user

    # Type (doctor vs resource/room)
    practitioner_type: Mapped[str] = mapped_column(
        String(50),
        default=PractitionerType.DOCTOR.value,
        nullable=False,
    )

    # === Core data ===
    name_i18n: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
        nullable=False,
    )
    description_i18n: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
        nullable=False,
    )

    # Speciality
    speciality_i18n: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
        nullable=False,
    )
    speciality_code: Mapped[str | None] = mapped_column(String(100))

    # Demographics
    sex: Mapped[str | None] = mapped_column(String(20))  # male, female, other
    languages: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSONB),
        default=list,
        nullable=False,
    )

    # Experience and qualifications
    years_of_experience: Mapped[int | None] = mapped_column(Integer)
    qualifications_i18n: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
        nullable=False,
    )

    # Patient types
    treats_babies: Mapped[bool | None] = mapped_column(Boolean)
    treats_children: Mapped[bool | None] = mapped_column(Boolean)
    treats_elderly: Mapped[bool | None] = mapped_column(Boolean)
    treats_athletes: Mapped[bool | None] = mapped_column(Boolean)
    patient_types_note: Mapped[str | None] = mapped_column(Text)

    # Conditions treated
    conditions_treated: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSONB),
        default=list,
        nullable=False,
    )

    # Photo
    photo_url: Mapped[str | None] = mapped_column(String(500))  # TODO: Remove later

    # === Visibility and status ===
    is_visible_to_ai: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # === EHR mapping ===
    external_id: Mapped[str | None] = mapped_column(String(200), index=True)
    source: Mapped[str] = mapped_column(
        String(50),
        default="manual",
        nullable=False,
    )
    source_data: Mapped[dict | None] = mapped_column(JSONB)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # === Overrides ===
    overridden_fields: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSONB),
        default=list,
        nullable=False,
    )

    # === Relationships ===
    location: Mapped[Location] = relationship("Location")
    service_links: Mapped[list[ServicePractitioner]] = relationship(
        "ServicePractitioner",
        back_populates="practitioner",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"Practitioner(id={self.id}, location_id={self.location_id}, name={self.get_name()})"

    def get_name(self, lang: str = "en") -> str:
        """Get name with fallback to English."""
        return self.name_i18n.get(lang) or self.name_i18n.get("en") or ""

    def get_speciality(self, lang: str = "en") -> str:
        """Get speciality with fallback to English."""
        return self.speciality_i18n.get(lang) or self.speciality_i18n.get("en") or ""

    @property
    def is_overridden(self) -> bool:
        """Check if practitioner has any manual overrides."""
        return len(self.overridden_fields) > 0


Index("ix__practitioners__location_type", Practitioner.location_id, Practitioner.practitioner_type)
Index("ix__practitioners__location_archived", Practitioner.location_id, Practitioner.is_archived)
Index("ix__practitioners__external_id", Practitioner.location_id, Practitioner.external_id)


class ServicePractitioner(BaseModel, Base):
    """Link between service and practitioner with per-practitioner parameters."""

    __tablename__ = "service_practitioners"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    practitioner_id: Mapped[int] = mapped_column(
        ForeignKey("practitioners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Per-practitioner parameters (override Service defaults)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    # From Altegio: different practitioners can have different duration for same service
    # If NULL — use Service.duration_minutes

    price_min: Mapped[float | None] = mapped_column(Numeric(10, 2))
    price_max: Mapped[float | None] = mapped_column(Numeric(10, 2))
    # Can override price for specific practitioner

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_visible_to_ai: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Fields manually overridden by manager (not from EHR sync)
    overridden_fields: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSONB),
        default=list,
        nullable=False,
    )

    # EHR data
    external_data: Mapped[dict | None] = mapped_column(JSONB)

    # Relationships
    service: Mapped[Service] = relationship("Service", back_populates="practitioner_links")
    practitioner: Mapped[Practitioner] = relationship("Practitioner", back_populates="service_links")

    def __repr__(self) -> str:
        return f"ServicePractitioner(service_id={self.service_id}, practitioner_id={self.practitioner_id})"

    __table_args__ = (
        UniqueConstraint("service_id", "practitioner_id", name="uq__service_practitioners__service_practitioner"),
    )


# =============================================================================
# Resource Models (Equipment, Rooms)
# =============================================================================


class Resource(BaseModel, Base):
    """Resource type (equipment, room, device)."""

    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    # Audit - who made the last change
    updated_by: Mapped[str | None] = mapped_column(String(255))  # email of the user

    # === Core data ===
    name_i18n: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
        nullable=False,
    )  # {"en": "Laser Machine", "ar": "جهاز ليزر"}
    description_i18n: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
        nullable=False,
    )

    # === Classification ===
    department: Mapped[str | None] = mapped_column(String(200))  # Text field for categorization

    # === Visibility and status ===
    is_visible_to_ai: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # === EHR mapping ===
    external_id: Mapped[str | None] = mapped_column(String(200), index=True)  # key from external system
    source: Mapped[str] = mapped_column(
        String(50),
        default="manual",
        nullable=False,
    )  # altegio, manual
    source_data: Mapped[dict | None] = mapped_column(JSONB)  # Raw EHR data
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # === Overrides ===
    overridden_fields: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSONB),
        default=list,
        nullable=False,
    )  # ["name_i18n", "description_i18n"]

    # === Relationships ===
    location: Mapped[Location] = relationship("Location")
    instances: Mapped[list[ResourceInstance]] = relationship(
        "ResourceInstance",
        back_populates="resource",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    service_links: Mapped[list[ServiceResource]] = relationship(
        "ServiceResource",
        back_populates="resource",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"Resource(id={self.id}, location_id={self.location_id}, name={self.get_name()})"

    def get_name(self, lang: str = "en") -> str:
        """Get name with fallback to English."""
        return self.name_i18n.get(lang) or self.name_i18n.get("en") or ""

    def get_description(self, lang: str = "en") -> str:
        """Get description with fallback to English."""
        return self.description_i18n.get(lang) or self.description_i18n.get("en") or ""

    @property
    def is_overridden(self) -> bool:
        """Check if resource has any manual overrides."""
        return len(self.overridden_fields) > 0

    def is_field_overridden(self, field: str) -> bool:
        """Check if specific field is overridden."""
        return field in self.overridden_fields

    @property
    def active_instance_count(self) -> int:
        """Get count of active instances."""
        return sum(1 for inst in self.instances if inst.is_active)


Index("ix__resources__location_archived", Resource.location_id, Resource.is_archived)
Index("ix__resources__location_external", Resource.location_id, Resource.external_id)


class ResourceInstance(BaseModel, Base):
    """Specific instance of a resource (e.g., 'Laser #1', 'Room 203')."""

    __tablename__ = "resource_instances"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # === Core data ===
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Not i18n — usually technical names/numbers like "LASER MACHINE CUTERA #1", "Room 203"

    # === Status ===
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Can deactivate (under repair, etc.)
    is_visible_to_ai: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # === EHR mapping ===
    external_id: Mapped[str | None] = mapped_column(String(200), index=True)
    source_data: Mapped[dict | None] = mapped_column(JSONB)

    # === Relationships ===
    resource: Mapped[Resource] = relationship("Resource", back_populates="instances")

    def __repr__(self) -> str:
        return f"ResourceInstance(id={self.id}, resource_id={self.resource_id}, name={self.name})"

    __table_args__ = (
        Index("ix__resource_instances__resource_active", "resource_id", "is_active"),
        UniqueConstraint("resource_id", "name", name="uq__resource_instances__resource_name"),
    )


class ServiceResource(BaseModel, Base):
    """Link between service and required resource."""

    __tablename__ = "service_resources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # === Requirement type ===
    requirement_type: Mapped[str] = mapped_column(
        String(20),
        default=ResourceRequirementType.REQUIRED.value,
        nullable=False,
    )
    # REQUIRED: this resource is mandatory
    # ALTERNATIVE: can use any of the alternative resources in the same group

    # Alternative group (for grouping OR-relations)
    alternative_group: Mapped[int | None] = mapped_column(Integer)
    # Example: service requires (Laser A OR Laser B) AND Room
    # Laser A: requirement_type=alternative, alternative_group=1
    # Laser B: requirement_type=alternative, alternative_group=1
    # Room: requirement_type=required, alternative_group=NULL

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_visible_to_ai: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Fields manually overridden by manager (not from EHR sync)
    overridden_fields: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSONB),
        default=list,
        nullable=False,
    )

    # EHR data
    external_data: Mapped[dict | None] = mapped_column(JSONB)

    # === Relationships ===
    service: Mapped[Service] = relationship("Service", back_populates="resource_links")
    resource: Mapped[Resource] = relationship("Resource", back_populates="service_links")

    def __repr__(self) -> str:
        return f"ServiceResource(service_id={self.service_id}, resource_id={self.resource_id})"

    __table_args__ = (UniqueConstraint("service_id", "resource_id", name="uq__service_resources__service_resource"),)


# =============================================================================
# Offer Models (Promotions, Special Deals)
# =============================================================================


class Offer(BaseModel, Base):
    """Offer / Promotion / Special deal for a location."""

    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    # Audit - who made the last change
    updated_by: Mapped[str | None] = mapped_column(String(255))  # email of the user

    # === Core data ===
    name_i18n: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
        nullable=False,
    )  # {"en": "First Visit Discount", "ar": "خصم الزيارة الأولى"}

    description_i18n: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
        nullable=False,
    )  # Terms and full description of the offer

    promo_text_i18n: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
        nullable=False,
    )  # Promotional text for LLM bot usage

    # === Discount ===
    discount_type: Mapped[str] = mapped_column(
        String(20),
        default=DiscountType.NONE.value,
        nullable=False,
    )  # percentage, fixed, none

    discount_value: Mapped[float | None] = mapped_column(Numeric(10, 2))
    # Discount value: 20 (for 20%) or 100 (for -100 AED)
    # NULL if discount_type = none

    # === Validity period ===
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # NULL = unlimited offer

    # === Time restrictions ===
    # Weekdays: [0, 1, 2, 3, 4, 5, 6] where 0 = Monday, 6 = Sunday
    weekdays: Mapped[list[int] | None] = mapped_column(
        MutableList.as_mutable(JSONB),
    )  # NULL = all days, [0, 1, 2] = Mon, Tue, Wed

    # Time of day (happy hour)
    time_from: Mapped[str | None] = mapped_column(String(5))  # "09:00"
    time_until: Mapped[str | None] = mapped_column(String(5))  # "18:00"

    # === Conditions ===
    is_first_visit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Only for client's first visit

    has_complex_logic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Flag for offers with complex conditions (VIP status, consecutive visits, etc.)
    # Conditions are described in description_i18n

    # === Advertising / UTM ===
    utm_ref: Mapped[str | None] = mapped_column(String(500))
    # Key from WhatsApp utm (ref parameter)
    # Example: "instagram_laser_promo_2024"

    pre_filled_message: Mapped[str | None] = mapped_column(Text)
    # Pre-filled message from WhatsApp advertising
    # Example: "I want to book with Instagram promo"

    # === Campaign type ===
    is_reactivation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Flag for reactivation campaigns (mailing to old customer base)

    # === Status ===
    is_visible_to_ai: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # === EHR mapping ===
    external_id: Mapped[str | None] = mapped_column(String(200), index=True)
    source: Mapped[str] = mapped_column(
        String(50),
        default="manual",
        nullable=False,
    )  # altegio, manual
    source_data: Mapped[dict | None] = mapped_column(JSONB)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # === Overrides ===
    overridden_fields: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSONB),
        default=list,
        nullable=False,
    )

    # === Relationships ===
    location: Mapped[Location] = relationship("Location")
    service_links: Mapped[list[OfferService]] = relationship(
        "OfferService",
        back_populates="offer",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"Offer(id={self.id}, location_id={self.location_id}, name={self.get_name()})"

    def get_name(self, lang: str = "en") -> str:
        """Get name with fallback to English."""
        return self.name_i18n.get(lang) or self.name_i18n.get("en") or ""

    def get_description(self, lang: str = "en") -> str:
        """Get description with fallback to English."""
        return self.description_i18n.get(lang) or self.description_i18n.get("en") or ""

    def get_promo_text(self, lang: str = "en") -> str:
        """Get promo text with fallback to English."""
        return self.promo_text_i18n.get(lang) or self.promo_text_i18n.get("en") or ""

    @property
    def is_overridden(self) -> bool:
        """Check if offer has any manual overrides."""
        return len(self.overridden_fields) > 0

    def is_field_overridden(self, field: str) -> bool:
        """Check if specific field is overridden."""
        return field in self.overridden_fields

    @property
    def is_time_limited(self) -> bool:
        """Check if offer has time restrictions."""
        return self.valid_from is not None or self.valid_until is not None

    @property
    def has_weekday_restrictions(self) -> bool:
        """Check if offer has weekday restrictions."""
        days_in_week = 7
        return self.weekdays is not None and len(self.weekdays) < days_in_week

    @property
    def has_time_of_day_restrictions(self) -> bool:
        """Check if offer has time of day restrictions (happy hour)."""
        return self.time_from is not None or self.time_until is not None

    @property
    def linked_services_count(self) -> int:
        """Get count of linked services."""
        return len(self.service_links) if self.service_links else 0


Index("ix__offers__location_archived", Offer.location_id, Offer.is_archived)
Index("ix__offers__location_reactivation", Offer.location_id, Offer.is_reactivation)
Index("ix__offers__utm_ref", Offer.utm_ref)
Index("ix__offers__location_external", Offer.location_id, Offer.external_id)


class OfferService(BaseModel, Base):
    """Link between offer and applicable service."""

    __tablename__ = "offer_services"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    offer_id: Mapped[int] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
    )

    # Per-service discount override (optional)
    # If NULL — uses discount from Offer
    discount_value_override: Mapped[float | None] = mapped_column(Numeric(10, 2))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # === Relationships ===
    offer: Mapped[Offer] = relationship("Offer", back_populates="service_links")
    service: Mapped[Service] = relationship("Service", back_populates="offer_links")

    def __repr__(self) -> str:
        return f"OfferService(offer_id={self.offer_id}, service_id={self.service_id})"

    __table_args__ = (UniqueConstraint("offer_id", "service_id", name="uq__offer_services__offer_service"),)


# =============================================================================
# Audit Log
# =============================================================================


class AuditEntityType(StrEnum):
    """Entity types that can be audited."""

    SERVICE = "service"
    SERVICE_CATEGORY = "service_category"
    PRACTITIONER = "practitioner"
    RESOURCE = "resource"
    OFFER = "offer"
    LOCATION = "location"
    CLIENT = "client"


class AuditAction(StrEnum):
    """Audit action types."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ARCHIVE = "archive"
    RESTORE = "restore"
    LINK = "link"
    UNLINK = "unlink"


class AuditLog(BaseModel, Base):
    """
    Audit log for tracking changes to entities.

    Records who changed what and when, with before/after values.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # What was changed
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    entity_name: Mapped[str | None] = mapped_column(String(255))  # Human-readable name for display

    # What action was performed
    action: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Who made the change
    actor: Mapped[str] = mapped_column(String(255), nullable=False)  # "user:email" or "system:ehr_sync"

    # When
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        nullable=False,
        index=True,
    )

    # What changed (field -> {old, new})
    changes: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
        nullable=False,
    )

    # Context (location_id for filtering)
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"),
        index=True,
    )

    def __repr__(self) -> str:
        return f"AuditLog(id={self.id}, {self.entity_type}:{self.entity_id}, {self.action}, by={self.actor})"


Index("ix__audit_logs__entity", AuditLog.entity_type, AuditLog.entity_id)
Index("ix__audit_logs__location_created", AuditLog.location_id, AuditLog.created_at.desc())


# =============================================================================
# Sync Log
# =============================================================================


class SyncLogStatus(StrEnum):
    """Status of a sync operation."""

    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class SyncLog(BaseModel, Base):
    """History of EHR sync operations."""

    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[float | None] = mapped_column(Numeric(10, 2))

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default=SyncLogStatus.IN_PROGRESS.value,
        nullable=False,
        index=True,
    )
    error: Mapped[str | None] = mapped_column(Text)

    # Results per entity (JSONB for flexibility)
    # Format: {"categories": {"created": 0, "updated": 5, ...}, "services": {...}, ...}
    results: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
        nullable=False,
    )

    # Totals (denormalized for quick queries and display)
    total_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_archived: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_errors: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Trigger info
    triggered_by: Mapped[str | None] = mapped_column(String(255))  # "user:email" or "system:scheduler"

    # Source info
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # altegio, simplex, etc.

    # Relationship
    location: Mapped[Location] = relationship("Location")

    def __repr__(self) -> str:
        return f"SyncLog(id={self.id}, location_id={self.location_id}, status={self.status})"

    @property
    def total_processed(self) -> int:
        return self.total_created + self.total_updated

    @property
    def has_errors(self) -> bool:
        return self.total_errors > 0


Index("ix__sync_logs__location_started", SyncLog.location_id, SyncLog.started_at.desc())
Index("ix__sync_logs__status", SyncLog.status)
