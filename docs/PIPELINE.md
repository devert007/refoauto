# Полный Pipeline: данные Hortman Clinics → DialogGauge API

## Обзор

Проект синхронизирует данные клиник (категории, сервисы, врачи) из Google Sheets в DialogGauge API для двух локаций:

| Location ID | Название  | Branch код |
|-------------|-----------|------------|
| 17          | Jumeirah  | `jumeirah` |
| 18          | SZR       | `szr`      |

---

## Структура проекта

```
refoauto/
├── config/                          # Секреты (НЕ коммитить)
│   ├── .dg_session.json             # Сессия DialogGauge API (авто-обновляется)
│   ├── cred.json                    # Google API credentials
│   └── sheets_token.json            # Google Sheets OAuth token
│
├── data/
│   ├── input/
│   │   └── raw_data.csv             # Исходный CSV из Google Sheets (373 строки)
│   ├── output/                      # Нормализованные JSON (ОСНОВНЫЕ ДАННЫЕ)
│   │   ├── categories.json          # 35 категорий
│   │   ├── services.json            # 373 сервиса с branches
│   │   ├── practitioners.json       # 26 врачей с полными профилями
│   │   └── service_practitioners.json  # 1004 связи сервис↔врач
│   └── api/                         # Кеш ответов API (для отладки)
│
├── scripts/                         # Скрипты обработки и загрузки
│   ├── process_data.py              # CSV → 4 JSON файла
│   ├── regenerate_data.py           # Полная перегенерация JSON
│   ├── parse_practitioners_sheet.py # Google Sheets → practitioners.json
│   ├── sync_with_api.py             # Синхронизация локальных ID с API
│   ├── fix_locations.py             # Загрузка на оба location (5 шагов)
│   └── get_categories.py            # API-клиент (fetch/create)
│
├── tests/                           # Тесты (pytest)
│   ├── test_each_service.py         # Атомарные: каждый сервис vs CSV
│   ├── test_data_integrity.py       # Целостность JSON файлов
│   ├── test_api_validation.py       # Валидация состояния API после загрузки
│   └── test_content_stats.py        # Проверка /content-stats endpoint
│
└── docs/                            # Документация
    ├── PIPELINE.md                  # ← ЭТОТ ФАЙЛ
    ├── PROMPT_1_PARSE_DATA.md       # Инструкция для Claude: парсинг
    ├── PROMPT_2_VALIDATE_DATA.md    # Инструкция для Claude: валидация
    ├── PROMPT_3_SYNC_IDS.md         # Инструкция для Claude: синхронизация ID
    └── PROMPT_4_MANUAL_UPLOAD.md    # Инструкция для ручной загрузки
```

---

## Pipeline: 6 этапов

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  1. ПАРСИНГ  │───→│ 2. ТЕСТЫ     │───→│ 3. SYNC IDs  │
│  CSV → JSON  │    │ (локальные)  │    │ local ↔ API  │
└──────────────┘    └──────────────┘    └──────────────┘
                                              │
┌──────────────┐    ┌──────────────┐          │
│ 5. ТЕСТЫ     │←───│ 4. ЗАГРУЗКА  │←─────────┘
│ (API)        │    │ POST → API   │
└──────────────┘    └──────────────┘
       │
       ▼
┌──────────────┐
│ 6. МОНИТОРИНГ│
│ content-stats│
└──────────────┘
```

---

## Этап 1: Парсинг данных (CSV → JSON)

**Скрипты:** `process_data.py` или `regenerate_data.py`

**Что делает:**
Читает `data/input/raw_data.csv` и создаёт 4 нормализованных JSON файла:

| Файл | Описание | Ключевые поля |
|------|----------|---------------|
| `categories.json` | 35 уникальных категорий | `id`, `name_i18n.en` |
| `services.json` | 373 сервиса | `id`, `name_i18n.en`, `category_id`, `price_min/max`, `duration_minutes`, `branches` |
| `practitioners.json` | 26 врачей | `id`, `name`, `name_i18n.en`, `speciality`, `sex`, `languages`, `branches` |
| `service_practitioners.json` | 1004 связи | `service_id`, `practitioner_id` |

**Как запустить:**

```bash
cd "/media/devert007/Windows 10 Compact/Users/devert/Desktop/работа YMA health/refoauto"

# Вариант 1: только CSV парсинг
python scripts/process_data.py

# Вариант 2: полная регенерация (сохраняет practitioners из Google Sheets)
python scripts/regenerate_data.py
```

**Правила парсинга:**
- Цена: `"500 + VAT"` → `price_min=500, price_max=500, has_vat=true`
- Длительность: `"30 min"` → `30`, `"1 hour"` → `60`, `"Individual"` → `None`
- Имя сервиса: первая строка = имя, остальные → `"Includes: ..."` (описание)
- Branches: `"Both"` → `["jumeirah","szr"]`, `"SZR"` → `["szr"]`, пусто → `["jumeirah","szr"]`
- Врачи: разделены `\n` в ячейке "Doctor name"

---

## Этап 2: Тесты ПЕРЕД загрузкой (ОБЯЗАТЕЛЬНЫЕ)

### 2a. Атомарные тесты каждого сервиса — `test_each_service.py`

**Что проверяет** (для КАЖДОГО из 373 сервисов):

| Тест | Описание |
|------|----------|
| `test_service_exists_in_json` | Сервис из CSV найден в JSON |
| `test_category_correct` | Категория совпадает с CSV |
| `test_price_correct` | Цена (min/max) совпадает с CSV |
| `test_duration_correct` | Длительность совпадает с CSV |
| `test_practitioner_count_correct` | Количество врачей совпадает с CSV |
| `test_branches_correct` | Branches совпадают с CSV |
| `test_print_descriptions` | Печатает описания из обоих источников (для ручной сверки) |
| `test_summary_report` | Сводная таблица всех проверок |

**Как запустить:**

```bash
# Все тесты (быстро, ~1 сек, НЕ требует API)
pytest tests/test_each_service.py -v

# Остановиться на первой ошибке
pytest tests/test_each_service.py -v -x

# Один конкретный сервис
pytest tests/test_each_service.py -v -k "ID_001"

# С выводом описаний (для ручной сверки)
pytest tests/test_each_service.py -v -s -k "test_print_descriptions"

# Только сводный отчёт
pytest tests/test_each_service.py -v -s -k "test_summary_report"
```

**Пример вывода ошибки:**
```
FAILED test_price_correct[ID_042_Accent_Prime_RF]
  Сервис: "Accent Prime – RF and Ultrasound - Small Area"
  CSV цена:  "1,500 + VAT" → min=1500.0
  JSON цена: min=None
  price_min НЕ СОВПАДАЕТ!
```

### 2b. Целостность JSON — `test_data_integrity.py`

**Что проверяет:**

| Класс тестов | Описание |
|-------------|----------|
| `TestFilesExist` | Все 4 JSON файла существуют и не пустые |
| `TestUniqueIds` | Все ID уникальны (нет дублей) |
| `TestBranchConsistency` | Нет `"srz"` вместо `"szr"`, все branches валидные |
| `TestReferentialIntegrity` | Все FK валидные: service→category, sp→service, sp→practitioner |
| `TestPractitionerCompleteness` | У каждого врача есть обязательные поля, пробелы в "Dr.Name" |
| `TestNameMatching` | Нормализация имён работает, em-dash vs dash |
| `TestServicePractitionerCounts` | Cherry Lou=18 links, Kinan=49, Shamoun=0 на SZR |
| `TestCsvCrossValidation` | Перекрёстная проверка JSON↔CSV |
| `TestStep5Simulation` | Симуляция step5 (dry-run без API) |
| `TestSourceConsistency` | Practitioners из разных источников согласованы |

**Как запустить:**

```bash
# Все тесты (быстро, ~1 сек, НЕ требует API)
pytest tests/test_data_integrity.py -v

# Конкретный класс
pytest tests/test_data_integrity.py -v -k "TestUniqueIds"

# С подробными traceback
pytest tests/test_data_integrity.py -v --tb=long
```

### Когда запускать тесты Этапа 2

```
ПРАВИЛО: ВСЕГДА запускай ОБА теста перед любой загрузкой.
Если хотя бы 1 тест падает → СТОП, не загружай!
```

```bash
# Быстрая полная проверка перед загрузкой (2 секунды):
pytest tests/test_each_service.py tests/test_data_integrity.py -v
```

---

## Этап 3: Синхронизация ID (local ↔ API)

**Скрипт:** `sync_with_api.py`

**Что делает:**
1. Получает текущие данные из API (categories, services, practitioners)
2. Сопоставляет по нормализованному имени (`name_i18n.en`)
3. Присваивает API ID если нашёл совпадение
4. Присваивает `max_api_id + 1` если новый
5. Обновляет ВСЕ ссылки (category_id в services, id в service_practitioners)

**Как запустить:**

```bash
python scripts/sync_with_api.py
```

**Когда нужен:** Перед ПЕРВОЙ загрузкой или после изменения данных в API вручную.

**Когда НЕ нужен:** `fix_locations.py` сам матчит по именам — можно пропустить этот шаг.

---

## Этап 4: Загрузка (POST → API)

**Скрипт:** `fix_locations.py`

**5 шагов (строго по порядку):**

```bash
# 0. Анализ текущего состояния (safe, ничего не меняет)
python scripts/fix_locations.py --analyze

# 1. Categories → Location 18 (SZR)
python scripts/fix_locations.py --step1             # dry-run
python scripts/fix_locations.py --step1 --execute   # загрузка

# 2. Services → Location 18 (SZR)
python scripts/fix_locations.py --step2             # dry-run
python scripts/fix_locations.py --step2 --execute   # загрузка

# 3. Удалить szr-only сервисы с Location 17 (Jumeirah)
python scripts/fix_locations.py --step3             # dry-run
python scripts/fix_locations.py --step3 --execute   # удаление

# 4. Practitioners → оба locations
python scripts/fix_locations.py --step4             # dry-run
python scripts/fix_locations.py --step4 --execute   # загрузка

# 5. Связи Service↔Practitioner → оба locations
python scripts/fix_locations.py --step5             # dry-run
python scripts/fix_locations.py --step5 --execute   # загрузка
```

**Безопасность:**
- Каждый шаг по умолчанию dry-run (показывает что сделает, НЕ выполняет)
- `--execute` нужен для реального выполнения
- Все операции идемпотентны (повторный запуск НЕ создаёт дубли)
- Матчинг по (name + category) для сервисов, по name для остального

**Зависимости шагов:**
```
Step 1 (categories)  ← нет зависимостей
   ↓
Step 2 (services)    ← зависит от Step 1 (category_id)
   ↓
Step 3 (delete)      ← независим (можно пропустить если не нужно)
   ↓
Step 4 (practitioners) ← независим от Step 2-3
   ↓
Step 5 (links)       ← зависит от Step 2 + Step 4
```

---

## Этап 5: Тесты ПОСЛЕ загрузки (API validation)

### 5a. Валидация API — `test_api_validation.py`

> **Требует:** активная сессия в `config/.dg_session.json`

**Что проверяет:**

| Класс тестов | Описание |
|-------------|----------|
| `TestSzrPractitionerServiceCounts` | Cherry Lou=18, Kinan=49, Shamoun=0 на SZR |
| `TestServiceNameMatching` | Все локальные SZR сервисы есть на API, спецсимволы ОК |
| `TestPractitionersOnApi` | Все ожидаемые practitioners есть на API |
| `TestDetailedLinkInspection` | Детальная инспекция конкретных врачей |

**Как запустить:**

```bash
# Все API тесты (~10 сек, ТРЕБУЕТ API)
pytest tests/test_api_validation.py -v

# С подробным выводом
pytest tests/test_api_validation.py -v -s
```

### 5b. Content-Stats мониторинг — `test_content_stats.py`

> **Требует:** активная сессия в `config/.dg_session.json`

**Что проверяет** (через API endpoint `/locations/{id}/content-stats`):

| Тест | Jumeirah | SZR | Что значит |
|------|----------|-----|------------|
| `duplicate_names` | **0** (strict) | **0** (strict) | Дублей имён нет |
| `no_practitioners` | **=7** (exact) | **=4** (exact) | Сервисы без врачей (нет данных в CSV) |
| `missing_duration` | **0** (strict) | **0** (strict) | Длительность заполнена |
| `missing_price` | **0** (strict) | **0** (strict) | Цена заполнена |
| `missing_description` | ~236 (info) | ~248 (info) | Нет описаний в CSV (не ошибка) |
| `empty_category` | **0** (strict) | **0** (strict) | Пустых категорий нет |
| `no_services` | **0** (strict) | **0** (strict) | Врачи без сервисов удалены |
| `too_many_services` | ≤3 allowed | ≤1 allowed | Только конкретные врачи >100 |
| Counts | 240/18/29 | 248/17/19 | services/practitioners/categories |

**Как запустить:**

```bash
# Все content-stats тесты (~2 сек, ТРЕБУЕТ API)
pytest tests/test_content_stats.py -v -s

# Только определённый тип
pytest tests/test_content_stats.py -v -k "duplicate"
pytest tests/test_content_stats.py -v -k "duration"
pytest tests/test_content_stats.py -v -k "jumeirah"
```

---

## Этап 6: Полный прогон всех тестов

```bash
# ВСЕ тесты разом (локальные + API, ~15 сек):
pytest tests/ -v -s

# Только локальные тесты (БЕЗ API, ~2 сек):
pytest tests/test_each_service.py tests/test_data_integrity.py -v

# Только API тесты (ТРЕБУЕТ сессию, ~12 сек):
pytest tests/test_api_validation.py tests/test_content_stats.py -v -s
```

---

## Как написать свой тест

### Пример 1: Проверить конкретный сервис

Добавь в `tests/test_each_service.py` или создай отдельный файл:

```python
def test_my_specific_service():
    """Проверяем что 'Botox Full Face' имеет цену 2500."""
    services = load_json(SERVICES_JSON)
    
    svc = next(
        (s for s in services 
         if "botox full face" in (s.get("name_i18n") or {}).get("en", "").lower()),
        None
    )
    
    assert svc is not None, "Botox Full Face не найден"
    assert svc["price_min"] == 2500, f"Ожидалось 2500, получили {svc['price_min']}"
```

### Пример 2: Проверить врача на API

Добавь в `tests/test_api_validation.py`:

```python
def test_my_doctor_has_correct_services(api_practitioners_szr):
    """Dr. My Doctor должен иметь 15 сервисов на SZR."""
    for p in api_practitioners_szr:
        if "my doctor" in get_name_en(p).lower():
            assert p.get("services_count", 0) == 15
            return
    pytest.fail("Dr. My Doctor не найден на SZR API")
```

### Пример 3: Проверить content-stats issue

Добавь в `tests/test_content_stats.py`:

```python
def test_jumeirah_no_new_issue(stats_jumeirah):
    """На Jumeirah не должно быть issue с кодом 'my_new_code'."""
    issue = get_issue(stats_jumeirah["services"]["issues"], "my_new_code")
    assert issue is None, f"Появилась новая проблема: {issue['message']}"
```

### Структура теста (правила):

```python
# 1. Имя начинается с test_
# 2. Используй fixtures (stats_jumeirah, api_practitioners_szr, и т.д.)
# 3. assert с понятным сообщением об ошибке
# 4. Один тест = одна проверка

def test_what_is_tested(fixture_name):
    """Описание что проверяем (docstring обязателен)."""
    # Arrange — подготовка
    data = fixture_name
    
    # Act — действие
    result = find_something(data)
    
    # Assert — проверка
    assert result == expected, f"Описание ошибки: got {result}"
```

---

## Полная шпаргалка: запуск с нуля

```bash
# Рабочая папка
cd "/media/devert007/Windows 10 Compact/Users/devert/Desktop/работа YMA health/refoauto"

# ── 1. ПАРСИНГ ──────────────────────────────────────────
python scripts/regenerate_data.py

# ── 2. ТЕСТЫ ПЕРЕД ЗАГРУЗКОЙ (ОБЯЗАТЕЛЬНО!) ────────────
pytest tests/test_each_service.py tests/test_data_integrity.py -v
# Если FAIL → исправить данные → перезапустить тесты
# Если OK   → продолжить

# ── 3. ЗАГРУЗКА (по шагам) ─────────────────────────────
python scripts/fix_locations.py --analyze             # анализ
python scripts/fix_locations.py --step1 --execute     # categories → SZR
python scripts/fix_locations.py --step2 --execute     # services → SZR
python scripts/fix_locations.py --step3 --execute     # delete szr-only from Jum
python scripts/fix_locations.py --step4 --execute     # practitioners → both
python scripts/fix_locations.py --step5 --execute     # links → both

# ── 4. ТЕСТЫ ПОСЛЕ ЗАГРУЗКИ ───────────────────────────
pytest tests/test_api_validation.py -v -s             # API validation
pytest tests/test_content_stats.py -v -s              # content-stats checks
# Если FAIL → исправить → перезапустить тесты
```

---

## Troubleshooting

### Сессия истекла (401)

```bash
rm config/.dg_session.json
python scripts/get_categories.py --categories
# → откроется браузер для авторизации через Google
```

### Тест падает: "duplicate service IDs"

```bash
# Проверить дубли
python3 -c "
import json
from collections import Counter
with open('data/output/services.json') as f:
    ids = [s['id'] for s in json.load(f)]
dupes = [x for x,c in Counter(ids).items() if c>1]
print(f'Дубли: {dupes}' if dupes else 'Дублей нет')
"
```

### Тест падает: "content-stats duplicate_names"

Сервис с одинаковым именем в разных категориях. Нужно переименовать:
1. Найти дубли через content-stats
2. Удалить старый сервис: `DELETE /locations/{loc}/services/{id}`
3. Создать новый с уникальным именем: добавить суффикс категории

### API возвращает "Method Not Allowed" (405) при PATCH

API не поддерживает PATCH/PUT для сервисов. Для изменения:
1. Запомнить linked practitioners
2. `DELETE /locations/{loc}/services/{id}`
3. `POST /locations/{loc}/services` с новыми данными
4. Переподвязать practitioners

### Количество сервисов у врача на API больше ожидаемого

API не удаляет старые связи при пересоздании. Это нормально.
Тесты проверяют `actual >= expected` (не строгое равенство).

---

## Что проверяет каждый тестовый файл (сводка)

```
tests/
├── test_each_service.py       ← 373×7 = 2611 тестов  │ Локальные
│   └── Каждый сервис: category, price, duration,      │ (без API)
│       practitioner count, branches, description       │ ~1 сек
│                                                       │
├── test_data_integrity.py     ← ~40 тестов             │ Локальные
│   └── Unique IDs, FK integrity, branches, names,      │ (без API)
│       step5 simulation, CSV cross-validation          │ ~1 сек
│                                                       │
├── test_api_validation.py     ← ~12 тестов             │ API
│   └── Practitioner service counts, name matching,     │ (нужна сессия)
│       special chars, practitioners on correct location │ ~10 сек
│                                                       │
└── test_content_stats.py      ← 23 теста               │ API
    └── duplicate_names=0, no_practitioners=7/4,        │ (нужна сессия)
        missing_duration=0, missing_price=0,            │ ~2 сек
        empty_categories=0, no_services=0, counts       │
```

---

## Ожидаемые предупреждения (НЕ ошибки)

Эти issues в content-stats **нормальны** и не исправимы без новых данных:

| Issue | Jumeirah | SZR | Причина |
|-------|----------|-----|---------|
| `no_practitioners` | 7 | 4 | В CSV у этих сервисов нет Doctor name |
| `missing_description` | 236 | 248 | В CSV нет поля Description |
| `too_many_services` (>100) | 3 врача | 1 врач | Реально много сервисов в CSV |
| `too_many_services` (>50) | 1 врач | 4 врача | Реально много сервисов в CSV |

---

## Зависимости (установка)

```bash
pip install requests playwright pytest google-api-python-client google-auth-oauthlib pydantic
playwright install chromium
```
