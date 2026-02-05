#!/usr/bin/env python3
"""
Upload local services to DialogGauge API.

Steps:
1. Fetch existing categories from API (for category_id mapping)
2. Fetch existing services from API
3. Compare with local services (by name)
4. Create only NEW services (not in API)

Usage:
    python3 scripts/upload_services.py                # Dry run (show what would be created)
    python3 scripts/upload_services.py --execute      # Actually create services
    python3 scripts/upload_services.py --limit=5      # Create only first 5 new services
"""

import json
import re
import sys
from pathlib import Path

# Project paths
SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent
DATA_OUTPUT_DIR = PROJECT_ROOT / "data" / "output"

# Import API functions
from get_categories import (
    get_categories,
    get_services,
    create_service,
    LOCATION_ID,
)


def normalize_name(name: str) -> str:
    """Normalize name for comparison."""
    if not name:
        return ""
    name = name.lower().strip()
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'[^\w\s]', '', name)
    return name


def load_local_services() -> list:
    """Load local services from JSON."""
    filepath = DATA_OUTPUT_DIR / "services.json"
    if not filepath.exists():
        print(f"Error: {filepath} not found")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_local_categories() -> list:
    """Load local categories from JSON."""
    filepath = DATA_OUTPUT_DIR / "categories.json"
    if not filepath.exists():
        print(f"Error: {filepath} not found")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def build_category_mapping(local_categories: list, api_categories: list) -> dict:
    """
    Build mapping: local_category_id -> api_category_id
    Based on matching category names.
    """
    # Build local_id -> name map
    local_id_to_name = {}
    for cat in local_categories:
        cat_id = cat.get("id")
        name_en = cat.get("name_i18n", {}).get("en", "")
        if cat_id and name_en:
            local_id_to_name[cat_id] = normalize_name(name_en)
    
    # Build api name -> id map
    api_name_to_id = {}
    for cat in api_categories:
        name_en = cat.get("name_i18n", {}).get("en", "")
        if name_en:
            api_name_to_id[normalize_name(name_en)] = cat["id"]
    
    # Build mapping: local_id -> api_id
    mapping = {}
    for local_id, local_name in local_id_to_name.items():
        if local_name in api_name_to_id:
            mapping[local_id] = api_name_to_id[local_name]
    
    return mapping


def main():
    execute = "--execute" in sys.argv
    
    # Parse limit
    limit = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
    
    print("=" * 60)
    print(f"UPLOAD SERVICES TO API (Location: {LOCATION_ID})")
    print("=" * 60)
    
    # 1. Load local data
    print("\n1. Loading local data...")
    local_services = load_local_services()
    local_categories = load_local_categories()
    print(f"   Found {len(local_services)} local services")
    print(f"   Found {len(local_categories)} local categories")
    
    if not local_services:
        return
    
    # 2. Fetch API data
    print("\n2. Fetching data from API...")
    try:
        api_categories = get_categories(location_id=LOCATION_ID, flat=True, include_archived=True)
        print(f"   Found {len(api_categories)} API categories")
    except Exception as e:
        print(f"   Error fetching categories: {e}")
        return
    
    try:
        api_services = get_services(location_id=LOCATION_ID, include_archived=True)
        print(f"   Found {len(api_services)} API services")
    except Exception as e:
        print(f"   Error fetching services: {e}")
        return
    
    # 3. Build category mapping (local_id -> api_id)
    print("\n3. Building category mapping...")
    category_mapping = build_category_mapping(local_categories, api_categories)
    print(f"   Mapped {len(category_mapping)} categories")
    
    # Show unmapped categories
    local_cat_ids = set(cat["id"] for cat in local_categories)
    mapped_ids = set(category_mapping.keys())
    unmapped_ids = local_cat_ids - mapped_ids
    if unmapped_ids:
        print(f"   WARNING: {len(unmapped_ids)} categories NOT mapped (not in API):")
        for cat in local_categories:
            if cat["id"] in unmapped_ids:
                print(f"      - ID {cat['id']}: {cat.get('name_i18n', {}).get('en', 'Unknown')}")
    
    # 4. Build API service name set
    api_service_names = set()
    for svc in api_services:
        name_en = svc.get("name_i18n", {}).get("en", "")
        if name_en:
            api_service_names.add(normalize_name(name_en))
    
    # 5. Find services to create
    to_create = []
    already_exist = []
    no_category = []
    
    for local_svc in local_services:
        name_en = local_svc.get("name_i18n", {}).get("en", "")
        normalized = normalize_name(name_en)
        
        if normalized in api_service_names:
            already_exist.append(name_en)
        else:
            # Check if category is mapped
            local_cat_id = local_svc.get("category_id")
            api_cat_id = category_mapping.get(local_cat_id)
            
            if local_cat_id and not api_cat_id:
                no_category.append({
                    "name": name_en,
                    "local_category_id": local_cat_id,
                })
            
            to_create.append({
                **local_svc,
                "api_category_id": api_cat_id,  # May be None
            })
    
    # 6. Show results
    print("\n" + "=" * 60)
    print("COMPARISON RESULTS")
    print("=" * 60)
    
    print(f"\nAlready exist in API: {len(already_exist)}")
    for name in already_exist[:5]:
        print(f"   ✓ {name[:50]}")
    if len(already_exist) > 5:
        print(f"   ... and {len(already_exist) - 5} more")
    
    print(f"\nNEW (to be created): {len(to_create)}")
    for svc in to_create[:10]:
        name = svc.get("name_i18n", {}).get("en", "Unknown")
        cat_id = svc.get("api_category_id", "NO CAT")
        print(f"   + {name[:45]} (cat: {cat_id})")
    if len(to_create) > 10:
        print(f"   ... and {len(to_create) - 10} more")
    
    if no_category:
        print(f"\nWARNING: {len(no_category)} services have unmapped categories:")
        for item in no_category[:5]:
            print(f"   ! {item['name'][:40]} (local cat: {item['local_category_id']})")
        if len(no_category) > 5:
            print(f"   ... and {len(no_category) - 5} more")
    
    if not to_create:
        print("\n✓ All services already exist in API. Nothing to do.")
        return
    
    # 7. Create services
    if not execute:
        print("\n" + "-" * 60)
        print("DRY RUN - No changes made.")
        print("To actually create services, run:")
        print("  python3 scripts/upload_services.py --execute")
        print("  python3 scripts/upload_services.py --execute --limit=5  # create first 5 only")
        return
    
    # Apply limit
    if limit:
        to_create = to_create[:limit]
        print(f"\nLimited to first {limit} services.")
    
    print("\n" + "=" * 60)
    print(f"CREATING {len(to_create)} SERVICES...")
    print("=" * 60)
    
    created = []
    failed = []
    
    for i, svc in enumerate(to_create, 1):
        name_en = svc.get("name_i18n", {}).get("en", "")
        api_cat_id = svc.get("api_category_id")
        description = svc.get("description_i18n", {}).get("en")
        duration = svc.get("duration_minutes")
        price_min = svc.get("price_min")
        price_max = svc.get("price_max")
        price_note = svc.get("price_note_i18n", {}).get("en")
        
        print(f"\n[{i}/{len(to_create)}] Creating: {name_en[:50]}...")
        try:
            result = create_service(
                name=name_en,
                location_id=LOCATION_ID,
                category_id=api_cat_id,
                description=description,
                duration_minutes=duration,
                price_min=price_min,
                price_max=price_max,
                price_note=price_note,
            )
            created.append({
                "local_id": svc["id"],
                "api_id": result["id"],
                "name": name_en,
            })
            print(f"   ✓ Created with ID: {result['id']}")
        except Exception as e:
            failed.append({
                "name": name_en,
                "error": str(e),
            })
            print(f"   ✗ Failed: {e}")
    
    # 8. Summary
    print("\n" + "=" * 60)
    print("UPLOAD COMPLETE")
    print("=" * 60)
    print(f"\nCreated: {len(created)}")
    print(f"Failed:  {len(failed)}")
    
    if failed:
        print("\nFailed services:")
        for item in failed:
            print(f"   ✗ {item['name'][:40]}: {item['error'][:50]}")
    
    # Save mapping for reference
    if created:
        mapping_file = DATA_OUTPUT_DIR / "_service_id_mapping.json"
        with open(mapping_file, "w", encoding="utf-8") as f:
            json.dump(created, f, ensure_ascii=False, indent=2)
        print(f"\nID mapping saved to: {mapping_file}")


if __name__ == "__main__":
    main()
