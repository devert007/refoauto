"""
Claude-powered data generator for DialogGauge pipeline.

Uses Claude API (Anthropic SDK) to:
- Parse input files (CSV, JSON, HTML)
- Generate categories.json, services.json, practitioners.json
- Translate descriptions (EN + RU)
- Fill missing fields intelligently

Requires: ANTHROPIC_API_KEY environment variable
"""

import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


MODEL = "claude-opus-4-6"
MAX_TOKENS = 16000


def get_anthropic_client():
    """Get Anthropic client, raise clear error if not configured."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set.\n"
            "Set it in .env or environment:\n"
            "  export ANTHROPIC_API_KEY=sk-ant-..."
        )
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "anthropic SDK not installed. Run:\n"
            "  pip install anthropic"
        )
    return anthropic.Anthropic(api_key=api_key)


def call_claude(
    prompt: str,
    system: str = "",
    model: str = MODEL,
    max_tokens: int = MAX_TOKENS,
    temperature: float = 0.3,
) -> str:
    """Call Claude API and return text response."""
    client = get_anthropic_client()

    messages = [{"role": "user", "content": prompt}]

    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system

    print(f"  Calling Claude ({model})...")
    response = client.messages.create(**kwargs)

    text = response.content[0].text
    print(f"  Response: {len(text)} chars, stop={response.stop_reason}")
    return text


def extract_json_from_response(text: str) -> list | dict:
    """Extract JSON from Claude's response (handles markdown code blocks)."""
    # Try to find JSON in code blocks
    json_match = re.search(r'```(?:json)?\s*\n([\s\S]*?)\n```', text)
    if json_match:
        return json.loads(json_match.group(1))

    # Try direct parse
    # Find first [ or { and last ] or }
    start = min(
        (text.find('['), text.find('{')),
        key=lambda x: x if x >= 0 else float('inf')
    )
    if start == float('inf'):
        raise ValueError(f"No JSON found in response:\n{text[:500]}")

    if text[start] == '[':
        end = text.rfind(']') + 1
    else:
        end = text.rfind('}') + 1

    return json.loads(text[start:end])


# === Input File Readers ===

def read_csv_data(filepath: Path) -> tuple[list[str], list[dict]]:
    """Read CSV file, return (headers, rows as dicts)."""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find header row (skip empty lines)
    header_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip().strip(",")
        if stripped and len(stripped.split(",")) > 1:
            header_idx = i
            break

    reader = csv.DictReader(lines[header_idx:])
    headers = [h for h in (reader.fieldnames or []) if h and h.strip()]
    rows = []
    for row in reader:
        # Skip completely empty rows
        if any(v.strip() for v in row.values() if v):
            rows.append({k: v.strip() if v else "" for k, v in row.items() if k})

    return headers, rows


def read_json_data(filepath: Path) -> list | dict:
    """Read JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def read_all_inputs(input_dir: Path) -> dict:
    """Read all input files from a directory, return structured data."""
    result = {"csv_files": {}, "json_files": {}}

    for f in sorted(input_dir.iterdir()):
        if not f.is_file():
            continue
        if f.suffix.lower() == ".csv":
            headers, rows = read_csv_data(f)
            result["csv_files"][f.name] = {
                "headers": headers,
                "rows": rows,
                "row_count": len(rows),
            }
        elif f.suffix.lower() == ".json":
            data = read_json_data(f)
            result["json_files"][f.name] = data

    return result


# === Generators ===

def generate_categories(
    input_data: dict,
    rules: str = "",
    field_mappings: dict | None = None,
    existing_api_data: list | None = None,
) -> list[dict]:
    """
    Generate categories.json using Claude.

    Args:
        input_data: Dict from read_all_inputs()
        rules: User-defined rules text
        field_mappings: Category field mapping config
        existing_api_data: Existing categories from API (for merge)
    """
    # Prepare input summary for Claude
    input_summary = _build_input_summary(input_data, max_rows=5)

    source_col = ""
    if field_mappings:
        source_col = field_mappings.get("source_column", "")

    api_context = ""
    if existing_api_data:
        api_context = f"""
## Existing API Categories (source of truth for IDs and names)
{json.dumps(existing_api_data[:30], ensure_ascii=False, indent=2)}
Total in API: {len(existing_api_data)}

IMPORTANT: For categories that already exist in API, use THEIR id and name_i18n.
Only add new categories that are in the input data but NOT in the API.
"""

    system = """You are a data processing assistant for a medical clinic management system (DialogGauge).
Your task is to extract and generate structured JSON data from raw input files.
Always output valid JSON. Always include both English and Russian translations where available.
If source data is in Russian, translate to English. If in English, keep as is.
Do NOT invent data - only extract what's in the source files."""

    prompt = f"""## Task: Generate categories.json

Extract unique categories from the input data and create a JSON array.

## Input Data
{input_summary}

{f"## Source Column: {source_col}" if source_col else ""}

{api_context}

## User Rules
{rules if rules else "Standard processing: extract categories, translate to EN+RU, assign sequential IDs"}

## Output Format
Return a JSON array where each item has:
- "id": integer (sequential starting from 1, or from API if exists)
- "name_i18n": {{"en": "English Name", "ru": "Russian Name"}}
- "sort_order": integer (same as id)

Only output the JSON array, no explanation. Wrap in ```json``` block."""

    response = call_claude(prompt, system=system)
    categories = extract_json_from_response(response)

    print(f"  Generated {len(categories)} categories")
    return categories


def generate_services(
    input_data: dict,
    categories: list[dict],
    rules: str = "",
    field_mappings: dict | None = None,
    existing_api_data: list | None = None,
) -> list[dict]:
    """
    Generate services.json using Claude.

    Args:
        input_data: Dict from read_all_inputs()
        categories: Generated categories (for category_id assignment)
        rules: User-defined rules text
        field_mappings: Service field mapping config
        existing_api_data: Existing services from API (for merge)
    """
    input_summary = _build_input_summary(input_data, max_rows=10)

    categories_ref = json.dumps(categories, ensure_ascii=False, indent=2)

    col_mappings = ""
    if field_mappings and field_mappings.get("columns"):
        cols = field_mappings["columns"]
        col_mappings = "## Column Mappings\n"
        for field_name, config in cols.items():
            if isinstance(config, dict) and config.get("source"):
                col_mappings += f"- {config['source']} -> {field_name}"
                if config.get("rules"):
                    col_mappings += f" (Rule: {config['rules']})"
                col_mappings += "\n"

    api_context = ""
    if existing_api_data:
        # Show first 20 services as reference
        sample = existing_api_data[:20]
        api_context = f"""
## Existing API Services (source of truth for IDs, names, prices)
{json.dumps(sample, ensure_ascii=False, indent=2)}
Total in API: {len(existing_api_data)}

CRITICAL RULES for API data:
- If a service exists in API, use API's id, name_i18n, category_id, price_*, duration_minutes
- Only fill description_i18n from input data if API's description is empty
- NEVER create duplicates of existing API services
- New services (in input but not in API) get id = max_api_id + 1, +2, ...
"""

    system = """You are a data processing assistant for a medical clinic management system (DialogGauge).
Your task is to extract services from raw input data and generate structured JSON.
For service names: extract the main procedure name, translate to English.
For descriptions: include the full effect/description text, translate to both EN and RU.
For duration: extract from text context if mentioned (e.g. "30 minutes" -> 30).
Match each service to the correct category_id from the provided categories list.
Do NOT invent data. Output valid JSON only."""

    prompt = f"""## Task: Generate services.json

Extract services from input data and create a JSON array.

## Categories Reference (use these for category_id)
{categories_ref}

## Input Data
{input_summary}

{col_mappings}

{api_context}

## User Rules
{rules if rules else "Standard processing: extract services, translate names and descriptions to EN+RU, match to categories, parse prices and durations"}

## Output Format
Return a JSON array where each item has:
- "id": integer
- "category_id": integer (must match a category from the reference)
- "name_i18n": {{"en": "English Name", "ru": "Russian Name"}}
- "description_i18n": {{"en": "English description", "ru": "Russian description"}}
- "duration_minutes": integer or null
- "price_min": float or null
- "price_max": float or null
- "price_note_i18n": {{}} or {{"en": "note"}}
- "branches": list of branch strings (use all branches if not specified)

Only output the JSON array, no explanation. Wrap in ```json``` block."""

    response = call_claude(prompt, system=system, max_tokens=MAX_TOKENS)
    services = extract_json_from_response(response)

    print(f"  Generated {len(services)} services")
    return services


def generate_practitioners(
    input_data: dict,
    rules: str = "",
    field_mappings: dict | None = None,
    existing_api_data: list | None = None,
) -> list[dict]:
    """Generate practitioners.json using Claude."""
    input_summary = _build_input_summary(input_data, max_rows=10)

    col_mappings = ""
    if field_mappings and field_mappings.get("columns"):
        cols = field_mappings["columns"]
        col_mappings = "## Column Mappings\n"
        for field_name, config in cols.items():
            if isinstance(config, dict) and config.get("source"):
                col_mappings += f"- {config['source']} -> {field_name}"
                if config.get("rules"):
                    col_mappings += f" (Rule: {config['rules']})"
                col_mappings += "\n"

    api_context = ""
    if existing_api_data:
        api_context = f"""
## Existing API Practitioners
{json.dumps(existing_api_data[:15], ensure_ascii=False, indent=2)}
Total in API: {len(existing_api_data)}

Use API IDs for matching practitioners. Only add truly new ones.
"""

    system = """You are a data processing assistant for a medical clinic management system.
Extract practitioner/doctor information from input data.
Parse names, specialities, languages, and descriptions.
Output valid JSON only."""

    prompt = f"""## Task: Generate practitioners.json

Extract practitioners from input data.

## Input Data
{input_summary}

{col_mappings}

{api_context}

## User Rules
{rules if rules else "Extract all practitioners/doctors with their details"}

## Output Format
Return a JSON array where each item has:
- "id": integer
- "name": "Full Name"
- "name_i18n": {{"en": "Full Name"}}
- "speciality": string
- "languages": ["ENGLISH", ...]
- "description_i18n": {{"en": "...", "ru": "..."}}
- "branches": list of strings

Only output the JSON array. Wrap in ```json``` block."""

    response = call_claude(prompt, system=system)
    practitioners = extract_json_from_response(response)

    print(f"  Generated {len(practitioners)} practitioners")
    return practitioners


def merge_with_api_data(
    generated: list[dict],
    api_data: list[dict],
    entity_type: str = "services",
) -> list[dict]:
    """
    Merge generated data with API data following API-first principle.

    - API data is source of truth for id, name, category_id, prices
    - Generated data fills description_i18n where API is empty
    """
    from src.shared.sync import normalize_name, get_item_name

    # Build API lookup
    api_by_name = {}
    for item in api_data:
        name = normalize_name(get_item_name(item))
        if name:
            api_by_name[name] = item

    max_api_id = max((item["id"] for item in api_data), default=0)
    next_id = max_api_id + 1

    merged = []
    matched_count = 0
    new_count = 0

    for gen_item in generated:
        gen_name = normalize_name(get_item_name(gen_item))
        api_item = api_by_name.get(gen_name)

        if api_item:
            # Merge: API structure + generated descriptions
            result = dict(api_item)

            # Fill description only if API is empty
            api_desc = api_item.get("description_i18n", {})
            gen_desc = gen_item.get("description_i18n", {})

            if not api_desc or (not api_desc.get("en") and not api_desc.get("ru")):
                if gen_desc:
                    result["description_i18n"] = gen_desc

            # Fill duration only if API is 0 or missing
            if not result.get("duration_minutes") and gen_item.get("duration_minutes"):
                result["duration_minutes"] = gen_item["duration_minutes"]

            matched_count += 1
        else:
            # New item
            result = dict(gen_item)
            result["id"] = next_id
            next_id += 1
            new_count += 1

        merged.append(result)

    # Add API items not in generated data (don't remove them!)
    gen_names = {normalize_name(get_item_name(g)) for g in generated}
    for api_item in api_data:
        api_name = normalize_name(get_item_name(api_item))
        if api_name not in gen_names:
            merged.append(api_item)

    print(f"  Merge: {matched_count} matched, {new_count} new, {len(api_data) - matched_count} API-only kept")

    # Sort by id
    merged.sort(key=lambda x: x.get("id", 0))

    return merged


# === Helpers ===

def _build_input_summary(input_data: dict, max_rows: int = 5) -> str:
    """Build a text summary of input data for Claude prompt."""
    parts = []

    for filename, csv_data in input_data.get("csv_files", {}).items():
        headers = csv_data["headers"]
        rows = csv_data["rows"]

        parts.append(f"### CSV File: {filename}")
        parts.append(f"Columns: {', '.join(headers)}")
        parts.append(f"Total rows: {csv_data['row_count']}")

        if rows:
            parts.append("\nSample rows:")
            for row in rows[:max_rows]:
                row_text = " | ".join(
                    f"{k}: {v[:150]}{'...' if len(v) > 150 else ''}"
                    for k, v in row.items()
                    if v and k.strip()
                )
                parts.append(f"  - {row_text}")

        parts.append("")

    for filename, json_data in input_data.get("json_files", {}).items():
        if isinstance(json_data, list):
            parts.append(f"### JSON File: {filename} ({len(json_data)} items)")
            if json_data:
                parts.append(f"Sample: {json.dumps(json_data[0], ensure_ascii=False)[:300]}")
        elif isinstance(json_data, dict):
            parts.append(f"### JSON File: {filename}")
            parts.append(f"Keys: {', '.join(list(json_data.keys())[:20])}")
        parts.append("")

    return "\n".join(parts)
