#!/usr/bin/env python3
"""
Выводит описания и атрибуты practitioners и services
в удобном формате для оценки качества моделью (Claude Code).

Использование:
    python scripts/print_quality.py
    python scripts/print_quality.py --services-sample 30
"""
import json
import random
import argparse
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
PRACTITIONERS = ROOT / "data" / "output" / "practitioners.json"
SERVICES = ROOT / "data" / "output" / "services.json"
CATEGORIES = ROOT / "data" / "output" / "categories.json"


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def name_en(item):
    return (item.get("name_i18n") or {}).get("en", "") or item.get("name", "")


def desc_en(item):
    return (item.get("description_i18n") or {}).get("en", "")


def truncate(s, n=200):
    s = s.replace("\n", " ").strip()
    return f"{s[:n]}..." if len(s) > n else s


def print_practitioners():
    practitioners = load(PRACTITIONERS)
    print(f"\n{'='*70}")
    print(f"  PRACTITIONERS ({len(practitioners)} total)")
    print(f"{'='*70}")

    for i, p in enumerate(practitioners, 1):
        name = p.get("name", "?")
        desc = desc_en(p)
        spec = p.get("speciality", "")
        langs = p.get("languages", [])
        exp = p.get("years_of_experience")
        source = p.get("source", "")
        branches = p.get("branches", [])
        sex = p.get("sex", "")
        treat = p.get("treat_children")
        treat_age = p.get("treat_children_age")

        pq = p.get("primary_qualifications") or ""
        sq = p.get("secondary_qualifications") or ""
        aq = p.get("additional_qualifications") or ""

        print(f"\n  --- {i}/{len(practitioners)}: {name} ---")
        print(f"  source:       {source}")
        print(f"  speciality:   {spec or '(empty)'}")
        print(f"  sex:          {sex}")
        print(f"  languages:    {', '.join(langs) if langs else '(empty)'}")
        print(f"  experience:   {exp if exp is not None else '(null)'} years")
        print(f"  branches:     {branches or '(both)'}")
        print(f"  treat_children: {treat} (age: {treat_age})")
        print(f"  description:  ({len(desc)} chars) {truncate(desc) if desc else '(empty)'}")

        if pq:
            print(f"  primary_q:    {truncate(str(pq), 120)}")
        if sq:
            print(f"  secondary_q:  {truncate(str(sq), 120)}")
        if aq:
            print(f"  additional_q: {truncate(str(aq), 120)}")

    # Summary
    empty_desc = [p for p in practitioners if not desc_en(p)]
    empty_spec = [p for p in practitioners if not p.get("speciality")]
    from_svc = [p for p in practitioners if p.get("source") == "services_sheet"]

    print(f"\n  {'─'*50}")
    print(f"  SUMMARY:")
    print(f"    Total:              {len(practitioners)}")
    print(f"    Empty description:  {len(empty_desc)}")
    print(f"    Empty speciality:   {len(empty_spec)}")
    print(f"    From services_sheet:{len(from_svc)}")
    if empty_desc:
        print(f"    Without desc: {', '.join(p.get('name','?') for p in empty_desc)}")


def print_services(sample_size=30):
    services = load(SERVICES)
    categories = load(CATEGORIES)
    cat_by_id = {c["id"]: name_en(c) for c in categories}

    # Sample from different categories
    by_cat = defaultdict(list)
    for s in services:
        by_cat[s.get("category_id")].append(s)

    sample = []
    cats = list(by_cat.keys())
    random.shuffle(cats)
    per_cat = max(1, sample_size // len(cats))
    for cat_id in cats:
        svcs = by_cat[cat_id]
        random.shuffle(svcs)
        sample.extend(svcs[:per_cat])
        if len(sample) >= sample_size:
            break
    sample = sample[:sample_size]

    print(f"\n{'='*70}")
    print(f"  SERVICES (sample {len(sample)}/{len(services)})")
    print(f"{'='*70}")

    for i, s in enumerate(sample, 1):
        sname = name_en(s)
        sdesc = desc_en(s)
        cat_name = cat_by_id.get(s.get("category_id"), "?")
        price = s.get("price_min")
        dur = s.get("duration_minutes")
        pnote = (s.get("price_note_i18n") or {}).get("en", "")
        branches = s.get("branches", [])

        print(f"\n  --- {i}/{len(sample)}: {sname} ---")
        print(f"  category:     {cat_name}")
        print(f"  branches:     {branches}")
        print(f"  price:        {price}")
        print(f"  duration:     {dur} min")
        print(f"  description:  ({len(sdesc)} chars) {truncate(sdesc) if sdesc else '(empty)'}")
        if pnote:
            print(f"  price_note:   {truncate(pnote, 100)}")

    # Summary
    with_desc = [s for s in services if desc_en(s)]
    no_price = [s for s in services if s.get("price_min") is None]
    no_dur = [s for s in services if s.get("duration_minutes") is None]

    print(f"\n  {'─'*50}")
    print(f"  SUMMARY (all {len(services)} services):")
    print(f"    With description:   {len(with_desc)}")
    print(f"    Without description:{len(services) - len(with_desc)}")
    print(f"    Without price:      {len(no_price)}")
    print(f"    Without duration:   {len(no_dur)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Print quality data for AI review")
    parser.add_argument("--services-sample", type=int, default=30,
                        help="Number of services to sample (default: 30)")
    args = parser.parse_args()

    print_practitioners()
    print_services(sample_size=args.services_sample)

    print(f"\n{'='*70}")
    print(f"  Now review the output above using criteria from")
    print(f"  docs/PROMPT_2.5_QUALITY_REVIEW.md")
    print(f"{'='*70}")
