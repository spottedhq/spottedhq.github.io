#!/opt/homebrew/bin/python3
"""
pSEO "Best Of" Page Generator for SpottedHQ

Reads a CSV of categories and generates "Best X for Y" Hugo markdown pages.

Usage:
    python3 generate-best-of.py --input data/best-of.csv --output content/best/

CSV format:
    category_name,use_case,seo_category,tags
"""

import csv
import argparse
import os
from datetime import datetime


TEMPLATE = """---
title: "Best {category_name} for {use_case} in {year}"
date: {date}
draft: false
categories: ["{seo_category}"]
tags: [{tags}]
description: "We tested the top {category_name} for {use_case}. Here are our honest picks for {year}."
summary: "Looking for the best {category_name} for {use_case}? We compared the top options so you don't have to."
ShowToc: true
TocOpen: true
---

## Our Top Picks

| Rank | Tool | Best For | Price | Rating |
|---|---|---|---|---|
| 1 | <!-- FILL --> | | | /10 |
| 2 | <!-- FILL --> | | | /10 |
| 3 | <!-- FILL --> | | | /10 |
| 4 | <!-- FILL --> | | | /10 |
| 5 | <!-- FILL --> | | | /10 |

## How We Tested

We evaluated each {category_name} tool based on:
- **Pricing** — value for money, free tier availability
- **Ease of use** — how quickly can you get started
- **Features** — does it actually deliver on its promises
- **{use_case} fit** — how well does it serve this specific need

<!-- EXPAND: add specific testing methodology -->

## 1. <!-- Tool Name --> — Best Overall

<!-- EXPAND: full review section for each tool -->

**[Try free →](AFFILIATE_LINK)**

## What to Look For in {category_name}

When choosing a {category_name} tool for {use_case}, pay attention to:

<!-- EXPAND: buyer's guide criteria -->

## FAQ

### What is the best free {category_name}?

<!-- FILL -->

### How much do {category_name} tools cost?

<!-- FILL -->

## Final Thoughts

<!-- EXPAND: closing recommendation -->

---

*This post contains affiliate links. See our [affiliate disclosure](/affiliate-disclosure/) for details.*
"""


def slugify(text):
    return text.lower().replace(" ", "-").replace(".", "").replace("(", "").replace(")", "").replace("/", "-")


def generate_page(row, output_dir):
    slug = f"best-{slugify(row['category_name'])}-for-{slugify(row['use_case'])}"
    filename = os.path.join(output_dir, f"{slug}.md")

    tags_formatted = ", ".join(f'"{t.strip()}"' for t in row.get("tags", "").split(",") if t.strip())
    year = datetime.now().year

    content = TEMPLATE.format(
        category_name=row["category_name"],
        use_case=row["use_case"],
        seo_category=row["seo_category"],
        tags=tags_formatted,
        date=datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        year=year,
    )

    with open(filename, "w") as f:
        f.write(content)

    return filename


def main():
    parser = argparse.ArgumentParser(description="Generate pSEO best-of pages")
    parser.add_argument("--input", required=True, help="Path to CSV file")
    parser.add_argument("--output", required=True, help="Output directory for markdown files")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    with open(args.input, "r") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            filepath = generate_page(row, args.output)
            print(f"  Generated: {filepath}")
            count += 1

    print(f"\nDone — {count} best-of pages generated in {args.output}")


if __name__ == "__main__":
    main()
