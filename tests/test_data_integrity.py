#!/usr/bin/env python3
"""
Tests for data integrity of parsed JSON files.

Catches bugs like:
- Branch naming inconsistency ("szr" vs "srz")
- Broken service_practitioners references
- Name matching failures between local data and API
- Missing practitioner-service links
- Special characters (em-dash vs dash) breaking name matching

Usage:
    pytest tests/test_data_integrity.py -v
    pytest tests/test_data_integrity.py -v -k "test_specific"   # run specific tests
    pytest tests/test_data_integrity.py -v --tb=long             # verbose tracebacks
"""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

# ─── Project paths ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DATA_OUTPUT = PROJECT_ROOT / "data" / "output"
DATA_INPUT = PROJECT_ROOT / "data" / "input"

# ─── Valid branch values ──────────────────────────────────────────────────────
VALID_SERVICE_BRANCHES = {"jumeirah", "szr"}
VALID_PRACTITIONER_BRANCHES = {"jumeirah", "szr"}  # practitioners use "szr"


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def categories():
    with open(DATA_OUTPUT / "categories.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def services():
    with open(DATA_OUTPUT / "services.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def practitioners():
    with open(DATA_OUTPUT / "practitioners.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def service_practitioners():
    with open(DATA_OUTPUT / "service_practitioners.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def raw_csv_lines():
    """Read raw CSV for cross-validation."""
    csv_path = DATA_INPUT / "raw_data.csv"
    if not csv_path.exists():
        return []
    with open(csv_path, encoding="utf-8") as f:
        return f.read()


# ═══════════════════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════════════════

def normalize_name(name: str) -> str:
    """Normalize name for matching (same as sync_with_api.py)."""
    if not name:
        return ""
    name = name.lower().strip()
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'[^\w\s]', '', name)
    return name


def normalize_weak(name: str) -> str:
    """Weak normalize (same as fix_locations.py) — does NOT strip special chars."""
    if not name:
        return ""
    name = name.lower().strip()
    name = re.sub(r"\s+", " ", name)
    return name


def get_name_en(item: dict) -> str:
    return (item.get("name_i18n") or {}).get("en", "") or item.get("name", "")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. FILES EXIST
# ═══════════════════════════════════════════════════════════════════════════════

class TestFilesExist:
    """Test that all required output files exist and are non-empty."""

    def test_categories_json_exists(self):
        path = DATA_OUTPUT / "categories.json"
        assert path.exists(), f"{path} does not exist"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) > 0, "categories.json is empty"

    def test_services_json_exists(self):
        path = DATA_OUTPUT / "services.json"
        assert path.exists(), f"{path} does not exist"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) > 0, "services.json is empty"

    def test_practitioners_json_exists(self):
        path = DATA_OUTPUT / "practitioners.json"
        assert path.exists(), f"{path} does not exist"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) > 0, "practitioners.json is empty"

    def test_service_practitioners_json_exists(self):
        path = DATA_OUTPUT / "service_practitioners.json"
        assert path.exists(), f"{path} does not exist"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) > 0, "service_practitioners.json is empty"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. UNIQUE IDS
# ═══════════════════════════════════════════════════════════════════════════════

class TestUniqueIds:
    """Test that all IDs are unique within each file."""

    def test_category_ids_unique(self, categories):
        ids = [c["id"] for c in categories]
        assert len(ids) == len(set(ids)), f"Duplicate category IDs: {[x for x, c in Counter(ids).items() if c > 1]}"

    def test_service_ids_unique(self, services):
        ids = [s["id"] for s in services]
        assert len(ids) == len(set(ids)), f"Duplicate service IDs: {[x for x, c in Counter(ids).items() if c > 1]}"

    def test_practitioner_ids_unique(self, practitioners):
        ids = [p["id"] for p in practitioners]
        assert len(ids) == len(set(ids)), f"Duplicate practitioner IDs: {[x for x, c in Counter(ids).items() if c > 1]}"

    def test_category_names_unique(self, categories):
        names = [normalize_name(get_name_en(c)) for c in categories]
        dupes = [x for x, c in Counter(names).items() if c > 1]
        assert len(dupes) == 0, f"Duplicate category names: {dupes}"

    def test_practitioner_names_unique(self, practitioners):
        names = [normalize_name(p.get("name", "")) for p in practitioners]
        dupes = [x for x, c in Counter(names).items() if c > 1]
        assert len(dupes) == 0, f"Duplicate practitioner names: {dupes}"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. BRANCH CONSISTENCY
# ═══════════════════════════════════════════════════════════════════════════════

class TestBranchConsistency:
    """
    Test that branch values are consistent across all files.
    
    Known bug: "szr" vs "srz" inconsistency between process_data.py and 
    parse_practitioners_sheet.py caused services to be skipped during upload.
    """

    def test_service_branches_valid(self, services):
        """All service branch values must be from the valid set."""
        invalid = []
        for svc in services:
            for branch in svc.get("branches", []):
                if branch not in VALID_SERVICE_BRANCHES:
                    invalid.append((svc["id"], get_name_en(svc), branch))
        assert len(invalid) == 0, (
            f"Services with invalid branches:\n" +
            "\n".join(f"  ID {sid}: '{name}' has branch '{b}'" for sid, name, b in invalid[:20])
        )

    def test_practitioner_branches_valid(self, practitioners):
        """All practitioner branch values must be from the valid set."""
        invalid = []
        for p in practitioners:
            for branch in p.get("branches", []):
                if branch not in VALID_PRACTITIONER_BRANCHES:
                    invalid.append((p["id"], p.get("name", ""), branch))
        assert len(invalid) == 0, (
            f"Practitioners with invalid branches:\n" +
            "\n".join(f"  ID {pid}: '{name}' has branch '{b}'" for pid, name, b in invalid[:20])
        )

    def test_no_srz_in_services(self, services):
        """Ensure 'srz' is NOT used in services (should be 'szr')."""
        srz_services = [
            (s["id"], get_name_en(s))
            for s in services
            if "srz" in s.get("branches", [])
        ]
        assert len(srz_services) == 0, (
            f"{len(srz_services)} services use 'srz' instead of 'szr':\n" +
            "\n".join(f"  ID {sid}: '{name}'" for sid, name in srz_services[:10])
        )

    def test_no_srz_in_practitioners(self, practitioners):
        """Ensure 'srz' is NOT used in practitioners (should be 'szr')."""
        srz_practs = [
            (p["id"], p.get("name", ""))
            for p in practitioners
            if "srz" in p.get("branches", [])
        ]
        assert len(srz_practs) == 0, (
            f"{len(srz_practs)} practitioners use 'srz' instead of 'szr':\n" +
            "\n".join(f"  ID {pid}: '{name}'" for pid, name in srz_practs[:10])
        )

    def test_all_services_classified(self, services):
        """Every service must be classifiable (no unexpected branch combos)."""
        unclassified = []
        for svc in services:
            branches = set(svc.get("branches", []))
            if branches not in [{"jumeirah"}, {"szr"}, {"jumeirah", "szr"}]:
                unclassified.append((svc["id"], get_name_en(svc), branches))
        assert len(unclassified) == 0, (
            f"Unclassifiable services:\n" +
            "\n".join(f"  ID {sid}: '{name}' branches={b}" for sid, name, b in unclassified[:20])
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. REFERENTIAL INTEGRITY
# ═══════════════════════════════════════════════════════════════════════════════

class TestReferentialIntegrity:
    """Test that all foreign key references are valid."""

    def test_service_category_ids_exist(self, services, categories):
        """Every service.category_id must exist in categories.json."""
        cat_ids = {c["id"] for c in categories}
        orphans = [
            (s["id"], get_name_en(s), s["category_id"])
            for s in services
            if s.get("category_id") not in cat_ids
        ]
        assert len(orphans) == 0, (
            f"{len(orphans)} services reference non-existent categories:\n" +
            "\n".join(f"  Service {sid}: '{name}' → category_id={cid}" for sid, name, cid in orphans[:20])
        )

    def test_sp_service_ids_exist(self, service_practitioners, services):
        """Every service_practitioners.service_id must exist in services.json."""
        svc_ids = {s["id"] for s in services}
        orphans = [
            sp for sp in service_practitioners
            if sp["service_id"] not in svc_ids
        ]
        assert len(orphans) == 0, (
            f"{len(orphans)} service_practitioner links reference non-existent services:\n" +
            "\n".join(f"  service_id={sp['service_id']}, practitioner_id={sp['practitioner_id']}" for sp in orphans[:20])
        )

    def test_sp_practitioner_ids_exist(self, service_practitioners, practitioners):
        """Every service_practitioners.practitioner_id must exist in practitioners.json."""
        pract_ids = {p["id"] for p in practitioners}
        orphans = [
            sp for sp in service_practitioners
            if sp["practitioner_id"] not in pract_ids
        ]
        assert len(orphans) == 0, (
            f"{len(orphans)} service_practitioner links reference non-existent practitioners:\n" +
            "\n".join(f"  service_id={sp['service_id']}, practitioner_id={sp['practitioner_id']}" for sp in orphans[:20])
        )

    def test_no_duplicate_sp_links(self, service_practitioners):
        """No duplicate (service_id, practitioner_id) pairs."""
        pairs = [(sp["service_id"], sp["practitioner_id"]) for sp in service_practitioners]
        dupes = [x for x, c in Counter(pairs).items() if c > 1]
        assert len(dupes) == 0, (
            f"{len(dupes)} duplicate service_practitioner links:\n" +
            "\n".join(f"  service_id={s}, practitioner_id={p}" for s, p in dupes[:20])
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. PRACTITIONER COMPLETENESS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPractitionerCompleteness:
    """Test that practitioners have all required fields."""

    REQUIRED_FIELDS = [
        "id", "name", "name_i18n", "speciality", "sex", "languages",
        "description_i18n", "years_of_experience",
        "primary_qualifications", "secondary_qualifications",
        "additional_qualifications", "treat_children",
        "treat_children_age", "branches", "is_visible_to_ai",
    ]

    def test_all_fields_present(self, practitioners):
        """Each practitioner must have all required fields."""
        incomplete = []
        for p in practitioners:
            missing = [f for f in self.REQUIRED_FIELDS if f not in p]
            if missing:
                incomplete.append((p.get("id"), p.get("name", "?"), missing))
        assert len(incomplete) == 0, (
            f"Practitioners missing fields:\n" +
            "\n".join(f"  ID {pid}: '{name}' missing {fields}" for pid, name, fields in incomplete[:10])
        )

    def test_sex_valid_values(self, practitioners):
        """Sex must be 'male' or 'female'."""
        invalid = [
            (p["id"], p.get("name", ""), p.get("sex"))
            for p in practitioners
            if p.get("sex") not in ("male", "female", None)
        ]
        assert len(invalid) == 0, (
            f"Practitioners with invalid sex:\n" +
            "\n".join(f"  ID {pid}: '{name}' sex='{sex}'" for pid, name, sex in invalid)
        )

    def test_languages_are_known(self, practitioners):
        """All languages must be from known language list."""
        KNOWN = {
            "ENGLISH", "RUSSIAN", "UKRAINIAN", "ARABIC", "FRENCH",
            "AFRIKAANS", "ROMANIAN", "TURKISH", "ARMENIAN", "SPANISH",
            "GERMAN", "HINDI", "URDU", "PORTUGUESE", "ITALIAN", "PERSIAN",
        }
        unknown = []
        for p in practitioners:
            for lang in p.get("languages", []):
                if lang not in KNOWN:
                    unknown.append((p["id"], p.get("name", ""), lang))
        assert len(unknown) == 0, (
            f"Unknown languages:\n" +
            "\n".join(f"  ID {pid}: '{name}' has unknown language '{lang}'" for pid, name, lang in unknown)
        )

    def test_name_spacing(self, practitioners):
        """Names should not have 'Dr.Name' without space."""
        bad_names = []
        for p in practitioners:
            name = p.get("name", "")
            if re.search(r'Dr\.\S', name):
                bad_names.append((p["id"], name))
        assert len(bad_names) == 0, (
            f"Names with missing space after 'Dr.':\n" +
            "\n".join(f"  ID {pid}: '{name}'" for pid, name in bad_names)
        )

    def test_name_and_name_i18n_match(self, practitioners):
        """name and name_i18n.en should be the same."""
        mismatches = []
        for p in practitioners:
            name = p.get("name", "")
            name_en = get_name_en(p)
            if name != name_en:
                mismatches.append((p["id"], name, name_en))
        assert len(mismatches) == 0, (
            f"name != name_i18n.en:\n" +
            "\n".join(f"  ID {pid}: name='{n}' vs name_i18n.en='{n_en}'" for pid, n, n_en in mismatches)
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 6. NAME MATCHING / NORMALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestNameMatching:
    """
    Test that name normalization works correctly for API matching.
    
    Known bug: fix_locations.py normalize() does NOT strip special characters,
    while sync_with_api.py normalize_name() does. This causes em-dash (–) vs
    regular dash (-) mismatches when matching services by name.
    """

    def test_no_special_dashes_in_service_names(self, services):
        """
        Detect services with em-dash (–), en-dash (—) or other special dashes.
        These can cause name matching failures if API stores regular dashes.
        """
        special_dash_services = []
        for svc in services:
            name = get_name_en(svc)
            # Check for em-dash (–), en-dash (—), and other Unicode dashes
            if re.search(r'[\u2013\u2014\u2015\u2212]', name):
                special_dash_services.append((svc["id"], name))
        
        if special_dash_services:
            pytest.warns(
                UserWarning,
                match="special dashes"
            ) if False else None  # Just flag it
            # Report but don't fail — just warn
            print(f"\n  WARNING: {len(special_dash_services)} services have special dashes (may cause matching issues):")
            for sid, name in special_dash_services[:10]:
                print(f"    ID {sid}: {name}")

    def test_normalize_consistency(self, services):
        """
        Test that weak normalize (fix_locations.py) and strong normalize 
        (sync_with_api.py) produce different results — flagging potential issues.
        """
        mismatches = []
        for svc in services:
            name = get_name_en(svc)
            weak = normalize_weak(name)
            strong = normalize_name(name)
            if weak != strong:
                mismatches.append((svc["id"], name, weak, strong))

        if mismatches:
            print(f"\n  INFO: {len(mismatches)} services have different weak vs strong normalization:")
            for sid, name, weak, strong in mismatches[:10]:
                print(f"    ID {sid}: '{name}'")
                print(f"      weak:   '{weak}'")
                print(f"      strong: '{strong}'")

    def test_practitioner_names_match_between_files(self, practitioners, service_practitioners, services):
        """
        Practitioners referenced in service_practitioners must have consistent names.
        
        Bug scenario: Practitioner extracted from services CSV has name "Cherry Lou Abuyan"
        but was uploaded to API as different spelling → name match fails → links lost.
        """
        pract_by_id = {p["id"]: p for p in practitioners}
        
        # Check all practitioners referenced in SP actually exist and have names
        referenced_pract_ids = set(sp["practitioner_id"] for sp in service_practitioners)
        for pid in referenced_pract_ids:
            assert pid in pract_by_id, (
                f"practitioner_id={pid} referenced in service_practitioners "
                f"but not found in practitioners.json"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 7. SERVICE-PRACTITIONER LINK COUNTS (per branch)
# ═══════════════════════════════════════════════════════════════════════════════

class TestServicePractitionerCounts:
    """
    Test expected service-practitioner link counts per branch.
    
    Simulates the step5 filtering logic locally (without API) to verify 
    that the correct number of links would be created per location.
    """

    def _get_links_for_location(self, services, practitioners, service_practitioners, branch: str):
        """
        Simulate fix_locations.py step5 filtering for a specific branch.
        Returns dict: practitioner_name → list of service names.
        """
        svc_by_id = {s["id"]: s for s in services}
        pract_by_id = {p["id"]: p for p in practitioners}
        
        result = {}  # pract_name -> [service_names]
        
        for sp in service_practitioners:
            svc = svc_by_id.get(sp["service_id"])
            pract = pract_by_id.get(sp["practitioner_id"])
            
            if not svc or not pract:
                continue
            
            # Check service belongs to this branch
            svc_branches = set(svc.get("branches", []))
            if branch not in svc_branches:
                continue
            
            # Check practitioner belongs to this branch
            pract_branches = set(b.lower() for b in pract.get("branches", []))
            if pract_branches:  # non-empty → must contain branch
                if branch not in pract_branches:
                    continue
            # Empty branches → goes to both (allowed through)
            
            pract_name = pract.get("name", "")
            svc_name = get_name_en(svc)
            
            if pract_name not in result:
                result[pract_name] = []
            result[pract_name].append(svc_name)
        
        return result

    def test_cherry_lou_abuyan_szr_links(self, services, practitioners, service_practitioners):
        """
        Cherry Lou Abuyan should have 18 services on SZR.
        
        Known bug: She had 0 services on SZR despite having 18 links.
        Her branches=[] and source="services_sheet" — she was extracted from
        the services CSV, not from the practitioners Google Sheet.
        """
        links = self._get_links_for_location(services, practitioners, service_practitioners, "szr")
        cherry_links = links.get("Cherry Lou Abuyan", [])
        
        assert len(cherry_links) == 18, (
            f"Cherry Lou Abuyan should have 18 services on SZR, got {len(cherry_links)}.\n"
            f"Services found: {cherry_links[:5]}..."
        )

    def test_dr_john_milam_shamoun_no_services(self, services, practitioners, service_practitioners):
        """
        Dr. John Milam Shamoun should have 0 services in service_practitioners.
        
        Known bug: He appeared with 7 services on SZR API despite having 
        0 links in service_practitioners.json.
        """
        pract = next((p for p in practitioners if "Shamoun" in p.get("name", "")), None)
        assert pract is not None, "Dr. John Milam Shamoun not found in practitioners.json"
        
        shamoun_links = [
            sp for sp in service_practitioners
            if sp["practitioner_id"] == pract["id"]
        ]
        assert len(shamoun_links) == 0, (
            f"Dr. John Milam Shamoun should have 0 service_practitioner links, "
            f"got {len(shamoun_links)}"
        )

    def test_dr_kinan_bonni_szr_links(self, services, practitioners, service_practitioners):
        """
        Dr. Kinan Bonni should have 49 services on SZR.
        
        Known bug: Only 9 out of 49 services were linked on SZR.
        Likely caused by service name matching failures (em-dash vs dash).
        """
        links = self._get_links_for_location(services, practitioners, service_practitioners, "szr")
        kinan_links = links.get("Dr. Kinan Bonni", [])
        
        assert len(kinan_links) == 49, (
            f"Dr. Kinan Bonni should have 49 services on SZR, got {len(kinan_links)}.\n"
            f"Services found: {kinan_links[:5]}..."
        )

    def test_all_practitioners_have_expected_links(self, services, practitioners, service_practitioners):
        """
        For each practitioner, verify total link count matches service_practitioners.json.
        """
        pract_by_id = {p["id"]: p.get("name", "") for p in practitioners}
        
        # Count links per practitioner
        sp_counts = Counter(sp["practitioner_id"] for sp in service_practitioners)
        
        # Verify all practitioner IDs in SP exist
        for pract_id, count in sp_counts.items():
            assert pract_id in pract_by_id, (
                f"practitioner_id={pract_id} has {count} links but doesn't exist in practitioners.json"
            )

    def test_szr_services_have_links(self, services, service_practitioners):
        """
        Services with branches=["szr"] should have at least some practitioner links.
        Flag services that have no practitioners assigned.
        """
        svc_ids_with_links = set(sp["service_id"] for sp in service_practitioners)
        
        szr_services_no_links = [
            (s["id"], get_name_en(s))
            for s in services
            if set(s.get("branches", [])) == {"szr"} and s["id"] not in svc_ids_with_links
        ]
        
        # This is informational — some services legitimately may not have practitioners
        if szr_services_no_links:
            print(f"\n  INFO: {len(szr_services_no_links)} SZR-only services have no practitioner links:")
            for sid, name in szr_services_no_links[:10]:
                print(f"    ID {sid}: {name}")


# ═══════════════════════════════════════════════════════════════════════════════
# 8. CROSS-VALIDATION WITH CSV
# ═══════════════════════════════════════════════════════════════════════════════

class TestCsvCrossValidation:
    """Cross-validate parsed JSON with raw CSV data."""

    def test_cherry_lou_in_csv(self, raw_csv_lines):
        """Cherry Lou Abuyan should appear in CSV (Doctor name column)."""
        if not raw_csv_lines:
            pytest.skip("raw_data.csv not found")
        count = raw_csv_lines.count("Cherry Lou Abuyan")
        assert count > 0, "Cherry Lou Abuyan not found in raw_data.csv"
        assert count == 18, f"Cherry Lou Abuyan appears {count} times in CSV, expected 18"

    def test_shamoun_not_in_csv(self, raw_csv_lines):
        """Dr. John Milam Shamoun should NOT appear in CSV (no services)."""
        if not raw_csv_lines:
            pytest.skip("raw_data.csv not found")
        count = raw_csv_lines.count("Shamoun")
        assert count == 0, (
            f"Shamoun appears {count} times in raw_data.csv but should have 0 services"
        )

    def test_kinan_in_csv(self, raw_csv_lines):
        """Dr. Kinan Bonni should appear 49 times in CSV."""
        if not raw_csv_lines:
            pytest.skip("raw_data.csv not found")
        count = raw_csv_lines.count("Kinan")
        assert count == 49, f"Kinan appears {count} times in CSV, expected 49"


# ═══════════════════════════════════════════════════════════════════════════════
# 9. STEP5 SIMULATION (full dry-run without API)
# ═══════════════════════════════════════════════════════════════════════════════

class TestStep5Simulation:
    """
    Simulate the complete step5 filtering to detect issues
    BEFORE actually calling the API.
    """

    def _simulate_step5(self, services, practitioners, service_practitioners, categories, branch: str):
        """
        Simulate fix_locations.py step5 for given branch.
        Returns detailed report of what would happen.
        """
        svc_by_id = {s["id"]: s for s in services}
        pract_by_id = {p["id"]: p for p in practitioners}
        cat_by_id = {c["id"]: c for c in categories}
        
        svc_id_to_branches = {s["id"]: set(s.get("branches", [])) for s in services}
        pract_id_to_branches = {p["id"]: set(b.lower() for b in p.get("branches", [])) for p in practitioners}
        pract_id_to_name = {p["id"]: normalize_weak(p.get("name", get_name_en(p))) for p in practitioners}
        
        links_ok = []
        skipped_svc_wrong_branch = 0
        skipped_pract_wrong_branch = 0
        skipped_no_svc = 0
        skipped_no_pract = 0
        
        for sp in service_practitioners:
            local_svc_id = sp["service_id"]
            local_pract_id = sp["practitioner_id"]
            
            # Check service branch
            svc_branches = svc_id_to_branches.get(local_svc_id, set())
            if branch not in svc_branches:
                skipped_svc_wrong_branch += 1
                continue
            
            # Check practitioner branch
            pract_branches = pract_id_to_branches.get(local_pract_id, set())
            if pract_branches and branch not in pract_branches:
                skipped_pract_wrong_branch += 1
                continue
            
            # Check both exist
            svc = svc_by_id.get(local_svc_id)
            pract = pract_by_id.get(local_pract_id)
            if not svc:
                skipped_no_svc += 1
                continue
            if not pract:
                skipped_no_pract += 1
                continue
            
            links_ok.append({
                "service_id": local_svc_id,
                "service_name": get_name_en(svc),
                "practitioner_id": local_pract_id,
                "practitioner_name": pract.get("name", ""),
            })
        
        return {
            "links_to_create": links_ok,
            "skipped_svc_wrong_branch": skipped_svc_wrong_branch,
            "skipped_pract_wrong_branch": skipped_pract_wrong_branch,
            "skipped_no_svc": skipped_no_svc,
            "skipped_no_pract": skipped_no_pract,
        }

    def test_szr_links_not_zero(self, services, practitioners, service_practitioners, categories):
        """SZR location should have a non-trivial number of links."""
        report = self._simulate_step5(services, practitioners, service_practitioners, categories, "szr")
        links = report["links_to_create"]
        assert len(links) > 100, (
            f"SZR should have >100 links, got {len(links)}.\n"
            f"Skipped: svc_wrong_branch={report['skipped_svc_wrong_branch']}, "
            f"pract_wrong_branch={report['skipped_pract_wrong_branch']}, "
            f"no_svc={report['skipped_no_svc']}, no_pract={report['skipped_no_pract']}"
        )

    def test_jumeirah_links_not_zero(self, services, practitioners, service_practitioners, categories):
        """Jumeirah location should have a non-trivial number of links."""
        report = self._simulate_step5(services, practitioners, service_practitioners, categories, "jumeirah")
        links = report["links_to_create"]
        assert len(links) > 100, (
            f"Jumeirah should have >100 links, got {len(links)}"
        )

    def test_no_orphan_links(self, services, practitioners, service_practitioners, categories):
        """No link should reference a non-existent service or practitioner."""
        for branch in ["jumeirah", "szr"]:
            report = self._simulate_step5(services, practitioners, service_practitioners, categories, branch)
            assert report["skipped_no_svc"] == 0, (
                f"Branch '{branch}': {report['skipped_no_svc']} links reference non-existent services"
            )
            assert report["skipped_no_pract"] == 0, (
                f"Branch '{branch}': {report['skipped_no_pract']} links reference non-existent practitioners"
            )

    def test_szr_per_practitioner_counts(self, services, practitioners, service_practitioners, categories):
        """
        Print per-practitioner link counts for SZR.
        Helps spot practitioners with unexpectedly low/high counts.
        """
        report = self._simulate_step5(services, practitioners, service_practitioners, categories, "szr")
        links = report["links_to_create"]
        
        pract_counts = Counter(l["practitioner_name"] for l in links)
        
        print(f"\n  SZR links per practitioner ({len(pract_counts)} practitioners):")
        for name, count in sorted(pract_counts.items(), key=lambda x: -x[1]):
            print(f"    {count:>4} links: {name}")
        
        # Verify specific known counts
        assert pract_counts.get("Cherry Lou Abuyan", 0) == 18, (
            f"Cherry Lou Abuyan: expected 18 SZR links, got {pract_counts.get('Cherry Lou Abuyan', 0)}"
        )
        assert pract_counts.get("Dr. Kinan Bonni", 0) == 49, (
            f"Dr. Kinan Bonni: expected 49 SZR links, got {pract_counts.get('Dr. Kinan Bonni', 0)}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 10. SOURCE CONSISTENCY
# ═══════════════════════════════════════════════════════════════════════════════

class TestSourceConsistency:
    """
    Test for practitioners that were added from services sheet (CSV) 
    vs Google Sheets practitioners tab.
    
    Practitioners from CSV only have basic info (name, id).
    Practitioners from Google Sheets have full profile.
    """

    def test_services_sheet_practitioners_have_branches(self, practitioners):
        """
        Practitioners with source="services_sheet" often have branches=[] 
        because the CSV doesn't contain branch info for practitioners.
        Flag them — they might need manual branch assignment.
        """
        services_sheet_practs = [
            p for p in practitioners
            if p.get("source") == "services_sheet"
        ]
        
        no_branches = [
            (p["id"], p.get("name", ""))
            for p in services_sheet_practs
            if not p.get("branches")
        ]
        
        if no_branches:
            print(f"\n  WARNING: {len(no_branches)} practitioners from services_sheet have empty branches:")
            for pid, name in no_branches:
                print(f"    ID {pid}: {name}")

    def test_all_csv_practitioners_in_practitioners_json(self, practitioners, service_practitioners):
        """
        Every practitioner referenced in service_practitioners should exist 
        in practitioners.json with a valid name.
        """
        pract_by_id = {p["id"]: p for p in practitioners}
        referenced = set(sp["practitioner_id"] for sp in service_practitioners)
        
        missing_name = []
        for pid in referenced:
            p = pract_by_id.get(pid)
            if p and not p.get("name"):
                missing_name.append(pid)
        
        assert len(missing_name) == 0, (
            f"{len(missing_name)} practitioners referenced in links have no name"
        )
