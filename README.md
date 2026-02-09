# Hortman Clinics → DialogGauge: Data Sync Pipeline

Автоматизация загрузки данных клиники Hortman (categories, services, practitioners) в DialogGauge API с учётом двух филиалов (locations).

## Архитектура

```
Google Sheets / CSV  →  JSON файлы  →  Sync IDs с API  →  Upload по locations
     (Step 1)            (Step 1)        (Step 2)            (Steps 3-5)
```

## Locations (Филиалы)

| Location ID | Название                | Branch в данных |
| ----------- | ----------------------- | --------------- |
| 17          | Jumeirah                | `jumeirah`      |
| 18          | SZR (Sheikh Zayed Road) | `szr` / `szr`   |

**Правило распределения по branches:**

- `branches: ["jumeirah"]` → только Location 17
- `branches: ["szr"]` → только Location 18
- `branches: ["jumeirah", "szr"]` → оба locations
- `branches: []` (пусто, только у practitioners) → оба locations
- Categories не имеют branches → одинаковые для обоих locations

## Структура проекта

```
refoauto/
├── config/
│   ├── .dg_session.json        # Сессия для DialogGauge API
│   ├── cred.json               # Google API credentials
│   ├── credentials.json        # Google API credentials (альт.)
│   └── sheets_token.json       # Google Sheets токен
├── data/
│   ├── input/
│   │   └── raw_data.csv        # Исходные данные (services, categories)
│   ├── output/                 # ← ОСНОВНЫЕ JSON ФАЙЛЫ
│   │   ├── categories.json     # 35 категорий
│   │   ├── services.json       # 373 сервиса (с branches)
│   │   ├── practitioners.json  # 26 practitioners (с branches)
│   │   └── service_practitioners.json  # 1005 связей service↔practitioner
│   └── api/                    # Ответы API (для отладки)
│       ├── _sync_report.json
│       └── ...
├── scripts/
│   ├── process_data.py              # [Step 1a] CSV → JSON (categories, services)
│   ├── parse_practitioners_sheet.py # [Step 1b] Google Sheets → practitioners JSON
│   ├── sync_with_api.py             # [Step 2]  Sync IDs: local ↔ API
│   ├── fix_locations.py             # [Step 3-5] Upload с учётом locations
│   └── get_categories.py            # Библиотека API (fetch/create/session)
├── models/
│   ├── pydantic_models.py      # Pydantic модели данных
│   └── models.py               # Полные модели DialogGauge
└── docs/
    ├── PROMPT_FOR_CLAUDE_CODE.md
    └── CLAUDE_CODE_CONTEXT.md
```

## Полный цикл: Пошаговая инструкция

### Step 1a: Получить categories + services из CSV

```bash
python scripts/process_data.py
```

**Что делает:** Парсит `data/input/raw_data.csv` и создаёт:

- `data/output/categories.json` — уникальные категории с ID
- `data/output/services.json` — сервисы с `branches` и `category_id`
- `data/output/service_practitioners.json` — связи service↔practitioner

**Когда запускать:** При изменении данных в CSV.

### Step 1b: Получить practitioners из Google Sheets

```bash
python scripts/parse_practitioners_sheet.py
```

**Что делает:** Читает вкладку "Practitioners" из Google Sheets и создаёт:

- `data/output/practitioners.json` — 26 practitioners с полями:
  - `name`, `name_i18n`, `speciality`, `sex`, `languages`
  - `description_i18n` (en + ru), `years_of_experience`
  - `primary/secondary/additional_qualifications`
  - `treat_children`, `treat_children_age`, `branches`

**Когда запускать:** При изменении данных о practitioners в Google Sheets.

**Требования:** Google API credentials в `config/cred.json`.

### Step 2: Синхронизация ID с API

```bash
python scripts/sync_with_api.py                  # Все типы
python scripts/sync_with_api.py --categories-only
python scripts/sync_with_api.py --services-only
python scripts/sync_with_api.py --practitioners-only
```

**Что делает:**

1. Получает данные из API (Location 17)
2. Сравнивает по имени: `name_i18n.en` (normalized)
3. Для совпавших → присваивает API ID
4. Для новых → присваивает `max_api_id + 1, +2, ...`
5. Обновляет `category_id` в services и `service_id/practitioner_id` в service_practitioners
6. Сохраняет отчёт в `data/api/_sync_report.json`

**Когда запускать:** После Step 1, перед загрузкой в API.

### Step 3: Анализ текущего состояния

```bash
python scripts/fix_locations.py --analyze
```

**Что делает:** Показывает:

- Сколько данных на каждом location сейчас
- Сколько должно быть
- Какие действия нужны

### Step 4: Загрузка categories на Location 18 (SZR)

```bash
python scripts/fix_locations.py --step1              # Dry-run (только показать)
python scripts/fix_locations.py --step1 --execute    # Выполнить загрузку
```

**Что делает:** Создаёт 35 категорий на Location 18 (SZR).
Категории одинаковые для обоих locations. На Location 17 они уже есть.

### Step 5: Загрузка services на Location 18 (SZR)

```bash
python scripts/fix_locations.py --step2              # Dry-run
python scripts/fix_locations.py --step2 --execute    # Выполнить
```

**Что делает:** Создаёт 249 сервисов на Location 18:

- 133 с `branches=["szr"]` (только SZR)
- 116 с `branches=["jumeirah","szr"]` (оба locations)

**Важно:** Матчинг по `(name + category)` для предотвращения ошибок с дубликатами имён (например, LHR сервисы существуют в двух категориях с разными branches).

### Step 6: Удаление лишних services с Location 17

```bash
python scripts/fix_locations.py --step3              # Dry-run
python scripts/fix_locations.py --step3 --execute    # Выполнить
```

**Что делает:** Удаляет 133 сервиса с `branches=["szr"]` с Location 17 (Jumeirah), где их быть не должно. Матчинг по `(name + category)`.

### Step 7: Загрузка practitioners на оба locations

```bash
python scripts/fix_locations.py --step4              # Dry-run
python scripts/fix_locations.py --step4 --execute    # Выполнить
```

**Что делает:** Создаёт practitioners на правильных locations:

- Location 17: 20 practitioners (5 jumeirah-only + 15 both/empty)
- Location 18: 21 practitioner (6 szr-only + 15 both/empty)

**API поля (выяснены тестированием):**

- `speciality` → `{"en": "..."}` (i18n, не plain string!)
- `qualifications` → одно поле `qualifications_i18n` (не три отдельных)
- `treats_children` (с "s") вместо `treat_children`

### Step 8: Привязка service-practitioner links

```bash
python scripts/fix_locations.py --step5              # Dry-run
python scripts/fix_locations.py --step5 --execute    # Выполнить
```

**Что делает:** Создаёт связи service↔practitioner на обоих locations.
Endpoint: `POST /locations/{loc}/practitioners/{id}/services` с `{"service_id": ...}`

Фильтрует связи: на каждый location попадают только связи где **и сервис, и practitioner** принадлежат этому location.

## Безопасность

- **Dry-run по умолчанию:** Без `--execute` ни один шаг ничего не делает.
- **Идемпотентность:** Каждый шаг проверяет существующие данные перед созданием.
- **Матчинг по (name + category):** Предотвращает ошибки с одноимёнными сервисами в разных категориях.
- **Сессия:** `config/.dg_session.json` содержит `dg_session` cookie (expires: 7 дней).

## API

- **Base URL:** `https://dialoggauge.yma.health/api`
- **Auth:** Cookie `dg_session` (получается через Playwright OAuth)
- **Client ID:** 15 (Hortman Test Content)

### Endpoints

| Метод  | Endpoint                                                      | Описание                         |
| ------ | ------------------------------------------------------------- | -------------------------------- |
| GET    | `/locations/{loc}/categories?flat=true&include_archived=true` | Список категорий                 |
| POST   | `/locations/{loc}/categories`                                 | Создать категорию                |
| DELETE | `/locations/{loc}/categories/{id}`                            | Архивировать категорию           |
| GET    | `/locations/{loc}/services?include_archived=true`             | Список сервисов                  |
| POST   | `/locations/{loc}/services`                                   | Создать сервис                   |
| DELETE | `/locations/{loc}/services/{id}`                              | Архивировать сервис              |
| GET    | `/locations/{loc}/practitioners?include_archived=true`        | Список practitioners             |
| POST   | `/locations/{loc}/practitioners`                              | Создать practitioner             |
| DELETE | `/locations/{loc}/practitioners/{id}`                         | Удалить practitioner             |
| POST   | `/locations/{loc}/practitioners/{id}/services`                | Привязать сервис к practitioner  |
| GET    | `/clients/wizard/15`                                          | Информация о клиенте и locations |

## Быстрый старт (полный цикл)

```bash
# 1. Получить данные
python scripts/process_data.py                        # categories + services из CSV
python scripts/parse_practitioners_sheet.py           # practitioners из Google Sheets

# 2. Синхронизировать ID
python scripts/sync_with_api.py

# 3. Проверить состояние
python scripts/fix_locations.py --analyze

# 4. Загрузить (в строгом порядке!)
python scripts/fix_locations.py --step1 --execute     # Categories → Location 18
python scripts/fix_locations.py --step2 --execute     # Services → Location 18
python scripts/fix_locations.py --step3 --execute     # Delete wrong services from Location 17
python scripts/fix_locations.py --step4 --execute     # Practitioners → both locations
python scripts/fix_locations.py --step5 --execute     # Service-practitioner links

# 5. Финальная проверка
python scripts/fix_locations.py --analyze
```

## Дублирующиеся имена сервисов

В данных есть 20 сервисов с одинаковыми именами в разных категориях/branches:

- "LHR: Full Face" в **Soprano Titanium** (cat 26) → `branches=["szr"]`
- "LHR: Full Face" в **Polylase MX** (cat 27) → `branches=["jumeirah"]`

Скрипт `fix_locations.py` использует ключ **(name + category)** для корректного матчинга.

## Category ID Mapping (Local → API)

| Local ID | API ID (Loc 17) | Название                 |
| -------- | --------------- | ------------------------ |
| 1        | 328             | INJECTABLE TREATMENTS    |
| 10       | 329             | AESTHETICS & DERMATOLOGY |
| 11       | 330             | DERMATOLOGY              |
| ...      | ...             | ...                      |
| 43       | 362             | DENTISTRY                |

Полный маппинг генерируется автоматически при запуске `sync_with_api.py`.
