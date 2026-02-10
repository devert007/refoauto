#!/usr/bin/env python3
"""
Тесты на основе API endpoint /content-stats.

Ловит ВСЕ типы ошибок на обоих locations:
  - duplicate_names       (error)   дубли имён сервисов
  - no_practitioners      (warning) сервисы без врачей
  - missing_duration      (warning) сервисы без длительности
  - missing_price         (warning) сервисы без цены
  - missing_description   (warning) сервисы без описания
  - empty_category        (warning) категории без сервисов
  - no_services           (warning) врачи без сервисов
  - too_many_services     (error)   врачи с >100 сервисов

Использование:
    pytest tests/test_content_stats.py -v -s
    pytest tests/test_content_stats.py -v -k "jumeirah"
    pytest tests/test_content_stats.py -v -k "duplicate"

NOTE: Требует активную сессию в config/.dg_session.json
"""

import json
import re
from pathlib import Path

import pytest
import requests

# ─── Config ──────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"

API_BASE = "https://dialoggauge.yma.health/api"
LOCATION_JUMEIRAH = 17
LOCATION_SZR = 18

# ─── Ожидаемые допустимые значения ───────────────────────────────────────────
# Сервисы без врачей: в CSV нет Doctor name → не исправимо
EXPECTED_NO_PRACTITIONERS_JUM = 7   # Biorepeel, TRT, Intimate Rejuvenation, и т.д.
EXPECTED_NO_PRACTITIONERS_SZR = 4   # Dermaplaning, Face Sculpt, Biorepeel, Ulthera

# Practitioners с >100 services (реальные данные из CSV)
ALLOWED_OVER_100_JUM = {
    "dr. tatiana kuznechenkova",
    "dr. nataliya sanytska",
    "dr. lyn al alamy alhassany",
}
ALLOWED_OVER_100_SZR = {
    "dr. anna zakhozha",
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def load_session() -> str:
    session_file = CONFIG_DIR / ".dg_session.json"
    if not session_file.exists():
        pytest.skip("No API session (config/.dg_session.json)")
    with open(session_file) as f:
        return json.load(f)["dg_session"]


def api_get(endpoint: str):
    headers = {
        "Accept": "application/json",
        "Cookie": f"dg_session={load_session()}",
    }
    r = requests.get(f"{API_BASE}{endpoint}", headers=headers)
    if r.status_code == 401:
        pytest.skip("API session expired (401)")
    r.raise_for_status()
    return r.json()


def get_name(item):
    return (item.get("name_i18n") or {}).get("en", "") or item.get("name", "")


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def get_issue(issues, code, severity=None):
    """Найти issue по коду. Вернёт dict или None."""
    for i in issues:
        if i["code"] == code:
            if severity is None or i["severity"] == severity:
                return i
    return None


# ─── Fixtures (только лёгкие запросы) ────────────────────────────────────────

@pytest.fixture(scope="module")
def stats_jumeirah():
    return api_get(f"/locations/{LOCATION_JUMEIRAH}/content-stats")


@pytest.fixture(scope="module")
def stats_szr():
    return api_get(f"/locations/{LOCATION_SZR}/content-stats")


@pytest.fixture(scope="module")
def api_practitioners_jumeirah():
    return api_get(f"/locations/{LOCATION_JUMEIRAH}/practitioners")


@pytest.fixture(scope="module")
def api_practitioners_szr():
    return api_get(f"/locations/{LOCATION_SZR}/practitioners")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. DUPLICATE SERVICE NAMES — должно быть 0 дублей
# ═══════════════════════════════════════════════════════════════════════════════

class TestDuplicateServiceNames:

    def test_jumeirah_no_duplicates(self, stats_jumeirah):
        """Jumeirah: дублей быть не должно (исправлены добавлением суффикса категории)."""
        issue = get_issue(stats_jumeirah["services"]["issues"], "duplicate_names")
        assert issue is None, (
            f"Jumeirah имеет дубли: {issue['message']}. "
            "Переименуйте дубли добавив суффикс категории."
        )

    def test_szr_no_duplicates(self, stats_szr):
        """SZR: дублей имён быть не должно."""
        issue = get_issue(stats_szr["services"]["issues"], "duplicate_names")
        assert issue is None, f"SZR имеет дубли: {issue['message']}"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SERVICES WITHOUT PRACTITIONERS — ожидаемое кол-во (нет данных в CSV)
# ═══════════════════════════════════════════════════════════════════════════════

class TestServicesWithoutPractitioners:

    def test_jumeirah_exact(self, stats_jumeirah):
        """
        Jumeirah: ровно 7 сервисов без врачей (в CSV у них нет Doctor name).
        Ожидаемые: Lymphatic Drainage Massage (add on), Microcurrent Treatment,
        Teen Facial, Biorepeel, Vein Laser Treatment (L), TRT Consultation,
        Intimate Rejuvenation Femilift package.
        """
        issue = get_issue(stats_jumeirah["services"]["issues"], "no_practitioners")
        count = issue["count"] if issue else 0
        assert count == EXPECTED_NO_PRACTITIONERS_JUM, (
            f"Jumeirah: ожидалось {EXPECTED_NO_PRACTITIONERS_JUM} без врачей, "
            f"найдено {count}. Появились новые или исчезли?"
        )

    def test_szr_exact(self, stats_szr):
        """
        SZR: ровно 4 сервиса без врачей.
        Ожидаемые: Dermaplaning, Face Sculpt (Danielle jum-only),
        Biorepeel, Ulthera (нет врача в CSV).
        """
        issue = get_issue(stats_szr["services"]["issues"], "no_practitioners")
        count = issue["count"] if issue else 0
        assert count == EXPECTED_NO_PRACTITIONERS_SZR, (
            f"SZR: ожидалось {EXPECTED_NO_PRACTITIONERS_SZR} без врачей, "
            f"найдено {count}. Появились новые или исчезли?"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. MISSING DURATION — должно быть 0 (всё исправлено)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMissingDuration:

    def test_jumeirah_none_missing(self, stats_jumeirah):
        """Jumeirah: duration заполнен у всех (LABIAPLASTY=120, Intimate Rejuvenation=60)."""
        issue = get_issue(stats_jumeirah["services"]["issues"], "missing_duration")
        assert issue is None, (
            f"Jumeirah: {issue['message']}. "
            "Пересоздайте сервисы с duration_minutes."
        )

    def test_szr_none_missing(self, stats_szr):
        """SZR: duration заполнен у всех (Hair Transplant=480, SMP=120, Dentistry=60)."""
        issue = get_issue(stats_szr["services"]["issues"], "missing_duration")
        assert issue is None, (
            f"SZR: {issue['message']}. "
            "Пересоздайте сервисы с duration_minutes."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. MISSING PRICE — должно быть 0 (Follow Up = 0.01 AED)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMissingPrice:

    def test_jumeirah_none_missing(self, stats_jumeirah):
        """Jumeirah: цена заполнена (Follow Up/FU Botox/FU Fillers → 0.01 AED)."""
        issue = get_issue(stats_jumeirah["services"]["issues"], "missing_price")
        assert issue is None, (
            f"Jumeirah: {issue['message']}. "
            "Пересоздайте Follow Up сервисы с price_min=0.01."
        )

    def test_szr_none_missing(self, stats_szr):
        """SZR: цена заполнена."""
        issue = get_issue(stats_szr["services"]["issues"], "missing_price")
        assert issue is None, (
            f"SZR: {issue['message']}. "
            "Пересоздайте Follow Up сервисы с price_min=0.01."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. MISSING DESCRIPTION — ожидаемо (в CSV нет описаний)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMissingDescription:

    def test_jumeirah(self, stats_jumeirah):
        """Jumeirah: почти все без описания (CSV не содержит описаний). Информационный."""
        issue = get_issue(stats_jumeirah["services"]["issues"], "missing_description")
        if issue:
            total = stats_jumeirah["services"]["count"]
            print(f"\n  INFO: Jumeirah: {issue['count']}/{total} services без описания")

    def test_szr(self, stats_szr):
        """SZR: все без описания. Информационный."""
        issue = get_issue(stats_szr["services"]["issues"], "missing_description")
        if issue:
            total = stats_szr["services"]["count"]
            print(f"\n  INFO: SZR: {issue['count']}/{total} services без описания")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. EMPTY CATEGORIES — должно быть 0
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmptyCategories:

    def test_jumeirah_no_empty(self, stats_jumeirah):
        """Jumeirah: не должно быть пустых категорий."""
        issue = get_issue(stats_jumeirah["categories"]["issues"], "empty_category")
        assert issue is None, (
            f"Jumeirah: {issue['message']}. "
            f"Удалите SZR-only и мусорные категории."
        )

    def test_szr_no_empty(self, stats_szr):
        """SZR: не должно быть пустых категорий."""
        issue = get_issue(stats_szr["categories"]["issues"], "empty_category")
        assert issue is None, (
            f"SZR: {issue['message']}. "
            f"Удалите Jumeirah-only категории."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 7. PRACTITIONERS WITHOUT SERVICES — должно быть 0
# ═══════════════════════════════════════════════════════════════════════════════

class TestPractitionersWithoutServices:

    def test_jumeirah(self, stats_jumeirah, api_practitioners_jumeirah):
        """Jumeirah: все practitioners должны иметь >=1 сервис."""
        issue = get_issue(stats_jumeirah["practitioners"]["issues"], "no_services")
        if not issue:
            return

        idle = [
            p for p in api_practitioners_jumeirah
            if not p.get("is_archived") and p.get("services_count", 0) == 0
        ]
        lines = [f"    ID={p['id']} \"{get_name(p)}\"" for p in idle]
        pytest.fail(
            f"Jumeirah: {len(idle)} practitioners без сервисов:\n"
            + "\n".join(lines)
            + "\n  Удалите их с этого location."
        )

    def test_szr(self, stats_szr, api_practitioners_szr):
        """SZR: все practitioners должны иметь >=1 сервис."""
        issue = get_issue(stats_szr["practitioners"]["issues"], "no_services")
        if not issue:
            return

        idle = [
            p for p in api_practitioners_szr
            if not p.get("is_archived") and p.get("services_count", 0) == 0
        ]
        lines = [f"    ID={p['id']} \"{get_name(p)}\"" for p in idle]
        pytest.fail(
            f"SZR: {len(idle)} practitioners без сервисов:\n"
            + "\n".join(lines)
            + "\n  Удалите их с этого location."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 8. TOO MANY SERVICES (>100) — только допустимые врачи
# ═══════════════════════════════════════════════════════════════════════════════

class TestTooManyServices:
    """
    Допустимые practitioners с >100 сервисов (реальные данные из CSV):
      Jumeirah: Dr. Tatiana Kuznechenkova, Dr. Nataliya Sanytska,
               Dr. Lyn Al Alamy AlHassany
      SZR: Dr. Anna Zakhozha
    """

    def test_jumeirah(self, stats_jumeirah, api_practitioners_jumeirah):
        """Jumeirah: только допустимые врачи могут иметь >100."""
        issue = get_issue(
            stats_jumeirah["practitioners"]["issues"], "too_many_services", "error"
        )
        if not issue:
            return

        over100 = [
            p for p in api_practitioners_jumeirah
            if not p.get("is_archived") and p.get("services_count", 0) > 100
        ]

        for p in over100:
            print(f"\n  Jumeirah >100: \"{get_name(p)}\" = {p.get('services_count')}")

        unexpected = [
            p for p in over100
            if norm(get_name(p)) not in ALLOWED_OVER_100_JUM
        ]
        assert len(unexpected) == 0, (
            f"Неожиданные practitioners с >100 сервисов: "
            + ", ".join(
                f"\"{get_name(p)}\"({p.get('services_count')})"
                for p in unexpected
            )
        )

    def test_szr(self, stats_szr, api_practitioners_szr):
        """SZR: только Dr. Anna Zakhozha может иметь >100."""
        issue = get_issue(
            stats_szr["practitioners"]["issues"], "too_many_services", "error"
        )
        if not issue:
            return

        over100 = [
            p for p in api_practitioners_szr
            if not p.get("is_archived") and p.get("services_count", 0) > 100
        ]

        for p in over100:
            print(f"\n  SZR >100: \"{get_name(p)}\" = {p.get('services_count')}")

        unexpected = [
            p for p in over100
            if norm(get_name(p)) not in ALLOWED_OVER_100_SZR
        ]
        assert len(unexpected) == 0, (
            f"Неожиданные practitioners с >100 сервисов: "
            + ", ".join(
                f"\"{get_name(p)}\"({p.get('services_count')})"
                for p in unexpected
            )
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 9. COUNTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestCounts:

    def test_jumeirah_services(self, stats_jumeirah):
        assert stats_jumeirah["services"]["count"] == 240

    def test_jumeirah_practitioners(self, stats_jumeirah):
        assert stats_jumeirah["practitioners"]["count"] == 18

    def test_jumeirah_categories(self, stats_jumeirah):
        assert stats_jumeirah["categories"]["count"] == 29

    def test_szr_services(self, stats_szr):
        assert stats_szr["services"]["count"] == 248

    def test_szr_practitioners(self, stats_szr):
        assert stats_szr["practitioners"]["count"] == 17

    def test_szr_categories(self, stats_szr):
        assert stats_szr["categories"]["count"] == 19


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

def test_summary(stats_jumeirah, stats_szr):
    """Полный отчёт."""
    for stats, name in [(stats_jumeirah, "Jumeirah"), (stats_szr, "SZR")]:
        print(f"\n  {'─'*50}")
        print(f"  {name}:")
        for section in ["services", "practitioners", "categories"]:
            data = stats[section]
            status = data["status"]
            icon = "✓" if status == "ok" else "⚠" if status == "warning" else "✗"
            print(f"    {icon} {section}: {data['count']} ({status})")
            for issue in data.get("issues", []):
                sev = "✗" if issue["severity"] == "error" else "⚠"
                print(f"        {sev} [{issue['code']}] {issue['message']}")
