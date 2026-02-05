#!/usr/bin/env python3
"""
Sync local JSON files with DialogGauge API.

Logic:
1. Fetch categories/services/practitioners from API
2. Get max ID from API
3. For each local item:
   - If name matches API item → use API's ID
   - If new (not in API) → assign new ID = max_api_id + 1, +2, ...
4. Update all references (category_id, service_id, practitioner_id)
5. Save updated files

Usage:
    python scripts/sync_with_api.py                  # Sync all
    python scripts/sync_with_api.py --categories-only
    python scripts/sync_with_api.py --services-only
    python scripts/sync_with_api.py --practitioners-only
"""

import json
import re
import sys
from pathlib import Path

# Project paths
SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent
DATA_OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
DATA_API_DIR = PROJECT_ROOT / "data" / "api"

# Ensure directories exist
DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_API_DIR.mkdir(parents=True, exist_ok=True)

# Import API functions
from get_categories import get_categories as fetch_api_categories
from get_categories import get_services as fetch_api_services
from get_categories import get_practitioners as fetch_api_practitioners


def normalize_name(name: str) -> str:
    """Normalize name for comparison."""
    if not name:
        return ""
    name = name.lower().strip()
    name = re.sub(r'\s+', ' ', name)
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


def get_item_name(item: dict) -> str:
    """Get item name from name_i18n.en or name field."""
    name = item.get("name_i18n", {}).get("en", "")
    if not name:
        name = item.get("name", "")
    return name


def sync_items(
    local_items: list,
    api_items: list,
    item_type: str = "items",
) -> tuple[list, dict, dict]:
    """
    Sync local items with API.
    
    - If local item name matches API → use API's ID
    - If local item is new → assign max_api_id + 1, +2, ...
    
    Returns:
        - synced_items: Updated items with correct IDs
        - id_mapping: old_local_id -> new_id
        - report: sync stats
    """
    # Build API name -> item map
    api_name_map = {}
    for item in api_items:
        name_en = get_item_name(item)
        normalized = normalize_name(name_en)
        if normalized:
            api_name_map[normalized] = item
    
    # Get max API ID
    max_api_id = max((item["id"] for item in api_items), default=0)
    print(f"  Max API ID: {max_api_id}")
    
    next_new_id = max_api_id + 1
    
    synced_items = []
    id_mapping = {}  # old_local_id -> new_id
    
    matched = []
    new_items = []
    
    for local_item in local_items:
        old_id = local_item["id"]
        local_name = get_item_name(local_item)
        normalized = normalize_name(local_name)
        
        if normalized in api_name_map:
            # MATCH: Use API's ID
            api_item = api_name_map[normalized]
            new_id = api_item["id"]
            
            matched.append({
                "local_name": local_name,
                "api_name": get_item_name(api_item),
                "old_id": old_id,
                "new_id": new_id,
                "is_archived": api_item.get("is_archived", False),
            })
        else:
            # NEW: Assign next ID
            new_id = next_new_id
            next_new_id += 1
            
            new_items.append({
                "local_name": local_name,
                "old_id": old_id,
                "new_id": new_id,
            })
        
        # Create synced item with new ID
        synced_item = local_item.copy()
        synced_item["id"] = new_id
        synced_items.append(synced_item)
        
        id_mapping[old_id] = new_id
    
    # Sort by ID
    synced_items.sort(key=lambda x: x["id"])
    
    report = {
        "type": item_type,
        "total_local": len(local_items),
        "total_api": len(api_items),
        "max_api_id": max_api_id,
        "matched": len(matched),
        "new": len(new_items),
        "new_id_start": max_api_id + 1 if new_items else None,
        "new_id_end": next_new_id - 1 if new_items else None,
        "matched_details": matched,
        "new_details": new_items,
    }
    
    return synced_items, id_mapping, report


def update_references(items: list, id_field: str, id_mapping: dict) -> list:
    """Update ID references in items."""
    updated = []
    for item in items:
        item_copy = item.copy()
        old_id = item.get(id_field)
        if old_id in id_mapping:
            item_copy[id_field] = id_mapping[old_id]
        updated.append(item_copy)
    return updated


def print_report(report: dict) -> None:
    """Print sync report."""
    item_type = report.get("type", "items").upper()
    
    print(f"\n{'=' * 60}")
    print(f"SYNC REPORT: {item_type}")
    print("=" * 60)
    
    print(f"\nLocal:     {report['total_local']}")
    print(f"API:       {report['total_api']}")
    print(f"Max API ID: {report['max_api_id']}")
    print(f"Matched:   {report['matched']}")
    print(f"New:       {report['new']}")
    
    if report['new'] > 0:
        print(f"New IDs:   {report['new_id_start']} - {report['new_id_end']}")
    
    if report["matched_details"]:
        print(f"\n--- MATCHED (using API ID) ---")
        for m in report["matched_details"][:15]:
            archived = " [ARCHIVED]" if m.get("is_archived") else ""
            name = m['local_name'][:35]
            print(f"  {m['old_id']:>5} → {m['new_id']:<5} '{name}'{archived}")
        if len(report["matched_details"]) > 15:
            print(f"  ... and {len(report['matched_details']) - 15} more")
    
    if report["new_details"]:
        print(f"\n--- NEW (assigned new ID) ---")
        for n in report["new_details"][:15]:
            name = n['local_name'][:35]
            print(f"  {n['old_id']:>5} → {n['new_id']:<5} '{name}'")
        if len(report["new_details"]) > 15:
            print(f"  ... and {len(report['new_details']) - 15} more")
    
    print("=" * 60)


def sync_categories() -> tuple[dict, dict]:
    """Sync categories with API."""
    print("\n" + "=" * 60)
    print("SYNCING CATEGORIES")
    print("=" * 60)
    
    local = load_json(DATA_OUTPUT_DIR / "categories.json")
    if not local:
        print("No local categories")
        return {}, {}
    
    print(f"Local categories: {len(local)}")
    
    try:
        api = fetch_api_categories(flat=True, include_archived=True)
        print(f"API categories: {len(api)}")
    except Exception as e:
        print(f"Error: {e}")
        api = []
    
    synced, id_mapping, report = sync_items(local, api, "categories")
    
    # Update sort_order
    for i, cat in enumerate(synced, 1):
        cat["sort_order"] = i
    
    save_json(DATA_OUTPUT_DIR / "categories.json", synced)
    print_report(report)
    
    return id_mapping, report


def sync_services(category_id_mapping: dict = None) -> tuple[dict, dict]:
    """Sync services with API."""
    print("\n" + "=" * 60)
    print("SYNCING SERVICES")
    print("=" * 60)
    
    local = load_json(DATA_OUTPUT_DIR / "services.json")
    if not local:
        print("No local services")
        return {}, {}
    
    print(f"Local services: {len(local)}")
    
    try:
        api = fetch_api_services(include_archived=True)
        print(f"API services: {len(api)}")
    except Exception as e:
        print(f"Error: {e}")
        api = []
    
    synced, id_mapping, report = sync_items(local, api, "services")
    
    # Update category_id if mapping provided
    if category_id_mapping:
        print("\nUpdating category_id references...")
        synced = update_references(synced, "category_id", category_id_mapping)
    
    save_json(DATA_OUTPUT_DIR / "services.json", synced)
    print_report(report)
    
    return id_mapping, report


def update_service_practitioners(
    service_id_mapping: dict = None,
    practitioner_id_mapping: dict = None,
) -> None:
    """Update service_practitioners with new service/practitioner IDs."""
    print("\n" + "-" * 40)
    print("Updating service_practitioners.json...")
    
    sp = load_json(DATA_OUTPUT_DIR / "service_practitioners.json")
    if not sp:
        print("No service_practitioners.json")
        return
    
    updated = sp
    
    if service_id_mapping:
        print(f"  Updating service_id references...")
        updated = update_references(updated, "service_id", service_id_mapping)
    
    if practitioner_id_mapping:
        print(f"  Updating practitioner_id references...")
        updated = update_references(updated, "practitioner_id", practitioner_id_mapping)
    
    save_json(DATA_OUTPUT_DIR / "service_practitioners.json", updated)
    print(f"Updated {len(updated)} links")


def sync_practitioners() -> tuple[dict, dict]:
    """Sync practitioners with API."""
    print("\n" + "=" * 60)
    print("SYNCING PRACTITIONERS")
    print("=" * 60)
    
    local = load_json(DATA_OUTPUT_DIR / "practitioners.json")
    if not local:
        print("No local practitioners")
        return {}, {}
    
    print(f"Local practitioners: {len(local)}")
    
    try:
        api = fetch_api_practitioners(include_archived=True)
        print(f"API practitioners: {len(api)}")
    except Exception as e:
        print(f"Error: {e}")
        api = []
    
    synced, id_mapping, report = sync_items(local, api, "practitioners")
    
    save_json(DATA_OUTPUT_DIR / "practitioners.json", synced)
    print_report(report)
    
    return id_mapping, report


def main():
    categories_only = "--categories-only" in sys.argv
    services_only = "--services-only" in sys.argv
    practitioners_only = "--practitioners-only" in sys.argv
    
    print("=" * 60)
    print("SYNC WITH DIALOGGAUGE API")
    print("=" * 60)
    
    full_report = {}
    category_id_mapping = {}
    service_id_mapping = {}
    practitioner_id_mapping = {}
    
    # Determine what to sync
    sync_categories_flag = not services_only and not practitioners_only
    sync_services_flag = not categories_only and not practitioners_only
    sync_practitioners_flag = not categories_only and not services_only
    
    # Sync categories
    if sync_categories_flag:
        category_id_mapping, cat_report = sync_categories()
        full_report["categories"] = cat_report
    
    # Sync services
    if sync_services_flag:
        service_id_mapping, svc_report = sync_services(category_id_mapping)
        full_report["services"] = svc_report
    
    # Sync practitioners
    if sync_practitioners_flag:
        practitioner_id_mapping, pract_report = sync_practitioners()
        full_report["practitioners"] = pract_report
    
    # Update service_practitioners with new IDs
    if service_id_mapping or practitioner_id_mapping:
        update_service_practitioners(service_id_mapping, practitioner_id_mapping)
    
    # Save report
    save_json(DATA_API_DIR / "_sync_report.json", full_report)
    
    # Summary
    print("\n" + "=" * 60)
    print("SYNC COMPLETE")
    print("=" * 60)
    
    if "categories" in full_report and full_report["categories"]:
        r = full_report["categories"]
        print(f"\nCategories: {r['matched']} matched, {r['new']} new")
        if r['new'] > 0:
            print(f"  New IDs: {r['new_id_start']} - {r['new_id_end']}")
    
    if "services" in full_report and full_report["services"]:
        r = full_report["services"]
        print(f"\nServices: {r['matched']} matched, {r['new']} new")
        if r['new'] > 0:
            print(f"  New IDs: {r['new_id_start']} - {r['new_id_end']}")
    
    if "practitioners" in full_report and full_report["practitioners"]:
        r = full_report["practitioners"]
        print(f"\nPractitioners: {r['matched']} matched, {r['new']} new")
        if r['new'] > 0:
            print(f"  New IDs: {r['new_id_start']} - {r['new_id_end']}")


if __name__ == "__main__":
    main()
