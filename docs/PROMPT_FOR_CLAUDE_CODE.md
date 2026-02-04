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
    "name_i18n": {"en": "AESTHETICS & DERMATOLOGY"},
    "sort_order": 1
  },
  {
    "id": 2,
    "name_i18n": {"en": "BOTOX"},
    "sort_order": 2
  }
]
```

### 2. practitioners.json

Extract unique doctors/practitioners and assign temporary IDs.

```json
[
  {
    "id": 1,
    "name": "Dr. Anna Zakhozha",
    "name_i18n": {"en": "Dr. Anna Zakhozha"}
  },
  {
    "id": 2,
    "name": "Dr. Sarah Mohamed",
    "name_i18n": {"en": "Dr. Sarah Mohamed"}
  }
]
```

**Important:** Fix spacing in names like "Dr.Sarah" → "Dr. Sarah"

### 3. services.json

Services with `category_id` (FK to categories.json), **WITHOUT practitioners field**.

```json
[
  {
    "id": 1,
    "category_id": 1,
    "name_i18n": {"en": "Aesthetics Consultation"},
    "description_i18n": {"en": "Initial consultation"},
    "duration_minutes": 30,
    "price_min": 500.0,
    "price_max": 500.0,
    "price_note_i18n": {"en": "Price excludes VAT"},
    "branches": ["jumeirah", "srz"]
  }
]
```

**NO `practitioners` field here!** Use service_practitioners.json instead.

**`branches` field values:**
- `["jumeirah", "srz"]` - available in both locations
- `["jumeirah"]` - only in Jumeirah
- `["srz"]` - only in SRZ

### 4. service_practitioners.json

Many-to-many relationship between services and practitioners.

```json
[
  {"service_id": 1, "practitioner_id": 1},
  {"service_id": 1, "practitioner_id": 2},
  {"service_id": 2, "practitioner_id": 1}
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
- If value is **"Both"** → `"branches": ["jumeirah", "srz"]`
- If value is **"Jumeirah"** → `"branches": ["jumeirah"]`
- If value is **"SRZ"** → `"branches": ["srz"]`
- If empty or unknown → `"branches": ["jumeirah", "srz"]` (default to both)

**Examples:**
| Column Value | Output |
|--------------|--------|
| Both | `"branches": ["jumeirah", "srz"]` |
| Jumeirah | `"branches": ["jumeirah"]` |
| SRZ | `"branches": ["srz"]` |
| (empty) | `"branches": ["jumeirah", "srz"]` |

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
- Fetch existing categories from DialogGauge API
- Match local categories with API categories by name (case-insensitive)
- **If category exists in API** → use API's ID (don't create duplicate)
- **If category is new** → assign new ID (starting from max_api_id + 1)
- Update `services.json` with correct `category_id` references
- Generate `data/api/_sync_report.json` with sync details

**Important:** 
- Categories that match existing API categories will use their IDs
- New categories will need to be created in DialogGauge manually (or via API)
- Check `data/api/_sync_report.json` to see which categories are new vs matched

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
- [ ] `data/output/practitioners.json` exists with id, name, name_i18n
- [ ] `data/output/services.json` exists with id, category_id, NO practitioners field
- [ ] `data/output/service_practitioners.json` exists with service_id, practitioner_id pairs
- [ ] Ran `python3 scripts/assign_ids.py` successfully
- [ ] Ran `python3 scripts/sync_with_api.py` successfully
- [ ] Reviewed `data/api/_sync_report.json` for matched/new categories

---

## Reference: Pydantic Models

```python
class ServiceCategory(BaseModel):
    id: int
    name_i18n: dict    # {"en": "Category Name"}
    sort_order: int

class Practitioner(BaseModel):
    id: int
    name: str          # "Dr. Anna Zakhozha"
    name_i18n: dict    # {"en": "Dr. Anna Zakhozha"}

class Service(BaseModel):
    id: int
    category_id: int   # FK to ServiceCategory
    name_i18n: dict
    description_i18n: dict
    duration_minutes: int
    price_min: float | None
    price_max: float | None
    price_note_i18n: dict
    branches: list[str]  # ["jumeirah", "srz"] or ["jumeirah"] or ["srz"]

class ServicePractitioner(BaseModel):
    service_id: int      # FK to Service
    practitioner_id: int # FK to Practitioner
```
