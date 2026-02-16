#!/usr/bin/env python3
"""
Fix data distribution across locations.

PROBLEM:
  All 373 services and 38 categories were uploaded to location_id=17 (Jumeirah) only.
  But services have a 'branches' field that specifies which location(s) they belong to.
  Location 18 (SZR) is empty.

LOCATION MAPPING:
  location_id=17  →  Jumeirah  →  branches containing "jumeirah"
  location_id=18  →  SZR       →  branches containing "szr"

WHAT THIS SCRIPT DOES (in order):

  Step 1: Upload categories to Location 18 (SZR)
    - Categories don't have 'branches' → same set for both locations
    - 35 categories need to be created on Location 18

  Step 2: Upload services to Location 18 (SZR)
    - Services with branches=["szr"] → 133 services (SZR only)
    - Services with branches=["jumeirah","szr"] → 116 services (both)
    - Total: 249 services need to be on Location 18
    - Maps category_id from local → API (Location 18 IDs)

  Step 3: Delete szr-only services from Location 17 (Jumeirah)
    - 133 services with branches=["szr"] should NOT be on Location 17
    - Matches by name_i18n.en between local data and API

  Step 4: Upload practitioners (per location)
    - branches=["jumeirah"] → Location 17 only (5 practitioners)
    - branches=["szr"] → Location 18 only (6 practitioners)
    - branches=["jumeirah","szr"] → both locations (1 practitioner)
    - branches=[] (empty) → BOTH locations (14 practitioners)
    - Total: 20 on Location 17, 21 on Location 18

  Step 5: Link service-practitioners (per location)
    - Uses service_practitioners.json
    - Links each (service_id, practitioner_id) pair on the correct location(s)
    - Maps local IDs → API IDs per location

USAGE:
    python scripts/fix_locations.py --analyze                     # Show what needs to be done
    python scripts/fix_locations.py --step1                       # Dry run: categories → Location 18
    python scripts/fix_locations.py --step1 --execute             # Execute: categories → Location 18
    python scripts/fix_locations.py --step2                       # Dry run: services → Location 18
    python scripts/fix_locations.py --step2 --execute             # Execute: services → Location 18
    python scripts/fix_locations.py --step3                       # Dry run: delete wrong services from 17
    python scripts/fix_locations.py --step3 --execute             # Execute: delete wrong services from 17
    python scripts/fix_locations.py --step4                       # Dry run: practitioners
    python scripts/fix_locations.py --step4 --execute             # Execute: practitioners
    python scripts/fix_locations.py --step5                       # Dry run: service-practitioner links
    python scripts/fix_locations.py --step5 --execute             # Execute: service-practitioner links
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

# ─── Project paths ───────────────────────────────────────────────────────────
SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_OUTPUT = PROJECT_ROOT / "data" / "output"
DATA_API = PROJECT_ROOT / "data" / "api"

# ─── API ─────────────────────────────────────────────────────────────────────
API_BASE = "https://dialoggauge.yma.health/api"

LOCATION_JUMEIRAH = 21
LOCATION_SZR = 20

# branch name in local JSON → location_id
BRANCH_TO_LOCATION = {
    "jumeirah": LOCATION_JUMEIRAH,
    "szr": LOCATION_SZR,
    "szr": LOCATION_SZR,  # alias (practitioners use "szr" instead of "szr")
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def load_session() -> str:
    with open(CONFIG_DIR / ".dg_session.json") as f:
        return json.load(f)["dg_session"]


def api_headers() -> dict:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Cookie": f"dg_session={load_session()}",
    }


def normalize(name: str) -> str:
    """Normalize name for comparison."""
    if not name:
        return ""
    name = name.lower().strip()
    name = re.sub(r"\s+", " ", name)
    return name


def get_name_en(item: dict) -> str:
    return (item.get("name_i18n") or {}).get("en", "") or item.get("name", "")


def load_local(filename: str) -> list:
    with open(DATA_OUTPUT / filename, encoding="utf-8") as f:
        return json.load(f)


def api_get(endpoint: str) -> list:
    r = requests.get(f"{API_BASE}{endpoint}", headers=api_headers())
    r.raise_for_status()
    return r.json()


def api_post(endpoint: str, data: dict) -> dict:
    r = requests.post(f"{API_BASE}{endpoint}", headers=api_headers(), json=data)
    if r.status_code not in (200, 201):
        raise Exception(f"POST {endpoint} → {r.status_code}: {r.text[:200]}")
    return r.json()


def api_put(endpoint: str, data: dict) -> dict:
    r = requests.put(f"{API_BASE}{endpoint}", headers=api_headers(), json=data)
    if r.status_code not in (200, 201):
        raise Exception(f"PUT {endpoint} → {r.status_code}: {r.text[:200]}")
    return r.json()


def api_delete(endpoint: str) -> int:
    r = requests.delete(f"{API_BASE}{endpoint}", headers=api_headers())
    return r.status_code


# ─── Fetch current API state ────────────────────────────────────────────────

def fetch_api_categories(location_id: int) -> list:
    return api_get(f"/locations/{location_id}/categories?flat=true&include_archived=true")


def fetch_api_services(location_id: int) -> list:
    return api_get(f"/locations/{location_id}/services?include_archived=true")


def fetch_api_practitioners(location_id: int) -> list:
    return api_get(f"/locations/{location_id}/practitioners?include_archived=true")


# ─── Classify local data by branch ──────────────────────────────────────────

def classify_services(services: list) -> dict:
    """Classify services by which locations they belong to."""
    result = {"jumeirah_only": [], "szr_only": [], "both": []}
    for svc in services:
        branches = set(svc.get("branches", []))
        if branches == {"jumeirah"}:
            result["jumeirah_only"].append(svc)
        elif branches == {"szr"}:
            result["szr_only"].append(svc)
        elif "jumeirah" in branches and "szr" in branches:
            result["both"].append(svc)
        else:
            print(f"  WARNING: unexpected branches {branches} for service '{get_name_en(svc)}'")
    return result


def classify_practitioners(practitioners: list) -> dict:
    """Classify practitioners by which locations they belong to.
    
    NOTE: In practitioners.json, SZR branch is spelled "szr" (not "szr").
    Practitioners with empty branches go to BOTH locations.
    """
    result = {"jumeirah_only": [], "szr_only": [], "both": []}
    for p in practitioners:
        branches = set(b.lower() for b in p.get("branches", []))
        has_jum = "jumeirah" in branches
        has_szr = "szr" in branches or "szr" in branches
        
        if has_jum and has_szr:
            result["both"].append(p)
        elif has_jum:
            result["jumeirah_only"].append(p)
        elif has_szr:
            result["szr_only"].append(p)
        else:
            # Empty branches → goes to both locations
            result["both"].append(p)
    return result


# ═════════════════════════════════════════════════════════════════════════════
# ANALYZE
# ═════════════════════════════════════════════════════════════════════════════

def do_analyze():
    print("\n" + "=" * 70)
    print("  ANALYSIS: Current State vs Expected State")
    print("=" * 70)

    # Local data
    local_cats = load_local("categories.json")
    local_svcs = load_local("services.json")
    local_practs = load_local("practitioners.json")
    local_sp = load_local("service_practitioners.json")

    svc_class = classify_services(local_svcs)
    pract_class = classify_practitioners(local_practs)

    print(f"\n{'─'*40}")
    print("LOCAL DATA")
    print(f"{'─'*40}")
    print(f"  Categories:              {len(local_cats)}")
    print(f"  Services total:          {len(local_svcs)}")
    print(f"    - jumeirah only:       {len(svc_class['jumeirah_only'])}")
    print(f"    - szr only:            {len(svc_class['szr_only'])}")
    print(f"    - both:                {len(svc_class['both'])}")
    print(f"  Practitioners total:     {len(local_practs)}")
    print(f"    - jumeirah only:       {len(pract_class['jumeirah_only'])}")
    print(f"    - szr only:            {len(pract_class['szr_only'])}")
    print(f"    - both (incl empty):   {len(pract_class['both'])}")
    print(f"  Service-Practitioner links: {len(local_sp)}")

    # API state
    print(f"\n{'─'*40}")
    print("CURRENT API STATE")
    print(f"{'─'*40}")
    for loc_id, loc_name in [(LOCATION_JUMEIRAH, "Jumeirah"), (LOCATION_SZR, "SZR")]:
        cats = fetch_api_categories(loc_id)
        svcs = fetch_api_services(loc_id)
        practs = fetch_api_practitioners(loc_id)
        print(f"  Location {loc_id} ({loc_name}):")
        print(f"    Categories:    {len(cats)}")
        print(f"    Services:      {len(svcs)}")
        print(f"    Practitioners: {len(practs)}")

    # Expected
    exp_17_svcs = len(svc_class["jumeirah_only"]) + len(svc_class["both"])
    exp_18_svcs = len(svc_class["szr_only"]) + len(svc_class["both"])
    exp_17_practs = len(pract_class["jumeirah_only"]) + len(pract_class["both"])
    exp_18_practs = len(pract_class["szr_only"]) + len(pract_class["both"])

    print(f"\n{'─'*40}")
    print("EXPECTED STATE")
    print(f"{'─'*40}")
    print(f"  Location {LOCATION_JUMEIRAH} (Jumeirah):")
    print(f"    Categories:    {len(local_cats)}")
    print(f"    Services:      {exp_17_svcs}")
    print(f"    Practitioners: {exp_17_practs}")
    print(f"  Location {LOCATION_SZR} (SZR):")
    print(f"    Categories:    {len(local_cats)}")
    print(f"    Services:      {exp_18_svcs}")
    print(f"    Practitioners: {exp_18_practs}")

    # Actions
    print(f"\n{'─'*40}")
    print("ACTIONS NEEDED")
    print(f"{'─'*40}")
    print(f"  [Step 1] Upload {len(local_cats)} categories to Location 18 (SZR)")
    print(f"  [Step 2] Upload {exp_18_svcs} services to Location 18 (SZR)")
    print(f"  [Step 3] Delete {len(svc_class['szr_only'])} szr-only services from Location 17")
    print(f"  [Step 4] Upload {exp_17_practs} practitioners to Loc 17 + {exp_18_practs} to Loc 18")
    print(f"  [Step 5] Link service-practitioners on both locations")
    print("=" * 70)


# ═════════════════════════════════════════════════════════════════════════════
# STEP 1: Upload categories to Location 18
# ═════════════════════════════════════════════════════════════════════════════

def do_step1(execute: bool):
    print("\n" + "=" * 70)
    print("  STEP 1: Upload categories to Location 18 (SZR)")
    print("=" * 70)

    local_cats = load_local("categories.json")
    api_cats = fetch_api_categories(LOCATION_SZR)

    # Existing on API (by normalized name)
    existing = {normalize(get_name_en(c)): c for c in api_cats}

    to_create = []
    already = []
    for cat in local_cats:
        name = normalize(get_name_en(cat))
        if name in existing:
            already.append(cat)
        else:
            to_create.append(cat)

    print(f"\n  Already on Location 18: {len(already)}")
    print(f"  To create:              {len(to_create)}")

    if not to_create:
        print("\n  All categories already exist. Nothing to do.")
        return

    for cat in to_create:
        print(f"    + {get_name_en(cat)}")

    if not execute:
        print(f"\n  [DRY RUN] Add --execute to actually create {len(to_create)} categories")
        return

    print(f"\n  Creating {len(to_create)} categories...")
    ok, fail = 0, 0
    for cat in to_create:
        name_en = get_name_en(cat)
        payload = {
            "location_id": LOCATION_SZR,
            "name": {"en": name_en},
            "is_visible_to_ai": True,
        }
        try:
            result = api_post(f"/locations/{LOCATION_SZR}/categories", payload)
            ok += 1
            print(f"    ✓ {name_en}  (api_id={result['id']})")
        except Exception as e:
            fail += 1
            print(f"    ✗ {name_en}  ({e})")

    print(f"\n  Result: {ok} created, {fail} failed")


# ═════════════════════════════════════════════════════════════════════════════
# STEP 2: Upload services to Location 18
# ═════════════════════════════════════════════════════════════════════════════

def build_category_name_to_api_id(location_id: int) -> dict:
    """Build mapping: normalized category name → API category ID for location."""
    api_cats = fetch_api_categories(location_id)
    return {normalize(get_name_en(c)): c["id"] for c in api_cats}


def build_api_catid_to_name(location_id: int) -> dict:
    """Build mapping: API category_id → normalized category name."""
    api_cats = fetch_api_categories(location_id)
    return {c["id"]: normalize(get_name_en(c)) for c in api_cats}


def build_local_catid_to_name(local_cats: list) -> dict:
    """Build mapping: local category_id → normalized name."""
    return {c["id"]: normalize(get_name_en(c)) for c in local_cats}


def svc_key(name: str, cat_name: str) -> tuple:
    """Unique service key = (normalized name, normalized category name).
    
    This is needed because some services have identical names but belong to
    different categories (e.g. LHR services exist in both Soprano Titanium
    and Polylase MX categories with different branch assignments).
    """
    return (normalize(name), normalize(cat_name))


def do_step2(execute: bool):
    print("\n" + "=" * 70)
    print("  STEP 2: Upload services to Location 18 (SZR)")
    print("=" * 70)

    local_cats = load_local("categories.json")
    local_svcs = load_local("services.json")
    svc_class = classify_services(local_svcs)
    local_catid_to_name = build_local_catid_to_name(local_cats)

    # Services for Location 18: szr_only + both
    services_for_18 = svc_class["szr_only"] + svc_class["both"]
    print(f"\n  Services with 'szr' in branches: {len(services_for_18)}")
    print(f"    - szr only:  {len(svc_class['szr_only'])}")
    print(f"    - both:      {len(svc_class['both'])}")

    # Check what already exists on Location 18 — match by (name, category)
    api_svcs = fetch_api_services(LOCATION_SZR)
    api_catid_to_name_18 = build_api_catid_to_name(LOCATION_SZR)
    existing_keys = set()
    for s in api_svcs:
        cat_name = api_catid_to_name_18.get(s.get("category_id"), "")
        existing_keys.add(svc_key(get_name_en(s), cat_name))

    to_create = []
    already = 0
    for s in services_for_18:
        local_cat_name = local_catid_to_name.get(s.get("category_id"), "")
        key = svc_key(get_name_en(s), local_cat_name)
        if key in existing_keys:
            already += 1
        else:
            to_create.append(s)

    print(f"\n  Already on Location 18: {already}")
    print(f"  To create:              {len(to_create)}")

    if not to_create:
        print("\n  All services already exist. Nothing to do.")
        return

    # Build category mapping
    cat_name_to_api_id = build_category_name_to_api_id(LOCATION_SZR)

    # Show first 20
    for svc in to_create[:20]:
        name = get_name_en(svc)
        local_cat = local_catid_to_name.get(svc.get("category_id"), "???")
        api_cat = cat_name_to_api_id.get(local_cat, "???")
        print(f"    + {name[:50]}  (cat: {local_cat[:20]} → api_cat_id={api_cat})")
    if len(to_create) > 20:
        print(f"    ... and {len(to_create) - 20} more")

    if not execute:
        print(f"\n  [DRY RUN] Add --execute to create {len(to_create)} services")
        return

    print(f"\n  Creating {len(to_create)} services...")
    ok, fail, no_cat = 0, 0, 0

    for svc in to_create:
        name_en = get_name_en(svc)
        local_cat_name = local_catid_to_name.get(svc.get("category_id"))
        api_cat_id = cat_name_to_api_id.get(local_cat_name) if local_cat_name else None

        if not api_cat_id:
            no_cat += 1
            print(f"    ⚠ SKIP (no category mapping): {name_en}")
            continue

        payload = {
            "location_id": LOCATION_SZR,
            "name": {"en": name_en},
            "category_id": api_cat_id,
            "is_visible_to_ai": True,
        }
        # Optional fields
        desc = (svc.get("description_i18n") or {}).get("en")
        if desc:
            payload["description"] = {"en": desc}
        if svc.get("duration_minutes"):
            payload["duration_minutes"] = svc["duration_minutes"]
        if svc.get("price_min") is not None:
            payload["price_min"] = svc["price_min"]
        if svc.get("price_max") is not None:
            payload["price_max"] = svc["price_max"]
        price_note = (svc.get("price_note_i18n") or {}).get("en")
        if price_note:
            payload["price_note"] = {"en": price_note}

        try:
            result = api_post(f"/locations/{LOCATION_SZR}/services", payload)
            ok += 1
            if ok % 50 == 0:
                print(f"    ... created {ok} services")
        except Exception as e:
            fail += 1
            print(f"    ✗ {name_en}: {e}")

    print(f"\n  Result: {ok} created, {fail} failed, {no_cat} skipped (no category)")


# ═════════════════════════════════════════════════════════════════════════════
# STEP 3: Delete szr-only services from Location 17
# ═════════════════════════════════════════════════════════════════════════════

def do_step3(execute: bool):
    print("\n" + "=" * 70)
    print("  STEP 3: Delete szr-only services from Location 17 (Jumeirah)")
    print("=" * 70)
    print("  NOTE: Uses (name + category) matching to avoid deleting")
    print("  services that share a name but belong to different categories/branches.")

    local_cats = load_local("categories.json")
    local_svcs = load_local("services.json")
    local_catid_to_name = build_local_catid_to_name(local_cats)
    svc_class = classify_services(local_svcs)

    # Build set of (name, category) keys for szr-only services
    szr_only_keys = set()
    for s in svc_class["szr_only"]:
        cat_name = local_catid_to_name.get(s.get("category_id"), "")
        szr_only_keys.add(svc_key(get_name_en(s), cat_name))
    print(f"\n  szr-only service (name,cat) keys: {len(szr_only_keys)}")

    # Fetch current Location 17 services and build (name, category) keys
    api_svcs = fetch_api_services(LOCATION_JUMEIRAH)
    api_catid_to_name_17 = build_api_catid_to_name(LOCATION_JUMEIRAH)

    to_delete = []
    kept = 0
    for svc in api_svcs:
        api_cat_name = api_catid_to_name_17.get(svc.get("category_id"), "")
        key = svc_key(get_name_en(svc), api_cat_name)
        if key in szr_only_keys:
            to_delete.append(svc)
        else:
            kept += 1

    print(f"  API services on Location 17: {len(api_svcs)}")
    print(f"  Services to DELETE (szr-only): {len(to_delete)}")
    print(f"  Services to KEEP:              {kept}")

    if not to_delete:
        print("\n  No szr-only services found on Location 17. Nothing to do.")
        return

    # Show first 20
    for svc in to_delete[:20]:
        cat_name = api_catid_to_name_17.get(svc.get("category_id"), "?")
        print(f"    - [{svc['id']}] {get_name_en(svc)[:45]} | cat: {cat_name[:25]}")
    if len(to_delete) > 20:
        print(f"    ... and {len(to_delete) - 20} more")

    if not execute:
        print(f"\n  [DRY RUN] Add --execute to delete {len(to_delete)} services")
        return

    print(f"\n  Deleting {len(to_delete)} services...")
    ok, fail = 0, 0
    for svc in to_delete:
        status = api_delete(f"/locations/{LOCATION_JUMEIRAH}/services/{svc['id']}")
        if status in (200, 204):
            ok += 1
        else:
            fail += 1
            print(f"    ✗ Failed to delete [{svc['id']}] {get_name_en(svc)} (status={status})")

    print(f"\n  Result: {ok} deleted, {fail} failed")


# ═════════════════════════════════════════════════════════════════════════════
# STEP 4: Upload practitioners to both locations
# ═════════════════════════════════════════════════════════════════════════════

def build_practitioner_payload(pract: dict, location_id: int) -> dict:
    """Build API payload for creating a practitioner.
    
    API fields (discovered from testing):
      - location_id: int (required)
      - name: {"en": "..."} (required)
      - description: {"en": "..."}
      - speciality: {"en": "..."} (NOT a plain string!)
      - sex: "male" | "female"
      - languages: ["ENGLISH", ...]
      - years_of_experience: int | null
      - is_visible_to_ai: bool
      - treats_children: bool | null  (NOTE: 's' in treats)
      - treat_children_age is NOT an API field
      - primary/secondary/additional qualifications are NOT separate fields;
        API has qualifications_i18n (one combined field)
    """
    payload = {
        "location_id": location_id,
        "name": {"en": pract.get("name", get_name_en(pract))},
        "is_visible_to_ai": pract.get("is_visible_to_ai", True),
    }

    # Description
    desc_en = (pract.get("description_i18n") or {}).get("en")
    if desc_en:
        payload["description"] = {"en": desc_en}

    # Speciality (API expects i18n dict)
    spec = pract.get("speciality")
    if spec:
        payload["speciality"] = {"en": spec}

    # Sex
    if pract.get("sex"):
        payload["sex"] = pract["sex"]

    # Languages
    if pract.get("languages"):
        payload["languages"] = pract["languages"]

    # Years of experience
    if pract.get("years_of_experience") is not None:
        payload["years_of_experience"] = pract["years_of_experience"]

    # Treat children
    if pract.get("treat_children") is not None:
        payload["treats_children"] = pract["treat_children"]

    # Qualifications - combine into one string
    quals = []
    for field in ["primary_qualifications", "secondary_qualifications", "additional_qualifications"]:
        val = pract.get(field)
        if val:
            quals.append(val)
    if quals:
        combined = "\n\n".join(quals)
        payload["qualifications"] = {"en": combined}

    return payload


def do_step4(execute: bool):
    print("\n" + "=" * 70)
    print("  STEP 4: Upload practitioners to both locations")
    print("=" * 70)

    local_practs = load_local("practitioners.json")
    pract_class = classify_practitioners(local_practs)

    # Which practitioners go where
    practs_for_17 = pract_class["jumeirah_only"] + pract_class["both"]
    practs_for_18 = pract_class["szr_only"] + pract_class["both"]

    print(f"\n  Practitioners for Location 17 (Jumeirah): {len(practs_for_17)}")
    print(f"    - jumeirah only: {len(pract_class['jumeirah_only'])}")
    print(f"    - both/empty:    {len(pract_class['both'])}")
    print(f"  Practitioners for Location 18 (SZR):      {len(practs_for_18)}")
    print(f"    - szr only:      {len(pract_class['szr_only'])}")
    print(f"    - both/empty:    {len(pract_class['both'])}")

    for loc_id, loc_name, practs_list in [
        (LOCATION_JUMEIRAH, "Jumeirah", practs_for_17),
        (LOCATION_SZR, "SZR", practs_for_18),
    ]:
        print(f"\n  {'─'*50}")
        print(f"  Location {loc_id} ({loc_name}): {len(practs_list)} practitioners")
        print(f"  {'─'*50}")

        # Check existing
        api_practs = fetch_api_practitioners(loc_id)
        existing = {normalize(get_name_en(p)): p for p in api_practs}

        to_create = []
        already = []
        for p in practs_list:
            name = normalize(p.get("name", get_name_en(p)))
            if name in existing:
                already.append(p)
            else:
                to_create.append(p)

        print(f"    Already exists: {len(already)}")
        print(f"    To create:      {len(to_create)}")

        for p in to_create:
            branches = p.get("branches", [])
            print(f"      + {p.get('name', get_name_en(p)):<40} branches={branches}")

        if not execute or not to_create:
            continue

        ok, fail = 0, 0
        for p in to_create:
            payload = build_practitioner_payload(p, loc_id)
            try:
                result = api_post(f"/locations/{loc_id}/practitioners", payload)
                ok += 1
                print(f"      ✓ {p.get('name', '?')} (api_id={result['id']})")
            except Exception as e:
                fail += 1
                print(f"      ✗ {p.get('name', '?')}: {e}")

        print(f"    Result: {ok} created, {fail} failed")

    if not execute:
        total = len(practs_for_17) + len(practs_for_18)
        print(f"\n  [DRY RUN] Add --execute to create practitioners")


# ═════════════════════════════════════════════════════════════════════════════
# STEP 5: Link service-practitioners
# ═════════════════════════════════════════════════════════════════════════════

def do_step5(execute: bool):
    print("\n" + "=" * 70)
    print("  STEP 5: Link service-practitioners on both locations")
    print("=" * 70)

    local_svcs = load_local("services.json")
    local_practs = load_local("practitioners.json")
    local_sp = load_local("service_practitioners.json")
    local_cats = load_local("categories.json")

    svc_class = classify_services(local_svcs)
    pract_class = classify_practitioners(local_practs)

    # Build local ID → info mappings
    local_svc_by_id = {s["id"]: s for s in local_svcs}
    local_pract_id_to_name = {p["id"]: normalize(p.get("name", get_name_en(p))) for p in local_practs}
    local_catid_to_name = build_local_catid_to_name(local_cats)

    # Build local ID → branches
    local_svc_id_to_branches = {s["id"]: set(s.get("branches", [])) for s in local_svcs}
    local_pract_id_to_branches = {}
    for p in local_practs:
        branches = set(b.lower() for b in p.get("branches", []))
        local_pract_id_to_branches[p["id"]] = branches

    # For each location, determine which service-practitioner links apply
    for loc_id, loc_name in [(LOCATION_JUMEIRAH, "Jumeirah"), (LOCATION_SZR, "SZR")]:
        print(f"\n  {'─'*50}")
        print(f"  Location {loc_id} ({loc_name})")
        print(f"  {'─'*50}")

        # Determine which branch names map to this location
        if loc_id == LOCATION_JUMEIRAH:
            loc_branch = "jumeirah"
        else:
            loc_branch = "szr"  # services use "szr"

        # Get API data for this location
        api_svcs = fetch_api_services(loc_id)
        api_practs = fetch_api_practitioners(loc_id)
        api_catid_to_name = build_api_catid_to_name(loc_id)

        # Build API (name, category) → ID mapping for services (handles duplicates!)
        api_svc_key_to_id = {}
        for s in api_svcs:
            cat_name = api_catid_to_name.get(s.get("category_id"), "")
            key = svc_key(get_name_en(s), cat_name)
            api_svc_key_to_id[key] = s["id"]

        # Build API name → ID for practitioners (no duplicates expected)
        api_pract_name_to_id = {normalize(get_name_en(p)): p["id"] for p in api_practs}

        print(f"    API services:      {len(api_svcs)}")
        print(f"    API practitioners: {len(api_practs)}")

        # Get existing links
        existing_links = set()
        for p in api_practs:
            for link in p.get("service_links", []):
                existing_links.add((link["service_id"], p["id"]))

        # Filter service-practitioner links for this location
        links_for_location = []
        skipped_svc = 0
        skipped_pract = 0
        skipped_no_api_svc = 0
        skipped_no_api_pract = 0

        for sp in local_sp:
            local_svc_id = sp["service_id"]
            local_pract_id = sp["practitioner_id"]

            # Check if service belongs to this location
            svc_branches = local_svc_id_to_branches.get(local_svc_id, set())

            if loc_branch == "szr":
                if "szr" not in svc_branches:
                    skipped_svc += 1
                    continue
            else:  # jumeirah
                if "jumeirah" not in svc_branches:
                    skipped_svc += 1
                    continue

            # Check if practitioner belongs to this location
            pract_branches = local_pract_id_to_branches.get(local_pract_id, set())
            pract_name = local_pract_id_to_name.get(local_pract_id)

            # Practitioner with empty branches → goes to both locations
            if pract_branches:
                if loc_id == LOCATION_SZR:
                    if "szr" not in pract_branches and "szr" not in pract_branches:
                        skipped_pract += 1
                        continue
                else:
                    if "jumeirah" not in pract_branches:
                        skipped_pract += 1
                        continue

            # Map service to API ID using (name, category) key
            local_svc = local_svc_by_id.get(local_svc_id)
            if not local_svc:
                skipped_no_api_svc += 1
                continue
            local_cat_name = local_catid_to_name.get(local_svc.get("category_id"), "")
            svc_k = svc_key(get_name_en(local_svc), local_cat_name)
            api_svc_id = api_svc_key_to_id.get(svc_k)

            api_pract_id = api_pract_name_to_id.get(pract_name)

            if not api_svc_id:
                skipped_no_api_svc += 1
                continue
            if not api_pract_id:
                skipped_no_api_pract += 1
                continue

            # Skip if already linked
            if (api_svc_id, api_pract_id) in existing_links:
                continue

            links_for_location.append({
                "api_service_id": api_svc_id,
                "api_practitioner_id": api_pract_id,
                "service_name": normalize(get_name_en(local_svc)),
                "practitioner_name": pract_name,
            })

        print(f"    Links to create:           {len(links_for_location)}")
        print(f"    Skipped (svc wrong loc):   {skipped_svc}")
        print(f"    Skipped (pract wrong loc): {skipped_pract}")
        print(f"    Skipped (no API service):  {skipped_no_api_svc}")
        print(f"    Skipped (no API pract):    {skipped_no_api_pract}")
        print(f"    Already linked:            {len(existing_links)}")

        if not links_for_location:
            print("    Nothing to create.")
            continue

        # Show sample
        for link in links_for_location[:10]:
            print(f"      + svc={link['api_service_id']} ↔ pract={link['api_practitioner_id']}")
        if len(links_for_location) > 10:
            print(f"      ... and {len(links_for_location) - 10} more")

        if not execute:
            continue

        print(f"    Creating {len(links_for_location)} links...")
        ok, fail = 0, 0
        for link in links_for_location:
            try:
                api_post(
                    f"/locations/{loc_id}/practitioners/{link['api_practitioner_id']}/services",
                    {"service_id": link["api_service_id"]},
                )
                ok += 1
                if ok % 50 == 0:
                    print(f"      ... created {ok} links")
            except Exception as e:
                fail += 1
                if fail <= 5:
                    print(f"      ✗ svc={link['api_service_id']} pract={link['api_practitioner_id']}: {e}")

        print(f"    Result: {ok} created, {fail} failed")

    if not execute:
        print(f"\n  [DRY RUN] Add --execute to create service-practitioner links")


# ═════════════════════════════════════════════════════════════════════════════
# STEP 6: Set price_type="fixed" for all services on both locations
# ═════════════════════════════════════════════════════════════════════════════

def do_step6(execute: bool):
    print("\n" + "=" * 70)
    print("  STEP 6: Set price_type='fixed' for all services")
    print("=" * 70)

    for loc_id, loc_name in [(LOCATION_JUMEIRAH, "Jumeirah"), (LOCATION_SZR, "SZR")]:
        api_svcs = fetch_api_services(loc_id)

        # Find services that are NOT "fixed"
        to_fix = [s for s in api_svcs if s.get("price_type") != "fixed"]
        already = len(api_svcs) - len(to_fix)

        print(f"\n  ──────────────────────────────────────────────────")
        print(f"  Location {loc_id} ({loc_name})")
        print(f"  ──────────────────────────────────────────────────")
        print(f"    Total services:       {len(api_svcs)}")
        print(f"    Already fixed:        {already}")
        print(f"    To update:            {len(to_fix)}")

        if not to_fix:
            print(f"    All services already have price_type='fixed'. Nothing to do.")
            continue

        for svc in to_fix[:5]:
            print(f"      {get_name_en(svc)[:45]:45} price_type={svc.get('price_type', '???')}")
        if len(to_fix) > 5:
            print(f"      ... and {len(to_fix) - 5} more")

        if not execute:
            print(f"\n    [DRY RUN] Add --execute to update {len(to_fix)} services")
            continue

        print(f"\n    Updating {len(to_fix)} services...")
        ok, fail = 0, 0
        for svc in to_fix:
            svc_id = svc["id"]
            payload = {"price_type": "fixed"}
            try:
                api_put(f"/locations/{loc_id}/services/{svc_id}", payload)
                ok += 1
                if ok % 50 == 0:
                    print(f"      ... updated {ok} services")
            except Exception as e:
                fail += 1
                print(f"      ✗ {get_name_en(svc)[:40]}: {e}")

        print(f"    Result: {ok} updated, {fail} failed")


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Fix data distribution across locations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/fix_locations.py --analyze
  python scripts/fix_locations.py --step1                # Dry run
  python scripts/fix_locations.py --step1 --execute      # Execute
  python scripts/fix_locations.py --step2 --execute
  python scripts/fix_locations.py --step3 --execute
  python scripts/fix_locations.py --step4 --execute
  python scripts/fix_locations.py --step5 --execute
        """,
    )
    parser.add_argument("--analyze", action="store_true", help="Show analysis of current vs expected state")
    parser.add_argument("--step1", action="store_true", help="Step 1: Upload categories to Location 18")
    parser.add_argument("--step2", action="store_true", help="Step 2: Upload services to Location 18")
    parser.add_argument("--step3", action="store_true", help="Step 3: Delete szr-only services from Location 17")
    parser.add_argument("--step4", action="store_true", help="Step 4: Upload practitioners to both locations")
    parser.add_argument("--step5", action="store_true", help="Step 5: Link service-practitioners on both locations")
    parser.add_argument("--step6", action="store_true", help="Step 6: Set price_type='fixed' for all services")
    parser.add_argument("--execute", action="store_true", help="Actually execute (default is dry-run)")

    args = parser.parse_args()

    if not any([args.analyze, args.step1, args.step2, args.step3, args.step4, args.step5, args.step6]):
        parser.print_help()
        return

    if args.analyze:
        do_analyze()

    if args.step1:
        do_step1(execute=args.execute)

    if args.step2:
        do_step2(execute=args.execute)

    if args.step3:
        do_step3(execute=args.execute)

    if args.step4:
        do_step4(execute=args.execute)

    if args.step5:
        do_step5(execute=args.execute)

    if args.step6:
        do_step6(execute=args.execute)


if __name__ == "__main__":
    main()
