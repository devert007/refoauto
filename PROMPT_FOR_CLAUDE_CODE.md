# Prompt for Claude Code - Google Sheets to JSON Conversion

## CRITICAL CONSTRAINTS - READ FIRST

**YOU MUST:**
- Use ONLY MCP tools (mcp__gdrive) to access Google Sheets
- Read data directly via MCP Google Drive tools
- Process data in memory and write final JSON

**YOU MUST NOT:**
- Create Python scripts or parsers
- Install any pip packages (gspread, google-auth, pandas, etc.)
- Use curl, wget, or any HTTP requests
- Create temporary files or intermediate scripts
- Ask user to download CSV manually

**If MCP tools are not available:**
- STOP and tell the user: "MCP Google Drive tools are not configured. Please set up MCP first."
- Do NOT fall back to creating scripts

---

## Task Description

Read data from Google Sheet using MCP tools and convert it to JSON format according to Pydantic models defined in `pydantic_models.py`.

## Google Sheet URL

```
https://docs.google.com/spreadsheets/d/1ZXYPl573sgfdRYDJj1RzPDJLPpyKpGY6vgr4NsgJSlk/edit?gid=12440639#gid=12440639
```

## Column Mapping Rules

### 1. Category → `category_name`
- Map directly to `category_name` field
- Example: "AESTHETICS & DERMATOLOGY" → `"category_name": "AESTHETICS & DERMATOLOGY"`

### 2. Service Name → `name_i18n` + `description_i18n`

**CRITICAL RULE: If cell contains MULTIPLE LINES (newlines, bullet points, or list of items):**
- **FIRST LINE ONLY** goes to `name_i18n.en`
- **ALL OTHER LINES** go to `description_i18n.en` (join with ", " or keep as list)

**Examples:**

1. **Simple case** (single line):
   - Input: "Aesthetics Consultation"
   - Output: `"name_i18n": {"en": "Aesthetics Consultation"}`

2. **With parentheses** (keep together if short):
   - Input: "Heleo4 Skin Cellular Detox Programme (5 sessions)"
   - Output: 
     - `"name_i18n": {"en": "Heleo4 Skin Cellular Detox Programme"}`
     - `"description_i18n": {"en": "Package of 5 sessions"}`

3. **MULTI-LINE / Package with components** (SPLIT!):
   - Input:
     ```
     Comprehensive Consultation & Examination
     Seca - Body Composition Analysis 
     Face Analyzer
     Vitals Check
     Supplements and/or IVs Recommendation
     ```
   - Output:
     - `"name_i18n": {"en": "Comprehensive Consultation & Examination"}`
     - `"description_i18n": {"en": "Includes: Seca - Body Composition Analysis, Face Analyzer, Vitals Check, Supplements and/or IVs Recommendation"}`

**Detection rules:**
- If text contains `\n` (newline) → SPLIT at first newline
- If text starts with bullet points or numbered list → First item = name, rest = description
- If text is longer than 100 characters → Likely needs splitting

### 3. Doctor name → `practitioners`
- Doctors are listed WITHOUT commas, separated by newlines
- Parse as array of strings and store in `practitioners` field
- Example input:
  ```
  Dr. Anna Zakhozha
  Dr.Sarah Mohamed
  Dr. Karem Harb
  ```
- Output: `"practitioners": ["Dr. Anna Zakhozha", "Dr. Sarah Mohamed", "Dr. Karem Harb"]`
- **Note**: Fix spacing issues like "Dr.Sarah" → "Dr. Sarah", "Dr.Lyn" → "Dr. Lyn"
- **Important**: Split by newlines, NOT by commas (names may contain commas)

### 4. Price → `price_min` and `price_max` + `price_note_i18n`
- **Parse the numeric value** (remove "+VAT", "AED", spaces)
- **If price contains "+VAT"**: Add note to `price_note_i18n`
- **If price is "0" or empty**: Set `price_min: null`, `price_max: null`
- Examples:
  - "500 + VAT" → `price_min: 500, price_max: 500, price_note_i18n: {"en": "Price excludes VAT"}`
  - "500" → `price_min: 500, price_max: 500`
  - "0" → `price_min: null, price_max: null` (free follow-up)

### 5. Duration → `duration_minutes`
- **Convert all durations to minutes (integer)**
- Parsing rules:
  - "30 min" → `30`
  - "45 min" → `45`
  - "1 hour" → `60`
  - "1.5 hour" → `90`
  - "75 min" → `75`
  - "1.5 hour" or "1.5 hours" → `90`
- Output must be integer in minutes

### 6. Note → `price_note_i18n` (append to existing)
- If Note column has content, add it to `price_note_i18n.en`
- Combine with VAT note if both exist
- Example: 
  - Note: "Consultation fees will be waived if you proceed with treatment"
  - With VAT: `"price_note_i18n": {"en": "Price excludes VAT. Consultation fees will be waived if you proceed with treatment"}`

### 7. Available In Branches → store in `aliases` or ignore
- Values: "Both", "Jumeirah", etc.
- Can be stored in service metadata or ignored for now

## Output Format

Generate a JSON array of Service objects. Use `exclude_defaults=True` logic - only include fields that differ from defaults.

```json
[
  {
    "name_i18n": {"en": "Aesthetics Consultation"},
    "practitioners": ["Dr. Anna Zakhozha", "Dr. Sarah Mohamed", "Dr. Karem Harb"],
    "duration_minutes": 30,
    "price_min": 500.0,
    "price_max": 500.0,
    "price_note_i18n": {"en": "Price excludes VAT. Consultation fees will be waived if you proceed with treatment on the same day."},
    "category_name": "AESTHETICS & DERMATOLOGY"
  },
  {
    "name_i18n": {"en": "Dermatology Consultation"},
    "practitioners": ["Dr. Anna Zakhozha", "Dr. Sarah Mohamed", "Dr. Nataliya Sanytska"],
    "duration_minutes": 30,
    "price_min": 500.0,
    "price_max": 500.0,
    "price_note_i18n": {"en": "You can claim this back from your Insurance provider."},
    "category_name": "AESTHETICS & DERMATOLOGY"
  }
]
```

## Steps to Execute (USING MCP TOOLS ONLY)

1. **Call MCP tool** `mcp__gdrive__search` or `mcp__gdrive__read_file` to access the spreadsheet
2. **Read spreadsheet content** using MCP Google Drive/Sheets tools
3. **Parse the data in your response** - process each row mentally/in-context
4. **Generate JSON directly** - write the final services.json file using standard file write tool
5. **Do NOT create any Python/JS scripts** - all processing must happen via MCP + direct JSON generation

Example MCP tool usage:
```
mcp__gdrive__read_file(fileId: "1ZXYPl573sgfdRYDJj1RzPDJLPpyKpGY6vgr4NsgJSlk")
```

Or search first:
```
mcp__gdrive__search(query: "name = 'Hortman'")
```

## Important Notes

- All text fields should be in English (use `en` key in i18n dicts)
- Numeric values should be proper numbers, not strings
- Empty or "0" prices should result in `null` values
- Duration must always be an integer (minutes)
- Handle edge cases gracefully (missing data, unusual formats)

## Authentication

Use the `cred.json` file in the project directory for Google API authentication.

This file contains Google Service Account credentials. Set the environment variable before running:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="./cred.json"
```

Or pass directly to MCP server configuration:
```json
{
  "mcpServers": {
    "gdrive": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-server-gdrive"],
      "env": {
        "GOOGLE_APPLICATION_CREDENTIALS": "/full/path/to/cred.json"
      }
    }
  }
}
```

## Pre-flight Check

Before starting, verify MCP tools are available by running:
```
/mcp
```

You should see `gdrive` in the list of available MCP servers. If not, STOP and ask user to configure MCP.

## Reference: Pydantic Model Fields (from pydantic_models.py)

```python
class Service(BaseModel):
    name_i18n: dict          # {"en": "Service Name"}
    description_i18n: dict   # {"en": "Description"}
    aliases: list[str]       # Alternative names for AI matching
    practitioners: list[str] # Doctors/staff who perform this service
    duration_minutes: int    # Duration in minutes (default: 60)
    capacity: int            # Max clients per session (default: 1)
    price_type: str          # "fixed", "range", "unknown" (default: "fixed")
    price_min: float | None  # Minimum price
    price_max: float | None  # Maximum price (same as min for fixed)
    price_note_i18n: dict    # Price notes {"en": "Note about price"}
    category_name: str | None # Category name
```
