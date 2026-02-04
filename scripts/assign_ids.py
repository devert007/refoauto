#!/usr/bin/env python3
"""
Script to assign unique IDs to services.
- Checks for conflicts (duplicate IDs)
- Automatically assigns new IDs to services without ID
- Preserves existing valid IDs
- Can be run multiple times safely (idempotent)

Usage:
    python scripts/assign_ids.py
"""

import json
from pathlib import Path
from typing import Any

# Project paths
SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent
DATA_OUTPUT_DIR = PROJECT_ROOT / "data" / "output"

# Ensure directory exists
DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def assign_ids(
    input_file: str,
    output_file: str | None = None,
    id_field: str = "id",
    start_id: int = 1
) -> dict[str, Any]:
    """
    Assign unique IDs to all items in a JSON array.
    
    Args:
        input_file: Filename in data/output/
        output_file: Output filename (defaults to input_file)
        id_field: Name of the ID field (default: "id")
        start_id: Starting ID for new items (default: 1)
    
    Returns:
        Summary dict with statistics
    """
    input_path = DATA_OUTPUT_DIR / input_file
    output_path = DATA_OUTPUT_DIR / (output_file or input_file)
    
    # Load data
    with open(input_path, "r", encoding="utf-8") as f:
        items = json.load(f)
    
    if not isinstance(items, list):
        raise ValueError(f"Expected JSON array, got {type(items).__name__}")
    
    print(f"Loaded {len(items)} items from {input_file}")
    
    # Collect existing IDs and check for conflicts
    existing_ids: dict[int, list[int]] = {}  # id -> list of indices
    items_without_id: list[int] = []  # indices
    
    for idx, item in enumerate(items):
        if id_field in item and item[id_field] is not None:
            item_id = item[id_field]
            if item_id in existing_ids:
                existing_ids[item_id].append(idx)
            else:
                existing_ids[item_id] = [idx]
        else:
            items_without_id.append(idx)
    
    # Report conflicts
    conflicts = {k: v for k, v in existing_ids.items() if len(v) > 1}
    if conflicts:
        print(f"\n⚠️  Found {len(conflicts)} ID conflicts:")
        for dup_id, indices in conflicts.items():
            print(f"   ID {dup_id} appears {len(indices)} times at indices: {indices}")
            # Show item names for debugging
            for i in indices:
                name = items[i].get("name_i18n", {}).get("en") or items[i].get("name", "Unknown")
                print(f"      [{i}] {name}")
    
    # Resolve conflicts by assigning new IDs to duplicates (keep first occurrence)
    ids_to_reassign: list[int] = []
    for dup_id, indices in conflicts.items():
        # Keep the first occurrence, reassign the rest
        ids_to_reassign.extend(indices[1:])
    
    # Combine items that need new IDs
    all_need_ids = set(items_without_id) | set(ids_to_reassign)
    
    # Find the next available ID
    used_ids = set(existing_ids.keys())
    next_id = start_id
    
    def get_next_id():
        nonlocal next_id
        while next_id in used_ids:
            next_id += 1
        used_ids.add(next_id)
        return next_id
    
    # Assign IDs
    assigned_count = 0
    reassigned_count = 0
    
    for idx in sorted(all_need_ids):
        new_id = get_next_id()
        old_id = items[idx].get(id_field)
        items[idx][id_field] = new_id
        
        if old_id is not None:
            reassigned_count += 1
            name = items[idx].get("name_i18n", {}).get("en") or items[idx].get("name", "Unknown")
            print(f"   Reassigned: {old_id} → {new_id} ({name})")
        else:
            assigned_count += 1
    
    # Verify all IDs are unique
    final_ids = [item.get(id_field) for item in items]
    if len(final_ids) != len(set(final_ids)):
        raise RuntimeError("Failed to make all IDs unique!")
    
    # Check for None IDs
    none_ids = [i for i, item in enumerate(items) if item.get(id_field) is None]
    if none_ids:
        raise RuntimeError(f"Some items still have no ID: indices {none_ids}")
    
    # Save result
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Saved to data/output/{output_file or input_file}")
    
    # Summary
    summary = {
        "total_items": len(items),
        "had_id": len(items) - len(items_without_id),
        "assigned_new": assigned_count,
        "reassigned_conflicts": reassigned_count,
        "conflicts_found": len(conflicts),
        "max_id": max(item[id_field] for item in items),
    }
    
    return summary


def main():
    print("=" * 60)
    print("ASSIGNING IDs TO SERVICES")
    print("=" * 60)
    
    result = assign_ids("services.json")
    
    print("\n" + "-" * 60)
    print("SUMMARY:")
    print(f"  Total services:      {result['total_items']}")
    print(f"  Already had ID:      {result['had_id']}")
    print(f"  Assigned new ID:     {result['assigned_new']}")
    print(f"  Reassigned (conflict): {result['reassigned_conflicts']}")
    print(f"  Max ID:              {result['max_id']}")
    print("-" * 60)
    
    # Also update services_normalized.json if it exists
    normalized_path = DATA_OUTPUT_DIR / "services_normalized.json"
    if normalized_path.exists():
        print("\n" + "=" * 60)
        print("ASSIGNING IDs TO SERVICES_NORMALIZED")
        print("=" * 60)
        result2 = assign_ids("services_normalized.json")
        print("\n" + "-" * 60)
        print("SUMMARY:")
        print(f"  Total services:      {result2['total_items']}")
        print(f"  Already had ID:      {result2['had_id']}")
        print(f"  Assigned new ID:     {result2['assigned_new']}")
        print(f"  Max ID:              {result2['max_id']}")
        print("-" * 60)


if __name__ == "__main__":
    main()
