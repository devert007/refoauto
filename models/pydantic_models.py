from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import re


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


class Sex:
    """Sex/Gender values"""
    MALE = "male"
    FEMALE = "female"


class Branch:
    """Branch/Location values"""
    JUMEIRAH = "jumeirah"  # Hortman Clinics - Jumeirah 3
    SRZ = "srz"  # Hortman Clinics - Sheikh Zayed Road


class Practitioner(BaseModel):
    """
    Practitioner/Doctor model.
    
    Data source: Google Sheets "Hortman - Practitioners"
    https://docs.google.com/spreadsheets/d/1ZXYPl573sgfdRYDJj1RzPDJLPpyKpGY6vgr4NsgJSlk/edit?gid=881293577#gid=881293577
    """
    id: int = Field(description="Unique practitioner identifier (from Google Sheets column A)")
    
    # === Basic Info ===
    name: str = Field(
        description="Full name of the practitioner. Column: Name. Example: 'Dr. Anna Zakhozha'"
    )
    name_i18n: dict = Field(
        default_factory=dict,
        description="Practitioner name in multiple languages. Format: {'en': 'Dr. Anna Zakhozha', 'ru': 'Др. Анна Захожа'}"
    )
    
    speciality: str = Field(
        default="",
        description="Medical speciality. Column: Speciality. Example: 'Specialist Dermatology', 'General Practitioner', 'Consultant Obstetrician and Gynaecologist'"
    )
    
    sex: str = Field(
        default=Sex.FEMALE,
        description="Sex/Gender. Column: Sex. Values: 'male', 'female'"
    )
    
    languages: list[str] = Field(
        default_factory=list,
        description="Languages spoken. Column: Languages. Example: ['ENGLISH', 'RUSSIAN', 'UKRAINIAN']. Parse from concatenated string like 'ENGLISHRUSSIANUKRAINIAN'"
    )
    
    # === Description ===
    description_i18n: dict = Field(
        default_factory=dict,
        description="Full biography/description. Columns: Description English, Description Russian. Format: {'en': '...', 'ru': '...'}"
    )
    
    # === Experience & Qualifications ===
    years_of_experience: Optional[int] = Field(
        default=None,
        description="Years of professional experience. Column: Years of experience. Example: 13, 25. Parse from strings like '13+' or '25'"
    )
    
    primary_qualifications: str = Field(
        default="",
        description="Primary qualifications, education, degrees. Column: Primary Qualifications. Medical degree, residency, board certifications."
    )
    
    secondary_qualifications: str = Field(
        default="",
        description="Secondary qualifications, fellowships, memberships. Column: Secondary Qualifications."
    )
    
    additional_qualifications: str = Field(
        default="",
        description="Additional certifications, courses, trainings. Column: Additional Qualifications."
    )
    
    # === Practice Info ===
    treat_children: bool = Field(
        default=False,
        description="Whether practitioner treats children. Column: treat children. Parse: 'No' → False, 'Any age' → True, '13+' → True (with age restriction)"
    )
    
    treat_children_age: Optional[str] = Field(
        default=None,
        description="Minimum age for child patients if applicable. Example: '13+', 'Any age'. Extracted from 'treat children' column."
    )
    
    branches: list[str] = Field(
        default_factory=list,
        description="Clinic branches where practitioner works. Column: Branch. Values: 'jumeirah' (Jumeirah 3), 'srz' (Sheikh Zayed Road). Parse from 'Hortman Clinics - Jumeirah 3' → 'jumeirah', 'Hortman Clinics - Sheikh Zayed Road' → 'srz'"
    )
    
    # === API Fields ===
    is_visible_to_ai: bool = Field(
        default=True,
        description="Whether AI assistant can see and recommend this practitioner"
    )
    
    is_archived: bool = Field(
        default=False,
        description="Whether practitioner is archived (hidden from active listings)"
    )
    
    external_id: Optional[str] = Field(
        default=None,
        description="External ID from EHR system"
    )
    
    source: str = Field(
        default="manual",
        description="Data source: 'manual', 'google_sheets', etc."
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


# === Helper functions for parsing Google Sheets data ===

# Known languages for parsing concatenated language strings
KNOWN_LANGUAGES = [
    "ENGLISH", "RUSSIAN", "UKRAINIAN", "ARABIC", "FRENCH", 
    "AFRIKAANS", "ROMANIAN", "TURKISH", "ARMENIAN", "SPANISH"
]


def parse_languages(raw: str) -> list[str]:
    """
    Parse concatenated language string from Google Sheets.
    
    Example: "ENGLISHRUSSIANUKRAINIAN" → ["ENGLISH", "RUSSIAN", "UKRAINIAN"]
    """
    if not raw:
        return []
    
    raw_upper = raw.upper().strip()
    found = []
    
    # Try to find each known language in the string
    for lang in KNOWN_LANGUAGES:
        if lang in raw_upper:
            found.append(lang)
            raw_upper = raw_upper.replace(lang, "", 1)
    
    return found


def parse_sex(raw: str) -> str:
    """
    Parse sex/gender from Google Sheets.
    
    Example: "Female" → "female", "Male" → "male"
    """
    if not raw:
        return Sex.FEMALE
    
    raw_lower = raw.lower().strip()
    if raw_lower == "male":
        return Sex.MALE
    return Sex.FEMALE


def parse_years_of_experience(raw: str) -> Optional[int]:
    """
    Parse years of experience from Google Sheets.
    
    Examples: "13+" → 13, "25" → 25, "13" → 13
    """
    if not raw:
        return None
    
    # Extract digits
    match = re.search(r'(\d+)', str(raw))
    if match:
        return int(match.group(1))
    return None


def parse_treat_children(raw: str) -> tuple[bool, Optional[str]]:
    """
    Parse 'treat children' field from Google Sheets.
    
    Returns: (treats_children: bool, age_restriction: str | None)
    
    Examples:
        "No" → (False, None)
        "Any age" → (True, "Any age")
        "13+" → (True, "13+")
        "" → (False, None)
    """
    if not raw:
        return (False, None)
    
    raw_clean = raw.strip()
    
    if raw_clean.lower() == "no":
        return (False, None)
    
    # Any other value means they treat children
    return (True, raw_clean if raw_clean else None)


def parse_branches(raw: str) -> list[str]:
    """
    Parse branch/location from Google Sheets.
    
    Examples:
        "Hortman Clinics - Jumeirah 3" → ["jumeirah"]
        "Hortman Clinics - Sheikh Zayed Road" → ["srz"]
        "Hortman Clinics - Sheikh Zayed RoadHortman Clinics - Jumeirah 3" → ["srz", "jumeirah"]
    """
    if not raw:
        return []
    
    branches = []
    raw_lower = raw.lower()
    
    if "jumeirah" in raw_lower:
        branches.append(Branch.JUMEIRAH)
    if "sheikh zayed" in raw_lower or "szr" in raw_lower or "zayed road" in raw_lower:
        branches.append(Branch.SRZ)
    
    return branches


def practitioner_from_sheets_row(row: dict) -> dict:
    """
    Convert a Google Sheets row to Practitioner dict.
    
    Args:
        row: Dict with keys matching column headers from Google Sheets
             (Name, Speciality, Sex, Languages, Description English, etc.)
    
    Returns:
        Dict ready to create Practitioner model
    """
    # Parse treat_children
    treat_children, treat_children_age = parse_treat_children(row.get("treat children", ""))
    
    return {
        "id": int(row.get("ID", 0)) if row.get("ID") else 0,
        "name": row.get("Name", "").strip(),
        "name_i18n": {"en": row.get("Name", "").strip()},
        "speciality": row.get("Speciality", "").strip(),
        "sex": parse_sex(row.get("Sex", "")),
        "languages": parse_languages(row.get("Languages", "")),
        "description_i18n": {
            "en": row.get("Description English", "").strip(),
            "ru": row.get("Description Russian", "").strip() or None
        },
        "years_of_experience": parse_years_of_experience(row.get("Years of experience", "")),
        "primary_qualifications": row.get("Primary Qualifications", "").strip(),
        "secondary_qualifications": row.get("Secondary Qualifications", "").strip(),
        "additional_qualifications": row.get("Additional Qualifications", "").strip(),
        "treat_children": treat_children,
        "treat_children_age": treat_children_age,
        "branches": parse_branches(row.get("Branch", "")),
        "is_visible_to_ai": True,
        "source": "google_sheets"
    }


# Clean up description_i18n (remove None values)
def _clean_i18n_dict(d: dict) -> dict:
    """Remove None values from i18n dict"""
    return {k: v for k, v in d.items() if v}
