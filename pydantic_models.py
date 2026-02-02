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


class SourceData(BaseModel):
    # id: Optional[int] = None
    # category_id: Optional[int] = None
    # salon_service_id: Optional[int] = None
    # api_service_id: Optional[int] = None
    # api_id: Optional[str] = None
    # vat_id: Optional[int] = None

    title: str = ""
    original_title: str = ""
    booking_title: str = ""
    print_title: str = ""
    comment: str = ""
    active: int = 0
    is_online: bool = False
    is_chain: bool = False
    is_multi: bool = False
    is_composite: bool = False
    duration: int = 0
    step: int = 0
    seance_search_step: int = 900
    seance_search_start: int = 0
    seance_search_finish: int = 86400
    price_min: float = 0
    price_max: float = 0
    discount: int = 0
    price_prepaid_amount: float = 0
    price_prepaid_percent: int = 100
    capacity: int = 0
    weight: int = 0
    date_from: str = "0000-00-00"
    date_to: str = "0000-00-00"
    dates: list = Field(default_factory=list)
    prepaid: str = "forbidden"
    service_type: int = 0
    schedule_template_type: int = 2
    staff: list = Field(default_factory=list)
    resources: list = Field(default_factory=list)
    image_group: list = Field(default_factory=list)
    tax_variant: Optional[int] = None
    is_need_limit_date: bool = False
    abonement_restriction_value: int = 0
    technical_break_duration: Optional[int] = None
    default_technical_break_duration: int = 0
    repeat_visit_days_step: Optional[int] = None
    online_invoicing_status: int = 0
    autopayment_before_visit_time: int = 0
    is_abonement_autopayment_enabled: int = 0
    is_price_managed_only_in_chain: bool = False
    is_comment_managed_only_in_chain: bool = False


class Service(BaseModel):
    # === ID fields  ===
    # id: int
    # location_id: int
    # category_id: Optional[int] = None
    # external_id: Optional[str] = None

    name_i18n: dict = Field(default_factory=dict)
    description_i18n: dict = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    duration_minutes: int = 60
    capacity: int = 1
    price_type: str = PriceType.FIXED
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    price_note_i18n: dict = Field(default_factory=dict)
    prepaid: str = PrepaidType.FORBIDDEN
    booking_mode: str = BookingMode.SLOTS
    is_visible_to_ai: bool = True
    is_archived: bool = False
    sort_order: int = 0
    source: str = "manual"
    source_data: Optional[SourceData] = None
    overridden_fields: list[str] = Field(default_factory=list)
    is_overridden: bool = False
    is_group_service: bool = False
    synced_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    category_name: Optional[str] = None
    practitioners_count: int = 0
    offers_count: int = 0


class ServiceList(BaseModel):
    services: list[Service] = Field(default_factory=list)


# === example ===
#
# 1. parsing response:
#    services = [Service(**item) for item in response_json]
#
# 2. Dump with exclude_defaults :
#    data = service.model_dump(exclude_defaults=True)
#
# 3. Dump in JSON:
#    json_str = service.model_dump_json(exclude_defaults=True)
