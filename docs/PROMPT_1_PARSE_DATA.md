# Prompt 1: Парсинг данных из Google Sheets в JSON

## Задача

Прочитать данные из Google Sheets и создать **4 нормализованных JSON файла** в папке `data/output/`.

---

## Источники данных

### Лист 1: Services (категории + сервисы + связи с врачами)

```
https://docs.google.com/spreadsheets/d/1ZXYPl573sgfdRYDJj1RzPDJLPpyKpGY6vgr4NsgJSlk/edit?gid=12440639#gid=12440639
```

### Лист 2: Practitioners (врачи)

```
https://docs.google.com/spreadsheets/d/1ZXYPl573sgfdRYDJj1RzPDJLPpyKpGY6vgr4NsgJSlk/edit?gid=881293577#gid=881293577
```

---

## КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ

**ОБЯЗАТЕЛЬНО:**

- Создать **4 отдельных JSON файла** (нормализованная структура как БД)
- Practitioners парсить с **отдельного листа** (gid=881293577), НЕ из листа Services
- Следовать точным правилам парсинга, описанным ниже

**ЗАПРЕЩЕНО:**

- Класть все данные в один файл
- Создавать поле `practitioners` внутри `services.json`
- Пропускать лист Practitioners
- Выдумывать данные — только то, что есть в таблице
- Пропускать часть данных — только то, что есть в таблице

---

## Выходные файлы

### 1. `data/output/categories.json`

Уникальные категории из колонки "Category" листа Services.

```json
[
	{
		"id": 1,
		"name_i18n": { "en": "INJECTABLE TREATMENTS" },
		"sort_order": 1
	},
	{
		"id": 2,
		"name_i18n": { "en": "AESTHETICS & DERMATOLOGY" },
		"sort_order": 2
	}
]
```

**Правила:**

- `id` — последовательный, начиная с 1
- `name_i18n.en` — точное имя категории из таблицы (регистр сохранять)
- `sort_order` — порядок появления в таблице

---

### 2. `data/output/services.json`

Сервисы из листа Services. **БЕЗ поля practitioners!**

```json
[
	{
		"id": 1,
		"category_id": 1,
		"name_i18n": { "en": "Aesthetics Consultation" },
		"description_i18n": { "en": "Initial consultation for skin assessment" },
		"duration_minutes": 30,
		"price_min": 500.0,
		"price_max": 500.0,
		"price_note_i18n": { "en": "Price excludes VAT" },
		"branches": ["jumeirah", "szr"]
	}
]
```

**Правила парсинга колонок:**

| Колонка               | Поле JSON                                   | Правило парсинга                                                                                    |
| --------------------- | ------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| ID                    | `id`                                        | Использовать как есть                                                                               |
| Category              | `category_id`                               | FK на categories.json (по имени → id)                                                               |
| Service Name          | `name_i18n.en`, `description_i18n.en`       | Если многострочная ячейка: 1-я строка → name, остальные → description (см. ниже)                    |
| Duration              | `duration_minutes`                          | "30 min" → 30, "1 hour" → 60, "1.5 hour" → 90                                                       |
| Price                 | `price_min`, `price_max`, `price_note_i18n` | "500 + VAT" → min=500, max=500, note="Price excludes VAT"                                           |
| Note                  | `price_note_i18n`                           | Добавить к существующей note                                                                        |
| Available In Branches | `branches`                                  | "Both" → ["jumeirah","szr"], "Jumeirah" → ["jumeirah"], "szr" → ["szr"], пусто → ["jumeirah","szr"] |
| Doctor name           | НЕ сюда!                                    | Идёт в service_practitioners.json                                                                   |

**Парсинг многострочного Service Name:**

```
Ячейка:
  Comprehensive Consultation & Examination
  Seca - Body Composition Analysis
  Face Analyzer
  Vitals Check

Результат:
  "name_i18n": {"en": "Comprehensive Consultation & Examination"}
  "description_i18n": {"en": "Includes: Seca - Body Composition Analysis, Face Analyzer, Vitals Check"}
```

**Парсинг Price:**

- "500 + VAT" → `price_min: 500, price_max: 500, price_note_i18n: {"en": "Price excludes VAT"}`
- "500" → `price_min: 500, price_max: 500`
- "1,500" → `price_min: 1500, price_max: 1500` (убрать запятую)
- "0" или пусто → `price_min: null, price_max: null`

**Парсинг Duration:**

- "30 min" → 30
- "1 hour" → 60
- "1.5 hour" → 90
- "75 min" → 75
- "Individual" или "2 + days" → null

---

### 3. `data/output/practitioners.json`

Врачи из **отдельного листа** "Practitioners" (gid=881293577).

```json
[
	{
		"id": 1,
		"name": "Dr. Anna Zakhozha",
		"name_i18n": { "en": "Dr. Anna Zakhozha" },
		"speciality": "Specialist Dermatology",
		"sex": "female",
		"languages": ["ENGLISH", "RUSSIAN", "UKRAINIAN"],
		"description_i18n": {
			"en": "Dr. Anna Zakhozha is a highly skilled...",
			"ru": "Доктор Анна Захожа — высококвалифицированный..."
		},
		"years_of_experience": 13,
		"primary_qualifications": "Board-certified Dermatologist...",
		"secondary_qualifications": "Fellowship from American Academy...",
		"additional_qualifications": "",
		"treat_children": true,
		"treat_children_age": "13+",
		"branches": ["szr"],
		"is_visible_to_ai": true,
		"source": "google_sheets"
	}
]
```

**Маппинг колонок Google Sheets:**

| Колонка (буква)               | Поле JSON                              | Правило парсинга                                                  |
| ----------------------------- | -------------------------------------- | ----------------------------------------------------------------- |
| A (ID)                        | `id`                                   | Использовать как есть (int)                                       |
| B (Name)                      | `name`, `name_i18n.en`                 | Исправить пробелы: "Dr.Sarah" → "Dr. Sarah"                       |
| C (Speciality)                | `speciality`                           | Как есть                                                          |
| D (Sex)                       | `sex`                                  | "Female" → "female", "Male" → "male"                              |
| E (Languages)                 | `languages`                            | Парсить слипшиеся: "ENGLISHRUSSIAN" → ["ENGLISH", "RUSSIAN"]      |
| F (Description English)       | `description_i18n.en`                  | Как есть                                                          |
| G (Description Russian)       | `description_i18n.ru`                  | Как есть                                                          |
| H (Years of experience)       | `years_of_experience`                  | "13+" → 13, "25" → 25                                             |
| I (Primary Qualifications)    | `primary_qualifications`               | Как есть                                                          |
| J (Secondary Qualifications)  | `secondary_qualifications`             | Как есть                                                          |
| K (Additional Qualifications) | `additional_qualifications`            | Как есть                                                          |
| L (treat children)            | `treat_children`, `treat_children_age` | "No" → false/null, "Any age" → true/"Any age", "13+" → true/"13+" |
| M (Branch)                    | `branches`                             | Маппинг клиника → код (см. ниже)                                  |

**Парсинг Languages (слипшиеся строки):**
Известные языки: ENGLISH, RUSSIAN, UKRAINIAN, ARABIC, FRENCH, AFRIKAANS, ROMANIAN, TURKISH, ARMENIAN, SPANISH, GERMAN, HINDI, URDU, PORTUGUESE, ITALIAN, PERSIAN

Примеры:

- `"ENGLISHRUSSIANUKRAINIAN"` → `["ENGLISH", "RUSSIAN", "UKRAINIAN"]`
- `"ENGLISHARABIC"` → `["ENGLISH", "ARABIC"]`
- `"ENGLISH"` → `["ENGLISH"]`

**Branch Mapping:**

- "Hortman Clinics - Jumeirah 3" → `["jumeirah"]`
- "Hortman Clinics - Sheikh Zayed Road" → `["szr"]`
- Если обе клиники (через перенос строки) → `["jumeirah", "szr"]`
- Пустое значение → `[]` (пустой массив)

**Исправление имён:**

- "Dr.Sarah" → "Dr. Sarah" (добавить пробел после точки)
- "Dr Name" → "Dr. Name" (добавить точку)

---

### 4. `data/output/service_practitioners.json`

Many-to-many связи между сервисами и врачами.

```json
[
	{ "service_id": 1, "practitioner_id": 1 },
	{ "service_id": 1, "practitioner_id": 2 },
	{ "service_id": 2, "practitioner_id": 1 }
]
```

**Правила:**

- `service_id` — ID из services.json
- `practitioner_id` — ID из practitioners.json
- Врачи в ячейке "Doctor name" разделены **ПЕРЕНОСАМИ строк** (не запятыми!)
- Имена врачей в листе Services и в листе Practitioners должны совпадать
- Исправлять пробелы в именах ("Dr.Sarah" → "Dr. Sarah") перед сопоставлением
- ВАЖНО КРИТИЧЕСКИ здесь не ошибаться и делать полное заполнение service <-> practitioner

---

## Существующие скрипты (можно использовать)

Ты можешь напрямую через MCP читать Google Sheets и создавать JSON файлы вручную, следуя правилам выше или
В проекте уже есть готовые скрипты:

### `scripts/process_data.py`

Парсит `data/input/raw_data.csv` → categories.json, services.json, service_practitioners.json

```bash
python scripts/process_data.py
```

### `scripts/parse_practitioners_sheet.py`

Парсит лист Practitioners из Google Sheets → practitioners.json
Требует Google API credentials в `config/credentials.json`

```bash
python scripts/parse_practitioners_sheet.py
```

**ВАЖНО:** Если данные в Google Sheets обновились, нужно:

1. Заново экспортировать CSV из листа Services → `data/input/raw_data.csv`
2. Запустить `python scripts/process_data.py`
3. Запустить `python scripts/parse_practitioners_sheet.py`

---

## Вспомогательные модели (для справки)

Pydantic модели в `models/pydantic_models.py`:

```python
class ServiceCategory(BaseModel):
    id: int
    name_i18n: dict    # {"en": "Category Name"}
    sort_order: int

class Service(BaseModel):
    id: int
    category_id: int                # FK к ServiceCategory
    name_i18n: dict                 # {"en": "Service Name"}
    description_i18n: dict          # {"en": "Description"}
    duration_minutes: int | None
    price_min: float | None
    price_max: float | None
    price_note_i18n: dict           # {"en": "Price excludes VAT"}
    branches: list[str]             # ["jumeirah", "szr"]

class Practitioner(BaseModel):
    id: int
    name: str                       # "Dr. Anna Zakhozha"
    name_i18n: dict                 # {"en": "Dr. Anna Zakhozha"}
    speciality: str
    sex: str                        # "male" | "female"
    languages: list[str]            # ["ENGLISH", "RUSSIAN"]
    description_i18n: dict          # {"en": "...", "ru": "..."}
    years_of_experience: int | None
    primary_qualifications: str
    secondary_qualifications: str
    additional_qualifications: str
    treat_children: bool
    treat_children_age: str | None  # "13+", "Any age", None
    branches: list[str]             # ["jumeirah"] | ["szr"] | ["jumeirah","szr"] | []
    is_visible_to_ai: bool = True
    source: str = "google_sheets"

class ServicePractitioner(BaseModel):
    service_id: int      # FK к Service
    practitioner_id: int # FK к Practitioner
```

Хелперы:

```python
from models.pydantic_models import (
    parse_languages,           # "ENGLISHRUSSIAN" → ["ENGLISH", "RUSSIAN"]
    parse_sex,                 # "Female" → "female"
    parse_years_of_experience, # "13+" → 13
    parse_treat_children,      # "No" → (False, None)
    parse_branches,            # "Jumeirah 3" → ["jumeirah"]
)
```

---

## Чеклист после выполнения

- [ ] `data/output/categories.json` — содержит все уникальные категории с `id`, `name_i18n`, `sort_order`
- [ ] `data/output/services.json` — содержит все сервисы с `category_id` (FK), **БЕЗ поля practitioners**
- [ ] `data/output/practitioners.json` — содержит всех врачей **с ПОЛНОЙ структурой** (все 15 полей)
- [ ] `data/output/service_practitioners.json` — содержит все связи `service_id` ↔ `practitioner_id`
- [ ] Practitioners взяты с **отдельного листа** (gid=881293577), а не из листа Services
- [ ] Языки распарсены правильно ("ENGLISHRUSSIAN" → ["ENGLISH", "RUSSIAN"])
- [ ] Пол в нижнем регистре ("Female" → "female")
- [ ] Опыт как число ("13+" → 13)
- [ ] Branches правильные ("Jumeirah 3" → "jumeirah", "Sheikh Zayed" → "szr")
- [ ] Имена исправлены ("Dr.Sarah" → "Dr. Sarah")
- [ ] Нет дубликатов по ID
