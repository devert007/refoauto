#!/usr/bin/env python3
"""
Regenerate all 4 JSON files according to PROMPT_1 specifications.

Creates:
1. categories.json - unique categories with sequential IDs
2. services.json - services with correct IDs from CSV
3. practitioners.json - keeps existing (from Google Sheets)
4. service_practitioners.json - many-to-many links

Usage:
    python scripts/regenerate_data.py
"""

import csv
import json
import re
from pathlib import Path

# Paths
SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent
DATA_INPUT_DIR = PROJECT_ROOT / "data" / "input"
DATA_OUTPUT_DIR = PROJECT_ROOT / "data" / "output"


def fix_doctor_name(name: str) -> str:
    """Fix spacing in doctor names like 'Dr.Sarah' -> 'Dr. Sarah'"""
    name = name.strip()
    # Fix "Dr.Name" -> "Dr. Name"
    name = re.sub(r'Dr\.(\S)', r'Dr. \1', name)
    # Fix "Dr Name" -> "Dr. Name" at the beginning
    if name.startswith("Dr "):
        name = "Dr. " + name[3:]
    return name


def parse_duration(duration_str: str) -> int | None:
    """Parse duration string to minutes"""
    if not duration_str or duration_str.strip() == "":
        return None

    duration_str = duration_str.strip().lower()

    # Handle "Individual", "2 + days", "2 days" etc
    if "individual" in duration_str or "days" in duration_str:
        return None

    # "30 min" -> 30
    if "min" in duration_str:
        match = re.search(r'(\d+)', duration_str)
        if match:
            return int(match.group(1))

    # "1 hour" -> 60, "1.5 hour" -> 90, "2 hour" -> 120
    if "hour" in duration_str:
        match = re.search(r'([\d.]+)', duration_str)
        if match:
            return int(float(match.group(1)) * 60)

    # Just a number
    match = re.search(r'^(\d+)$', duration_str)
    if match:
        return int(match.group(1))

    return None


def parse_price(price_str: str) -> tuple[float | None, float | None, dict | None]:
    """Parse price string and return (price_min, price_max, price_note_i18n)"""
    if not price_str or price_str.strip() == "" or price_str.strip() == "0":
        return None, None, None

    price_str = price_str.strip()
    price_note = None

    # Check for "+ VAT" or "+VAT"
    has_vat = "vat" in price_str.lower()
    if has_vat:
        price_note = {"en": "Price excludes VAT"}

    # Extract numeric value
    clean_price = re.sub(r'\s*\+?\s*vat', '', price_str, flags=re.IGNORECASE)
    clean_price = re.sub(r'\s*aed', '', clean_price, flags=re.IGNORECASE)
    clean_price = clean_price.strip()

    # Try to extract number
    match = re.search(r'([\d,]+(?:\.\d+)?)', clean_price)
    if match:
        price_value = float(match.group(1).replace(',', ''))
        return price_value, price_value, price_note

    return None, None, price_note


def parse_branches(branch_str: str) -> list[str]:
    """Parse branch string to list"""
    if not branch_str or branch_str.strip() == "":
        return ["jumeirah", "szr"]

    branch_str = branch_str.strip().lower()

    if branch_str == "both":
        return ["jumeirah", "szr"]
    elif branch_str == "jumeirah":
        return ["jumeirah"]
    elif branch_str in ["szr", "szr"]:
        return ["szr"]
    else:
        return ["jumeirah", "szr"]


def parse_service_name(name_str: str) -> tuple[str, str | None]:
    """
    Parse service name - if multiline, first line is name, rest is description.
    Returns (name, description)
    """
    if not name_str:
        return "", None

    lines = [line.strip() for line in name_str.strip().split('\n') if line.strip()]

    if len(lines) == 0:
        return "", None
    elif len(lines) == 1:
        return lines[0], None
    else:
        name = lines[0]
        description = "Includes: " + ", ".join(lines[1:])
        return name, description


def parse_practitioners_from_cell(practitioners_str: str) -> list[str]:
    """Parse practitioners string (newline separated)"""
    if not practitioners_str or practitioners_str.strip() == "":
        return []

    practitioners = []
    for line in practitioners_str.split('\n'):
        name = fix_doctor_name(line.strip())
        if name:
            practitioners.append(name)

    return practitioners


def normalize_name_for_matching(name: str) -> str:
    """Normalize name for matching purposes"""
    # Convert to lowercase, remove extra spaces
    normalized = name.lower().strip()
    # Remove "Dr." or "Dr " prefix variations
    normalized = re.sub(r'^dr\.?\s*', '', normalized)
    # Remove multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized


# Manual name mappings for known variations
NAME_ALIASES = {
    "danielle stephen": "danielle april stephen",
    "dr karem harb": "dr. karem harb",
    "dr nataliya sanytska": "dr. nataliya sanytska",
    "dr mohsen": "dr. mohsen soofian",
}


def load_existing_practitioners() -> list[dict]:
    """Load existing practitioners.json"""
    practitioners_file = DATA_OUTPUT_DIR / "practitioners.json"
    if practitioners_file.exists():
        with open(practitioners_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def build_practitioner_name_map(practitioners: list[dict]) -> dict[str, int]:
    """Build a mapping from normalized names to practitioner IDs"""
    name_map = {}

    for p in practitioners:
        name = p.get("name", "")
        pid = p.get("id")
        if name and pid:
            # Store both original and normalized versions
            name_map[name] = pid
            name_map[normalize_name_for_matching(name)] = pid

    return name_map


def find_practitioner_id(name: str, name_map: dict[str, int]) -> int | None:
    """Find practitioner ID by name, trying various matching strategies"""
    # Try exact match first
    if name in name_map:
        return name_map[name]

    # Try normalized match
    normalized = normalize_name_for_matching(name)
    if normalized in name_map:
        return name_map[normalized]

    # Try alias mapping
    if normalized in NAME_ALIASES:
        alias = NAME_ALIASES[normalized]
        if alias in name_map:
            return name_map[alias]

    # Try partial matches
    for map_name, pid in name_map.items():
        map_normalized = normalize_name_for_matching(map_name)
        if normalized == map_normalized:
            return pid
        # Check if one contains the other (for name variations)
        if len(normalized) > 3 and len(map_normalized) > 3:
            if normalized in map_normalized or map_normalized in normalized:
                return pid

    return None


def main():
    print("=" * 60)
    print("Regenerating all JSON files according to PROMPT_1 specs")
    print("=" * 60)

    # Read CSV
    csv_path = DATA_INPUT_DIR / "raw_data.csv"

    if not csv_path.exists():
        print(f"Error: {csv_path} not found")
        return

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        # Skip header row if it's a duplicate
        if rows and rows[0].get("ID", "") == "ID":
            rows = rows[1:]

    print(f"Loaded {len(rows)} rows from CSV")

    # Load existing practitioners
    existing_practitioners = load_existing_practitioners()
    print(f"Loaded {len(existing_practitioners)} existing practitioners")

    # Build name mapping
    practitioner_name_map = build_practitioner_name_map(existing_practitioners)

    # Collections
    categories: dict[str, int] = {}  # name -> id
    category_order: list[str] = []   # for sort_order
    services: list[dict] = []
    service_practitioners: list[dict] = []

    # Track unmatched practitioners
    unmatched_practitioners = set()

    category_id_counter = 1

    for row in rows:
        # Get category
        category_name = row.get("Category", "").strip()
        if category_name and category_name not in categories:
            categories[category_name] = category_id_counter
            category_order.append(category_name)
            category_id_counter += 1

        # Parse service data
        service_id_str = row.get("ID", "0")
        try:
            service_id = int(service_id_str)
        except ValueError:
            continue

        if service_id == 0:
            continue

        service_name_raw = row.get("Service Name", "")
        service_name, description = parse_service_name(service_name_raw)

        duration = parse_duration(row.get("Duration", ""))
        price_min, price_max, price_note = parse_price(row.get("Price", ""))
        branches = parse_branches(row.get("Available In Branches", ""))
        note = row.get("Note", "").strip()

        # Combine notes
        if note:
            if price_note:
                price_note["en"] = price_note["en"] + ". " + note
            else:
                price_note = {"en": note}

        # Create service object (WITHOUT practitioners field!)
        service = {
            "id": service_id,
            "category_id": categories.get(category_name, 1),
            "name_i18n": {"en": service_name},
            "description_i18n": {"en": description} if description else {},
            "duration_minutes": duration,
            "price_min": price_min,
            "price_max": price_max,
            "price_note_i18n": price_note if price_note else {},
            "branches": branches
        }
        services.append(service)

        # Parse practitioners from Doctor name column
        practitioners_str = row.get("Doctor name", "")
        pract_names = parse_practitioners_from_cell(practitioners_str)

        # Create service-practitioner links
        for pract_name in pract_names:
            pract_id = find_practitioner_id(pract_name, practitioner_name_map)
            if pract_id:
                service_practitioners.append({
                    "service_id": service_id,
                    "practitioner_id": pract_id
                })
            else:
                unmatched_practitioners.add(pract_name)

    # Create categories list with sequential IDs and sort_order
    categories_list = []
    for sort_order, cat_name in enumerate(category_order, start=1):
        categories_list.append({
            "id": categories[cat_name],
            "name_i18n": {"en": cat_name},
            "sort_order": sort_order
        })

    # Add missing practitioners to the list
    if unmatched_practitioners:
        print(f"\nAdding {len(unmatched_practitioners)} missing practitioners:")
        max_id = max(p["id"] for p in existing_practitioners) if existing_practitioners else 0

        for name in sorted(unmatched_practitioners):
            max_id += 1
            new_practitioner = {
                "id": max_id,
                "name": name,
                "name_i18n": {"en": name},
                "speciality": "Aesthetics",  # Default speciality
                "sex": "female",  # Default, can be updated later
                "languages": ["ENGLISH"],
                "description_i18n": {"en": "", "ru": ""},
                "years_of_experience": None,
                "primary_qualifications": None,
                "secondary_qualifications": None,
                "additional_qualifications": None,
                "treat_children": None,
                "treat_children_age": None,
                "branches": [],
                "is_visible_to_ai": True,
                "source": "services_sheet"
            }
            existing_practitioners.append(new_practitioner)
            practitioner_name_map[name] = max_id
            practitioner_name_map[normalize_name_for_matching(name)] = max_id
            print(f"  + {name} (ID: {max_id})")

        # Re-process service_practitioners with updated name map
        service_practitioners.clear()
        for row in rows:
            service_id_str = row.get("ID", "0")
            try:
                service_id = int(service_id_str)
            except ValueError:
                continue
            if service_id == 0:
                continue

            practitioners_str = row.get("Doctor name", "")
            pract_names = parse_practitioners_from_cell(practitioners_str)

            for pract_name in pract_names:
                pract_id = find_practitioner_id(pract_name, practitioner_name_map)
                if pract_id:
                    service_practitioners.append({
                        "service_id": service_id,
                        "practitioner_id": pract_id
                    })

    # Save categories.json
    with open(DATA_OUTPUT_DIR / "categories.json", "w", encoding="utf-8") as f:
        json.dump(categories_list, f, ensure_ascii=False, indent=2)
    print(f"\nCreated categories.json with {len(categories_list)} categories")

    # Save services.json
    with open(DATA_OUTPUT_DIR / "services.json", "w", encoding="utf-8") as f:
        json.dump(services, f, ensure_ascii=False, indent=2)
    print(f"Created services.json with {len(services)} services")

    # Save practitioners.json (includes existing from Google Sheets + new ones from Services)
    with open(DATA_OUTPUT_DIR / "practitioners.json", "w", encoding="utf-8") as f:
        json.dump(existing_practitioners, f, ensure_ascii=False, indent=2)
    print(f"Created practitioners.json with {len(existing_practitioners)} practitioners")

    # Save service_practitioners.json
    with open(DATA_OUTPUT_DIR / "service_practitioners.json", "w", encoding="utf-8") as f:
        json.dump(service_practitioners, f, ensure_ascii=False, indent=2)
    print(f"Created service_practitioners.json with {len(service_practitioners)} links")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Categories: {len(categories_list)}")
    print(f"Services: {len(services)}")
    print(f"Practitioners: {len(existing_practitioners)}")
    print(f"Service-Practitioner links: {len(service_practitioners)}")

    if unmatched_practitioners:
        print(f"\nUnmatched practitioners: {len(unmatched_practitioners)}")
        print("These practitioners from Services sheet are not in Practitioners sheet:")
        for name in sorted(unmatched_practitioners):
            print(f"  - {name}")


if __name__ == "__main__":
    main()
