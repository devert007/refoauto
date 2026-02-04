#!/usr/bin/env python3
"""
Sync local JSON files with DialogGauge API.

This script:
1. Fetches categories from API
2. Compares with locally generated categories.json
3. Matches by name (case-insensitive, normalized)
4. Uses existing API IDs for matching categories
5. Assigns new IDs for new categories (starting from max_api_id + 1)
6. Updates services.json with correct category_id references
7. Creates sync report

Usage:
    python scripts/sync_with_api.py
"""

import json
import re
from pathlib import Path

# Project paths
SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent
DATA_OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
DATA_API_DIR = PROJECT_ROOT / "data" / "api"

# Ensure directories exist
DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_API_DIR.mkdir(parents=True, exist_ok=True)

# Import get_categories from existing script
from get_categories import get_categories as fetch_api_categories


def normalize_name(name: str) -> str:
    """
    Normalize category name for comparison.
    - Lowercase
    - Remove extra spaces
    - Remove special characters
    """
    if not name:
        return ""
    # Lowercase
    name = name.lower().strip()
    # Replace multiple spaces with single
    name = re.sub(r'\s+', ' ', name)
    # Remove special characters except spaces
    name = re.sub(r'[^\w\s]', '', name)
    return name


def load_json(filepath: Path) -> list:
    """Load JSON file."""
    if not filepath.exists():
        print(f"Warning: {filepath} not found")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(filepath: Path, data: list) -> None:
    """Save JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved: {filepath}")


def build_api_name_map(api_categories: list) -> dict:
    """
    Build a map of normalized_name -> api_category for matching.
    """
    name_map = {}
    for cat in api_categories:
        name_en = cat.get("name_i18n", {}).get("en", "")
        normalized = normalize_name(name_en)
        if normalized:
            name_map[normalized] = cat
    return name_map


def sync_categories(
    local_categories: list,
    api_categories: list,
) -> tuple[list, dict, dict]:
    """
    Sync local categories with API categories.
    
    Returns:
        - synced_categories: Updated local categories with correct IDs
        - id_mapping: old_local_id -> new_id mapping
        - report: sync statistics
    """
    # Build API name map
    api_name_map = build_api_name_map(api_categories)
    
    # Find max ID from API to assign new IDs
    max_api_id = max((cat["id"] for cat in api_categories), default=0)
    next_new_id = max_api_id + 1
    
    # Track results
    synced_categories = []
    id_mapping = {}  # old_local_id -> new_id
    
    matched = []
    new_categories = []
    
    for local_cat in local_categories:
        old_id = local_cat["id"]
        local_name = local_cat.get("name_i18n", {}).get("en", "")
        normalized = normalize_name(local_name)
        
        if normalized in api_name_map:
            # Found match in API - use API's ID
            api_cat = api_name_map[normalized]
            new_id = api_cat["id"]
            
            matched.append({
                "local_name": local_name,
                "api_name": api_cat.get("name_i18n", {}).get("en", ""),
                "old_id": old_id,
                "new_id": new_id,
                "is_archived": api_cat.get("is_archived", False),
            })
            
            # Keep local structure but update ID
            synced_cat = local_cat.copy()
            synced_cat["id"] = new_id
            synced_cat["_api_match"] = True
            synced_cat["_api_archived"] = api_cat.get("is_archived", False)
            
        else:
            # No match - assign new ID
            new_id = next_new_id
            next_new_id += 1
            
            new_categories.append({
                "local_name": local_name,
                "old_id": old_id,
                "new_id": new_id,
            })
            
            synced_cat = local_cat.copy()
            synced_cat["id"] = new_id
            synced_cat["_api_match"] = False
        
        id_mapping[old_id] = new_id
        synced_categories.append(synced_cat)
    
    # Sort by ID
    synced_categories.sort(key=lambda x: x["id"])
    
    # Update sort_order to match new IDs
    for i, cat in enumerate(synced_categories, 1):
        cat["sort_order"] = i
    
    report = {
        "total_local": len(local_categories),
        "total_api": len(api_categories),
        "matched": len(matched),
        "new": len(new_categories),
        "matched_details": matched,
        "new_details": new_categories,
    }
    
    return synced_categories, id_mapping, report


def update_services_category_ids(services: list, id_mapping: dict) -> list:
    """
    Update category_id in services based on id_mapping.
    """
    updated_services = []
    
    for service in services:
        service_copy = service.copy()
        old_category_id = service.get("category_id")
        
        if old_category_id in id_mapping:
            service_copy["category_id"] = id_mapping[old_category_id]
        
        updated_services.append(service_copy)
    
    return updated_services


def clean_categories_for_output(categories: list) -> list:
    """
    Remove internal fields (_api_match, _api_archived) for final output.
    """
    cleaned = []
    for cat in categories:
        clean_cat = {k: v for k, v in cat.items() if not k.startswith("_")}
        cleaned.append(clean_cat)
    return cleaned


def print_report(report: dict) -> None:
    """Print sync report."""
    print("\n" + "=" * 60)
    print("SYNC REPORT")
    print("=" * 60)
    
    print(f"\nLocal categories: {report['total_local']}")
    print(f"API categories:   {report['total_api']}")
    print(f"Matched:          {report['matched']}")
    print(f"New (to create):  {report['new']}")
    
    if report["matched_details"]:
        print("\n--- MATCHED CATEGORIES ---")
        for m in report["matched_details"]:
            archived = " [ARCHIVED]" if m["is_archived"] else ""
            print(f"  '{m['local_name']}' → API ID {m['new_id']}{archived}")
            if m["local_name"].lower() != m["api_name"].lower():
                print(f"    (API name: '{m['api_name']}')")
    
    if report["new_details"]:
        print("\n--- NEW CATEGORIES (not in API) ---")
        for n in report["new_details"]:
            print(f"  '{n['local_name']}' → New ID {n['new_id']}")
    
    print("\n" + "=" * 60)


def main():
    print("Syncing local data with DialogGauge API...")
    
    # 1. Load local files
    print("\nLoading local files...")
    local_categories = load_json(DATA_OUTPUT_DIR / "categories.json")
    local_services = load_json(DATA_OUTPUT_DIR / "services.json")
    
    if not local_categories:
        print("Error: categories.json is empty or not found")
        return
    
    print(f"  - categories.json: {len(local_categories)} categories")
    print(f"  - services.json: {len(local_services)} services")
    
    # 2. Fetch API categories
    print("\nFetching categories from API...")
    try:
        api_categories = fetch_api_categories(
            flat=True,
            include_archived=True,
        )
        print(f"  - API returned: {len(api_categories)} categories")
    except Exception as e:
        print(f"Error fetching API categories: {e}")
        print("Continuing with empty API categories...")
        api_categories = []
    
    # 3. Sync categories
    print("\nSyncing categories...")
    synced_categories, id_mapping, report = sync_categories(
        local_categories,
        api_categories,
    )
    
    # 4. Update services
    print("\nUpdating services with new category IDs...")
    updated_services = update_services_category_ids(local_services, id_mapping)
    
    # 5. Print report
    print_report(report)
    
    # 6. Save updated files
    print("\nSaving updated files...")
    
    # Clean and save categories
    clean_categories = clean_categories_for_output(synced_categories)
    save_json(DATA_OUTPUT_DIR / "categories.json", clean_categories)
    
    # Save services
    save_json(DATA_OUTPUT_DIR / "services.json", updated_services)
    
    # Save sync report
    save_json(DATA_API_DIR / "_sync_report.json", report)
    
    # 7. Print ID mapping for reference
    print("\n--- ID MAPPING (old → new) ---")
    for old_id, new_id in sorted(id_mapping.items()):
        marker = " *" if old_id != new_id else ""
        print(f"  {old_id} → {new_id}{marker}")
    
    print("\nSync complete!")
    print("\nNext steps:")
    print("  1. Review data/api/_sync_report.json for details")
    print("  2. New categories need to be created in DialogGauge manually")
    print("  3. Or use API to create them if available")


if __name__ == "__main__":
    main()
