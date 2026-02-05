#!/usr/bin/env python3
"""
Upload local categories to DialogGauge API.

Steps:
1. Fetch existing categories from API
2. Compare with local categories (by name)
3. Create only NEW categories (not in API)

Usage:
    python3 scripts/upload_categories.py              # Dry run (show what would be created)
    python3 scripts/upload_categories.py --execute    # Actually create categories
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
from get_categories import get_categories, create_category, LOCATION_ID


def normalize_name(name: str) -> str:
    """Normalize name for comparison."""
    if not name:
        return ""
    name = name.lower().strip()
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'[^\w\s]', '', name)
    return name


def load_local_categories() -> list:
    """Load local categories from JSON."""
    filepath = DATA_OUTPUT_DIR / "categories.json"
    if not filepath.exists():
        print(f"Error: {filepath} not found")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    execute = "--execute" in sys.argv
    
    print("=" * 60)
    print(f"UPLOAD CATEGORIES TO API (Location: {LOCATION_ID})")
    print("=" * 60)
    
    # 1. Load local categories
    print("\n1. Loading local categories...")
    local_categories = load_local_categories()
    print(f"   Found {len(local_categories)} local categories")
    
    if not local_categories:
        return
    
    # 2. Fetch API categories
    print("\n2. Fetching categories from API...")
    try:
        api_categories = get_categories(location_id=LOCATION_ID, flat=True, include_archived=True)
        print(f"   Found {len(api_categories)} API categories")
    except Exception as e:
        print(f"   Error: {e}")
        return
    
    # 3. Build API name map
    api_names = set()
    for cat in api_categories:
        name_en = cat.get("name_i18n", {}).get("en", "")
        if name_en:
            api_names.add(normalize_name(name_en))
    
    # 4. Find categories to create
    to_create = []
    already_exist = []
    
    for local_cat in local_categories:
        name_en = local_cat.get("name_i18n", {}).get("en", "")
        normalized = normalize_name(name_en)
        
        if normalized in api_names:
            already_exist.append(name_en)
        else:
            to_create.append(local_cat)
    
    # 5. Show results
    print("\n" + "=" * 60)
    print("COMPARISON RESULTS")
    print("=" * 60)
    
    print(f"\nAlready exist in API: {len(already_exist)}")
    for name in already_exist[:10]:
        print(f"   ✓ {name}")
    if len(already_exist) > 10:
        print(f"   ... and {len(already_exist) - 10} more")
    
    print(f"\nNEW (to be created): {len(to_create)}")
    for cat in to_create:
        name = cat.get("name_i18n", {}).get("en", "Unknown")
        print(f"   + {name}")
    
    if not to_create:
        print("\n✓ All categories already exist in API. Nothing to do.")
        return
    
    # 6. Create categories
    if not execute:
        print("\n" + "-" * 60)
        print("DRY RUN - No changes made.")
        print("To actually create categories, run:")
        print("  python3 scripts/upload_categories.py --execute")
        return
    
    print("\n" + "=" * 60)
    print("CREATING CATEGORIES...")
    print("=" * 60)
    
    created = []
    failed = []
    
    for cat in to_create:
        name_en = cat.get("name_i18n", {}).get("en", "")
        sort_order = cat.get("sort_order", 0)
        
        print(f"\nCreating: {name_en}...")
        try:
            result = create_category(
                name=name_en,
                location_id=LOCATION_ID,
            )
            created.append({
                "local_id": cat["id"],
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
    
    # 7. Summary
    print("\n" + "=" * 60)
    print("UPLOAD COMPLETE")
    print("=" * 60)
    print(f"\nCreated: {len(created)}")
    print(f"Failed:  {len(failed)}")
    
    if created:
        print("\nID Mapping (local → API):")
        for item in created:
            print(f"   {item['local_id']} → {item['api_id']}: {item['name']}")


if __name__ == "__main__":
    main()
