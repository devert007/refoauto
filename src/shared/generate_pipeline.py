#!/usr/bin/env python3
"""
Full generation pipeline: Input data -> Claude -> Output JSON -> (optional) Sync with API.

Usage:
    python src/shared/generate_pipeline.py <client_name> [options]

Options:
    --categories-only    Generate only categories
    --services-only      Generate only services
    --practitioners-only Generate only practitioners
    --no-api             Skip API data fetch (use local cache only)
    --no-merge           Skip merging with API data
    --sync               Also sync IDs with API after generation
    --all-locations      Fetch API data for ALL locations (not just first)

Examples:
    python src/shared/generate_pipeline.py hortman
    python src/shared/generate_pipeline.py milena --categories-only
    python src/shared/generate_pipeline.py milena --sync
    python run.py hortman generate
"""

import json
import sys
import time
from pathlib import Path

# Add project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.shared.claude_generator import (
    read_all_inputs,
    generate_categories,
    generate_services,
    generate_practitioners,
    merge_with_api_data,
)
from src.shared.utils import load_json, save_json
from src.shared.api_client import DGApiClient
from src.config_manager import get_client_config


def fetch_api_data(client_name: str, all_locations: bool = True) -> dict:
    """Fetch current data from DialogGauge API for all locations."""
    config = get_client_config(client_name)
    location_ids = config.get_location_ids()

    if not all_locations:
        location_ids = location_ids[:1]

    api_client = DGApiClient()
    api_data = {
        "categories": [],
        "services": [],
        "practitioners": [],
    }

    for loc_id in location_ids:
        print(f"\nFetching API data for location {loc_id}...")

        try:
            cats = api_client.get_categories(loc_id)
            api_data["categories"].extend(cats)
            print(f"  Categories: {len(cats)}")
        except Exception as e:
            print(f"  Categories fetch failed: {e}")

        try:
            svcs = api_client.get_services(loc_id)
            api_data["services"].extend(svcs)
            print(f"  Services: {len(svcs)}")
        except Exception as e:
            print(f"  Services fetch failed: {e}")

        try:
            practs = api_client.get_practitioners(loc_id)
            api_data["practitioners"].extend(practs)
            print(f"  Practitioners: {len(practs)}")
        except Exception as e:
            print(f"  Practitioners fetch failed: {e}")

    # Deduplicate by id
    for key in api_data:
        seen_ids = set()
        unique = []
        for item in api_data[key]:
            item_id = item.get("id")
            if item_id not in seen_ids:
                seen_ids.add(item_id)
                unique.append(item)
        api_data[key] = unique

    # Cache API data
    api_dir = config.data_api_dir
    api_dir.mkdir(parents=True, exist_ok=True)
    for key, data in api_data.items():
        save_json(api_dir / f"{key}_api_response.json", data)

    return api_data


def load_cached_api_data(client_name: str) -> dict:
    """Load cached API data from local files."""
    config = get_client_config(client_name)
    api_dir = config.data_api_dir

    return {
        "categories": load_json(api_dir / "categories_api_response.json") or [],
        "services": load_json(api_dir / "services_api_response.json") or [],
        "practitioners": load_json(api_dir / "practitioners_api_response.json") or [],
    }


def load_client_rules(client_name: str) -> tuple[str, dict]:
    """Load client rules and field mappings from config."""
    from web.server import load_clients_config
    config = load_clients_config()
    client = config.get("clients", {}).get(client_name, {})

    common_rules = client.get("common_rules", "")
    field_mappings = client.get("field_mappings", {})

    # Also try to load PROMPT.md as fallback rules
    prompt_path = PROJECT_ROOT / "src" / client_name / "docs" / "PROMPT.md"
    if not common_rules and prompt_path.exists():
        with open(prompt_path, "r", encoding="utf-8") as f:
            common_rules = f.read()

    return common_rules, field_mappings


def run_pipeline(
    client_name: str,
    categories_only: bool = False,
    services_only: bool = False,
    practitioners_only: bool = False,
    no_api: bool = False,
    no_merge: bool = False,
    do_sync: bool = False,
    all_locations: bool = True,
) -> dict:
    """
    Run the full generation pipeline.

    Returns dict with generation results and stats.
    """
    start_time = time.time()
    config = get_client_config(client_name)
    output_dir = config.data_output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(f"GENERATION PIPELINE: {config.display_name}")
    print("=" * 60)

    # Determine what to generate
    gen_cats = not services_only and not practitioners_only
    gen_svcs = not categories_only and not practitioners_only
    gen_practs = not categories_only and not services_only

    # Step 1: Read input data
    print("\n--- Step 1: Reading input data ---")
    input_data = read_all_inputs(config.data_input_dir)
    csv_count = len(input_data.get("csv_files", {}))
    json_count = len(input_data.get("json_files", {}))
    print(f"  Found {csv_count} CSV files, {json_count} JSON files")

    if csv_count == 0 and json_count == 0:
        print("ERROR: No input data found!")
        return {"error": "No input data", "elapsed": 0}

    # Step 2: Fetch/load API data
    print("\n--- Step 2: Loading API data ---")
    if no_api:
        api_data = load_cached_api_data(client_name)
        print(f"  Using cached API data")
    else:
        try:
            api_data = fetch_api_data(client_name, all_locations=all_locations)
        except Exception as e:
            print(f"  API fetch failed: {e}")
            print("  Falling back to cached data...")
            api_data = load_cached_api_data(client_name)

    print(f"  API: {len(api_data['categories'])} categories, {len(api_data['services'])} services, {len(api_data['practitioners'])} practitioners")

    # Step 3: Load rules
    print("\n--- Step 3: Loading rules ---")
    common_rules, field_mappings = load_client_rules(client_name)
    print(f"  Rules: {len(common_rules)} chars")
    print(f"  Field mappings: {list(field_mappings.keys())}")

    results = {}
    branches = [loc.get("branch", "1") for loc in config.locations]

    # Step 4: Generate categories
    if gen_cats:
        print("\n--- Step 4: Generating categories ---")
        categories = generate_categories(
            input_data=input_data,
            rules=common_rules,
            field_mappings=field_mappings.get("categories"),
            existing_api_data=api_data["categories"] if not no_merge else None,
        )

        if not no_merge and api_data["categories"]:
            print("  Merging with API data...")
            categories = merge_with_api_data(categories, api_data["categories"], "categories")

        save_json(output_dir / "categories.json", categories)
        results["categories"] = len(categories)
    else:
        # Load existing for service generation
        categories = load_json(output_dir / "categories.json") or []

    # Step 5: Generate services
    if gen_svcs:
        print("\n--- Step 5: Generating services ---")
        services = generate_services(
            input_data=input_data,
            categories=categories,
            rules=common_rules,
            field_mappings=field_mappings.get("services"),
            existing_api_data=api_data["services"] if not no_merge else None,
        )

        # Set default branches if not set
        for svc in services:
            if not svc.get("branches"):
                svc["branches"] = branches

        if not no_merge and api_data["services"]:
            print("  Merging with API data...")
            services = merge_with_api_data(services, api_data["services"], "services")

        save_json(output_dir / "services.json", services)
        results["services"] = len(services)

    # Step 6: Generate practitioners
    if gen_practs:
        print("\n--- Step 6: Generating practitioners ---")
        practitioners = generate_practitioners(
            input_data=input_data,
            rules=common_rules,
            field_mappings=field_mappings.get("practitioners"),
            existing_api_data=api_data["practitioners"] if not no_merge else None,
        )

        if not no_merge and api_data["practitioners"]:
            print("  Merging with API data...")
            practitioners = merge_with_api_data(practitioners, api_data["practitioners"], "practitioners")

        save_json(output_dir / "practitioners.json", practitioners)
        results["practitioners"] = len(practitioners)

    # Step 7: Optional sync
    if do_sync:
        print("\n--- Step 7: Syncing IDs with API ---")
        from src.shared.sync import sync_items, update_references, print_report

        if gen_cats and categories:
            local = load_json(output_dir / "categories.json")
            synced, cat_mapping, report = sync_items(local, api_data["categories"], "categories")
            save_json(output_dir / "categories.json", synced)
            print_report(report)

        if gen_svcs:
            local = load_json(output_dir / "services.json")
            synced, svc_mapping, report = sync_items(local, api_data["services"], "services")
            save_json(output_dir / "services.json", synced)
            print_report(report)

    elapsed = time.time() - start_time

    # Summary
    print("\n" + "=" * 60)
    print("GENERATION COMPLETE")
    print("=" * 60)
    for entity, count in results.items():
        print(f"  {entity}: {count}")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Output: {output_dir}")

    results["elapsed"] = round(elapsed, 1)
    return results


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    client_name = sys.argv[1]

    # Parse flags
    args = sys.argv[2:]
    categories_only = "--categories-only" in args
    services_only = "--services-only" in args
    practitioners_only = "--practitioners-only" in args
    no_api = "--no-api" in args
    no_merge = "--no-merge" in args
    do_sync = "--sync" in args
    all_locations = "--all-locations" in args or True  # default: all

    results = run_pipeline(
        client_name=client_name,
        categories_only=categories_only,
        services_only=services_only,
        practitioners_only=practitioners_only,
        no_api=no_api,
        no_merge=no_merge,
        do_sync=do_sync,
        all_locations=all_locations,
    )

    return 0 if "error" not in results else 1


if __name__ == "__main__":
    sys.exit(main())
