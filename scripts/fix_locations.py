#!/usr/bin/env python3
"""
Script to fix data distribution across locations.

Problem:
- All data was uploaded only to location_id=17 (Jumeirah)
- But services have 'branches' field that determines which location they belong to

Locations:
- location_id=17 → Jumeirah → branches: ["jumeirah"]
- location_id=18 → SZR → branches: ["srz"]

This script will:
1. Analyze what needs to be fixed
2. Upload categories to location 18 (SZR)
3. Upload services with 'srz' in branches to location 18
4. Delete services with ONLY 'srz' from location 17 (optional)

Usage:
    python scripts/fix_locations.py --analyze           # Just show what needs to be done
    python scripts/fix_locations.py --upload-categories # Upload categories to location 18
    python scripts/fix_locations.py --upload-services   # Upload services to location 18
    python scripts/fix_locations.py --delete-wrong      # Delete srz-only services from location 17
    python scripts/fix_locations.py --all --execute     # Do everything (requires --execute)
"""

import argparse
import json
import sys
from pathlib import Path

import requests

# Project paths
SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_OUTPUT = PROJECT_ROOT / "data" / "output"
DATA_API = PROJECT_ROOT / "data" / "api"

# API Configuration
API_BASE_URL = "https://dialoggauge.yma.health/api"

# Location mapping
LOCATIONS = {
    "jumeirah": 17,
    "srz": 18,
}

LOCATION_17_NAME = "Jumeirah"
LOCATION_18_NAME = "SZR"


def load_session() -> str:
    """Load session cookie."""
    session_file = CONFIG_DIR / ".dg_session.json"
    with open(session_file) as f:
        data = json.load(f)
    return data["dg_session"]


def get_headers() -> dict:
    """Get request headers with auth cookie."""
    return {"Cookie": f"dg_session={load_session()}"}


def load_local_data():
    """Load local JSON data."""
    with open(DATA_OUTPUT / "categories.json") as f:
        categories = json.load(f)
    with open(DATA_OUTPUT / "services.json") as f:
        services = json.load(f)
    return categories, services


def fetch_api_data(location_id: int):
    """Fetch current data from API for a location."""
    headers = get_headers()
    
    # Categories
    r = requests.get(
        f"{API_BASE_URL}/locations/{location_id}/categories?flat=true&include_archived=true",
        headers=headers
    )
    categories = r.json() if r.status_code == 200 else []
    
    # Services
    r = requests.get(
        f"{API_BASE_URL}/locations/{location_id}/services?include_archived=true",
        headers=headers
    )
    services = r.json() if r.status_code == 200 else []
    
    return categories, services


def analyze():
    """Analyze what needs to be fixed."""
    print("\n" + "=" * 70)
    print("ANALYSIS: Current state vs Expected state")
    print("=" * 70)
    
    local_categories, local_services = load_local_data()
    
    # Analyze services by branches
    services_by_branch = {
        "jumeirah_only": [],
        "srz_only": [],
        "both": [],
    }
    
    for svc in local_services:
        branches = set(svc.get("branches", []))
        if branches == {"jumeirah"}:
            services_by_branch["jumeirah_only"].append(svc)
        elif branches == {"srz"}:
            services_by_branch["srz_only"].append(svc)
        elif "jumeirah" in branches and "srz" in branches:
            services_by_branch["both"].append(svc)
        else:
            print(f"  WARNING: Service '{svc.get('name', 'unknown')}' has unexpected branches: {branches}")
    
    print("\n--- LOCAL DATA ---")
    print(f"Categories: {len(local_categories)}")
    print(f"Services total: {len(local_services)}")
    print(f"  - jumeirah only: {len(services_by_branch['jumeirah_only'])}")
    print(f"  - srz only: {len(services_by_branch['srz_only'])}")
    print(f"  - both locations: {len(services_by_branch['both'])}")
    
    # Fetch current API state
    print("\n--- CURRENT API STATE ---")
    
    api_17_cats, api_17_svcs = fetch_api_data(17)
    api_18_cats, api_18_svcs = fetch_api_data(18)
    
    print(f"Location 17 (Jumeirah):")
    print(f"  Categories: {len(api_17_cats)}")
    print(f"  Services: {len(api_17_svcs)}")
    
    print(f"Location 18 (SZR):")
    print(f"  Categories: {len(api_18_cats)}")
    print(f"  Services: {len(api_18_svcs)}")
    
    # Calculate what should be
    expected_17_svcs = len(services_by_branch["jumeirah_only"]) + len(services_by_branch["both"])
    expected_18_svcs = len(services_by_branch["srz_only"]) + len(services_by_branch["both"])
    
    print("\n--- EXPECTED STATE ---")
    print(f"Location 17 (Jumeirah):")
    print(f"  Categories: {len(local_categories)}")
    print(f"  Services: {expected_17_svcs} (jumeirah + both)")
    
    print(f"Location 18 (SZR):")
    print(f"  Categories: {len(local_categories)}")
    print(f"  Services: {expected_18_svcs} (srz + both)")
    
    # What needs to be done
    print("\n--- ACTIONS NEEDED ---")
    
    if len(api_18_cats) < len(local_categories):
        print(f"[1] Upload {len(local_categories)} categories to Location 18 (SZR)")
    else:
        print("[1] Categories on Location 18: OK")
    
    services_for_18 = services_by_branch["srz_only"] + services_by_branch["both"]
    if len(api_18_svcs) < len(services_for_18):
        print(f"[2] Upload {len(services_for_18)} services to Location 18 (SZR)")
    else:
        print("[2] Services on Location 18: OK")
    
    # Services to delete from 17
    if len(api_17_svcs) > expected_17_svcs:
        to_delete = len(api_17_svcs) - expected_17_svcs
        print(f"[3] Delete ~{to_delete} srz-only services from Location 17 (optional)")
    else:
        print("[3] Services on Location 17: OK")
    
    print("\n" + "=" * 70)
    
    return services_by_branch


def upload_categories_to_18(execute: bool = False):
    """Upload all categories to location 18."""
    print("\n--- UPLOADING CATEGORIES TO LOCATION 18 (SZR) ---")
    
    local_categories, _ = load_local_data()
    api_cats, _ = fetch_api_data(18)
    
    # Build lookup of existing categories by name
    existing_by_name = {}
    for cat in api_cats:
        name_en = cat.get("name_i18n", {}).get("en", "").lower()
        name = cat.get("name", "").lower()
        if name_en:
            existing_by_name[name_en] = cat
        if name:
            existing_by_name[name] = cat
    
    to_upload = []
    for cat in local_categories:
        name_en = cat.get("name_i18n", {}).get("en", "").lower()
        name = cat.get("name", "").lower()
        if name_en not in existing_by_name and name not in existing_by_name:
            to_upload.append(cat)
    
    print(f"Categories to upload: {len(to_upload)} (already exists: {len(local_categories) - len(to_upload)})")
    
    if not execute:
        print("\n[DRY RUN] Add --execute to actually upload")
        return
    
    headers = get_headers()
    headers["Content-Type"] = "application/json"
    
    success = 0
    failed = 0
    
    for cat in to_upload:
        # Prepare payload (remove local id)
        payload = {
            "name": cat.get("name"),
            "name_i18n": cat.get("name_i18n"),
            "description_i18n": cat.get("description_i18n"),
            "parent_id": None,  # Categories are flat for now
            "is_active": True,
        }
        
        response = requests.post(
            f"{API_BASE_URL}/locations/18/categories",
            headers=headers,
            json=payload,
        )
        
        if response.status_code in (200, 201):
            success += 1
            print(f"  ✓ Created: {cat.get('name')}")
        else:
            failed += 1
            print(f"  ✗ Failed: {cat.get('name')} - {response.status_code}: {response.text[:100]}")
    
    print(f"\nResult: {success} success, {failed} failed")


def upload_services_to_18(execute: bool = False):
    """Upload services with 'srz' in branches to location 18."""
    print("\n--- UPLOADING SERVICES TO LOCATION 18 (SZR) ---")
    
    local_categories, local_services = load_local_data()
    api_cats, api_svcs = fetch_api_data(18)
    
    # Services to upload: those with 'srz' in branches
    services_for_18 = [s for s in local_services if "srz" in s.get("branches", [])]
    
    print(f"Services with 'srz' in branches: {len(services_for_18)}")
    
    # Build lookup of existing services by name
    existing_by_name = {}
    for svc in api_svcs:
        name_en = svc.get("name_i18n", {}).get("en", "").lower()
        if name_en:
            existing_by_name[name_en] = svc
    
    to_upload = []
    for svc in services_for_18:
        name_en = svc.get("name_i18n", {}).get("en", "").lower()
        if name_en not in existing_by_name:
            to_upload.append(svc)
    
    print(f"Services to upload: {len(to_upload)} (already exists: {len(services_for_18) - len(to_upload)})")
    
    if not execute:
        print("\n[DRY RUN] Add --execute to actually upload")
        return
    
    # Build category mapping: local category name -> API category ID on location 18
    api_cats_18, _ = fetch_api_data(18)
    cat_name_to_api_id = {}
    for cat in api_cats_18:
        name_en = cat.get("name_i18n", {}).get("en", "").lower()
        if name_en:
            cat_name_to_api_id[name_en] = cat["id"]
    
    # Also need local category id -> name mapping
    local_cat_id_to_name = {}
    for cat in local_categories:
        cat_id = cat.get("id")
        name_en = cat.get("name_i18n", {}).get("en", "").lower()
        if cat_id and name_en:
            local_cat_id_to_name[cat_id] = name_en
    
    headers = get_headers()
    headers["Content-Type"] = "application/json"
    
    success = 0
    failed = 0
    skipped_no_cat = 0
    
    for svc in to_upload:
        # Map category_id from local to API
        local_cat_id = svc.get("category_id")
        cat_name = local_cat_id_to_name.get(local_cat_id)
        api_cat_id = cat_name_to_api_id.get(cat_name) if cat_name else None
        
        if not api_cat_id:
            skipped_no_cat += 1
            print(f"  ⚠ Skipped (no category mapping): {svc.get('name_i18n', {}).get('en', 'unknown')}")
            continue
        
        payload = {
            "name_i18n": svc.get("name_i18n"),
            "description_i18n": svc.get("description_i18n"),
            "category_id": api_cat_id,
            "duration_minutes": svc.get("duration_minutes"),
            "price": svc.get("price"),
            "is_active": True,
        }
        
        response = requests.post(
            f"{API_BASE_URL}/locations/18/services",
            headers=headers,
            json=payload,
        )
        
        if response.status_code in (200, 201):
            success += 1
            if success % 50 == 0:
                print(f"  ... uploaded {success} services")
        else:
            failed += 1
            print(f"  ✗ Failed: {svc.get('name_i18n', {}).get('en', 'unknown')} - {response.status_code}")
    
    print(f"\nResult: {success} success, {failed} failed, {skipped_no_cat} skipped (no category)")


def delete_wrong_services_from_17(execute: bool = False):
    """Delete services that are srz-only from location 17."""
    print("\n--- DELETING SRZ-ONLY SERVICES FROM LOCATION 17 ---")
    
    _, local_services = load_local_data()
    _, api_svcs = fetch_api_data(17)
    
    # Services that are srz-only in local data
    srz_only_names = set()
    for svc in local_services:
        branches = set(svc.get("branches", []))
        if branches == {"srz"}:
            name_en = svc.get("name_i18n", {}).get("en", "").lower()
            if name_en:
                srz_only_names.add(name_en)
    
    print(f"SRZ-only services in local data: {len(srz_only_names)}")
    
    # Find API services to delete
    to_delete = []
    for svc in api_svcs:
        name_en = svc.get("name_i18n", {}).get("en", "").lower()
        if name_en in srz_only_names:
            to_delete.append(svc)
    
    print(f"Services to delete from Location 17: {len(to_delete)}")
    
    if not execute:
        print("\n[DRY RUN] Add --execute to actually delete")
        if to_delete:
            print("\nFirst 10 services that would be deleted:")
            for svc in to_delete[:10]:
                print(f"  - {svc.get('name_i18n', {}).get('en', 'unknown')} (id={svc['id']})")
        return
    
    headers = get_headers()
    
    success = 0
    failed = 0
    
    for svc in to_delete:
        response = requests.delete(
            f"{API_BASE_URL}/locations/17/services/{svc['id']}",
            headers=headers,
        )
        
        if response.status_code in (200, 204):
            success += 1
        else:
            failed += 1
            print(f"  ✗ Failed to delete: {svc.get('name_i18n', {}).get('en', 'unknown')} (id={svc['id']})")
    
    print(f"\nResult: {success} deleted, {failed} failed")


def main():
    parser = argparse.ArgumentParser(description="Fix data distribution across locations")
    parser.add_argument("--analyze", action="store_true", help="Analyze current state")
    parser.add_argument("--upload-categories", action="store_true", help="Upload categories to Location 18")
    parser.add_argument("--upload-services", action="store_true", help="Upload services to Location 18")
    parser.add_argument("--delete-wrong", action="store_true", help="Delete srz-only services from Location 17")
    parser.add_argument("--all", action="store_true", help="Do all operations")
    parser.add_argument("--execute", action="store_true", help="Actually execute (default is dry-run)")
    
    args = parser.parse_args()
    
    if not any([args.analyze, args.upload_categories, args.upload_services, args.delete_wrong, args.all]):
        parser.print_help()
        print("\nExample:")
        print("  python scripts/fix_locations.py --analyze")
        print("  python scripts/fix_locations.py --upload-categories --execute")
        return
    
    if args.analyze or args.all:
        analyze()
    
    if args.upload_categories or args.all:
        upload_categories_to_18(execute=args.execute)
    
    if args.upload_services or args.all:
        upload_services_to_18(execute=args.execute)
    
    if args.delete_wrong or args.all:
        delete_wrong_services_from_17(execute=args.execute)


if __name__ == "__main__":
    main()
