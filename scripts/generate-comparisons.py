#!/opt/homebrew/bin/python3
"""
pSEO Comparison Page Generator for SpottedHQ

Reads a CSV of tool pairs and generates Hugo markdown comparison pages.
Each row produces a "[Tool A] vs [Tool B]" post targeting long-tail SEO keywords.

Usage:
    python3 generate-comparisons.py --input data/comparisons.csv --output content/compare/

CSV format:
    tool_a,tool_b,category,tags,tool_a_price,tool_b_price,tool_a_free,tool_b_free,tool_a_best_for,tool_b_best_for,tool_a_link,tool_b_link
"""

import csv
import argparse
import os
from datetime import datetime


TEMPLATE = """---
title: "{tool_a} vs {tool_b}: Which One Is Better in {year}?"
date: {date}
draft: false
categories: ["{category}"]
tags: [{tags}]
description: "{tool_a} vs {tool_b} — honest comparison of pricing, features, and use cases. Find out which one is right for you."
summary: "Detailed comparison of {tool_a} and {tool_b}. We break down pricing, features, ease of use, and who should pick which."
ShowToc: true
TocOpen: true
---

## Quick Verdict

Choosing between **{tool_a}** and **{tool_b}**? Here's the short version: **{tool_a}** is best for {tool_a_best_for}, while **{tool_b}** shines for {tool_b_best_for}. Read on for the full breakdown.

## At a Glance

| Feature | **{tool_a}** | **{tool_b}** |
|---|---|---|
| **Pricing** | {tool_a_price} | {tool_b_price} |
| **Free tier** | {tool_a_free} | {tool_b_free} |
| **Best for** | {tool_a_best_for} | {tool_b_best_for} |

## What Is {tool_a}?

{tool_a} is a popular tool in the {category} space. <!-- EXPAND: add 2-3 paragraphs with real details -->

## What Is {tool_b}?

{tool_b} is a well-known alternative in {category}. <!-- EXPAND: add 2-3 paragraphs with real details -->

## Head-to-Head Comparison

### Pricing

{tool_a} starts at {tool_a_price}, while {tool_b} comes in at {tool_b_price}. <!-- EXPAND with tier details -->

### Features

<!-- EXPAND: key feature comparison -->

### Ease of Use

<!-- EXPAND: onboarding, learning curve -->

## Who Should Use What?

**Pick {tool_a} if:** you need {tool_a_best_for}.

**Pick {tool_b} if:** you need {tool_b_best_for}.

## FAQ

### Is {tool_a} better than {tool_b}?

It depends on your needs. {tool_a} is better for {tool_a_best_for}, while {tool_b} excels at {tool_b_best_for}.

### Can I switch from {tool_a} to {tool_b}?

Most tools in this category allow data export. Check both platforms for migration guides.

## Our Recommendation

Both are solid choices. For most users, we'd suggest trying both free tiers before committing.

**[Try {tool_a} free →]({tool_a_link})** | **[Try {tool_b} free →]({tool_b_link})**

---

*This post contains affiliate links. See our [affiliate disclosure](/affiliate-disclosure/) for details.*
"""


def slugify(text):
    return text.lower().replace(" ", "-").replace(".", "").replace("(", "").replace(")", "")


def generate_page(row, output_dir):
    slug = f"{slugify(row['tool_a'])}-vs-{slugify(row['tool_b'])}"
    filename = os.path.join(output_dir, f"{slug}.md")

    tags_formatted = ", ".join(f'"{t.strip()}"' for t in row.get("tags", "").split(",") if t.strip())
    year = datetime.now().year

    content = TEMPLATE.format(
        tool_a=row["tool_a"],
        tool_b=row["tool_b"],
        category=row["category"],
        tags=tags_formatted,
        date=datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        year=year,
        tool_a_price=row.get("tool_a_price", "See website"),
        tool_b_price=row.get("tool_b_price", "See website"),
        tool_a_free=row.get("tool_a_free", "Check website"),
        tool_b_free=row.get("tool_b_free", "Check website"),
        tool_a_best_for=row.get("tool_a_best_for", "general use"),
        tool_b_best_for=row.get("tool_b_best_for", "general use"),
        tool_a_link=row.get("tool_a_link", "#"),
        tool_b_link=row.get("tool_b_link", "#"),
    )

    with open(filename, "w") as f:
        f.write(content)

    return filename


def main():
    parser = argparse.ArgumentParser(description="Generate pSEO comparison pages")
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

    print(f"\nDone — {count} comparison pages generated in {args.output}")


if __name__ == "__main__":
    main()
