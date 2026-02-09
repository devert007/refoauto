#!/usr/bin/env python3
"""
Tests for validating API state after upload.

These tests actually call the DialogGauge API to verify that:
- Practitioners have the correct number of service links
- No phantom services appear on wrong practitioners
- Service names match between local data and API

Usage:
    pytest tests/test_api_validation.py -v                    # Run all API tests
    pytest tests/test_api_validation.py -v -k "test_specific" # Run specific
    pytest tests/test_api_validation.py -v --location=18      # Test Location 18

NOTE: Requires active dg_session in config/.dg_session.json
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

import pytest
import requests

# ─── Project paths ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DATA_OUTPUT = PROJECT_ROOT / "data" / "output"
CONFIG_DIR = PROJECT_ROOT / "config"

API_BASE = "https://dialoggauge.yma.health/api"
LOCATION_JUMEIRAH = 17
LOCATION_SZR = 18


# ─── API Helpers ──────────────────────────────────────────────────────────────

def load_session() -> str:
    session_file = CONFIG_DIR / ".dg_session.json"
    if not session_file.exists():
        pytest.skip("No API session found (config/.dg_session.json missing)")
    with open(session_file) as f:
        return json.load(f)["dg_session"]


def api_headers() -> dict:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Cookie": f"dg_session={load_session()}",
    }


def api_get(endpoint: str) -> list:
    r = requests.get(f"{API_BASE}{endpoint}", headers=api_headers())
    if r.status_code == 401:
        pytest.skip("API session expired (401 Unauthorized)")
    r.raise_for_status()
    return r.json()


def normalize(name: str) -> str:
    """Normalize name (weak — same as fix_locations.py)."""
    if not name:
        return ""
    name = name.lower().strip()
    name = re.sub(r"\s+", " ", name)
    return name


def normalize_strong(name: str) -> str:
    """Normalize name (strong — same as sync_with_api.py, strips special chars)."""
    if not name:
        return ""
    name = name.lower().strip()
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'[^\w\s]', '', name)
    return name


def get_name_en(item: dict) -> str:
    return (item.get("name_i18n") or {}).get("en", "") or item.get("name", "")


# ─── Local data helpers ───────────────────────────────────────────────────────

def load_local(filename: str) -> list:
    with open(DATA_OUTPUT / filename, encoding="utf-8") as f:
        return json.load(f)


def get_expected_links_per_practitioner(branch: str) -> dict:
    """
    Calculate expected service count per practitioner for a given branch.
    Returns dict: practitioner_name (normalized) → expected_count
    """
    services = load_local("services.json")
    practitioners = load_local("practitioners.json")
    sp = load_local("service_practitioners.json")

    svc_by_id = {s["id"]: s for s in services}
    pract_by_id = {p["id"]: p for p in practitioners}

    result = {}  # normalized_name → count

    for link in sp:
        svc = svc_by_id.get(link["service_id"])
        pract = pract_by_id.get(link["practitioner_id"])
        if not svc or not pract:
            continue

        # Service must belong to this branch
        svc_branches = set(svc.get("branches", []))
        if branch not in svc_branches:
            continue

        # Practitioner must belong to this branch (empty = both)
        pract_branches = set(b.lower() for b in pract.get("branches", []))
        if pract_branches and branch not in pract_branches:
            continue

        name = normalize(pract.get("name", ""))
        result[name] = result.get(name, 0) + 1

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def api_practitioners_szr():
    """Fetch practitioners from SZR API."""
    return api_get(f"/locations/{LOCATION_SZR}/practitioners?include_archived=true")


@pytest.fixture(scope="module")
def api_practitioners_jum():
    """Fetch practitioners from Jumeirah API."""
    return api_get(f"/locations/{LOCATION_JUMEIRAH}/practitioners?include_archived=true")


@pytest.fixture(scope="module")
def api_services_szr():
    """Fetch services from SZR API."""
    return api_get(f"/locations/{LOCATION_SZR}/services?include_archived=true")


@pytest.fixture(scope="module")
def api_categories_szr():
    """Fetch categories from SZR API."""
    return api_get(f"/locations/{LOCATION_SZR}/categories?flat=true&include_archived=true")


@pytest.fixture(scope="module")
def expected_szr_links():
    """Expected link counts per practitioner for SZR."""
    return get_expected_links_per_practitioner("szr")


@pytest.fixture(scope="module")
def local_services():
    return load_local("services.json")


@pytest.fixture(scope="module")
def local_practitioners():
    return load_local("practitioners.json")


@pytest.fixture(scope="module")
def local_categories():
    return load_local("categories.json")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. PRACTITIONER SERVICE COUNTS (SZR)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSzrPractitionerServiceCounts:
    """
    Validate that each practitioner on SZR API has the expected number
    of service links. Catches bugs where links are dropped or misassigned.
    """

    def _get_api_link_counts(self, api_practitioners: list) -> dict:
        """Get service link count per practitioner from API."""
        result = {}
        for p in api_practitioners:
            name = normalize(get_name_en(p))
            service_links = p.get("service_links", [])
            result[name] = len(service_links)
        return result

    def test_cherry_lou_abuyan_has_18_services(self, api_practitioners_szr):
        """
        Cherry Lou Abuyan should have 18 services on SZR.
        Known bug: She appeared with 0 services despite having 18 links.
        """
        counts = self._get_api_link_counts(api_practitioners_szr)
        actual = counts.get(normalize("Cherry Lou Abuyan"), -1)
        if actual == -1:
            pytest.fail("Cherry Lou Abuyan NOT FOUND on SZR API")
        assert actual == 18, (
            f"Cherry Lou Abuyan: expected 18 services on SZR, got {actual}"
        )

    def test_dr_shamoun_has_0_services(self, api_practitioners_szr):
        """
        Dr. John Milam Shamoun should have 0 services on SZR.
        Known bug: He appeared with 7 services despite having 0 links.
        """
        counts = self._get_api_link_counts(api_practitioners_szr)
        actual = counts.get(normalize("Dr. John Milam Shamoun"), -1)
        if actual == -1:
            return  # Not found on API — that's also acceptable
        assert actual == 0, (
            f"Dr. John Milam Shamoun: expected 0 services on SZR, got {actual}. "
            f"These were likely assigned by mistake."
        )

    def test_dr_kinan_bonni_has_49_services(self, api_practitioners_szr):
        """
        Dr. Kinan Bonni should have 49 services on SZR.
        Known bug: Only 9 out of 49 were linked.
        """
        counts = self._get_api_link_counts(api_practitioners_szr)
        actual = counts.get(normalize("Dr. Kinan Bonni"), -1)
        if actual == -1:
            pytest.fail("Dr. Kinan Bonni NOT FOUND on SZR API")
        assert actual == 49, (
            f"Dr. Kinan Bonni: expected 49 services on SZR, got {actual}"
        )

    def test_all_practitioners_expected_counts(self, api_practitioners_szr, expected_szr_links):
        """
        Compare API service link counts with expected (from local data).
        Reports all practitioners with mismatched counts.
        """
        api_counts = self._get_api_link_counts(api_practitioners_szr)

        mismatches = []
        for name, expected in expected_szr_links.items():
            actual = api_counts.get(name, 0)
            if actual != expected:
                mismatches.append((name, expected, actual))

        # Also check for practitioners with services they shouldn't have
        for name, actual in api_counts.items():
            expected = expected_szr_links.get(name, 0)
            if actual > 0 and expected == 0:
                mismatches.append((name, 0, actual))

        if mismatches:
            lines = []
            for name, exp, act in sorted(mismatches, key=lambda x: abs(x[1]-x[2]), reverse=True):
                diff = act - exp
                sign = "+" if diff > 0 else ""
                lines.append(f"  {name:<40} expected={exp:>3} actual={act:>3} ({sign}{diff})")
            report = "\n".join(lines)
            pytest.fail(
                f"{len(mismatches)} practitioners have wrong service counts on SZR:\n{report}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SERVICE NAME MATCHING
# ═══════════════════════════════════════════════════════════════════════════════

class TestServiceNameMatching:
    """
    Verify that local service names match API service names.
    Catches bugs with special characters (em-dash, etc.) breaking matching.
    """

    def test_szr_services_all_on_api(self, api_services_szr, local_services, api_categories_szr, local_categories):
        """All local SZR services should exist on the SZR API (by name+category)."""
        # Build API category ID → name mapping
        api_cat_name = {c["id"]: normalize(get_name_en(c)) for c in api_categories_szr}
        local_cat_name = {c["id"]: normalize(get_name_en(c)) for c in local_categories}

        # Build API service keys: (name, category_name)
        api_keys = set()
        for s in api_services_szr:
            cat = api_cat_name.get(s.get("category_id"), "")
            api_keys.add((normalize(get_name_en(s)), cat))

        # Check local SZR services
        missing = []
        for s in local_services:
            branches = set(s.get("branches", []))
            if "szr" not in branches:
                continue

            cat = local_cat_name.get(s.get("category_id"), "")
            key = (normalize(get_name_en(s)), cat)

            if key not in api_keys:
                missing.append((s["id"], get_name_en(s), cat))

        if missing:
            lines = [f"  ID={sid}: \"{name}\" (cat: {cat})" for sid, name, cat in missing[:30]]
            pytest.fail(
                f"{len(missing)} local SZR services NOT found on SZR API:\n" +
                "\n".join(lines)
            )

    def test_special_chars_matching(self, api_services_szr, local_services):
        """
        Test that services with special characters (em-dash, etc.)
        can be matched between local and API using STRONG normalization.
        """
        # Build API names (strong normalized)
        api_names_strong = set()
        for s in api_services_szr:
            api_names_strong.add(normalize_strong(get_name_en(s)))

        # Check local SZR services with special chars
        special_char_services = []
        for s in local_services:
            if "szr" not in set(s.get("branches", [])):
                continue
            name = get_name_en(s)
            if re.search(r'[\u2013\u2014\u2015\u2212]', name):
                strong = normalize_strong(name)
                found = strong in api_names_strong
                special_char_services.append((s["id"], name, strong, found))

        if special_char_services:
            not_found = [(sid, name) for sid, name, strong, found in special_char_services if not found]
            print(f"\n  Services with special chars: {len(special_char_services)}")
            print(f"  Found on API (strong match): {len(special_char_services) - len(not_found)}")
            print(f"  NOT found: {len(not_found)}")
            for sid, name in not_found[:10]:
                print(f"    ID={sid}: {name}")

            if not_found:
                pytest.fail(
                    f"{len(not_found)} services with special chars NOT found on API "
                    f"(em-dash/en-dash mismatch?)"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. PRACTITIONERS EXIST ON API
# ═══════════════════════════════════════════════════════════════════════════════

class TestPractitionersOnApi:
    """Verify all expected practitioners exist on the correct API locations."""

    def test_szr_practitioners_all_on_api(self, api_practitioners_szr, local_practitioners):
        """All local practitioners with szr branch should be on SZR API."""
        api_names = {normalize(get_name_en(p)) for p in api_practitioners_szr}

        missing = []
        for p in local_practitioners:
            branches = set(b.lower() for b in p.get("branches", []))
            # szr practitioners or empty branches (both locations)
            if "szr" in branches or not branches:
                name = normalize(p.get("name", ""))
                if name not in api_names:
                    missing.append((p["id"], p.get("name", ""), list(branches)))

        if missing:
            lines = [f"  ID={pid}: \"{name}\" branches={b}" for pid, name, b in missing]
            pytest.fail(
                f"{len(missing)} practitioners NOT found on SZR API:\n" +
                "\n".join(lines)
            )

    def test_no_extra_practitioners_on_szr(self, api_practitioners_szr, local_practitioners):
        """
        Flag practitioners on SZR API that are NOT in local data.
        These may be manually added or incorrectly matched.
        """
        local_names = set()
        for p in local_practitioners:
            branches = set(b.lower() for b in p.get("branches", []))
            if "szr" in branches or not branches:
                local_names.add(normalize(p.get("name", "")))

        extra = []
        for p in api_practitioners_szr:
            name = normalize(get_name_en(p))
            if name not in local_names:
                extra.append((p["id"], get_name_en(p)))

        if extra:
            print(f"\n  WARNING: {len(extra)} practitioners on SZR API NOT in local data:")
            for pid, name in extra:
                print(f"    API ID={pid}: {name}")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. DETAILED LINK INSPECTION
# ═══════════════════════════════════════════════════════════════════════════════

class TestDetailedLinkInspection:
    """
    Detailed inspection of specific practitioners' service links.
    Helps debug exactly which services are linked/missing.
    """

    def test_cherry_lou_service_names(self, api_practitioners_szr, local_services):
        """Print Cherry Lou's actual services on API for debugging."""
        for p in api_practitioners_szr:
            if "cherry" in get_name_en(p).lower() and "abuyan" in get_name_en(p).lower():
                links = p.get("service_links", [])
                print(f"\n  Cherry Lou Abuyan (API ID={p['id']}) on SZR:")
                print(f"  Total service links: {len(links)}")
                for link in links[:20]:
                    print(f"    service_id={link['service_id']}")
                return

        # Check if she's even on the API
        all_names = [get_name_en(p) for p in api_practitioners_szr]
        print(f"\n  Cherry Lou Abuyan NOT found on SZR API!")
        print(f"  All practitioners on SZR ({len(all_names)}):")
        for name in sorted(all_names):
            print(f"    {name}")

    def test_kinan_service_names(self, api_practitioners_szr, api_services_szr):
        """Print Kinan Bonni's actual services on API for debugging."""
        api_svc_by_id = {s["id"]: s for s in api_services_szr}

        for p in api_practitioners_szr:
            if "kinan" in get_name_en(p).lower():
                links = p.get("service_links", [])
                print(f"\n  Dr. Kinan Bonni (API ID={p['id']}) on SZR:")
                print(f"  Total service links: {len(links)}")
                for link in links[:20]:
                    svc = api_svc_by_id.get(link['service_id'], {})
                    svc_name = get_name_en(svc) or "???"
                    print(f"    service_id={link['service_id']}: {svc_name}")
                if len(links) > 20:
                    print(f"    ... and {len(links) - 20} more")
                return

    def test_shamoun_service_names(self, api_practitioners_szr, api_services_szr):
        """Print Shamoun's actual services on API to detect phantom links."""
        api_svc_by_id = {s["id"]: s for s in api_services_szr}

        for p in api_practitioners_szr:
            if "shamoun" in get_name_en(p).lower():
                links = p.get("service_links", [])
                if links:
                    print(f"\n  !! Dr. Shamoun (API ID={p['id']}) has {len(links)} phantom services:")
                    for link in links:
                        svc = api_svc_by_id.get(link['service_id'], {})
                        svc_name = get_name_en(svc) or "???"
                        print(f"    service_id={link['service_id']}: {svc_name}")
                else:
                    print(f"\n  Dr. Shamoun (API ID={p['id']}): 0 services (correct)")
                return
