#!/usr/bin/env python3
"""
Sync practitioners with DialogGauge API.

This script:
1. Fetches existing practitioners from API (location_id=17)
2. Compares with local practitioners.json by name
3. Updates local IDs to match API IDs for existing practitioners
4. Assigns new IDs for practitioners not in API
"""

import json
import re
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.get_categories import get_practitioners

# File paths
LOCAL_PRACTITIONERS_FILE = PROJECT_ROOT / "data/output/practitioners.json"
API_RESPONSE_FILE = PROJECT_ROOT / "data/api/practitioners_api_response_17.json"
SYNC_REPORT_FILE = PROJECT_ROOT / "data/api/_practitioners_sync_report.json"

LOCATION_ID = 17  # Hortman Clinics


def normalize_name(name: str) -> str:
    """Normalize name for comparison."""
    if not name:
        return ""
    # lowercase, remove extra spaces, remove special chars
    name = name.lower().strip()
    name = re.sub(r'\s+', ' ', name)
    # Remove "Dr." prefix for better matching
    name = re.sub(r'^dr\.?\s*', '', name)
    return name


def load_local_practitioners() -> list[dict]:
    """Load local practitioners from JSON."""
    if not LOCAL_PRACTITIONERS_FILE.exists():
        print(f"ERROR: Local file not found: {LOCAL_PRACTITIONERS_FILE}")
        sys.exit(1)
    
    with open(LOCAL_PRACTITIONERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_local_practitioners(practitioners: list[dict]):
    """Save practitioners back to JSON."""
    with open(LOCAL_PRACTITIONERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(practitioners, f, indent=2, ensure_ascii=False)


def fetch_api_practitioners() -> list[dict]:
    """Fetch practitioners from API."""
    print(f"Fetching practitioners from API (location_id={LOCATION_ID})...")
    practitioners = get_practitioners(location_id=LOCATION_ID, include_archived=True)
    
    # Save response for reference
    API_RESPONSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(API_RESPONSE_FILE, 'w', encoding='utf-8') as f:
        json.dump(practitioners, f, indent=2, ensure_ascii=False)
    
    print(f"Fetched {len(practitioners)} practitioners from API")
    print(f"Saved to: {API_RESPONSE_FILE}")
    
    return practitioners


def sync_practitioners():
    """Main sync function."""
    # Load data
    local_practitioners = load_local_practitioners()
    api_practitioners = fetch_api_practitioners()
    
    # Build API lookup by normalized name
    api_by_name = {}
    for p in api_practitioners:
        name_en = p.get('name_i18n', {}).get('en', '')
        if name_en:
            normalized = normalize_name(name_en)
            api_by_name[normalized] = p
    
    print(f"\n{'='*60}")
    print("SYNCING PRACTITIONERS")
    print(f"{'='*60}")
    print(f"Local practitioners: {len(local_practitioners)}")
    print(f"API practitioners:   {len(api_practitioners)}")
    print()
    
    # Track changes
    matched = []
    not_found = []
    
    # Find max API ID for new practitioners
    max_api_id = max((p['id'] for p in api_practitioners), default=0)
    next_new_id = max_api_id + 1
    
    # Sync IDs
    for local_p in local_practitioners:
        local_name = local_p.get('name', '')
        normalized = normalize_name(local_name)
        old_id = local_p['id']
        
        if normalized in api_by_name:
            api_p = api_by_name[normalized]
            new_id = api_p['id']
            local_p['id'] = new_id
            matched.append({
                'name': local_name,
                'old_id': old_id,
                'new_id': new_id,
                'api_name': api_p.get('name_i18n', {}).get('en', ''),
            })
            print(f"✓ MATCHED: {local_name}")
            print(f"    Local ID {old_id} → API ID {new_id}")
        else:
            # Assign new ID
            local_p['id'] = next_new_id
            not_found.append({
                'name': local_name,
                'old_id': old_id,
                'new_id': next_new_id,
            })
            print(f"✗ NOT FOUND: {local_name}")
            print(f"    Assigned new ID: {next_new_id}")
            next_new_id += 1
    
    # Save updated practitioners
    save_local_practitioners(local_practitioners)
    print(f"\n✓ Saved updated practitioners to: {LOCAL_PRACTITIONERS_FILE}")
    
    # Save sync report
    report = {
        'location_id': LOCATION_ID,
        'local_count': len(local_practitioners),
        'api_count': len(api_practitioners),
        'matched_count': len(matched),
        'not_found_count': len(not_found),
        'matched': matched,
        'not_found_in_api': not_found,
    }
    
    with open(SYNC_REPORT_FILE, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Sync report saved to: {SYNC_REPORT_FILE}")
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Matched with API:    {len(matched)}")
    print(f"Not found (new):     {len(not_found)}")
    
    if not_found:
        print(f"\nPractitioners to CREATE in API:")
        for p in not_found:
            print(f"  - {p['name']} (will get ID {p['new_id']})")


if __name__ == "__main__":
    sync_practitioners()
