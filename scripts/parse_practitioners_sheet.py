#!/usr/bin/env python3
"""
Parse practitioners data from Google Sheets and create practitioners.json

Usage:
    python parse_practitioners_sheet.py

Requires:
    pip install google-api-python-client google-auth-oauthlib
"""

import json
import os
import re
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Paths
BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = BASE_DIR / "config"
OUTPUT_DIR = BASE_DIR / "data" / "output"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"
TOKEN_FILE = CONFIG_DIR / "sheets_token.json"

# Google Sheets settings
SPREADSHEET_ID = "1ZXYPl573sgfdRYDJj1RzPDJLPpyKpGY6vgr4NsgJSlk"
SHEET_GID = 881293577
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Known languages for parsing concatenated strings
KNOWN_LANGUAGES = [
    "ENGLISH", "RUSSIAN", "UKRAINIAN", "ARABIC", "FRENCH",
    "AFRIKAANS", "ROMANIAN", "TURKISH", "ARMENIAN", "SPANISH",
    "GERMAN", "HINDI", "URDU", "PORTUGUESE", "ITALIAN", "PERSIAN"
]


def get_sheets_service():
    """Authenticate and return Google Sheets service."""
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"Credentials file not found: {CREDENTIALS_FILE}\n"
                    "Download OAuth credentials from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("sheets", "v4", credentials=creds)


def get_sheet_name_by_gid(service, spreadsheet_id: str, gid: int) -> str:
    """Get sheet name by GID."""
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sheet in spreadsheet.get("sheets", []):
        if sheet["properties"]["sheetId"] == gid:
            return sheet["properties"]["title"]
    raise ValueError(f"Sheet with GID {gid} not found")


def parse_name(raw_name: str) -> str:
    """Fix spacing in names: 'Dr.Sarah' -> 'Dr. Sarah'."""
    if not raw_name:
        return ""
    # Add space after Dr./Mr./Ms. etc if missing
    fixed = re.sub(r"(Dr\.|Mr\.|Ms\.|Mrs\.)(\S)", r"\1 \2", raw_name)
    return fixed.strip()


def parse_sex(raw_sex: str) -> str | None:
    """Parse sex: 'Female' -> 'female', 'Male' -> 'male'."""
    if not raw_sex:
        return None
    return raw_sex.strip().lower() if raw_sex.strip().lower() in ("male", "female") else None


def parse_languages(raw_languages: str) -> list[str]:
    """Parse concatenated languages: 'ENGLISHRUSSIAN' -> ['ENGLISH', 'RUSSIAN']."""
    if not raw_languages:
        return []

    # First try comma/semicolon separation
    if "," in raw_languages or ";" in raw_languages:
        parts = re.split(r"[,;]", raw_languages)
        return [p.strip().upper() for p in parts if p.strip()]

    # Try to split concatenated languages
    text = raw_languages.upper().replace(" ", "")
    result = []

    while text:
        matched = False
        for lang in sorted(KNOWN_LANGUAGES, key=len, reverse=True):
            if text.startswith(lang):
                result.append(lang)
                text = text[len(lang):]
                matched = True
                break
        if not matched:
            # Unknown language, skip one char and continue
            text = text[1:]

    return result


def parse_years_of_experience(raw_years: str) -> int | None:
    """Extract number from years: '13+' -> 13, '25' -> 25."""
    if not raw_years:
        return None
    match = re.search(r"(\d+)", str(raw_years))
    return int(match.group(1)) if match else None


def parse_treat_children(raw_value: str) -> tuple[bool | None, str | None]:
    """
    Parse treat_children field.
    Returns (treat_children: bool, treat_children_age: str | None)

    'No' -> (False, None)
    'Any age' -> (True, 'Any age')
    '13+' -> (True, '13+')
    """
    if not raw_value:
        return None, None

    value = raw_value.strip()

    if value.lower() == "no":
        return False, None
    elif value.lower() in ("yes", "any age"):
        return True, "Any age"
    else:
        # Assume it's an age like "13+"
        return True, value


def parse_branch(raw_branch: str) -> list[str]:
    """
    Parse branch to branch codes.
    'Hortman Clinics - Jumeirah 3' -> ['jumeirah']
    'Sheikh Zayed Road' -> ['szr']
    'Both' or contains both -> ['jumeirah', 'szr']
    """
    if not raw_branch:
        return []

    branch_lower = raw_branch.lower()
    branches = []

    if "both" in branch_lower:
        return ["jumeirah", "szr"]

    if "jumeirah" in branch_lower:
        branches.append("jumeirah")

    if "sheikh zayed" in branch_lower or "szr" in branch_lower or "zayed road" in branch_lower:
        branches.append("szr")

    return branches if branches else ["jumeirah", "szr"]  # Default to both if unclear


def parse_row(row: list, headers: list) -> dict | None:
    """Parse a single row into practitioner dict."""

    def get_val(col_name: str) -> str:
        """Get value by column name."""
        try:
            idx = headers.index(col_name)
            return row[idx].strip() if idx < len(row) and row[idx] else ""
        except ValueError:
            return ""

    # Get ID
    raw_id = get_val("ID")
    if not raw_id:
        return None

    try:
        practitioner_id = int(raw_id)
    except ValueError:
        return None

    # Parse name
    raw_name = get_val("Name")
    name = parse_name(raw_name)
    if not name:
        return None

    # Parse other fields
    speciality = get_val("Speciality") or None
    sex = parse_sex(get_val("Sex"))
    languages = parse_languages(get_val("Languages"))

    description_en = get_val("Description English") or None
    description_ru = get_val("Description Russian") or None

    years_of_experience = parse_years_of_experience(get_val("Years of experience"))

    primary_qualifications = get_val("Primary Qualifications") or None
    secondary_qualifications = get_val("Secondary Qualifications") or None
    additional_qualifications = get_val("Additional Qualifications") or None

    treat_children, treat_children_age = parse_treat_children(get_val("treat children"))

    branches = parse_branch(get_val("Branch"))

    # Build practitioner object
    practitioner = {
        "id": practitioner_id,
        "name": name,
        "name_i18n": {"en": name},
        "speciality": speciality,
        "sex": sex,
        "languages": languages,
        "description_i18n": {},
        "years_of_experience": years_of_experience,
        "primary_qualifications": primary_qualifications,
        "secondary_qualifications": secondary_qualifications,
        "additional_qualifications": additional_qualifications,
        "treat_children": treat_children,
        "treat_children_age": treat_children_age,
        "branches": branches,
        "is_visible_to_ai": True,
        "source": "google_sheets"
    }

    # Add descriptions if present
    if description_en:
        practitioner["description_i18n"]["en"] = description_en
    if description_ru:
        practitioner["description_i18n"]["ru"] = description_ru

    return practitioner


def main():
    print("=" * 60)
    print("Parsing Practitioners from Google Sheets")
    print("=" * 60)

    # Get sheets service
    print("\nAuthenticating with Google Sheets API...")
    service = get_sheets_service()

    # Get sheet name
    print(f"Getting sheet name for GID {SHEET_GID}...")
    sheet_name = get_sheet_name_by_gid(service, SPREADSHEET_ID, SHEET_GID)
    print(f"Sheet name: {sheet_name}")

    # Read data
    print(f"Reading data from sheet '{sheet_name}'...")
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{sheet_name}'"
    ).execute()

    rows = result.get("values", [])

    if not rows:
        print("No data found in sheet!")
        return

    print(f"Found {len(rows)} rows (including header)")

    # Parse header
    headers = [h.strip() for h in rows[0]]
    print(f"Headers: {headers}")

    # Parse data rows
    practitioners = []
    for i, row in enumerate(rows[1:], start=2):
        try:
            practitioner = parse_row(row, headers)
            if practitioner:
                practitioners.append(practitioner)
                print(f"  Row {i}: {practitioner['name']} (ID: {practitioner['id']})")
        except Exception as e:
            print(f"  Row {i}: Error - {e}")

    print(f"\nParsed {len(practitioners)} practitioners")

    # Save to JSON
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "practitioners.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(practitioners, f, indent=2, ensure_ascii=False)

    print(f"\nSaved to: {output_file}")
    print("=" * 60)

    # Show sample
    if practitioners:
        print("\nSample output:")
        print(json.dumps(practitioners[0], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
