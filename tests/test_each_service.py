#!/usr/bin/env python3
"""
Атомарные тесты для КАЖДОГО сервиса.
Сравнивает JSON (распарсенные данные) с CSV (исходник из Google Sheets).

Для каждого сервиса проверяет:
  - Категория правильная
  - Цена правильная
  - Длительность правильная
  - Количество врачей правильное
  - Описания из обоих источников выводятся для сравнения

Запускай ПЕРЕД отправкой данных по API!

Использование:
    pytest tests/test_each_service.py -v              # все тесты
    pytest tests/test_each_service.py -v -x           # остановиться на первом FAIL
    pytest tests/test_each_service.py -v -k "ID_001"  # один конкретный сервис
    pytest tests/test_each_service.py -v -s            # с выводом описаний
"""

import csv
import json
import re
from pathlib import Path

import pytest

# ─── Пути к файлам ───────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
CSV_FILE = ROOT / "data" / "input" / "raw_data.csv"
SERVICES_JSON = ROOT / "data" / "output" / "services.json"
CATEGORIES_JSON = ROOT / "data" / "output" / "categories.json"
SP_JSON = ROOT / "data" / "output" / "service_practitioners.json"
PRACTITIONERS_JSON = ROOT / "data" / "output" / "practitioners.json"


# ═══════════════════════════════════════════════════════════════════════════════
# Парсеры — ровно те же правила что в process_data.py
# ═══════════════════════════════════════════════════════════════════════════════

def parse_price_from_csv(raw: str):
    """
    Парсит цену из CSV точно как process_data.py.
    Возвращает (price_min, price_max, has_vat).

    '500 + VAT'  → (500, 500, True)
    '1,500'      → (1500, 1500, False)
    '0'          → (None, None, False)
    ''           → (None, None, False)
    """
    if not raw or raw.strip() == "" or raw.strip() == "0":
        return None, None, False

    has_vat = "vat" in raw.lower()

    # Убрать "+ VAT", "+VAT", "AED"
    clean = re.sub(r'\s*\+?\s*vat', '', raw, flags=re.IGNORECASE)
    clean = re.sub(r'\s*aed', '', clean, flags=re.IGNORECASE)
    clean = clean.strip()

    match = re.search(r'([\d,]+(?:\.\d+)?)', clean)
    if match:
        value = float(match.group(1).replace(',', ''))
        return value, value, has_vat

    return None, None, has_vat


def parse_duration_from_csv(raw: str):
    """
    Парсит длительность из CSV точно как process_data.py.
    Возвращает int | None.

    '30 min'    → 30
    '1 hour'    → 60
    '1.5 hour'  → 90
    'Individual' → None
    """
    if not raw or raw.strip() == "":
        return None

    s = raw.strip().lower()

    if "individual" in s or "days" in s or "+" in s:
        return None

    if "min" in s:
        m = re.search(r'(\d+)', s)
        return int(m.group(1)) if m else None

    if "hour" in s:
        m = re.search(r'([\d.]+)', s)
        return int(float(m.group(1)) * 60) if m else None

    m = re.search(r'^(\d+)$', s)
    return int(m.group(1)) if m else None


def parse_service_name_from_csv(raw: str):
    """
    Первая строка = имя, остальные = описание.

    'Consultation\nSeca\nFace Analyzer'
      → name='Consultation', desc='Includes: Seca, Face Analyzer'
    """
    if not raw:
        return "", None
    lines = [l.strip() for l in raw.strip().split('\n') if l.strip()]
    if not lines:
        return "", None
    if len(lines) == 1:
        return lines[0], None
    return lines[0], "Includes: " + ", ".join(lines[1:])


def count_doctors_in_csv(raw: str) -> int:
    """Считает врачей в ячейке (по строкам)."""
    if not raw or raw.strip() == "":
        return 0
    return len([l for l in raw.split('\n') if l.strip()])


def parse_branches_from_csv(raw: str) -> list:
    """'Both' → ['jumeirah','szr'], 'SZR' → ['szr'], etc."""
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


# ═══════════════════════════════════════════════════════════════════════════════
# Загрузка данных
# ═══════════════════════════════════════════════════════════════════════════════

def load_csv_rows() -> list[dict]:
    """Читает CSV и возвращает список строк."""
    with open(CSV_FILE, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # Пропустить дубль заголовка
    if rows and rows[0].get("ID") == "ID":
        rows = rows[1:]
    return rows


def load_json(path: Path) -> list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════════════════
# Подготовка тест-данных
# ═══════════════════════════════════════════════════════════════════════════════

def build_test_pairs():
    """
    Строит пары (csv_row, json_service) для каждого сервиса.
    Матчинг по имени + категории (после sync ID уже другие).
    """
    csv_rows = load_csv_rows()
    services = load_json(SERVICES_JSON)
    categories = load_json(CATEGORIES_JSON)
    sp_links = load_json(SP_JSON)

    # category_id → name (из JSON)
    cat_id_to_name = {}
    for c in categories:
        name = (c.get("name_i18n") or {}).get("en", "")
        cat_id_to_name[c["id"]] = name

    # Считаем practitioners на каждый service_id в JSON
    json_pract_count = {}
    for link in sp_links:
        sid = link["service_id"]
        json_pract_count[sid] = json_pract_count.get(sid, 0) + 1

    # Строим lookup JSON сервисов: (normalized_name, normalized_cat) → service
    def norm(s):
        return (s or "").strip().lower()

    json_lookup = {}
    for svc in services:
        svc_name = norm((svc.get("name_i18n") or {}).get("en", ""))
        cat_name = norm(cat_id_to_name.get(svc.get("category_id"), ""))
        key = (svc_name, cat_name)
        # Если дубль (LHR сервисы) — берём первый
        if key not in json_lookup:
            json_lookup[key] = svc

    # Строим пары
    pairs = []
    for row in csv_rows:
        csv_id = row.get("ID", "?")
        csv_cat = row.get("Category", "")
        csv_name_raw = row.get("Service Name", "")
        csv_name, csv_desc = parse_service_name_from_csv(csv_name_raw)

        key = (norm(csv_name), norm(csv_cat))
        json_svc = json_lookup.get(key)

        pairs.append({
            "csv_id": csv_id,
            "csv_row": row,
            "csv_name": csv_name,
            "csv_desc": csv_desc,
            "csv_cat": csv_cat,
            "json_svc": json_svc,
            "json_pract_count": json_pract_count.get(json_svc["id"], 0) if json_svc else 0,
        })

    return pairs


# Кешируем чтобы не перечитывать для каждого теста
_PAIRS = None

def get_pairs():
    global _PAIRS
    if _PAIRS is None:
        _PAIRS = build_test_pairs()
    return _PAIRS


def make_test_id(pair: dict) -> str:
    """Красивое имя для теста: ID_001_Aesthetics_Consultation"""
    csv_id = pair["csv_id"]
    name = pair["csv_name"][:40].replace(" ", "_").replace("/", "_")
    return f"ID_{str(csv_id).zfill(3)}_{name}"


# ═══════════════════════════════════════════════════════════════════════════════
# ТЕСТЫ
# ═══════════════════════════════════════════════════════════════════════════════


# ---------- 1. Каждый CSV сервис найден в JSON ----------

@pytest.mark.parametrize(
    "pair",
    get_pairs(),
    ids=[make_test_id(p) for p in get_pairs()],
)
def test_service_exists_in_json(pair):
    """Сервис из CSV должен существовать в JSON."""
    assert pair["json_svc"] is not None, (
        f"\n"
        f"  CSV ID={pair['csv_id']}: \"{pair['csv_name']}\"\n"
        f"  Категория: \"{pair['csv_cat']}\"\n"
        f"  НЕ НАЙДЕН в services.json!"
    )


# ---------- 2. Категория правильная ----------

@pytest.mark.parametrize(
    "pair",
    [p for p in get_pairs() if p["json_svc"] is not None],
    ids=[make_test_id(p) for p in get_pairs() if p["json_svc"] is not None],
)
def test_category_correct(pair):
    """Категория в JSON совпадает с категорией в CSV."""
    csv_cat = pair["csv_cat"].strip().lower()

    # Достаём имя категории из JSON
    categories = load_json(CATEGORIES_JSON)
    cat_id_to_name = {c["id"]: (c.get("name_i18n") or {}).get("en", "") for c in categories}
    json_cat = cat_id_to_name.get(pair["json_svc"]["category_id"], "???").strip().lower()

    assert csv_cat == json_cat, (
        f"\n"
        f"  Сервис: \"{pair['csv_name']}\"\n"
        f"  CSV категория:  \"{pair['csv_cat']}\"\n"
        f"  JSON категория: \"{json_cat}\"\n"
        f"  НЕ СОВПАДАЮТ!"
    )


# ---------- 3. Цена правильная ----------

@pytest.mark.parametrize(
    "pair",
    [p for p in get_pairs() if p["json_svc"] is not None],
    ids=[make_test_id(p) for p in get_pairs() if p["json_svc"] is not None],
)
def test_price_correct(pair):
    """Цена в JSON совпадает с ценой в CSV."""
    csv_price_raw = pair["csv_row"].get("Price", "")
    csv_min, csv_max, csv_has_vat = parse_price_from_csv(csv_price_raw)

    json_svc = pair["json_svc"]
    json_min = json_svc.get("price_min")
    json_max = json_svc.get("price_max")

    assert csv_min == json_min, (
        f"\n"
        f"  Сервис: \"{pair['csv_name']}\"\n"
        f"  CSV цена:  \"{csv_price_raw}\" → min={csv_min}\n"
        f"  JSON цена: min={json_min}\n"
        f"  price_min НЕ СОВПАДАЕТ!"
    )
    assert csv_max == json_max, (
        f"\n"
        f"  Сервис: \"{pair['csv_name']}\"\n"
        f"  CSV цена:  \"{csv_price_raw}\" → max={csv_max}\n"
        f"  JSON цена: max={json_max}\n"
        f"  price_max НЕ СОВПАДАЕТ!"
    )


# ---------- 4. Длительность правильная ----------

@pytest.mark.parametrize(
    "pair",
    [p for p in get_pairs() if p["json_svc"] is not None],
    ids=[make_test_id(p) for p in get_pairs() if p["json_svc"] is not None],
)
def test_duration_correct(pair):
    """Длительность в JSON совпадает с CSV."""
    csv_dur_raw = pair["csv_row"].get("Duration", "")
    csv_dur = parse_duration_from_csv(csv_dur_raw)

    json_dur = pair["json_svc"].get("duration_minutes")

    assert csv_dur == json_dur, (
        f"\n"
        f"  Сервис: \"{pair['csv_name']}\"\n"
        f"  CSV длительность:  \"{csv_dur_raw}\" → {csv_dur} мин\n"
        f"  JSON длительность: {json_dur} мин\n"
        f"  НЕ СОВПАДАЕТ!"
    )


# ---------- 5. Количество врачей правильное ----------

@pytest.mark.parametrize(
    "pair",
    [p for p in get_pairs() if p["json_svc"] is not None],
    ids=[make_test_id(p) for p in get_pairs() if p["json_svc"] is not None],
)
def test_practitioner_count_correct(pair):
    """Количество врачей для сервиса совпадает с CSV."""
    csv_docs_raw = pair["csv_row"].get("Doctor name", "")
    csv_count = count_doctors_in_csv(csv_docs_raw)
    json_count = pair["json_pract_count"]

    assert csv_count == json_count, (
        f"\n"
        f"  Сервис: \"{pair['csv_name']}\"\n"
        f"  CSV врачи ({csv_count}):\n"
        + "\n".join(f"    - {d.strip()}" for d in csv_docs_raw.split('\n') if d.strip()) +
        f"\n  JSON врачи ({json_count}) — из service_practitioners.json\n"
        f"  КОЛИЧЕСТВО НЕ СОВПАДАЕТ!"
    )


# ---------- 6. Branches правильные ----------

@pytest.mark.parametrize(
    "pair",
    [p for p in get_pairs() if p["json_svc"] is not None],
    ids=[make_test_id(p) for p in get_pairs() if p["json_svc"] is not None],
)
def test_branches_correct(pair):
    """Branches в JSON совпадают с CSV."""
    csv_branch_raw = pair["csv_row"].get("Available In Branches", "")
    csv_branches = sorted(parse_branches_from_csv(csv_branch_raw))

    json_branches = sorted(pair["json_svc"].get("branches", []))

    assert csv_branches == json_branches, (
        f"\n"
        f"  Сервис: \"{pair['csv_name']}\"\n"
        f"  CSV branches:  \"{csv_branch_raw}\" → {csv_branches}\n"
        f"  JSON branches: {json_branches}\n"
        f"  НЕ СОВПАДАЮТ!"
    )


# ---------- 7. Описания из обоих источников (для визуальной сверки) ----------

@pytest.mark.parametrize(
    "pair",
    [p for p in get_pairs() if p["json_svc"] is not None],
    ids=[make_test_id(p) for p in get_pairs() if p["json_svc"] is not None],
)
def test_print_descriptions(pair, capsys):
    """
    Выводит описания из обоих источников для ручной сверки.
    Этот тест всегда PASS — он только печатает.

    Запусти с -s чтобы увидеть вывод:
        pytest tests/test_each_service.py::test_print_descriptions -s
    """
    csv_name_raw = pair["csv_row"].get("Service Name", "")
    csv_name, csv_desc = parse_service_name_from_csv(csv_name_raw)

    json_svc = pair["json_svc"]
    json_name = (json_svc.get("name_i18n") or {}).get("en", "")
    json_desc = (json_svc.get("description_i18n") or {}).get("en", "")
    json_note = (json_svc.get("price_note_i18n") or {}).get("en", "")
    csv_note = pair["csv_row"].get("Note", "").strip()

    print(f"\n{'─'*60}")
    print(f"  CSV ID={pair['csv_id']} | JSON ID={json_svc['id']}")
    print(f"  CSV name:  {csv_name}")
    print(f"  JSON name: {json_name}")
    if csv_desc or json_desc:
        print(f"  CSV desc:  {csv_desc or '(пусто)'}")
        print(f"  JSON desc: {json_desc or '(пусто)'}")
    if csv_note or json_note:
        print(f"  CSV note:  {csv_note or '(пусто)'}")
        print(f"  JSON note: {json_note or '(пусто)'}")


# ═══════════════════════════════════════════════════════════════════════════════
# СУММАРНЫЙ ОТЧЁТ — один тест с полной таблицей
# ═══════════════════════════════════════════════════════════════════════════════

def test_summary_report():
    """
    Печатает сводную таблицу ВСЕХ сервисов с результатами проверки.
    Запусти с -s:
        pytest tests/test_each_service.py::test_summary_report -s
    """
    pairs = get_pairs()
    categories = load_json(CATEGORIES_JSON)
    cat_id_to_name = {c["id"]: (c.get("name_i18n") or {}).get("en", "") for c in categories}

    errors = []
    ok = 0

    for p in pairs:
        csv_id = p["csv_id"]
        name = p["csv_name"]
        row = p["csv_row"]
        svc = p["json_svc"]

        if svc is None:
            errors.append((csv_id, name, "НЕ НАЙДЕН В JSON"))
            continue

        problems = []

        # Категория
        csv_cat = row.get("Category", "").strip().lower()
        json_cat = cat_id_to_name.get(svc.get("category_id"), "???").strip().lower()
        if csv_cat != json_cat:
            problems.append(f"категория: csv=\"{csv_cat}\" json=\"{json_cat}\"")

        # Цена
        csv_min, csv_max, _ = parse_price_from_csv(row.get("Price", ""))
        if csv_min != svc.get("price_min"):
            problems.append(f"цена min: csv={csv_min} json={svc.get('price_min')}")
        if csv_max != svc.get("price_max"):
            problems.append(f"цена max: csv={csv_max} json={svc.get('price_max')}")

        # Длительность
        csv_dur = parse_duration_from_csv(row.get("Duration", ""))
        if csv_dur != svc.get("duration_minutes"):
            problems.append(f"длительность: csv={csv_dur} json={svc.get('duration_minutes')}")

        # Practitioners
        csv_count = count_doctors_in_csv(row.get("Doctor name", ""))
        json_count = p["json_pract_count"]
        if csv_count != json_count:
            problems.append(f"врачи: csv={csv_count} json={json_count}")

        # Branches
        csv_branches = sorted(parse_branches_from_csv(row.get("Available In Branches", "")))
        json_branches = sorted(svc.get("branches", []))
        if csv_branches != json_branches:
            problems.append(f"branches: csv={csv_branches} json={json_branches}")

        if problems:
            errors.append((csv_id, name, "; ".join(problems)))
        else:
            ok += 1

    # Вывод
    print(f"\n{'='*70}")
    print(f"  СВОДНЫЙ ОТЧЁТ: {ok} OK / {len(errors)} ОШИБОК / {len(pairs)} ВСЕГО")
    print(f"{'='*70}")

    if errors:
        print(f"\nОшибки:")
        for csv_id, name, problem in errors:
            print(f"  ID={csv_id}: \"{name[:45]}\"")
            print(f"    → {problem}")
        print()

    assert len(errors) == 0, f"{len(errors)} сервисов с ошибками (см. вывод выше)"
