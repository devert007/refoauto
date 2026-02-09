# Claude Code Context: DialogGauge Data Sync

## Обзор проекта

Этот проект синхронизирует данные (категории, сервисы, врачи) между локальными JSON файлами и DialogGauge API.

**API Base URL:** `https://dialoggauge.yma.health/api`
**Location ID:** `17` (настраивается в `scripts/get_categories.py`)

---

## Ключевые концепции

### 1. Два типа ID

| Тип          | Где хранится         | Описание                         |
| ------------ | -------------------- | -------------------------------- |
| **Local ID** | `data/output/*.json` | Временные ID, созданные локально |
| **API ID**   | DialogGauge API      | Реальные ID в базе данных        |

**ВАЖНО:** Local ID и API ID — это РАЗНЫЕ числа! При загрузке в API создаётся новый API ID.

### 2. Сравнение по имени, не по ID

Скрипты сравнивают элементы **по нормализованному имени (name_i18n.en)**:

- Приводится к нижнему регистру
- Убираются лишние пробелы и спецсимволы
- `"BOTOX "` == `"botox"` == `"Botox!"`

### 3. Зависимости между сущностями

```
Categories (категории)
    │
    │ category_id (API ID категории!)
    ▼
Services (услуги)
    │
    │ service_id + practitioner_id
    ▼
ServicePractitioners (связи)
    │
    │ practitioner_id
    ▼
Practitioners (врачи)
```

---

## Файловая структура

```
refoauto/
├── config/
│   └── .dg_session.json          # Cookie сессии (автообновление)
│
├── data/
│   ├── output/                   # ЛОКАЛЬНЫЕ данные для загрузки
│   │   ├── categories.json       # Категории с local ID
│   │   ├── services.json         # Сервисы с local ID и local category_id
│   │   ├── practitioners.json    # Врачи с local ID
│   │   └── service_practitioners.json  # Связи
│   │
│   └── api/                      # Ответы от API (для отладки)
│       ├── categories_api_response.json
│       ├── services_api_response.json
│       └── _sync_report.json
│
├── scripts/
│   ├── get_categories.py         # API функции (GET/POST)
│   ├── upload_categories.py      # Загрузка категорий в API
│   ├── upload_services.py        # Загрузка сервисов в API
│   ├── sync_with_api.py          # Синхронизация ID (старый скрипт)
│   └── process_data.py           # Обработка raw_data.csv
│
└── docs/
    ├── UPLOAD_GUIDE.md           # Руководство пользователя
    └── CLAUDE_CODE_CONTEXT.md    # Этот файл
```

---

## Скрипты и когда их использовать

### `scripts/upload_categories.py`

**Когда:** Нужно загрузить категории в API

**Что делает:**

1. Читает `data/output/categories.json`
2. GET `/api/locations/17/categories` — получает существующие
3. Сравнивает по имени
4. POST создаёт только НОВЫЕ

**Команды:**

```bash
# Dry run (только показать план)
python3 scripts/upload_categories.py

# Выполнить загрузку
python3 scripts/upload_categories.py --execute
```

**Безопасность:** Можно запускать многократно — дубли НЕ создаются.

---

### `scripts/upload_services.py`

**Когда:** Нужно загрузить сервисы в API (ПОСЛЕ категорий!)

**Что делает:**

1. Читает `data/output/services.json` и `data/output/categories.json`
2. GET категории и сервисы из API
3. Строит маппинг категорий: `local_category_id → api_category_id` (по имени!)
4. Сравнивает сервисы по имени
5. POST создаёт только НОВЫЕ сервисы с правильным `category_id`

**Команды:**

```bash
# Dry run
python3 scripts/upload_services.py

# Выполнить загрузку
python3 scripts/upload_services.py --execute

# Загрузить только первые N (для теста)
python3 scripts/upload_services.py --execute --limit=5
```

**Предупреждения:**

- Покажет сервисы без категории (если категория не найдена в API)
- Такие сервисы создадутся БЕЗ `category_id`

**Безопасность:** Можно запускать многократно — дубли НЕ создаются.

---

### `scripts/get_categories.py`

**Когда:** Нужно получить данные из API или создать тестовый элемент

**Команды:**

```bash
# Получить категории
python3 scripts/get_categories.py --categories

# Получить сервисы
python3 scripts/get_categories.py --services

# Получить врачей
python3 scripts/get_categories.py --practitioners

# Всё сразу
python3 scripts/get_categories.py --all

# Создать тестовую категорию
python3 scripts/get_categories.py --create-test --location=17 --name="Test"
```

**Результаты сохраняются в:** `data/api/`

---

### `scripts/sync_with_api.py` (устаревший)

**Когда:** НЕ использовать для загрузки! Только для синхронизации локальных ID.

**Что делает:**

- GET данные из API
- Обновляет `data/output/*.json` чтобы local ID совпадали с API ID
- НЕ создаёт новые элементы в API

---

## Порядок загрузки данных

```
1. КАТЕГОРИИ (нет зависимостей)
   └── python3 scripts/upload_categories.py --execute

2. СЕРВИСЫ (зависят от категорий)
   └── python3 scripts/upload_services.py --execute

3. PRACTITIONERS (нет зависимостей) — скрипт ещё не создан
   └── TODO: upload_practitioners.py

4. SERVICE_PRACTITIONERS (зависят от сервисов и врачей) — скрипт ещё не создан
   └── TODO: upload_service_practitioners.py
```

---

## Логика маппинга category_id для сервисов

```python
# Локальный сервис
{
  "id": 7,                    # local service ID
  "category_id": 17,          # local category ID (!!)
  "name_i18n": {"en": "MesoTherapy - Face"}
}

# Локальная категория
{
  "id": 17,                   # local category ID
  "name_i18n": {"en": "MESOTHERAPY"}
}

# API категория (после загрузки)
{
  "id": 328,                  # API category ID (!!)
  "name_i18n": {"en": "MESOTHERAPY"}
}

# При загрузке сервиса:
# 1. Находим локальную категорию по local_category_id=17
# 2. Получаем имя: "MESOTHERAPY"
# 3. Ищем в API категорию с таким именем
# 4. Получаем api_category_id=328
# 5. Создаём сервис с category_id=328
```

---

## API Endpoints

### Categories

| Метод  | Endpoint                                                         | Описание     |
| ------ | ---------------------------------------------------------------- | ------------ |
| GET    | `/api/locations/{id}/categories?flat=true&include_archived=true` | Список       |
| POST   | `/api/locations/{id}/categories`                                 | Создать      |
| PUT    | `/api/locations/{id}/categories/{cat_id}`                        | Обновить     |
| DELETE | `/api/locations/{id}/categories/{cat_id}`                        | Архивировать |

**POST Body:**

```json
{
	"location_id": 17,
	"name": { "en": "Category Name" },
	"is_visible_to_ai": true
}
```

### Services

| Метод  | Endpoint                                             | Описание     |
| ------ | ---------------------------------------------------- | ------------ |
| GET    | `/api/locations/{id}/services?include_archived=true` | Список       |
| POST   | `/api/locations/{id}/services`                       | Создать      |
| PUT    | `/api/locations/{id}/services/{svc_id}`              | Обновить     |
| DELETE | `/api/locations/{id}/services/{svc_id}`              | Архивировать |

**POST Body:**

```json
{
	"location_id": 17,
	"name": { "en": "Service Name" },
	"category_id": 328,
	"duration_minutes": 60,
	"price_min": 500.0,
	"price_max": 500.0,
	"price_note": { "en": "Price excludes VAT" },
	"is_visible_to_ai": true
}
```

---

## Авторизация

- Cookie: `dg_session`
- Хранится в: `config/.dg_session.json`
- Срок действия: 7 дней
- Автообновление: Да (через Playwright + Google OAuth)

Если сессия истекла — скрипт автоматически откроет браузер для входа.

---

## Что проверять перед загрузкой

### Перед загрузкой категорий:

- [ ] `data/output/categories.json` существует и не пустой
- [ ] Имена категорий на английском (`name_i18n.en`)
- [ ] Нет дубликатов имён в локальном файле

### Перед загрузкой сервисов:

- [ ] ВСЕ категории уже загружены в API
- [ ] `data/output/services.json` существует
- [ ] Каждый сервис имеет `category_id` (local ID)
- [ ] Соответствующая категория есть в `data/output/categories.json`

---

## Troubleshooting

### Ошибка 401 (Unauthorized)

Сессия истекла. Удалите `config/.dg_session.json` и запустите снова.

### Ошибка 422 (Validation Error)

Проверьте формат. Частые ошибки:

- `name` должен быть объектом `{"en": "..."}`, не строкой
- `location_id` должен быть в body

### Сервис создался без категории

Категория не найдена в API по имени. Возможные причины:

1. Категория не была загружена
2. Имя категории отличается (проверьте спецсимволы, пробелы)

### Дубликаты в API

Если случайно создались дубли — удалите их вручную через UI DialogGauge или API (DELETE).

---

---

## Practitioners Data Source

### Google Sheets

**URL:** https://docs.google.com/spreadsheets/d/1ZXYPl573sgfdRYDJj1RzPDJLPpyKpGY6vgr4NsgJSlk/edit?gid=881293577#gid=881293577

**Tab:** Practitioners

### Column Mapping

| Google Sheets Column          | JSON Field                             | Type      | Notes                                           |
| ----------------------------- | -------------------------------------- | --------- | ----------------------------------------------- |
| A (ID)                        | `id`                                   | int       | Unique identifier                               |
| B (Name)                      | `name`, `name_i18n.en`                 | str       | Full name                                       |
| C (Speciality)                | `speciality`                           | str       | e.g. "Specialist Dermatology"                   |
| D (Sex)                       | `sex`                                  | str       | "Male" → "male", "Female" → "female"            |
| E (Languages)                 | `languages`                            | list[str] | Parse "ENGLISHRUSSIAN" → ["ENGLISH", "RUSSIAN"] |
| F (Description English)       | `description_i18n.en`                  | str       | Full bio                                        |
| G (Description Russian)       | `description_i18n.ru`                  | str       | Russian translation                             |
| H (Years of experience)       | `years_of_experience`                  | int       | Parse "13+" → 13                                |
| I (Primary Qualifications)    | `primary_qualifications`               | str       | Degrees, education                              |
| J (Secondary Qualifications)  | `secondary_qualifications`             | str       | Fellowships                                     |
| K (Additional Qualifications) | `additional_qualifications`            | str       | Certifications                                  |
| L (treat children)            | `treat_children`, `treat_children_age` | bool, str | "No" → False, "13+" → True + "13+"              |
| M (Branch)                    | `branches`                             | list[str] | See branch mapping below                        |

### Branch Mapping

| Google Sheets Value                   | JSON Value            |
| ------------------------------------- | --------------------- |
| "Hortman Clinics - Jumeirah 3"        | `"jumeirah"`          |
| "Hortman Clinics - Sheikh Zayed Road" | `"szr"`               |
| Both (separated by newline)           | `["jumeirah", "szr"]` |

### Languages Parsing

Column E contains concatenated language names without separator.

Common patterns:

- `"ENGLISHRUSSIANUKRAINIAN"` → `["ENGLISH", "RUSSIAN", "UKRAINIAN"]`
- `"ENGLISHARABIC"` → `["ENGLISH", "ARABIC"]`
- `"ENGLISH"` → `["ENGLISH"]`

Known languages: ENGLISH, RUSSIAN, UKRAINIAN, ARABIC, FRENCH, AFRIKAANS, ROMANIAN, TURKISH, ARMENIAN, SPANISH

### Example JSON Output

```json
{
	"id": 1,
	"name": "Dr. Anna Zakhozha",
	"name_i18n": {
		"en": "Dr. Anna Zakhozha"
	},
	"speciality": "Specialist Dermatology",
	"sex": "female",
	"languages": ["ENGLISH", "RUSSIAN", "UKRAINIAN"],
	"description_i18n": {
		"en": "Dr. Anna Zakhozha is a highly skilled..."
	},
	"years_of_experience": 13,
	"primary_qualifications": "Dr. Anna is a board-certified Dermatologist...",
	"secondary_qualifications": "Fellowship from the American Academy...",
	"additional_qualifications": "",
	"treat_children": true,
	"treat_children_age": "13+",
	"branches": ["szr"],
	"is_visible_to_ai": true
}
```

---

## Pydantic Models

Модели находятся в `models/pydantic_models.py`.

Основные модели:

- `ServiceCategory` — категория услуг
- `Service` — услуга
- `Practitioner` — врач/специалист (с полными полями из Google Sheets)
- `ServicePractitioner` — связь услуга-врач

---

## TODO (что ещё нужно сделать)

- [ ] `upload_practitioners.py` — загрузка врачей
- [ ] `upload_service_practitioners.py` — загрузка связей сервис-врач
- [ ] Скрипт парсинга Google Sheets → practitioners.json
- [ ] Добавить `--dry-run` флаг явно (сейчас по умолчанию)
- [ ] Логирование в файл
- [ ] Откат изменений (delete созданных элементов)
