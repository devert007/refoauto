# Prompt for Claude Code - Google Sheets to Normalized JSON

## CRITICAL CONSTRAINTS - READ FIRST

**YOU MUST:**

- Read data from Google Sheet (via MCP or public export)
- Create **4 separate JSON files** (normalized database structure)
- Run `assign_ids.py` script after creating JSON files
- Run `sync_with_api.py` script to sync with DialogGauge API
- Follow the exact output structure specified below

**YOU MUST NOT:**

- Put all data in a single file
- Skip running the assign_ids.py script
- Skip running the sync_with_api.py script
- Create practitioners field inside services.json

---

## Task Description

Read data from Google Sheet and create **4 normalized JSON files**:

1. `categories.json` - Service categories
2. `practitioners.json` - Doctors/practitioners
3. `services.json` - Services (with category_id FK, WITHOUT practitioners)
4. `service_practitioners.json` - Many-to-many links

## Google Sheet URL

```
https://docs.google.com/spreadsheets/d/1ZXYPl573sgfdRYDJj1RzPDJLPpyKpGY6vgr4NsgJSlk/edit?gid=12440639#gid=12440639
```

---

## OUTPUT FILES STRUCTURE

### 1. categories.json

Extract unique categories and assign temporary IDs (will be fixed by script).

```json
[
	{
		"id": 1,
		"name_i18n": { "en": "AESTHETICS & DERMATOLOGY" },
		"sort_order": 1
	},
	{
		"id": 2,
		"name_i18n": { "en": "BOTOX" },
		"sort_order": 2
	}
]
```

### 2. practitioners.json

Extract practitioners from Google Sheets tab "Practitioners".

**Google Sheets URL:**

```
https://docs.google.com/spreadsheets/d/1ZXYPl573sgfdRYDJj1RzPDJLPpyKpGY6vgr4NsgJSlk/edit?gid=881293577#gid=881293577
```

**Full structure:**

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
		"additional_qualifications": "Certified in botulinum toxin...",
		"treat_children": true,
		"treat_children_age": "13+",
		"branches": ["szr"],
		"is_visible_to_ai": true,
		"source": "google_sheets"
	}
]
```

**Column Mapping from Google Sheets:**

| Column                    | Field                                  | Parsing Rule                                                                 |
| ------------------------- | -------------------------------------- | ---------------------------------------------------------------------------- |
| ID (col A)                | `id`                                   | Use as-is                                                                    |
| Name                      | `name`, `name_i18n.en`                 | Fix spacing: "Dr.Sarah" → "Dr. Sarah"                                        |
| Speciality                | `speciality`                           | As-is                                                                        |
| Sex                       | `sex`                                  | "Female" → "female", "Male" → "male"                                         |
| Languages                 | `languages`                            | Parse concatenated: "ENGLISHRUSSIAN" → ["ENGLISH", "RUSSIAN"]                |
| Description English       | `description_i18n.en`                  | As-is                                                                        |
| Description Russian       | `description_i18n.ru`                  | As-is                                                                        |
| Years of experience       | `years_of_experience`                  | Extract number: "13+" → 13, "25" → 25                                        |
| Primary Qualifications    | `primary_qualifications`               | As-is                                                                        |
| Secondary Qualifications  | `secondary_qualifications`             | As-is                                                                        |
| Additional Qualifications | `additional_qualifications`            | As-is                                                                        |
| treat children            | `treat_children`, `treat_children_age` | "No" → false/null, "Any age" → true/"Any age", "13+" → true/"13+"            |
| Branch                    | `branches`                             | "Hortman Clinics - Jumeirah 3" → ["jumeirah"], "Sheikh Zayed Road" → ["szr"] |

**Known Languages for parsing:**
ENGLISH, RUSSIAN, UKRAINIAN, ARABIC, FRENCH, AFRIKAANS, ROMANIAN, TURKISH, ARMENIAN, SPANISH

**Branch Mapping:**

- "Hortman Clinics - Jumeirah 3" → "jumeirah"
- "Hortman Clinics - Sheikh Zayed Road" → "szr"
- If both mentioned → ["jumeirah", "szr"]

**Important:** Fix spacing in names like "Dr.Sarah" → "Dr. Sarah"

### 3. services.json

Services with `category_id` (FK to categories.json), **WITHOUT practitioners field**.

```json
[
	{
		"id": 1,
		"category_id": 1,
		"name_i18n": { "en": "Aesthetics Consultation" },
		"description_i18n": { "en": "Initial consultation" },
		"duration_minutes": 30,
		"price_min": 500.0,
		"price_max": 500.0,
		"price_note_i18n": { "en": "Price excludes VAT" },
		"branches": ["jumeirah", "szr"]
	}
]
```

**NO `practitioners` field here!** Use service_practitioners.json instead.

**`branches` field values:**

- `["jumeirah", "szr"]` - available in both locations
- `["jumeirah"]` - only in Jumeirah
- `["szr"]` - only in szr

### 4. service_practitioners.json

Many-to-many relationship between services and practitioners.

```json
[
	{ "service_id": 1, "practitioner_id": 1 },
	{ "service_id": 1, "practitioner_id": 2 },
	{ "service_id": 2, "practitioner_id": 1 }
]
```

---

## COLUMN MAPPING RULES

### Category Column → categories.json + services.category_id

1. Collect all unique category names
2. Create categories.json with id, name_i18n, sort_order
3. Map category_name to category_id in services.json

### Service Name Column → services.name_i18n + description_i18n

**CRITICAL: If cell contains MULTIPLE LINES:**

- **FIRST LINE** → `name_i18n.en`
- **OTHER LINES** → `description_i18n.en`

Example:

```
Input:
  Comprehensive Consultation & Examination
  Seca - Body Composition Analysis
  Face Analyzer
  Vitals Check

Output:
  "name_i18n": {"en": "Comprehensive Consultation & Examination"}
  "description_i18n": {"en": "Includes: Seca - Body Composition Analysis, Face Analyzer, Vitals Check"}
```

### Doctor Name Column → practitioners.json + service_practitioners.json

1. Doctors are listed **separated by NEWLINES** (not commas!)
2. Extract unique doctors → practitioners.json
3. Create links → service_practitioners.json

Example input cell:

```
Dr. Anna Zakhozha
Dr.Sarah Mohamed
Dr. Karem Harb
```

**Fix spacing:** "Dr.Sarah" → "Dr. Sarah"

### Price Column → services.price_min, price_max, price_note_i18n

- "500 + VAT" → `price_min: 500, price_max: 500, price_note_i18n: {"en": "Price excludes VAT"}`
- "500" → `price_min: 500, price_max: 500`
- "0" or empty → `price_min: null, price_max: null`

### Duration Column → services.duration_minutes

- "30 min" → `30`
- "1 hour" → `60`
- "1.5 hour" → `90`
- "75 min" → `75`

### Note Column → Append to services.price_note_i18n

### Available In Branches Column → services.branches

**IMPORTANT RULE:**

- If value is **"Both"** → `"branches": ["jumeirah", "szr"]`
- If value is **"Jumeirah"** → `"branches": ["jumeirah"]`
- If value is **"szr"** → `"branches": ["szr"]`
- If empty or unknown → `"branches": ["jumeirah", "szr"]` (default to both)

**Examples:**
| Column Value | Output |
|--------------|--------|
| Both | `"branches": ["jumeirah", "szr"]` |
| Jumeirah | `"branches": ["jumeirah"]` |
| szr | `"branches": ["szr"]` |
| (empty) | `"branches": ["jumeirah", "szr"]` |

---

## STEPS TO EXECUTE

### Step 1: Read Google Sheet

Use MCP tools or fetch public CSV export.

### Step 2: Process Data

For each row:

1. Extract/create category → add to categories list
2. Extract practitioners → add to practitioners list
3. Create service object → add to services list
4. Create service-practitioner links → add to links list

### Step 3: Create JSON Files

Write 4 files to `data/output/`:

```
data/output/categories.json
data/output/practitioners.json
data/output/services.json
data/output/service_practitioners.json
```

### Step 4: Run ID Assignment Script (REQUIRED!)

```bash
python3 scripts/assign_ids.py
```

This script will:

- Verify all IDs are unique
- Fix any conflicts
- Ensure proper ID sequence

### Step 5: Sync with DialogGauge API (REQUIRED!)

```bash
python3 scripts/sync_with_api.py
```

This script will:

- Fetch existing **categories** and **services** from DialogGauge API
- Match local items with API items by name (case-insensitive)
- **If item exists in API** → use API's ID (don't create duplicate)
- **If item is new** → assign new ID (starting from max_api_id + 1)
- Update all references (`category_id` in services, `service_id` in service_practitioners)
- Generate `data/api/_sync_report.json` with sync details

**Options:**

```bash
python3 scripts/sync_with_api.py                  # Sync both categories and services
python3 scripts/sync_with_api.py --categories-only # Sync only categories
python3 scripts/sync_with_api.py --services-only   # Sync only services
```

**Important:**

- Items that match existing API items will use their IDs
- New items will need to be created in DialogGauge manually (or via API)
- Check `data/api/_sync_report.json` to see which items are new vs matched

---

## PROJECT STRUCTURE

```
refoauto/
├── scripts/              # All Python scripts
│   ├── get_categories.py # Fetch categories from API
│   ├── sync_with_api.py  # Sync local data with API
│   ├── assign_ids.py     # Assign unique IDs
│   └── process_data.py   # Process CSV to JSON
├── data/
│   ├── output/           # Generated JSON files (for upload)
│   │   ├── categories.json
│   │   ├── practitioners.json
│   │   ├── services.json
│   │   └── service_practitioners.json
│   ├── api/              # Data from API
│   │   ├── categories_api_response.json
│   │   └── _sync_report.json
│   └── input/            # Input data
│       └── raw_data.csv
├── config/               # Credentials and sessions
├── docs/                 # Documentation
└── models/               # Python models
```

---

## FINAL CHECKLIST

Before completing, verify:

- [ ] `data/output/categories.json` exists with id, name_i18n, sort_order
- [ ] `data/output/practitioners.json` exists with FULL structure (all fields from Google Sheets)
- [ ] `data/output/services.json` exists with id, category_id, NO practitioners field
- [ ] `data/output/service_practitioners.json` exists with service_id, practitioner_id pairs
- [ ] Ran `python3 scripts/assign_ids.py` successfully
- [ ] Ran `python3 scripts/sync_with_api.py` successfully
- [ ] Reviewed `data/api/_sync_report.json` for matched/new categories

## Practitioners-Specific Checklist

- [ ] Read Google Sheets tab "Practitioners" (gid=881293577)
- [ ] Parsed `languages` correctly (split concatenated strings)
- [ ] Parsed `sex` correctly ("Female" → "female")
- [ ] Parsed `years_of_experience` correctly ("13+" → 13)
- [ ] Parsed `treat_children` correctly ("No" → false, "13+" → true with age)
- [ ] Parsed `branches` correctly (clinic name → short code)
- [ ] All practitioners have unique IDs

---

## Reference: Pydantic Models

```python
class ServiceCategory(BaseModel):
    id: int
    name_i18n: dict    # {"en": "Category Name"}
    sort_order: int

class Practitioner(BaseModel):
    """Full model - see models/pydantic_models.py"""
    id: int
    name: str                          # "Dr. Anna Zakhozha"
    name_i18n: dict                    # {"en": "Dr. Anna Zakhozha"}
    speciality: str                    # "Specialist Dermatology"
    sex: str                           # "male" | "female"
    languages: list[str]               # ["ENGLISH", "RUSSIAN"]
    description_i18n: dict             # {"en": "...", "ru": "..."}
    years_of_experience: int | None    # 13
    primary_qualifications: str
    secondary_qualifications: str
    additional_qualifications: str
    treat_children: bool               # False = "No", True = any other
    treat_children_age: str | None     # "13+", "Any age", None
    branches: list[str]                # ["jumeirah"] or ["szr"] or both
    is_visible_to_ai: bool = True
    source: str = "google_sheets"

class Service(BaseModel):
    id: int
    category_id: int   # FK to ServiceCategory
    name_i18n: dict
    description_i18n: dict
    duration_minutes: int
    price_min: float | None
    price_max: float | None
    price_note_i18n: dict
    branches: list[str]  # ["jumeirah", "szr"] or ["jumeirah"] or ["szr"]

class ServicePractitioner(BaseModel):
    service_id: int      # FK to Service
    practitioner_id: int # FK to Practitioner
```

## Helper Functions (models/pydantic_models.py)

```python
from models import (
    parse_languages,           # "ENGLISHRUSSIAN" → ["ENGLISH", "RUSSIAN"]
    parse_sex,                 # "Female" → "female"
    parse_years_of_experience, # "13+" → 13
    parse_treat_children,      # "No" → (False, None), "13+" → (True, "13+")
    parse_branches,            # "Jumeirah 3" → ["jumeirah"]
    practitioner_from_sheets_row,  # Full row → Practitioner dict
)
```
