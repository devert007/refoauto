from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PriceType:
    FIXED = "fixed"
    RANGE = "range"
    UNKNOWN = "unknown"


class PrepaidType:
    FORBIDDEN = "forbidden"
    ALLOWED = "allowed"
    REQUIRED = "required"


class BookingMode:
    SLOTS = "slots"
    REQUEST = "request"


# === New Models ===

class ServiceCategory(BaseModel):
    """Service category model"""
    id: int = Field(description="Unique category identifier")
    name_i18n: dict = Field(
        default_factory=dict,
        description="Category name in multiple languages. Format: {'en': 'Category Name'}"
    )
    sort_order: int = Field(default=0, description="Sort order for displaying categories")


class Practitioner(BaseModel):
    """Practitioner/Doctor model"""
    id: int = Field(description="Unique practitioner identifier")
    name: str = Field(description="Full name of the practitioner. Example: 'Dr. Anna Zakhozha'")
    name_i18n: dict = Field(
        default_factory=dict,
        description="Practitioner name in multiple languages. Format: {'en': 'Dr. Anna Zakhozha'}"
    )


class ServicePractitioner(BaseModel):
    """Many-to-many relationship between Service and Practitioner"""
    service_id: int = Field(description="Foreign key to Service")
    practitioner_id: int = Field(description="Foreign key to Practitioner")


# === Existing Models (updated) ===

class SourceData(BaseModel):
    """Raw data from external EHR system (Altegio)"""
    
    # id: Optional[int] = None
    # category_id: Optional[int] = None
    # salon_service_id: Optional[int] = None
    # api_service_id: Optional[int] = None
    # api_id: Optional[str] = None
    # vat_id: Optional[int] = None

    title: str = Field(default="", description="Service title in EHR system")
    original_title: str = Field(default="", description="Original unmodified title from EHR")
    booking_title: str = Field(default="", description="Title displayed during booking process")
    print_title: str = Field(default="", description="Title used for printing receipts/documents")
    comment: str = Field(default="", description="Internal comment or note about the service")
    active: int = Field(default=0, description="Service active status: 0=inactive, 1=active")
    is_online: bool = Field(default=False, description="Whether service is available for online booking")
    is_chain: bool = Field(default=False, description="Whether service belongs to a chain/network")
    is_multi: bool = Field(default=False, description="Whether multiple services can be booked together")
    is_composite: bool = Field(default=False, description="Whether service is composed of sub-services")
    duration: int = Field(default=0, description="Service duration in seconds")
    step: int = Field(default=0, description="Time step for scheduling in seconds")
    seance_search_step: int = Field(default=900, description="Search step for available slots in seconds (default 15 min)")
    seance_search_start: int = Field(default=0, description="Start time offset for slot search in seconds from midnight")
    seance_search_finish: int = Field(default=86400, description="End time offset for slot search in seconds from midnight")
    price_min: float = Field(default=0, description="Minimum price of the service")
    price_max: float = Field(default=0, description="Maximum price of the service")
    discount: int = Field(default=0, description="Discount percentage applied to service")
    price_prepaid_amount: float = Field(default=0, description="Fixed prepayment amount required")
    price_prepaid_percent: int = Field(default=100, description="Prepayment percentage of total price")
    capacity: int = Field(default=0, description="Maximum number of clients per session")
    weight: int = Field(default=0, description="Sort weight for ordering services")
    date_from: str = Field(default="0000-00-00", description="Service availability start date (YYYY-MM-DD)")
    date_to: str = Field(default="0000-00-00", description="Service availability end date (YYYY-MM-DD)")
    dates: list = Field(default_factory=list, description="List of specific available dates")
    prepaid: str = Field(default="forbidden", description="Prepayment policy: forbidden, allowed, required")
    service_type: int = Field(default=0, description="Type identifier of the service")
    schedule_template_type: int = Field(default=2, description="Schedule template type used for this service")
    staff: list = Field(default_factory=list, description="List of staff members who can perform this service")
    resources: list = Field(default_factory=list, description="List of resources/equipment needed for service")
    image_group: list = Field(default_factory=list, description="List of image URLs or IDs for the service")
    tax_variant: Optional[int] = Field(default=None, description="Tax variant ID applied to this service")
    is_need_limit_date: bool = Field(default=False, description="Whether service requires date limitations")
    abonement_restriction_value: int = Field(default=0, description="Subscription/membership restriction value")
    technical_break_duration: Optional[int] = Field(default=None, description="Break time after service in seconds")
    default_technical_break_duration: int = Field(default=0, description="Default break time in seconds")
    repeat_visit_days_step: Optional[int] = Field(default=None, description="Recommended days between repeat visits")
    online_invoicing_status: int = Field(default=0, description="Online invoicing status: 0=disabled")
    autopayment_before_visit_time: int = Field(default=0, description="Auto-charge time before visit in seconds")
    is_abonement_autopayment_enabled: int = Field(default=0, description="Whether subscription autopay is enabled")
    is_price_managed_only_in_chain: bool = Field(default=False, description="Price can only be changed at chain level")
    is_comment_managed_only_in_chain: bool = Field(default=False, description="Comments can only be changed at chain level")


class Service(BaseModel):
    """Service model representing a bookable service in the system"""
    
    id: int = Field(description="Unique service identifier")
    category_id: int = Field(description="Foreign key to ServiceCategory")
    branches: list[str] = Field(
        default_factory=lambda: ["jumeirah", "srz"],
        description="Branches where service is available. Values: 'jumeirah', 'srz'. Example: ['jumeirah', 'srz'] for both"
    )
    
    name_i18n: dict = Field(
        default_factory=dict,
        description="Service name in multiple languages. Format: {'en': 'English name', 'ru': 'Русское название'}"
    )
    description_i18n: dict = Field(
        default_factory=dict,
        description="Service description in multiple languages. Format: {'en': 'Description', 'ru': 'Описание'}"
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Alternative names for AI matching. Example: ['botox', 'botulinum', 'filler']"
    )
    duration_minutes: int = Field(
        default=60,
        description="Service duration in minutes"
    )
    capacity: int = Field(
        default=1,
        description="Maximum clients per session. 1=individual, >1=group service (yoga, etc.)"
    )
    price_type: str = Field(
        default=PriceType.FIXED,
        description="Price type: 'fixed', 'range', or 'unknown'"
    )
    price_min: Optional[float] = Field(
        default=None,
        description="Minimum price. Null if price is not set"
    )
    price_max: Optional[float] = Field(
        default=None,
        description="Maximum price. Same as price_min for fixed price"
    )
    price_note_i18n: dict = Field(
        default_factory=dict,
        description="Price notes in multiple languages. Example: {'en': 'Price depends on treatment area'}"
    )
    prepaid: str = Field(
        default=PrepaidType.FORBIDDEN,
        description="Prepayment policy: 'forbidden', 'allowed', or 'required'"
    )
    booking_mode: str = Field(
        default=BookingMode.SLOTS,
        description="Booking mode: 'slots' (time slots) or 'request' (on request)"
    )
    is_visible_to_ai: bool = Field(
        default=True,
        description="Whether AI assistant can see and book this service"
    )
    is_archived: bool = Field(
        default=False,
        description="Whether service is archived (hidden from active listings)"
    )
    sort_order: int = Field(
        default=0,
        description="Sort order for displaying services. Lower numbers appear first"
    )
    source: str = Field(
        default="manual",
        description="Data source: 'manual', 'Altegio', or other EHR system name"
    )
    source_data: Optional[SourceData] = Field(
        default=None,
        description="Raw data from external EHR system"
    )
    overridden_fields: list[str] = Field(
        default_factory=list,
        description="Fields manually overridden, won't be updated during sync. Example: ['name_i18n', 'price_min']"
    )
    is_overridden: bool = Field(
        default=False,
        description="Whether any fields have been manually overridden"
    )
    is_group_service: bool = Field(
        default=False,
        description="Whether this is a group service (capacity > 1)"
    )
    synced_at: Optional[datetime] = Field(
        default=None,
        description="Last synchronization timestamp with external system"
    )
    created_at: Optional[datetime] = Field(
        default=None,
        description="Record creation timestamp"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Record last update timestamp"
    )
    updated_by: Optional[str] = Field(
        default=None,
        description="Email of user who made the last update"
    )
