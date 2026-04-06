"""
Shared sync logic for matching local data with DialogGauge API.

Used by all clients' sync_with_api.py scripts.
"""

import re


def normalize_name(name: str) -> str:
    """Normalize name for comparison."""
    if not name:
        return ""
    name = name.lower().strip()
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'[^\w\s]', '', name)
    return name


def get_item_name(item: dict) -> str:
    """Get item name from name_i18n.en or name field."""
    name = item.get("name_i18n", {}).get("en", "")
    if not name:
        name = item.get("name", "")
    return name


def sync_items(
    local_items: list,
    api_items: list,
    item_type: str = "items",
) -> tuple[list, dict, dict]:
    """
    Sync local items with API.

    - If local item name matches API -> use API's ID
    - If local item is new -> assign max_api_id + 1, +2, ...

    Returns:
        - synced_items: Updated items with correct IDs
        - id_mapping: old_local_id -> new_id
        - report: sync stats
    """
    api_name_map = {}
    for item in api_items:
        name_en = get_item_name(item)
        normalized = normalize_name(name_en)
        if normalized:
            api_name_map[normalized] = item

    max_api_id = max((item["id"] for item in api_items), default=0)
    print(f"  Max API ID: {max_api_id}")

    next_new_id = max_api_id + 1

    synced_items = []
    id_mapping = {}
    matched = []
    new_items = []

    for local_item in local_items:
        old_id = local_item["id"]
        local_name = get_item_name(local_item)
        normalized = normalize_name(local_name)

        if normalized in api_name_map:
            api_item = api_name_map[normalized]
            new_id = api_item["id"]

            matched.append({
                "local_name": local_name,
                "api_name": get_item_name(api_item),
                "old_id": old_id,
                "new_id": new_id,
                "is_archived": api_item.get("is_archived", False),
            })
        else:
            new_id = next_new_id
            next_new_id += 1

            new_items.append({
                "local_name": local_name,
                "old_id": old_id,
                "new_id": new_id,
            })

        synced_item = local_item.copy()
        synced_item["id"] = new_id
        synced_items.append(synced_item)
        id_mapping[old_id] = new_id

    synced_items.sort(key=lambda x: x["id"])

    report = {
        "type": item_type,
        "total_local": len(local_items),
        "total_api": len(api_items),
        "max_api_id": max_api_id,
        "matched": len(matched),
        "new": len(new_items),
        "new_id_start": max_api_id + 1 if new_items else None,
        "new_id_end": next_new_id - 1 if new_items else None,
        "matched_details": matched,
        "new_details": new_items,
    }

    return synced_items, id_mapping, report


def update_references(items: list, id_field: str, id_mapping: dict) -> list:
    """Update ID references in items."""
    updated = []
    for item in items:
        item_copy = item.copy()
        old_id = item.get(id_field)
        if old_id in id_mapping:
            item_copy[id_field] = id_mapping[old_id]
        updated.append(item_copy)
    return updated


def print_report(report: dict) -> None:
    """Print sync report."""
    item_type = report.get("type", "items").upper()

    print(f"\n{'=' * 60}")
    print(f"SYNC REPORT: {item_type}")
    print("=" * 60)

    print(f"\nLocal:     {report['total_local']}")
    print(f"API:       {report['total_api']}")
    print(f"Max API ID: {report['max_api_id']}")
    print(f"Matched:   {report['matched']}")
    print(f"New:       {report['new']}")

    if report['new'] > 0:
        print(f"New IDs:   {report['new_id_start']} - {report['new_id_end']}")

    if report["matched_details"]:
        print(f"\n--- MATCHED (using API ID) ---")
        for m in report["matched_details"][:15]:
            archived = " [ARCHIVED]" if m.get("is_archived") else ""
            name = m['local_name'][:35]
            print(f"  {m['old_id']:>5} -> {m['new_id']:<5} '{name}'{archived}")
        if len(report["matched_details"]) > 15:
            print(f"  ... and {len(report['matched_details']) - 15} more")

    if report["new_details"]:
        print(f"\n--- NEW (assigned new ID) ---")
        for n in report["new_details"][:15]:
            name = n['local_name'][:35]
            print(f"  {n['old_id']:>5} -> {n['new_id']:<5} '{name}'")
        if len(report["new_details"]) > 15:
            print(f"  ... and {len(report['new_details']) - 15} more")

    print("=" * 60)
