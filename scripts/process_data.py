#!/usr/bin/env python3
"""
Script to process raw_data.csv and create 4 normalized JSON files:
1. categories.json
2. practitioners.json
3. services.json
4. service_practitioners.json

Usage:
    python scripts/process_data.py
"""

import csv
import json
import re
from pathlib import Path

# Project paths
SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent
DATA_INPUT_DIR = PROJECT_ROOT / "data" / "input"
DATA_OUTPUT_DIR = PROJECT_ROOT / "data" / "output"

# Ensure directories exist
DATA_INPUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


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
    if "individual" in duration_str or "days" in duration_str or "+" in duration_str:
        return None

    # "30 min" -> 30
    if "min" in duration_str:
        match = re.search(r'(\d+)', duration_str)
        if match:
            return int(match.group(1))

    # "1 hour" -> 60
    # "1.5 hour" -> 90
    # "2 hour" -> 120
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
    # Remove "+ VAT", "+VAT", "AED" etc
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
        return ["jumeirah", "srz"]

    branch_str = branch_str.strip().lower()

    if branch_str == "both":
        return ["jumeirah", "srz"]
    elif branch_str == "jumeirah":
        return ["jumeirah"]
    elif branch_str in ["szr", "srz"]:
        return ["srz"]
    else:
        return ["jumeirah", "srz"]


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


def parse_practitioners(practitioners_str: str) -> list[str]:
    """Parse practitioners string (newline separated)"""
    if not practitioners_str or practitioners_str.strip() == "":
        return []

    practitioners = []
    for line in practitioners_str.split('\n'):
        name = fix_doctor_name(line.strip())
        if name:
            practitioners.append(name)

    return practitioners


def main():
    # Read CSV
    csv_path = DATA_INPUT_DIR / "raw_data.csv"
    
    if not csv_path.exists():
        print(f"Error: {csv_path} not found")
        print(f"Please place your CSV file at: {csv_path}")
        return

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # Skip header row if it's a duplicate
        rows = list(reader)

        # Check if first row is header duplicate
        if rows and rows[0].get("ID", "") == "ID":
            rows = rows[1:]

    # Collections
    categories: dict[str, int] = {}  # name -> id
    practitioners: dict[str, int] = {}  # name -> id
    services: list[dict] = []
    service_practitioners: list[dict] = []

    category_id_counter = 1
    practitioner_id_counter = 1

    for row in rows:
        # Get category
        category_name = row.get("Category", "").strip()
        if category_name and category_name not in categories:
            categories[category_name] = category_id_counter
            category_id_counter += 1

        # Get practitioners
        practitioners_str = row.get("Doctor name", "")
        pract_names = parse_practitioners(practitioners_str)

        for pract_name in pract_names:
            if pract_name and pract_name not in practitioners:
                practitioners[pract_name] = practitioner_id_counter
                practitioner_id_counter += 1

        # Parse service data
        service_id = int(row.get("ID", 0))
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

        # Create service object
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

        # Create service-practitioner links
        for pract_name in pract_names:
            if pract_name in practitioners:
                service_practitioners.append({
                    "service_id": service_id,
                    "practitioner_id": practitioners[pract_name]
                })

    # Create output data structures
    categories_list = [
        {
            "id": cat_id,
            "name_i18n": {"en": cat_name},
            "sort_order": cat_id
        }
        for cat_name, cat_id in sorted(categories.items(), key=lambda x: x[1])
    ]

    practitioners_list = [
        {
            "id": pract_id,
            "name": pract_name,
            "name_i18n": {"en": pract_name}
        }
        for pract_name, pract_id in sorted(practitioners.items(), key=lambda x: x[1])
    ]

    # Write JSON files
    with open(DATA_OUTPUT_DIR / "categories.json", "w", encoding="utf-8") as f:
        json.dump(categories_list, f, ensure_ascii=False, indent=2)
    print(f"Created data/output/categories.json with {len(categories_list)} categories")

    with open(DATA_OUTPUT_DIR / "practitioners.json", "w", encoding="utf-8") as f:
        json.dump(practitioners_list, f, ensure_ascii=False, indent=2)
    print(f"Created data/output/practitioners.json with {len(practitioners_list)} practitioners")

    with open(DATA_OUTPUT_DIR / "services.json", "w", encoding="utf-8") as f:
        json.dump(services, f, ensure_ascii=False, indent=2)
    print(f"Created data/output/services.json with {len(services)} services")

    with open(DATA_OUTPUT_DIR / "service_practitioners.json", "w", encoding="utf-8") as f:
        json.dump(service_practitioners, f, ensure_ascii=False, indent=2)
    print(f"Created data/output/service_practitioners.json with {len(service_practitioners)} links")

    # Print summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Categories: {len(categories_list)}")
    print(f"Practitioners: {len(practitioners_list)}")
    print(f"Services: {len(services)}")
    print(f"Service-Practitioner links: {len(service_practitioners)}")


if __name__ == "__main__":
    main()
