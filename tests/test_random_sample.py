#!/usr/bin/env python3
"""
Random sampling test: берёт 10-15% practitioners и проверяет их
service_practitioners и branches, сравнивая JSON ↔ CSV.

Каждый запуск — другая случайная выборка.
Запускай ПЕРЕД POST запросами.

Использование:
    pytest tests/test_random_sample.py -v -s              # случайная выборка
    pytest tests/test_random_sample.py -v -s --count 5    # ровно 5 врачей
    SEED=42 pytest tests/test_random_sample.py -v -s      # фиксированный seed
"""

import csv
import json
import os
import random
import re
from collections import defaultdict
from pathlib import Path

import pytest

# ─── Paths ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
CSV_FILE = ROOT / "data" / "input" / "raw_data.csv"
SERVICES_JSON = ROOT / "data" / "output" / "services.json"
CATEGORIES_JSON = ROOT / "data" / "output" / "categories.json"
PRACTITIONERS_JSON = ROOT / "data" / "output" / "practitioners.json"
SP_JSON = ROOT / "data" / "output" / "service_practitioners.json"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def norm(s: str) -> str:
    """Normalize name: lowercase, collapse spaces, strip dots after Dr."""
    if not s:
        return ""
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def norm_doctor(s: str) -> str:
    """Normalize doctor name for matching CSV ↔ JSON.

    CSV has: 'Dr.Sarah Mohamed', 'Dr Kinan Bonni', 'Dr. Karem Harb'
    JSON has: 'Dr. Sarah Mohamed', 'Dr. Kinan Bonni', 'Dr. Karem Harb'

    Rules:
      1. lowercase, collapse whitespace
      2. 'dr.' → 'dr. ' (ensure space after dot)
      3. 'dr ' → 'dr. ' (add missing dot)
      4. strip trailing annotations like '(private area only)'
    """
    s = norm(s)
    s = re.sub(r"\(.*?\)", "", s).strip()          # remove (annotations)
    s = re.sub(r"^dr\.(\S)", r"dr. \1", s)         # "dr.sarah" → "dr. sarah"
    s = re.sub(r"^dr\s+(?!\.)", "dr. ", s)         # "dr karem" → "dr. karem"
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ─── CSV Doctor name aliases ─────────────────────────────────────────────────
# CSV uses shortened names for the same practitioner. This map links
# the canonical JSON name → all possible CSV aliases (after norm_doctor).
# Build: for each JSON practitioner, find all CSV "Doctor name" variants
# that refer to the same person.

DOCTOR_ALIASES = {
    # JSON name (norm_doctor)          →  extra CSV aliases (norm_doctor)
    "danielle april stephen":           ["danielle stephen"],
    "dr. mohsen soofian":               ["dr. mohsen"],
    "dr. sarah mohamed":                ["dr. sarah mohamed"],  # Dr.Sarah → dr. sarah
    "dr. karem harb":                   ["dr. karem harb"],     # "Dr Karem Harb" already normalizes
    "dr. nataliya sanytska":            ["dr. nataliya sanytska"],
    "dr. tatiana kuznechenkova":        ["dr. tatiana kuznechenkova"],
    "dr. lyn al alamy alhassany":       ["dr. lyn al alamy alhassany"],
    "dr. zainab mohi":                  ["dr. zainab mohi"],
    "dr. sezgin cagatay":               ["dr. sezgin cagatay"],
}


def get_csv_keys_for_practitioner(pract_name: str) -> list:
    """Return all CSV norm_doctor keys that map to this JSON practitioner."""
    canonical = norm_doctor(pract_name)
    keys = [canonical]
    for alias in DOCTOR_ALIASES.get(canonical, []):
        if alias != canonical:
            keys.append(alias)
    return keys


def parse_branches_csv(raw: str) -> list:
    """Parse branch string from CSV."""
    if not raw or raw.strip() == "":
        return ["jumeirah", "szr"]
    s = raw.strip().lower()
    if s == "both":
        return ["jumeirah", "szr"]
    if s == "jumeirah":
        return ["jumeirah"]
    if s in ("szr", "srz"):
        return ["szr"]
    return ["jumeirah", "szr"]


def get_name_en(item: dict) -> str:
    return (item.get("name_i18n") or {}).get("en", "") or item.get("name", "")


# ─── Data loading (cached) ───────────────────────────────────────────────────

_CACHE = {}


def load_json(path: Path) -> list:
    key = str(path)
    if key not in _CACHE:
        with open(path, encoding="utf-8") as f:
            _CACHE[key] = json.load(f)
    return _CACHE[key]


def load_csv_rows() -> list:
    if "csv" not in _CACHE:
        with open(CSV_FILE, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        _CACHE["csv"] = [r for r in rows if r.get("ID") != "ID"]
    return _CACHE["csv"]


def build_csv_doctor_index() -> dict:
    """Build index: normalized_doctor_name → list of UNIQUE CSV rows.

    CSV may have duplicate rows (same doctor + same service + same category).
    We deduplicate by (doctor, service_name, category) — because the SAME
    service name in DIFFERENT categories is a different service
    (e.g. "Comprehensive Consultation & Examination" in 4 categories).
    """
    if "csv_doc_idx" not in _CACHE:
        idx = defaultdict(list)
        seen = set()  # (norm_doctor, norm_service_name, norm_category)
        for row in load_csv_rows():
            svc_name = (row.get("Service Name") or "").split("\n")[0].strip()
            category = (row.get("Category") or "").strip()
            for doc in row.get("Doctor name", "").split("\n"):
                doc = doc.strip()
                if not doc:
                    continue
                key = (norm_doctor(doc), norm(svc_name), norm(category))
                if key in seen:
                    continue
                seen.add(key)
                idx[norm_doctor(doc)].append(row)
        _CACHE["csv_doc_idx"] = dict(idx)
    return _CACHE["csv_doc_idx"]


# ─── Sample selection ─────────────────────────────────────────────────────────

def pick_sample(fraction: float = 0.15, min_count: int = 3) -> list:
    """Pick random 10-15% of practitioners. Returns list of dicts."""
    practitioners = load_json(PRACTITIONERS_JSON)
    seed = int(os.environ.get("SEED", random.randint(0, 999999)))

    count = max(min_count, int(len(practitioners) * fraction))
    count = min(count, len(practitioners))

    rng = random.Random(seed)
    sample = rng.sample(practitioners, count)

    print(f"\n  Random sample: {count}/{len(practitioners)} practitioners (seed={seed})")
    for p in sample:
        print(f"    - {p.get('name', '?')} (branches={p.get('branches', [])})")

    return sample


_SAMPLE = None


def get_sample():
    global _SAMPLE
    if _SAMPLE is None:
        _SAMPLE = pick_sample()
    return _SAMPLE


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestRandomPractitionerServiceCount:
    """
    Для каждого sampled practitioner: количество сервисов в JSON
    совпадает с количеством строк в CSV где его имя упоминается.
    """

    @pytest.mark.parametrize(
        "pract",
        get_sample(),
        ids=[p.get("name", "?") for p in get_sample()],
    )
    def test_service_count_matches_csv(self, pract):
        sp_links = load_json(SP_JSON)
        csv_idx = build_csv_doctor_index()

        pract_id = pract["id"]
        pract_name = pract.get("name", "")

        # JSON: count links
        json_count = sum(1 for sp in sp_links if sp["practitioner_id"] == pract_id)

        # CSV: count rows where this doctor appears (across all aliases)
        csv_keys = get_csv_keys_for_practitioner(pract_name)
        csv_rows = []
        seen_svc = set()
        for key in csv_keys:
            for row in csv_idx.get(key, []):
                svc = norm((row.get("Service Name") or "").split("\n")[0].strip())
                cat = norm((row.get("Category") or "").strip())
                dedup_key = (svc, cat)
                if dedup_key not in seen_svc:
                    seen_svc.add(dedup_key)
                    csv_rows.append(row)
        csv_count = len(csv_rows)

        print(f"\n  {pract_name}:")
        print(f"    JSON links (service_practitioners.json): {json_count}")
        print(f"    CSV rows  (Doctor name matches):         {csv_count}")
        print(f"    CSV keys used: {csv_keys}")

        if csv_count == 0 and json_count == 0:
            print(f"    OK — no services in either source")
            return

        assert json_count == csv_count, (
            f"\n  {pract_name}: count mismatch!\n"
            f"    JSON service_practitioners: {json_count}\n"
            f"    CSV Doctor name rows:       {csv_count}\n"
            f"    CSV keys: {csv_keys}"
        )


class TestRandomPractitionerBranches:
    """
    Для каждого sampled practitioner: ВСЕ его сервисы из
    service_practitioners должны быть совместимы с его branches.
    """

    @pytest.mark.parametrize(
        "pract",
        get_sample(),
        ids=[p.get("name", "?") for p in get_sample()],
    )
    def test_service_branches_consistent(self, pract):
        """
        Проверяет что связи service↔practitioner совместимы по branch.

        ВАЖНО: cross-branch связи допустимы в локальных данных.
        fix_locations.py --step5 фильтрует их при загрузке —
        на каждый location попадают только совместимые пары.
        Поэтому cross-branch links — WARNING, а не FAIL.

        FAIL — если у practitioner branches=[] (оба location),
        но все сервисы на одном branch (подозрительно).
        """
        sp_links = load_json(SP_JSON)
        services = load_json(SERVICES_JSON)

        svc_by_id = {s["id"]: s for s in services}
        pract_id = pract["id"]
        pract_name = pract.get("name", "")
        pract_branches = set(b.lower() for b in pract.get("branches", []))

        # Get all linked services
        linked_svcs = [
            svc_by_id[sp["service_id"]]
            for sp in sp_links
            if sp["practitioner_id"] == pract_id and sp["service_id"] in svc_by_id
        ]

        if not linked_svcs:
            print(f"\n  {pract_name}: 0 linked services — skipping branch check")
            return

        cross_branch = []
        same_branch = 0
        for svc in linked_svcs:
            svc_branches = set(svc.get("branches", []))
            svc_name = get_name_en(svc)

            if pract_branches:
                overlap = pract_branches & svc_branches
                if not overlap:
                    cross_branch.append(
                        f"    {svc_name}: svc={sorted(svc_branches)} "
                        f"pract={sorted(pract_branches)}"
                    )
                else:
                    same_branch += 1

        print(f"\n  {pract_name} (branches={sorted(pract_branches) or '[]→both'}):")
        print(f"    Linked services: {len(linked_svcs)}")
        print(f"    Same branch: {same_branch}, Cross-branch: {len(cross_branch)}")
        if cross_branch:
            print(f"    Cross-branch links (filtered out during upload):")
            for v in cross_branch[:5]:
                print(v)
            if len(cross_branch) > 5:
                print(f"    ... and {len(cross_branch) - 5} more")

        # FAIL only if practitioner has explicit branches but NO matching services
        if pract_branches and same_branch == 0 and linked_svcs:
            pytest.fail(
                f"\n  {pract_name}: has {len(linked_svcs)} services but "
                f"NONE match branches {sorted(pract_branches)}!\n"
                f"  This practitioner will have 0 services after upload."
            )


class TestRandomPractitionerServiceNames:
    """
    Для каждого sampled practitioner: имена сервисов из JSON
    совпадают с именами из CSV.
    """

    @pytest.mark.parametrize(
        "pract",
        get_sample(),
        ids=[p.get("name", "?") for p in get_sample()],
    )
    def test_service_names_match_csv(self, pract):
        sp_links = load_json(SP_JSON)
        services = load_json(SERVICES_JSON)
        csv_idx = build_csv_doctor_index()

        svc_by_id = {s["id"]: s for s in services}
        pract_id = pract["id"]
        pract_name = pract.get("name", "")

        # JSON service names
        json_svc_names = set()
        for sp in sp_links:
            if sp["practitioner_id"] == pract_id:
                svc = svc_by_id.get(sp["service_id"])
                if svc:
                    json_svc_names.add(norm(get_name_en(svc)))

        # CSV service names (across all aliases)
        csv_keys = get_csv_keys_for_practitioner(pract_name)
        csv_svc_names = set()
        for key in csv_keys:
            for row in csv_idx.get(key, []):
                raw = row.get("Service Name", "")
                first_line = raw.split("\n")[0].strip() if raw else ""
                if first_line:
                    csv_svc_names.add(norm(first_line))

        if not json_svc_names and not csv_svc_names:
            return

        # Find differences
        only_in_json = json_svc_names - csv_svc_names
        only_in_csv = csv_svc_names - json_svc_names

        print(f"\n  {pract_name}:")
        print(f"    JSON services: {len(json_svc_names)}")
        print(f"    CSV services:  {len(csv_svc_names)}")
        if only_in_json:
            print(f"    Only in JSON ({len(only_in_json)}):")
            for n in sorted(only_in_json)[:5]:
                print(f"      + {n}")
        if only_in_csv:
            print(f"    Only in CSV ({len(only_in_csv)}):")
            for n in sorted(only_in_csv)[:5]:
                print(f"      - {n}")

        assert len(only_in_json) == 0 and len(only_in_csv) == 0, (
            f"\n  {pract_name}: service name mismatch!\n"
            f"    Only in JSON: {len(only_in_json)}\n"
            f"    Only in CSV:  {len(only_in_csv)}"
        )


class TestRandomPractitionerProfile:
    """
    Для каждого sampled practitioner: печатает полный профиль
    из JSON для ручной сверки (описание, специальность, языки, квалификации).
    Этот тест всегда PASS — только печатает.
    """

    @pytest.mark.parametrize(
        "pract",
        get_sample(),
        ids=[p.get("name", "?") for p in get_sample()],
    )
    def test_print_profile(self, pract):
        sp_links = load_json(SP_JSON)
        services = load_json(SERVICES_JSON)
        categories = load_json(CATEGORIES_JSON)

        svc_by_id = {s["id"]: s for s in services}
        cat_by_id = {c["id"]: get_name_en(c) for c in categories}

        pract_id = pract["id"]
        pract_name = pract.get("name", "")

        linked = [
            svc_by_id[sp["service_id"]]
            for sp in sp_links
            if sp["practitioner_id"] == pract_id and sp["service_id"] in svc_by_id
        ]

        # Group by branch
        jum = [s for s in linked if "jumeirah" in s.get("branches", [])]
        szr = [s for s in linked if "szr" in s.get("branches", [])]

        desc = (pract.get("description_i18n") or {}).get("en", "")

        print(f"\n{'═'*70}")
        print(f"  PRACTITIONER: {pract_name}")
        print(f"{'═'*70}")
        print(f"  ID:            {pract_id}")
        print(f"  Speciality:    {pract.get('speciality', '—')}")
        print(f"  Sex:           {pract.get('sex', '—')}")
        print(f"  Languages:     {', '.join(pract.get('languages', []))}")
        print(f"  Experience:    {pract.get('years_of_experience', '—')} years")
        print(f"  Branches:      {pract.get('branches', [])}")
        print(f"  Source:        {pract.get('source', '—')}")
        print(f"  Treat children:{pract.get('treat_children', '—')}")
        print(f"  Description:   {desc[:120]}{'...' if len(desc) > 120 else ''}")

        quals = []
        for f in ["primary_qualifications", "secondary_qualifications",
                   "additional_qualifications"]:
            v = pract.get(f)
            if v:
                quals.append(f"    {f}: {str(v)[:80]}...")
        if quals:
            print(f"  Qualifications:")
            for q in quals:
                print(q)

        print(f"\n  Services: {len(linked)} total "
              f"(Jumeirah: {len(jum)}, SZR: {len(szr)})")

        for svc in sorted(linked, key=lambda s: get_name_en(s))[:15]:
            cat = cat_by_id.get(svc.get("category_id"), "?")
            br = ",".join(svc.get("branches", []))
            price = svc.get("price_min")
            dur = svc.get("duration_minutes")
            print(f"    [{br:12}] {get_name_en(svc)[:45]:45} "
                  f"cat={cat[:20]:20} price={price} dur={dur}")

        if len(linked) > 15:
            print(f"    ... and {len(linked) - 15} more")


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

def test_random_sample_summary():
    """
    Сводка по всей выборке: общее количество ошибок.
    """
    sample = get_sample()
    sp_links = load_json(SP_JSON)
    services = load_json(SERVICES_JSON)
    csv_idx = build_csv_doctor_index()
    svc_by_id = {s["id"]: s for s in services}

    total_ok = 0
    total_issues = 0

    print(f"\n{'═'*70}")
    print(f"  RANDOM SAMPLE SUMMARY ({len(sample)} practitioners)")
    print(f"{'═'*70}")

    for pract in sample:
        pid = pract["id"]
        name = pract.get("name", "?")
        pract_branches = set(b.lower() for b in pract.get("branches", []))

        json_count = sum(1 for sp in sp_links if sp["practitioner_id"] == pid)
        csv_keys = get_csv_keys_for_practitioner(name)
        seen_svc = set()
        csv_count = 0
        for key in csv_keys:
            for row in csv_idx.get(key, []):
                svc = norm((row.get("Service Name") or "").split("\n")[0].strip())
                cat = norm((row.get("Category") or "").strip())
                dedup_key = (svc, cat)
                if dedup_key not in seen_svc:
                    seen_svc.add(dedup_key)
                    csv_count += 1

        # Branch check (cross-branch links are INFO, not error)
        linked = [
            svc_by_id[sp["service_id"]]
            for sp in sp_links
            if sp["practitioner_id"] == pid and sp["service_id"] in svc_by_id
        ]
        cross_branch = 0
        same_branch = 0
        if pract_branches:
            for svc in linked:
                if pract_branches & set(svc.get("branches", [])):
                    same_branch += 1
                else:
                    cross_branch += 1

        issues = []
        if json_count != csv_count:
            issues.append(f"count: json={json_count} csv={csv_count}")
        # FAIL only if practitioner has services but NONE match their branches
        if pract_branches and linked and same_branch == 0:
            issues.append(f"NO matching branches! (all {len(linked)} are cross-branch)")

        status = "FAIL" if issues else "OK"
        if issues:
            total_issues += 1
            print(f"  FAIL {name:40} {'; '.join(issues)}")
        else:
            total_ok += 1
            info = f"{json_count} services"
            if cross_branch:
                info += f" ({cross_branch} cross-branch, filtered at upload)"
            print(f"  OK   {name:40} {info}")

    print(f"\n  Result: {total_ok} OK / {total_issues} FAIL / {len(sample)} total")

    assert total_issues == 0, f"{total_issues} practitioners with issues (see output above)"
