#!/usr/bin/env python3
"""
Web server for RefoAuto pipeline management.

Vanilla Python HTTP server (no Flask) with JSON API endpoints.
Serves static files from web/static/ and handles API routes.

Usage:
    python web/server.py
    python web/server.py --port 8080
    python run.py web
"""

import csv
import io
import json
import os
import subprocess
import sys
import threading
import time
import re
import cgi
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.shared.api_client import DGApiClient
from src.config_manager import ConfigManager


# === Config Management ===

def load_clients_config() -> dict:
    config_path = PROJECT_ROOT / "clients_config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_clients_config(config: dict) -> None:
    config_path = PROJECT_ROOT / "clients_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_client_settings(client_name: str) -> dict:
    """Load client-specific settings (field mappings, rules, pipeline)."""
    config = load_clients_config()
    client = config.get("clients", {}).get(client_name, {})
    steps = client.get("pipeline_steps") or get_default_pipeline_steps(client_name)
    return {
        "field_mappings": client.get("field_mappings", {}),
        "common_rules": client.get("common_rules", ""),
        "pipeline_steps": steps,
        "uploaded_files": client.get("uploaded_files", []),
    }


def save_client_settings(client_name: str, settings: dict) -> None:
    config = load_clients_config()
    if client_name not in config.get("clients", {}):
        return
    for key in ("field_mappings", "common_rules", "pipeline_steps", "uploaded_files"):
        if key in settings:
            config["clients"][client_name][key] = settings[key]
    save_clients_config(config)


def get_default_pipeline_steps(client_name: str) -> list:
    """Default pipeline steps based on available scripts."""
    base_path = PROJECT_ROOT / "src" / client_name / "scripts"
    steps = []
    default_scripts = [
        ("get_categories", "Fetch data from API", ["--all"]),
        ("sync_with_api", "Sync IDs with API", []),
        ("process_data", "Process raw input data", []),
        ("merge_descriptions", "Merge descriptions from CSV", []),
        ("generate_categories", "Generate categories from CSV", []),
        ("translate", "Translate descriptions", []),
        ("fix_locations", "Distribute data across locations", ["--analyze"]),
        ("delete_duplicates", "Delete duplicate services", []),
    ]
    for name, desc, args in default_scripts:
        script_file = base_path / f"{name}.py"
        if script_file.exists():
            steps.append({
                "name": name,
                "description": desc,
                "enabled": True,
                "args": args,
            })
    return steps


# === Field Extraction ===

def extract_fields_from_csv(filepath: Path) -> list[dict]:
    """Extract column names and sample data from CSV."""
    fields = []
    with open(filepath, "r", encoding="utf-8") as f:
        # Try to find header row (skip empty rows)
        lines = f.readlines()

    # Find first non-empty row with content
    header_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip().strip(",")
        if stripped and len(stripped.split(",")) > 1:
            header_idx = i
            break

    reader = csv.DictReader(lines[header_idx:])
    if not reader.fieldnames:
        return []

    # Collect samples (up to 3 rows)
    samples = {fn: [] for fn in reader.fieldnames if fn}
    row_count = 0
    for row in reader:
        if row_count >= 3:
            break
        for fn in reader.fieldnames:
            if fn and row.get(fn, "").strip():
                samples[fn].append(row[fn].strip()[:200])
        row_count += 1

    for fn in reader.fieldnames:
        if fn and fn.strip():
            fields.append({
                "name": fn.strip(),
                "sample": samples.get(fn, []),
                "hidden": False,
                "prompt": "",
            })

    return fields


def extract_fields_from_json(filepath: Path) -> list[dict]:
    """Extract keys and sample data from JSON."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list) and data:
        item = data[0]
    elif isinstance(data, dict):
        item = data
    else:
        return []

    fields = []
    for key, value in item.items():
        sample_str = str(value)[:200] if value is not None else ""
        fields.append({
            "name": key,
            "sample": [sample_str] if sample_str else [],
            "hidden": False,
            "prompt": "",
        })

    return fields


def extract_fields_from_html(filepath: Path) -> list[dict]:
    """Extract table headers from HTML."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    headers = re.findall(r'<th[^>]*>(.*?)</th>', content, re.IGNORECASE | re.DOTALL)
    headers = [re.sub(r'<[^>]+>', '', h).strip() for h in headers]

    fields = []
    for h in headers:
        if h:
            fields.append({
                "name": h,
                "sample": [],
                "hidden": False,
                "prompt": "",
            })

    return fields


# === Generation with Claude ===

generate_logs = {}  # client_name -> {"status": "...", "output": str}


def run_generate_async(client_name: str, options: dict):
    """Run Claude generation pipeline in background thread."""
    generate_logs[client_name] = {"status": "running", "output": "", "started_at": time.time()}

    gen_args = [
        sys.executable,
        str(PROJECT_ROOT / "src" / "shared" / "generate_pipeline.py"),
        client_name,
    ]

    if options.get("categories_only"):
        gen_args.append("--categories-only")
    if options.get("services_only"):
        gen_args.append("--services-only")
    if options.get("practitioners_only"):
        gen_args.append("--practitioners-only")
    if options.get("no_api"):
        gen_args.append("--no-api")
    if options.get("no_merge"):
        gen_args.append("--no-merge")
    if options.get("sync"):
        gen_args.append("--sync")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    try:
        result = subprocess.run(
            gen_args,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(PROJECT_ROOT),
            timeout=600,  # 10 min max for generation
        )
        output = result.stdout
        if result.stderr:
            output += f"\n--- STDERR ---\n{result.stderr}"
        generate_logs[client_name]["output"] = output
        generate_logs[client_name]["status"] = "done" if result.returncode == 0 else "error"
    except subprocess.TimeoutExpired:
        generate_logs[client_name]["output"] = "ERROR: Generation timed out (600s)"
        generate_logs[client_name]["status"] = "error"
    except Exception as e:
        generate_logs[client_name]["output"] = f"ERROR: {e}"
        generate_logs[client_name]["status"] = "error"

    generate_logs[client_name]["finished_at"] = time.time()


# === Pipeline Execution ===

pipeline_logs = {}  # client_name -> {"status": "running"|"done"|"error", "output": str}


def run_pipeline_step(client_name: str, step_name: str, args: list, mode: str = "dry-run") -> str:
    """Run a single pipeline step and return output."""
    script_map = {
        "get_categories": "get_categories.py",
        "sync_with_api": "sync_with_api.py",
        "process_data": "process_data.py",
        "fix_locations": "fix_locations.py",
        "merge_descriptions": "merge_descriptions.py",
        "generate_categories": "generate_categories.py",
        "translate": "translate.py",
        "delete_duplicates": "delete_duplicates.py",
        "parse_practitioners": "parse_practitioners_sheet.py",
        "print_quality": "print_quality.py",
    }

    script_file = script_map.get(step_name, f"{step_name}.py")
    script_path = PROJECT_ROOT / "src" / client_name / "scripts" / script_file

    if not script_path.exists():
        return f"ERROR: Script not found: {script_path}"

    cmd_args = [sys.executable, str(script_path)] + args

    # Handle execute mode for fix_locations
    if step_name == "fix_locations" and mode == "execute":
        if "--analyze" in cmd_args:
            cmd_args.remove("--analyze")
        if "--execute" not in cmd_args:
            cmd_args.append("--execute")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    try:
        result = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT / "src" / client_name),
            env=env,
            timeout=300,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n--- STDERR ---\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n--- EXIT CODE: {result.returncode} ---"
        return output
    except subprocess.TimeoutExpired:
        return "ERROR: Script timed out (300s)"
    except Exception as e:
        return f"ERROR: {e}"


def run_pipeline_async(client_name: str, steps: list, mode: str, locations: list | None):
    """Run pipeline steps in background thread."""
    pipeline_logs[client_name] = {"status": "running", "output": "", "started_at": time.time()}

    config = load_clients_config()
    client = config.get("clients", {}).get(client_name, {})
    all_locations = [loc["location_id"] for loc in client.get("locations", [])]

    target_locations = locations if locations else all_locations

    output_parts = []
    for step in steps:
        step_name = step if isinstance(step, str) else step.get("name", "")
        step_args = [] if isinstance(step, str) else step.get("args", [])

        output_parts.append(f"\n{'='*60}\nRUNNING: {step_name}\n{'='*60}\n")

        # For location-dependent steps, run for each location
        if step_name in ("get_categories", "fix_locations") and len(target_locations) > 1:
            for loc_id in target_locations:
                output_parts.append(f"\n--- Location {loc_id} ---\n")
                loc_args = step_args + [f"--location={loc_id}"]
                result = run_pipeline_step(client_name, step_name, loc_args, mode)
                output_parts.append(result)
        else:
            result = run_pipeline_step(client_name, step_name, step_args, mode)
            output_parts.append(result)

        pipeline_logs[client_name]["output"] = "\n".join(output_parts)

    pipeline_logs[client_name]["status"] = "done"
    pipeline_logs[client_name]["finished_at"] = time.time()


# === Client Script Templates ===

def _generate_client_scripts(client_name: str, client_dir: Path) -> None:
    """Generate standard scripts for a new client."""
    scripts_dir = client_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    # get_categories.py
    (scripts_dir / "get_categories.py").write_text(f'''#!/usr/bin/env python3
"""Fetch data from DialogGauge API for {client_name}."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.shared.api_client import DGApiClient
from src.config_manager import get_client_config

config = get_client_config("{client_name}")
LOCATION_ID = config.get_location_ids()[0] if config.get_location_ids() else None

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent
DATA_API_DIR = PROJECT_ROOT / "data" / "api"
DATA_API_DIR.mkdir(parents=True, exist_ok=True)

_client = DGApiClient()

def get_categories(location_id=LOCATION_ID, flat=True, include_archived=True, session_cookie=None):
    return _client.get_categories(location_id, flat, include_archived)

def get_services(location_id=LOCATION_ID, include_archived=True, session_cookie=None):
    return _client.get_services(location_id, include_archived)

def get_practitioners(location_id=LOCATION_ID, include_archived=True, session_cookie=None):
    return _client.get_practitioners(location_id, include_archived)

def create_category(name, location_id=LOCATION_ID, **kwargs):
    return _client.create_category(location_id, name, **kwargs)

def create_service(name, location_id=LOCATION_ID, **kwargs):
    return _client.create_service(location_id, name, **kwargs)


def main():
    fetch_services = "--services" in sys.argv or "--all" in sys.argv
    fetch_practitioners = "--practitioners" in sys.argv or "--all" in sys.argv
    fetch_categories = "--categories" in sys.argv or "--all" in sys.argv or (
        not fetch_services and not fetch_practitioners
    )

    all_locations = config.get_location_ids()
    target_locs = all_locations

    for arg in sys.argv:
        if arg.startswith("--location="):
            target_locs = [int(arg.split("=")[1])]

    for loc_id in target_locs:
        print(f"\\n=== Location {{loc_id}} ===")

        if fetch_categories:
            cats = get_categories(location_id=loc_id)
            print(f"Categories: {{len(cats)}}")
            with open(DATA_API_DIR / f"categories_api_response.json", "w", encoding="utf-8") as f:
                json.dump(cats, f, ensure_ascii=False, indent=2)

        if fetch_services:
            svcs = get_services(location_id=loc_id)
            print(f"Services: {{len(svcs)}}")
            with open(DATA_API_DIR / f"services_api_response.json", "w", encoding="utf-8") as f:
                json.dump(svcs, f, ensure_ascii=False, indent=2)

        if fetch_practitioners:
            practs = get_practitioners(location_id=loc_id)
            print(f"Practitioners: {{len(practs)}}")
            with open(DATA_API_DIR / f"practitioners_api_response.json", "w", encoding="utf-8") as f:
                json.dump(practs, f, ensure_ascii=False, indent=2)

    print("Done!")


if __name__ == "__main__":
    main()
''')

    # sync_with_api.py
    (scripts_dir / "sync_with_api.py").write_text(f'''#!/usr/bin/env python3
"""Sync local JSON files with DialogGauge API for {client_name}."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.shared.sync import sync_items, update_references, print_report
from src.shared.utils import load_json, save_json
from get_categories import get_categories as fetch_api_categories
from get_categories import get_services as fetch_api_services
from get_categories import get_practitioners as fetch_api_practitioners

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent
DATA_OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
DATA_API_DIR = PROJECT_ROOT / "data" / "api"
DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_API_DIR.mkdir(parents=True, exist_ok=True)


def sync_categories():
    print("\\nSYNCING CATEGORIES")
    local = load_json(DATA_OUTPUT_DIR / "categories.json")
    if not local:
        return {{}}, {{}}
    api = fetch_api_categories(flat=True, include_archived=True)
    synced, id_mapping, report = sync_items(local, api, "categories")
    for i, cat in enumerate(synced, 1):
        cat["sort_order"] = i
    save_json(DATA_OUTPUT_DIR / "categories.json", synced)
    print_report(report)
    return id_mapping, report


def sync_services(category_id_mapping=None):
    print("\\nSYNCING SERVICES")
    local = load_json(DATA_OUTPUT_DIR / "services.json")
    if not local:
        return {{}}, {{}}
    api = fetch_api_services(include_archived=True)
    synced, id_mapping, report = sync_items(local, api, "services")
    if category_id_mapping:
        synced = update_references(synced, "category_id", category_id_mapping)
    save_json(DATA_OUTPUT_DIR / "services.json", synced)
    print_report(report)
    return id_mapping, report


def sync_practitioners():
    print("\\nSYNCING PRACTITIONERS")
    local = load_json(DATA_OUTPUT_DIR / "practitioners.json")
    if not local:
        return {{}}, {{}}
    api = fetch_api_practitioners(include_archived=True)
    synced, id_mapping, report = sync_items(local, api, "practitioners")
    save_json(DATA_OUTPUT_DIR / "practitioners.json", synced)
    print_report(report)
    return id_mapping, report


def main():
    cat_map, _ = sync_categories()
    svc_map, _ = sync_services(cat_map)
    sync_practitioners()
    save_json(DATA_API_DIR / "_sync_report.json", {{}})
    print("\\nSYNC COMPLETE")


if __name__ == "__main__":
    main()
''')

    # fix_locations.py
    (scripts_dir / "fix_locations.py").write_text(f'''#!/usr/bin/env python3
"""Distribute data across locations for {client_name}."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.shared.api_client import DGApiClient
from src.shared.utils import load_json
from src.shared.sync import normalize_name, get_item_name
from src.config_manager import get_client_config

config = get_client_config("{client_name}")
PROJECT_ROOT = Path(__file__).parent.parent
DATA_OUTPUT_DIR = PROJECT_ROOT / "data" / "output"

_client = DGApiClient()


def _matches_branch(branches, branch):
    if not branches:
        return True
    for b in branches:
        if b.lower() in ("all", "both", "*", ""):
            return True
        if b == branch:
            return True
    return False


def analyze():
    categories = load_json(DATA_OUTPUT_DIR / "categories.json") or []
    services = load_json(DATA_OUTPUT_DIR / "services.json") or []
    practitioners = load_json(DATA_OUTPUT_DIR / "practitioners.json") or []
    sp_links = load_json(DATA_OUTPUT_DIR / "service_practitioners.json") or []

    print(f"Categories: {{len(categories)}}")
    print(f"Services: {{len(services)}}")
    print(f"Practitioners: {{len(practitioners)}}")
    print(f"Links: {{len(sp_links)}}")

    for loc_id in config.get_location_ids():
        loc_info = config.get_location_info(loc_id)
        branch = loc_info.get("branch", "") if loc_info else ""
        bs = [s for s in services if _matches_branch(s.get("branches", []), branch)]
        bp = [p for p in practitioners if _matches_branch(p.get("branches", []), branch)]
        print(f"  Location {{loc_id}} ({{branch}}): {{len(bs)}} services, {{len(bp)}} practitioners")


def _build_name_map(api_items):
    m = {{}}
    for item in api_items:
        name = normalize_name(get_item_name(item))
        if name:
            m[name] = item
    return m


def execute():
    categories = load_json(DATA_OUTPUT_DIR / "categories.json") or []
    services = load_json(DATA_OUTPUT_DIR / "services.json") or []
    practitioners = load_json(DATA_OUTPUT_DIR / "practitioners.json") or []
    sp_links = load_json(DATA_OUTPUT_DIR / "service_practitioners.json") or []

    for loc_id in config.get_location_ids():
        loc_info = config.get_location_info(loc_id)
        branch = loc_info.get("branch", "") if loc_info else ""
        print(f"\\n=== Location {{loc_id}} ({{branch}}) ===")

        # Fetch existing to avoid duplicates
        print(f"\\n--- Fetching existing API data ---")
        existing_cats = _build_name_map(_client.get_categories(loc_id))
        existing_svcs = _build_name_map(_client.get_services(loc_id))
        existing_practs = _build_name_map(_client.get_practitioners(loc_id))
        print(f"  API: {{len(existing_cats)}} cats, {{len(existing_svcs)}} svcs, {{len(existing_practs)}} practs")

        # Categories
        print(f"\\n--- Categories ({{len(categories)}}) ---")
        cat_id_map = {{}}
        c_new, c_skip = 0, 0
        for cat in categories:
            name_en = cat.get("name_i18n", {{}}).get("en", "")
            if not name_en:
                continue
            norm = normalize_name(name_en)
            if norm in existing_cats:
                cat_id_map[cat["id"]] = existing_cats[norm]["id"]
                print(f"  = exists: {{name_en}} ({{cat['id']}} -> {{existing_cats[norm]['id']}})")
                c_skip += 1
            else:
                try:
                    result = _client.create_category(loc_id, name_en)
                    cat_id_map[cat["id"]] = result.get("id")
                    existing_cats[norm] = result
                    print(f"  + new: {{name_en}} ({{cat['id']}} -> {{result.get('id')}})")
                    c_new += 1
                except Exception as e:
                    print(f"  ! error: {{name_en}}: {{e}}")
        print(f"  {{c_new}} created, {{c_skip}} existed")

        # Services
        branch_svcs = [s for s in services if _matches_branch(s.get("branches", []), branch)]
        print(f"\\n--- Services ({{len(branch_svcs)}}) ---")
        svc_id_map = {{}}
        s_new, s_skip = 0, 0
        for svc in branch_svcs:
            name_en = svc.get("name_i18n", {{}}).get("en", "")
            if not name_en:
                continue
            norm = normalize_name(name_en)
            api_cat_id = cat_id_map.get(svc.get("category_id"))
            if norm in existing_svcs:
                api_item = existing_svcs[norm]
                svc_id_map[svc["id"]] = api_item["id"]
                print(f"  = exists: {{name_en}} ({{svc['id']}} -> {{api_item['id']}})")
                s_skip += 1
                # Fill empty description
                if svc.get("description_i18n", {{}}).get("en") and not api_item.get("description_i18n", {{}}).get("en"):
                    try:
                        _client.update_service(loc_id, api_item["id"], {{"description_i18n": svc["description_i18n"]}})
                        print(f"    -> updated description")
                    except:
                        pass
            else:
                try:
                    result = _client.create_service(
                        loc_id, name_en,
                        category_id=api_cat_id,
                        description=svc.get("description_i18n", {{}}).get("en"),
                        duration_minutes=svc.get("duration_minutes"),
                        price_min=svc.get("price_min"),
                        price_max=svc.get("price_max"),
                    )
                    svc_id_map[svc["id"]] = result.get("id")
                    existing_svcs[norm] = result
                    print(f"  + new: {{name_en}} ({{svc['id']}} -> {{result.get('id')}})")
                    s_new += 1
                except Exception as e:
                    print(f"  ! error: {{name_en}}: {{e}}")
        print(f"  {{s_new}} created, {{s_skip}} existed")

        # Practitioners
        branch_practs = [p for p in practitioners if _matches_branch(p.get("branches", []), branch)]
        print(f"\\n--- Practitioners ({{len(branch_practs)}}) ---")
        pract_id_map = {{}}
        for lp in branch_practs:
            ln = normalize_name(lp.get("name", ""))
            if ln in existing_practs:
                pract_id_map[lp["id"]] = existing_practs[ln]["id"]
        print(f"  Matched {{len(pract_id_map)}}/{{len(branch_practs)}}")

        # Links
        print(f"\\n--- Links ---")
        ok, skip = 0, 0
        for link in sp_links:
            asid = svc_id_map.get(link.get("service_id"))
            apid = pract_id_map.get(link.get("practitioner_id"))
            if asid and apid:
                try:
                    _client.create_service_practitioner(loc_id, asid, apid)
                    ok += 1
                except:
                    skip += 1
            else:
                skip += 1
        print(f"  {{ok}} created, {{skip}} skipped")

    print("\\nDone!")


def main():
    if "--execute" in sys.argv:
        execute()
    else:
        analyze()


if __name__ == "__main__":
    main()
''')

    print(f"  Generated scripts: get_categories.py, sync_with_api.py, fix_locations.py")


# === HTTP Handler ===

class APIHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler with API routes."""

    def __init__(self, *args, **kwargs):
        # Serve static files from web/static/
        super().__init__(*args, directory=str(PROJECT_ROOT / "web" / "static"), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # API routes
        if path.startswith("/api/"):
            self._handle_api_get(path, parse_qs(parsed.query))
            return

        # Serve index.html for root
        if path == "/":
            self.path = "/index.html"

        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            self._handle_api_post(path)
            return

        self._send_error(404, "Not found")

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            self._handle_api_put(path)
            return

        self._send_error(404, "Not found")

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            self._handle_api_delete(path)
            return

        self._send_error(404, "Not found")

    # === API GET ===

    def _handle_api_get(self, path: str, params: dict):
        # GET /api/clients
        if path == "/api/clients":
            config = load_clients_config()
            clients = []
            for name, data in config.get("clients", {}).items():
                clients.append({
                    "name": name,
                    "display_name": data.get("display_name", name),
                    "enabled": data.get("enabled", True),
                    "locations": data.get("locations", []),
                })
            self._send_json({"clients": clients, "active_client": config.get("active_client")})
            return

        # GET /api/clients/{name}
        m = re.match(r'^/api/clients/([^/]+)$', path)
        if m:
            client_name = m.group(1)
            config = load_clients_config()
            client = config.get("clients", {}).get(client_name)
            if not client:
                self._send_error(404, f"Client '{client_name}' not found")
                return
            self._send_json({"name": client_name, **client})
            return

        # GET /api/clients/{name}/settings
        m = re.match(r'^/api/clients/([^/]+)/settings$', path)
        if m:
            client_name = m.group(1)
            settings = load_client_settings(client_name)
            self._send_json(settings)
            return

        # GET /api/clients/{name}/data/{type}
        m = re.match(r'^/api/clients/([^/]+)/data/(\w+)$', path)
        if m:
            client_name, data_type = m.group(1), m.group(2)
            filepath = PROJECT_ROOT / "src" / client_name / "data" / "output" / f"{data_type}.json"
            if filepath.exists():
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._send_json(data)
            else:
                self._send_json([])
            return

        # GET /api/clients/{name}/files
        m = re.match(r'^/api/clients/([^/]+)/files$', path)
        if m:
            client_name = m.group(1)
            input_dir = PROJECT_ROOT / "src" / client_name / "data" / "input"
            files = []
            if input_dir.exists():
                for f in sorted(input_dir.iterdir()):
                    if f.is_file():
                        files.append({
                            "name": f.name,
                            "size": f.stat().st_size,
                            "ext": f.suffix.lower(),
                        })
            self._send_json({"files": files})
            return

        # GET /api/pipeline/{client}/status
        m = re.match(r'^/api/pipeline/([^/]+)/status$', path)
        if m:
            client_name = m.group(1)
            log = pipeline_logs.get(client_name, {"status": "idle", "output": ""})
            self._send_json(log)
            return

        # GET /api/auth/status
        if path == "/api/auth/status":
            client = DGApiClient()
            status = client.check_auth_status()
            self._send_json(status)
            return

        # GET /api/generate/{client}/status
        m = re.match(r'^/api/generate/([^/]+)/status$', path)
        if m:
            client_name = m.group(1)
            log = generate_logs.get(client_name, {"status": "idle", "output": ""})
            self._send_json(log)
            return

        self._send_error(404, f"Unknown API endpoint: {path}")

    # === API POST ===

    def _handle_api_post(self, path: str):
        # File upload — handle BEFORE reading body as JSON
        m = re.match(r'^/api/upload/([^/]+)$', path)
        if m:
            client_name = m.group(1)
            self._handle_file_upload(client_name)
            return

        body = self._read_body()

        # POST /api/clients
        if path == "/api/clients":
            config = load_clients_config()
            name = body.get("name", "").strip().lower().replace(" ", "_")
            if not name:
                self._send_error(400, "Client name is required")
                return
            if name in config.get("clients", {}):
                self._send_error(409, f"Client '{name}' already exists")
                return

            # Create client directories
            base_path = f"src/{name}"
            client_dir = PROJECT_ROOT / base_path
            for subdir in ["scripts", "models", "data/input", "data/output", "data/api", "config", "docs", "tests"]:
                (client_dir / subdir).mkdir(parents=True, exist_ok=True)

            # Write __init__.py files
            for init_dir in ["", "models", "scripts"]:
                init_path = client_dir / init_dir / "__init__.py" if init_dir else client_dir / "__init__.py"
                if not init_path.exists():
                    init_path.write_text("")

            # Write model re-export
            models_file = client_dir / "models" / "pydantic_models.py"
            models_file.write_text(
                f'"""\n{name.title()} models -- re-exported from shared.\n"""\n'
                'from src.shared.models.pydantic_models import *  # noqa: F401,F403\n'
            )

            # Generate client scripts from templates
            _generate_client_scripts(name, client_dir)

            new_client = {
                "enabled": body.get("enabled", True),
                "display_name": body.get("display_name", name.title()),
                "base_path": base_path,
                "locations": body.get("locations", []),
                "branch_to_location": body.get("branch_to_location", {}),
            }

            config["clients"][name] = new_client
            save_clients_config(config)
            self._send_json({"name": name, **new_client}, status=201)
            return

        # POST /api/extract-fields/{client}
        m = re.match(r'^/api/extract-fields/([^/]+)$', path)
        if m:
            client_name = m.group(1)
            filename = body.get("filename", "")
            if not filename:
                self._send_error(400, "filename is required")
                return

            filepath = PROJECT_ROOT / "src" / client_name / "data" / "input" / filename
            if not filepath.exists():
                self._send_error(404, f"File not found: {filename}")
                return

            ext = filepath.suffix.lower()
            if ext == ".csv":
                fields = extract_fields_from_csv(filepath)
            elif ext == ".json":
                fields = extract_fields_from_json(filepath)
            elif ext in (".html", ".htm"):
                fields = extract_fields_from_html(filepath)
            else:
                self._send_error(400, f"Unsupported file type: {ext}")
                return

            self._send_json({"filename": filename, "fields": fields})
            return

        # POST /api/pipeline/{client}/run
        m = re.match(r'^/api/pipeline/([^/]+)/run$', path)
        if m:
            client_name = m.group(1)
            steps = body.get("steps", [])
            mode = body.get("mode", "dry-run")
            locations = body.get("locations", None)

            if not steps:
                self._send_error(400, "No steps specified")
                return

            # Run in background
            thread = threading.Thread(
                target=run_pipeline_async,
                args=(client_name, steps, mode, locations),
                daemon=True,
            )
            thread.start()

            self._send_json({"status": "started", "steps": len(steps)})
            return

        # POST /api/auth/refresh
        if path == "/api/auth/refresh":
            try:
                client = DGApiClient()
                client.get_session(force_refresh=True)
                status = client.check_auth_status()
                self._send_json({"status": "ok", **status})
            except Exception as e:
                self._send_error(500, f"Auth failed: {e}")
            return

        # POST /api/generate/{client}
        m = re.match(r'^/api/generate/([^/]+)$', path)
        if m:
            client_name = m.group(1)
            options = body or {}

            thread = threading.Thread(
                target=run_generate_async,
                args=(client_name, options),
                daemon=True,
            )
            thread.start()

            self._send_json({"status": "started", "client": client_name})
            return

        self._send_error(404, f"Unknown API endpoint: {path}")

    # === API PUT ===

    def _handle_api_put(self, path: str):
        body = self._read_body()

        # PUT /api/clients/{name}
        m = re.match(r'^/api/clients/([^/]+)$', path)
        if m:
            client_name = m.group(1)
            config = load_clients_config()
            if client_name not in config.get("clients", {}):
                self._send_error(404, f"Client '{client_name}' not found")
                return

            client = config["clients"][client_name]
            for key in ("display_name", "enabled", "locations", "branch_to_location"):
                if key in body:
                    client[key] = body[key]

            if "active" in body and body["active"]:
                config["active_client"] = client_name

            save_clients_config(config)
            self._send_json({"name": client_name, **client})
            return

        # PUT /api/clients/{name}/settings
        m = re.match(r'^/api/clients/([^/]+)/settings$', path)
        if m:
            client_name = m.group(1)
            save_client_settings(client_name, body)
            self._send_json({"status": "ok"})
            return

        self._send_error(404, f"Unknown API endpoint: {path}")

    # === API DELETE ===

    def _handle_api_delete(self, path: str):
        # DELETE /api/clients/{name}
        m = re.match(r'^/api/clients/([^/]+)$', path)
        if m:
            client_name = m.group(1)
            config = load_clients_config()
            if client_name not in config.get("clients", {}):
                self._send_error(404, f"Client '{client_name}' not found")
                return

            del config["clients"][client_name]
            if config.get("active_client") == client_name:
                remaining = list(config.get("clients", {}).keys())
                config["active_client"] = remaining[0] if remaining else None
            save_clients_config(config)
            self._send_json({"status": "deleted"})
            return

        self._send_error(404, f"Unknown API endpoint: {path}")

    # === File Upload ===

    def _handle_file_upload(self, client_name: str):
        content_type = self.headers.get("Content-Type", "")

        if "multipart/form-data" in content_type:
            # Parse multipart form data
            boundary = content_type.split("boundary=")[1] if "boundary=" in content_type else None
            if not boundary:
                self._send_error(400, "Missing boundary in multipart form")
                return

            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            # Simple multipart parser
            parts = body.split(f"--{boundary}".encode())
            for part in parts:
                if b"filename=" not in part:
                    continue

                # Extract filename
                header_end = part.find(b"\r\n\r\n")
                if header_end == -1:
                    continue
                headers_raw = part[:header_end].decode("utf-8", errors="replace")
                file_data = part[header_end + 4:]
                if file_data.endswith(b"\r\n"):
                    file_data = file_data[:-2]

                fn_match = re.search(r'filename="([^"]+)"', headers_raw)
                if not fn_match:
                    continue
                filename = fn_match.group(1)

                # Save file
                input_dir = PROJECT_ROOT / "src" / client_name / "data" / "input"
                input_dir.mkdir(parents=True, exist_ok=True)
                filepath = input_dir / filename
                with open(filepath, "wb") as f:
                    f.write(file_data)

                self._send_json({"filename": filename, "size": len(file_data)}, status=201)
                return

            self._send_error(400, "No file found in upload")
        else:
            self._send_error(400, "Expected multipart/form-data")

    # === Helpers ===

    def _read_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _send_json(self, data, status: int = 200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str):
        self._send_json({"error": message}, status=status)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        # Suppress noisy access logs for static files
        if args and isinstance(args[0], str) and args[0].startswith("GET /api/"):
            super().log_message(format, *args)


def main():
    port = 8080
    for arg in sys.argv[1:]:
        if arg.startswith("--port"):
            if "=" in arg:
                port = int(arg.split("=")[1])
            else:
                idx = sys.argv.index(arg)
                if idx + 1 < len(sys.argv):
                    port = int(sys.argv[idx + 1])

    # Check auth on startup
    print("Checking DialogGauge authentication...")
    api_client = DGApiClient()
    auth_status = api_client.check_auth_status()
    if auth_status["valid"]:
        print("Auth: Valid session found")
    else:
        print("Auth: No valid session. Will authenticate on first API call.")
        print("  You can also visit /api/auth/refresh to trigger auth manually.")

    server = HTTPServer(("0.0.0.0", port), APIHandler)
    print(f"\nRefoAuto Web UI running at http://localhost:{port}")
    print("Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
