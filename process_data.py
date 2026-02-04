#!/usr/bin/env python3
"""
Script to process services.json and create normalized data:
- categories.json
- practitioners.json
- services.json (updated with category_id)
- service_practitioners.json
"""

import json
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent
INPUT_FILE = BASE_DIR / "services.json"
OUTPUT_CATEGORIES = BASE_DIR / "categories.json"
OUTPUT_PRACTITIONERS = BASE_DIR / "practitioners.json"
OUTPUT_SERVICES = BASE_DIR / "services_normalized.json"
OUTPUT_SERVICE_PRACTITIONERS = BASE_DIR / "service_practitioners.json"


def main():
    # Load original services
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        services_raw = json.load(f)
    
    print(f"Loaded {len(services_raw)} services")
    
    # === 1. Extract unique categories ===
    categories_set = set()
    for service in services_raw:
        cat_name = service.get("category_name")
        if cat_name:
            categories_set.add(cat_name)
    
    # Create categories with IDs
    categories = []
    category_name_to_id = {}
    for idx, cat_name in enumerate(sorted(categories_set), start=1):
        category = {
            "id": idx,
            "name_i18n": {"en": cat_name},
            "sort_order": idx
        }
        categories.append(category)
        category_name_to_id[cat_name] = idx
    
    print(f"Found {len(categories)} unique categories")
    
    # === 2. Extract unique practitioners ===
    practitioners_set = set()
    for service in services_raw:
        practitioners_list = service.get("practitioners", [])
        for p in practitioners_list:
            if p and p.strip():
                practitioners_set.add(p.strip())
    
    # Create practitioners with IDs
    practitioners = []
    practitioner_name_to_id = {}
    for idx, p_name in enumerate(sorted(practitioners_set), start=1):
        practitioner = {
            "id": idx,
            "name": p_name,
            "name_i18n": {"en": p_name}
        }
        practitioners.append(practitioner)
        practitioner_name_to_id[p_name] = idx
    
    print(f"Found {len(practitioners)} unique practitioners")
    
    # === 3. Create normalized services ===
    services_normalized = []
    service_practitioners = []
    
    for idx, service in enumerate(services_raw, start=1):
        # Get category_id
        cat_name = service.get("category_name")
        category_id = category_name_to_id.get(cat_name, 0)
        
        # Get practitioners for this service
        practitioners_list = service.get("practitioners", [])
        
        # Create service-practitioner links
        for p_name in practitioners_list:
            p_name = p_name.strip() if p_name else ""
            if p_name and p_name in practitioner_name_to_id:
                link = {
                    "service_id": idx,
                    "practitioner_id": practitioner_name_to_id[p_name]
                }
                service_practitioners.append(link)
        
        # Create normalized service (without category_name and practitioners)
        normalized = {
            "id": idx,
            "category_id": category_id,
        }
        
        # Copy other fields (excluding category_name and practitioners)
        for key, value in service.items():
            if key not in ("category_name", "practitioners"):
                normalized[key] = value
        
        services_normalized.append(normalized)
    
    print(f"Created {len(service_practitioners)} service-practitioner links")
    
    # === 4. Save all files ===
    
    # Categories
    with open(OUTPUT_CATEGORIES, "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)
    print(f"Saved: {OUTPUT_CATEGORIES}")
    
    # Practitioners
    with open(OUTPUT_PRACTITIONERS, "w", encoding="utf-8") as f:
        json.dump(practitioners, f, ensure_ascii=False, indent=2)
    print(f"Saved: {OUTPUT_PRACTITIONERS}")
    
    # Services (normalized)
    with open(OUTPUT_SERVICES, "w", encoding="utf-8") as f:
        json.dump(services_normalized, f, ensure_ascii=False, indent=2)
    print(f"Saved: {OUTPUT_SERVICES}")
    
    # Service-Practitioners
    with open(OUTPUT_SERVICE_PRACTITIONERS, "w", encoding="utf-8") as f:
        json.dump(service_practitioners, f, ensure_ascii=False, indent=2)
    print(f"Saved: {OUTPUT_SERVICE_PRACTITIONERS}")
    
    # === Summary ===
    print("\n" + "=" * 50)
    print("SUMMARY:")
    print(f"  Categories:            {len(categories)}")
    print(f"  Practitioners:         {len(practitioners)}")
    print(f"  Services:              {len(services_normalized)}")
    print(f"  Service-Practitioner:  {len(service_practitioners)}")
    print("=" * 50)


if __name__ == "__main__":
    main()
