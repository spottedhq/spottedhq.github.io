#!/opt/homebrew/bin/python3
"""
SpottedHQ Auto Content Pipeline

End-to-end: discover products → generate comparison pages → generate pins.

Reads the product opportunities report, finds natural comparison pairs
within the same category, generates Hugo comparison pages + Pinterest pins
for any pairs that don't already have pages.

Usage:
    python3 auto-pipeline.py                          # full pipeline
    python3 auto-pipeline.py --dry-run                # show what would be generated
    python3 auto-pipeline.py --category ai             # only AI tools
    python3 auto-pipeline.py --min-score 60            # only high-scoring products
    python3 auto-pipeline.py --skip-pins               # pages only, no pins
    python3 auto-pipeline.py --discover                # run discovery first, then pipeline
"""

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from itertools import combinations

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
DATA_DIR = ROOT_DIR / "data"
COMPARE_DIR = ROOT_DIR / "content" / "compare"
PINS_DIR = ROOT_DIR / "static" / "pins"
COMPARISONS_CSV = DATA_DIR / "comparisons-auto.csv"

DISCOVER_SCRIPT = SCRIPT_DIR / "discover-products.py"
COMPARE_SCRIPT = SCRIPT_DIR / "generate-comparisons.py"
PINS_SCRIPT = SCRIPT_DIR / "generate-pins.py"

PYTHON = "/opt/homebrew/bin/python3"


def slugify(text):
    return (
        text.lower()
        .replace(" ", "-")
        .replace(".", "")
        .replace("(", "")
        .replace(")", "")
        .replace("'", "")
    )


def get_existing_comparisons():
    """Return set of existing comparison slugs."""
    existing = set()
    if COMPARE_DIR.exists():
        for f in COMPARE_DIR.glob("*.md"):
            existing.add(f.stem)
    return existing


def load_opportunities(category=None, min_score=0):
    """Load the most recent product opportunities report."""
    reports = sorted(DATA_DIR.glob("product-opportunities-*.json"), reverse=True)
    if not reports:
        print("ERROR: No product opportunities report found.")
        print("       Run: python3 scripts/discover-products.py --seed-only")
        sys.exit(1)

    report_path = reports[0]
    print(f"  Loading: {report_path.name}")

    with open(report_path) as f:
        data = json.load(f)

    products = data.get("programs", data.get("products", []))

    # Filter
    if category:
        products = [p for p in products if p.get("category", "").lower() == category.lower()]
    if min_score:
        products = [p for p in products if p.get("score", 0) >= min_score]

    return products


def generate_pairs(products):
    """Generate comparison pairs from products in the same category."""
    # Group by category
    by_category = {}
    for p in products:
        cat = p.get("category", "other")
        by_category.setdefault(cat, []).append(p)

    pairs = []
    existing = get_existing_comparisons()

    for cat, prods in by_category.items():
        # Sort by score descending — pair top products first
        prods.sort(key=lambda x: x.get("score", 0), reverse=True)

        for a, b in combinations(prods, 2):
            name_a = a["name"]
            name_b = b["name"]

            # Check both slug orderings
            slug1 = f"{slugify(name_a)}-vs-{slugify(name_b)}"
            slug2 = f"{slugify(name_b)}-vs-{slugify(name_a)}"

            if slug1 in existing or slug2 in existing:
                continue

            # Put higher-scored product first
            if a.get("score", 0) >= b.get("score", 0):
                pairs.append((a, b, cat))
            else:
                pairs.append((b, a, cat))

    # Sort pairs by combined score
    pairs.sort(key=lambda x: x[0].get("score", 0) + x[1].get("score", 0), reverse=True)

    return pairs


def format_commission(product):
    """Format commission string for CSV."""
    comm = product.get("commission_pct", product.get("commission", "See website"))
    if isinstance(comm, (int, float)):
        return f"{comm}%/mo" if product.get("recurring") else f"{comm}%"
    return str(comm)


def write_csv(pairs):
    """Write comparison pairs to auto CSV."""
    COMPARISONS_CSV.parent.mkdir(parents=True, exist_ok=True)

    with open(COMPARISONS_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "tool_a", "tool_b", "category", "tags",
            "tool_a_price", "tool_b_price",
            "tool_a_free", "tool_b_free",
            "tool_a_best_for", "tool_b_best_for",
            "tool_a_link", "tool_b_link",
        ])

        for a, b, cat in pairs:
            # Map category to blog category
            blog_cat = "ai-tools" if cat in ("ai",) else "saas"
            tags = f"{cat},comparison,affiliate"

            writer.writerow([
                a["name"],
                b["name"],
                blog_cat,
                tags,
                format_commission(a),
                format_commission(b),
                "Check website",
                "Check website",
                a.get("best_for", "see review"),
                b.get("best_for", "see review"),
                a.get("url", "#"),
                b.get("url", "#"),
            ])

    return COMPARISONS_CSV


def run_discovery():
    """Run the product discovery script."""
    print("\n[1/4] Running product discovery...")
    result = subprocess.run(
        [PYTHON, str(DISCOVER_SCRIPT), "--seed-only"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  WARNING: Discovery failed: {result.stderr[:200]}")
        return False
    print("  Discovery complete.")
    return True


def run_page_generator():
    """Run the comparison page generator."""
    print("\n[3/4] Generating comparison pages...")
    result = subprocess.run(
        [PYTHON, str(COMPARE_SCRIPT),
         "--input", str(COMPARISONS_CSV),
         "--output", str(COMPARE_DIR)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  ERROR: Page generation failed: {result.stderr[:200]}")
        return False
    print(result.stdout)
    return True


def run_pin_generator():
    """Run the Pinterest pin generator."""
    print("\n[4/4] Generating Pinterest pins...")
    result = subprocess.run(
        [PYTHON, str(PINS_SCRIPT),
         "--type", "compare",
         "--input", str(COMPARISONS_CSV),
         "--output", str(PINS_DIR)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  ERROR: Pin generation failed: {result.stderr[:200]}")
        return False
    print(result.stdout)
    return True


def main():
    parser = argparse.ArgumentParser(description="SpottedHQ Auto Content Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated")
    parser.add_argument("--category", help="Filter by product category")
    parser.add_argument("--min-score", type=float, default=0, help="Minimum product score")
    parser.add_argument("--skip-pins", action="store_true", help="Skip pin generation")
    parser.add_argument("--discover", action="store_true", help="Run discovery first")
    args = parser.parse_args()

    print("=" * 70)
    print("  SpottedHQ Auto Content Pipeline")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    # Step 1: Optionally run discovery
    if args.discover:
        run_discovery()

    # Step 2: Load opportunities and generate pairs
    print("\n[2/4] Generating comparison pairs...")
    products = load_opportunities(category=args.category, min_score=args.min_score)
    print(f"  Products loaded: {len(products)}")

    pairs = generate_pairs(products)
    print(f"  New comparison pairs found: {len(pairs)}")

    if not pairs:
        print("\n  No new pairs to generate. All combinations already have pages.")
        print("  Add more products to the discovery seed list or lower --min-score.")
        return

    # Show what we'll generate
    print(f"\n  Pairs to generate:")
    for i, (a, b, cat) in enumerate(pairs[:20], 1):
        a_comm = format_commission(a)
        b_comm = format_commission(b)
        print(f"    {i:2}. {a['name']} vs {b['name']} [{cat}] — {a_comm} / {b_comm}")
    if len(pairs) > 20:
        print(f"    ... and {len(pairs) - 20} more")

    if args.dry_run:
        print(f"\n  [DRY RUN] Would generate {len(pairs)} pages + pins.")
        return

    # Step 3: Write CSV and generate pages
    csv_path = write_csv(pairs)
    print(f"\n  CSV written: {csv_path}")

    run_page_generator()

    # Step 4: Generate pins
    if not args.skip_pins:
        run_pin_generator()

    # Summary
    print("\n" + "=" * 70)
    print(f"  DONE — {len(pairs)} new comparison pages + pins generated")
    print(f"  Next: fill pages with real content, then deploy")
    print("=" * 70)


if __name__ == "__main__":
    main()
