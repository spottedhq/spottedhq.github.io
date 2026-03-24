#!/opt/homebrew/bin/python3
"""
Affiliate Product Discovery for SpottedHQ

Researches and discovers high-commission affiliate products by scraping
public program directories, checking affiliate network listings, and
cross-referencing with search demand signals.

Usage:
    python3 discover-products.py                    # full discovery
    python3 discover-products.py --category ai      # filter by category
    python3 discover-products.py --min-commission 20 # minimum commission %
    python3 discover-products.py --seed-only        # just use seed list (offline mode)

Output:
    data/product-opportunities-YYYY-MM-DD.json
"""

import argparse
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "data"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
OUTPUT_FILE = DATA_DIR / f"product-opportunities-{TODAY}.json"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

REQUEST_DELAY = 2.5  # seconds between requests

# SSL context that works on macOS without certifi
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# ---------------------------------------------------------------------------
# Seed list — curated high-value affiliate programs as fallback
# ---------------------------------------------------------------------------

SEED_PROGRAMS = [
    # AI Tools
    {"name": "Jasper", "category": "ai", "commission_pct": 30, "recurring": True, "cookie_days": 30, "url": "jasper.ai", "source": "seed"},
    {"name": "Copy.ai", "category": "ai", "commission_pct": 45, "recurring": True, "cookie_days": 30, "url": "copy.ai", "source": "seed"},
    {"name": "Writesonic", "category": "ai", "commission_pct": 30, "recurring": True, "cookie_days": 30, "url": "writesonic.com", "source": "seed"},
    {"name": "Surfer SEO", "category": "ai", "commission_pct": 25, "recurring": True, "cookie_days": 60, "url": "surferseo.com", "source": "seed"},
    {"name": "Pictory", "category": "ai", "commission_pct": 20, "recurring": True, "cookie_days": 30, "url": "pictory.ai", "source": "seed"},
    {"name": "Synthesia", "category": "ai", "commission_pct": 25, "recurring": False, "cookie_days": 30, "url": "synthesia.io", "source": "seed"},
    {"name": "Descript", "category": "ai", "commission_pct": 15, "recurring": False, "cookie_days": 30, "url": "descript.com", "source": "seed"},
    {"name": "Murf AI", "category": "ai", "commission_pct": 20, "recurring": True, "cookie_days": 30, "url": "murf.ai", "source": "seed"},
    {"name": "Notion AI", "category": "ai", "commission_pct": 50, "recurring": False, "cookie_days": 90, "url": "notion.so", "source": "seed"},
    {"name": "Fireflies.ai", "category": "ai", "commission_pct": 25, "recurring": True, "cookie_days": 30, "url": "fireflies.ai", "source": "seed"},

    # Email Marketing
    {"name": "ConvertKit", "category": "email", "commission_pct": 30, "recurring": True, "cookie_days": 30, "url": "convertkit.com", "source": "seed"},
    {"name": "ActiveCampaign", "category": "email", "commission_pct": 30, "recurring": True, "cookie_days": 90, "url": "activecampaign.com", "source": "seed"},
    {"name": "GetResponse", "category": "email", "commission_pct": 33, "recurring": True, "cookie_days": 120, "url": "getresponse.com", "source": "seed"},
    {"name": "Moosend", "category": "email", "commission_pct": 30, "recurring": True, "cookie_days": 90, "url": "moosend.com", "source": "seed"},
    {"name": "AWeber", "category": "email", "commission_pct": 30, "recurring": True, "cookie_days": 365, "url": "aweber.com", "source": "seed"},
    {"name": "Brevo (Sendinblue)", "category": "email", "commission_pct": 5, "recurring": False, "cookie_days": 90, "url": "brevo.com", "source": "seed"},

    # Website Builders / Hosting
    {"name": "Hostinger", "category": "hosting", "commission_pct": 60, "recurring": False, "cookie_days": 30, "url": "hostinger.com", "source": "seed"},
    {"name": "Cloudways", "category": "hosting", "commission_pct": 30, "recurring": False, "cookie_days": 90, "url": "cloudways.com", "source": "seed"},
    {"name": "Kinsta", "category": "hosting", "commission_pct": 0, "commission_flat": 500, "recurring": False, "cookie_days": 60, "url": "kinsta.com", "source": "seed"},
    {"name": "Squarespace", "category": "website-builder", "commission_pct": 30, "recurring": False, "cookie_days": 45, "url": "squarespace.com", "source": "seed"},
    {"name": "Wix", "category": "website-builder", "commission_pct": 0, "commission_flat": 100, "recurring": False, "cookie_days": 30, "url": "wix.com", "source": "seed"},
    {"name": "Webflow", "category": "website-builder", "commission_pct": 50, "recurring": False, "cookie_days": 90, "url": "webflow.com", "source": "seed"},

    # SEO Tools
    {"name": "Semrush", "category": "seo", "commission_pct": 0, "commission_flat": 200, "recurring": True, "cookie_days": 120, "url": "semrush.com", "source": "seed"},
    {"name": "Mangools", "category": "seo", "commission_pct": 30, "recurring": True, "cookie_days": 30, "url": "mangools.com", "source": "seed"},
    {"name": "SE Ranking", "category": "seo", "commission_pct": 30, "recurring": True, "cookie_days": 120, "url": "seranking.com", "source": "seed"},
    {"name": "SpyFu", "category": "seo", "commission_pct": 40, "recurring": True, "cookie_days": 30, "url": "spyfu.com", "source": "seed"},

    # Design Tools
    {"name": "Canva", "category": "design", "commission_pct": 25, "recurring": False, "cookie_days": 30, "url": "canva.com", "source": "seed"},
    {"name": "Visme", "category": "design", "commission_pct": 25, "recurring": True, "cookie_days": 60, "url": "visme.co", "source": "seed"},
    {"name": "Snappa", "category": "design", "commission_pct": 30, "recurring": True, "cookie_days": 30, "url": "snappa.com", "source": "seed"},
    {"name": "Placeit", "category": "design", "commission_pct": 25, "recurring": False, "cookie_days": 30, "url": "placeit.net", "source": "seed"},

    # SaaS / Productivity
    {"name": "Monday.com", "category": "saas", "commission_pct": 0, "commission_flat": 150, "recurring": False, "cookie_days": 30, "url": "monday.com", "source": "seed"},
    {"name": "ClickUp", "category": "saas", "commission_pct": 20, "recurring": True, "cookie_days": 30, "url": "clickup.com", "source": "seed"},
    {"name": "Freshworks", "category": "saas", "commission_pct": 15, "recurring": False, "cookie_days": 30, "url": "freshworks.com", "source": "seed"},
    {"name": "HubSpot", "category": "saas", "commission_pct": 30, "recurring": False, "cookie_days": 180, "url": "hubspot.com", "source": "seed"},
    {"name": "Pipedrive", "category": "saas", "commission_pct": 33, "recurring": True, "cookie_days": 30, "url": "pipedrive.com", "source": "seed"},
    {"name": "Zoho", "category": "saas", "commission_pct": 15, "recurring": True, "cookie_days": 45, "url": "zoho.com", "source": "seed"},
    {"name": "Calendly", "category": "saas", "commission_pct": 25, "recurring": True, "cookie_days": 30, "url": "calendly.com", "source": "seed"},

    # Online Course / Learning
    {"name": "Teachable", "category": "education", "commission_pct": 30, "recurring": True, "cookie_days": 90, "url": "teachable.com", "source": "seed"},
    {"name": "Thinkific", "category": "education", "commission_pct": 30, "recurring": True, "cookie_days": 90, "url": "thinkific.com", "source": "seed"},
    {"name": "Podia", "category": "education", "commission_pct": 30, "recurring": True, "cookie_days": 30, "url": "podia.com", "source": "seed"},

    # VPN / Security
    {"name": "NordVPN", "category": "security", "commission_pct": 40, "recurring": False, "cookie_days": 30, "url": "nordvpn.com", "source": "seed"},
    {"name": "Surfshark", "category": "security", "commission_pct": 40, "recurring": False, "cookie_days": 30, "url": "surfshark.com", "source": "seed"},
    {"name": "1Password", "category": "security", "commission_pct": 25, "recurring": False, "cookie_days": 30, "url": "1password.com", "source": "seed"},
]


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def fetch(url, max_retries=2):
    """Fetch a URL with browser UA, retries, and delays."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=15, context=SSL_CTX) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            if attempt < max_retries:
                time.sleep(REQUEST_DELAY)
                continue
            print(f"  [WARN] Failed to fetch {url}: {e}")
            return None
    return None


# ---------------------------------------------------------------------------
# Source 1: PartnerStack public directory
# ---------------------------------------------------------------------------

def scrape_partnerstack():
    """Scrape PartnerStack's public marketplace for affiliate programs."""
    programs = []
    print("[1/3] Scraping PartnerStack directory...")

    url = "https://partnerstack.com/marketplace"
    html = fetch(url)
    if not html:
        print("  PartnerStack: could not reach marketplace, skipping")
        return programs

    # Try to extract program cards from the HTML
    # PartnerStack uses various patterns; we try several
    # Look for JSON data embedded in the page
    json_match = re.search(r'__NEXT_DATA__.*?<script[^>]*>({.+?})</script>', html, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            # Navigate Next.js page props for program listings
            props = data.get("props", {}).get("pageProps", {})
            items = props.get("programs", props.get("partners", props.get("listings", [])))
            if isinstance(items, list):
                for item in items[:50]:
                    name = item.get("name") or item.get("title") or ""
                    if not name:
                        continue
                    prog = {
                        "name": name,
                        "category": item.get("category", "saas"),
                        "commission_pct": _extract_pct(str(item.get("commission", ""))),
                        "recurring": bool(item.get("recurring")),
                        "cookie_days": item.get("cookie_duration", 30),
                        "url": item.get("url", ""),
                        "source": "partnerstack",
                    }
                    programs.append(prog)
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback: regex-scrape program cards from rendered HTML
    if not programs:
        # Look for patterns like program names + commission rates in the HTML
        card_blocks = re.findall(
            r'(?:class="[^"]*program[^"]*"[^>]*>[\s\S]*?)'
            r'([A-Z][A-Za-z0-9. ]+?)[\s<].*?'
            r'(\d{1,3}%)',
            html
        )
        for name, pct in card_blocks[:30]:
            name = name.strip()
            if len(name) < 3 or len(name) > 50:
                continue
            programs.append({
                "name": name,
                "category": "saas",
                "commission_pct": int(pct.rstrip("%")),
                "recurring": False,
                "cookie_days": 30,
                "url": "",
                "source": "partnerstack",
            })

    print(f"  PartnerStack: found {len(programs)} programs")
    time.sleep(REQUEST_DELAY)
    return programs


# ---------------------------------------------------------------------------
# Source 2: Impact.com public marketplace + ShareASale trending
# ---------------------------------------------------------------------------

def scrape_impact():
    """Check Impact.com and ShareASale public listings."""
    programs = []
    print("[2/3] Checking affiliate network marketplaces...")

    # Impact.com marketplace
    url = "https://impact.com/partnerships/marketplace/"
    html = fetch(url)
    if html:
        # Try to pull any program names and commission patterns
        # Impact often lists featured partners
        pairs = re.findall(
            r'(?:data-name|alt|title)="([^"]{3,40})"[^>]*>.*?'
            r'(\d{1,3})%',
            html, re.DOTALL
        )
        for name, pct in pairs[:20]:
            programs.append({
                "name": name.strip(),
                "category": "saas",
                "commission_pct": int(pct),
                "recurring": False,
                "cookie_days": 30,
                "url": "",
                "source": "impact",
            })
        print(f"  Impact.com: found {len(programs)} programs")
    else:
        print("  Impact.com: could not reach, skipping")

    time.sleep(REQUEST_DELAY)

    # ShareASale merchant search (public-facing)
    shareasale_progs = []
    url2 = "https://www.shareasale.com/info/"
    html2 = fetch(url2)
    if html2:
        pairs2 = re.findall(
            r'>([A-Z][A-Za-z0-9. &]+?)</.*?'
            r'(\d{1,3})%',
            html2, re.DOTALL
        )
        for name, pct in pairs2[:20]:
            name = name.strip()
            if len(name) >= 3:
                shareasale_progs.append({
                    "name": name,
                    "category": "saas",
                    "commission_pct": int(pct),
                    "recurring": False,
                    "cookie_days": 30,
                    "url": "",
                    "source": "shareasale",
                })
        print(f"  ShareASale: found {len(shareasale_progs)} programs")
    else:
        print("  ShareASale: could not reach, skipping")

    time.sleep(REQUEST_DELAY)
    programs.extend(shareasale_progs)
    return programs


# ---------------------------------------------------------------------------
# Source 3: Google Trends interest estimation
# ---------------------------------------------------------------------------

def estimate_search_interest(product_name):
    """
    Estimate relative search interest for a product via Google Trends.
    Returns a 0-100 score. Falls back to a heuristic if blocked.
    """
    query = urllib.request.quote(product_name)
    url = (
        f"https://trends.google.com/trends/api/dailytrends"
        f"?hl=en-US&tz=-540&geo=US&ns=15"
    )

    # Google Trends API is notoriously hard to scrape without auth.
    # We use the explore widget endpoint as a lightweight probe.
    explore_url = (
        f"https://trends.google.com/trends/api/explore"
        f"?hl=en-US&tz=-540&req=%7B%22comparisonItem%22%3A%5B%7B"
        f"%22keyword%22%3A%22{query}%22%2C%22geo%22%3A%22%22%2C"
        f"%22time%22%3A%22today+3-m%22%7D%5D%2C%22category%22%3A0"
        f"%2C%22property%22%3A%22%22%7D"
    )

    html = fetch(explore_url, max_retries=1)
    if html:
        # Google Trends returns JSON prefixed with ")]}'\n"
        clean = html.lstrip(")]}'\n")
        try:
            data = json.loads(clean)
            # Extract interest from the timeline data
            widgets = data.get("widgets", [])
            for w in widgets:
                if w.get("id") == "TIMESERIES":
                    token = w.get("token", "")
                    if token:
                        # We found a valid token — the product is indexed
                        return 65  # moderate-to-high baseline if indexed
            return 50
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback heuristic: well-known names get higher scores
    return _heuristic_interest(product_name)


def _heuristic_interest(name):
    """
    Simple heuristic: brand recognition correlates with search volume.
    Known big brands get high scores; unknowns get a baseline.
    """
    big_brands = {
        "hubspot", "canva", "notion", "semrush", "nordvpn", "wix",
        "squarespace", "monday.com", "clickup", "surfshark", "jasper",
        "hostinger", "aweber", "calendly", "1password", "webflow",
        "freshworks", "pipedrive", "zoho", "descript", "grammarly",
        "convertkit", "activecampaign", "getresponse",
    }
    mid_brands = {
        "copy.ai", "writesonic", "surfer seo", "pictory", "synthesia",
        "murf ai", "fireflies.ai", "mangools", "se ranking", "spyfu",
        "visme", "snappa", "teachable", "thinkific", "podia", "moosend",
        "cloudways", "kinsta", "brevo",
    }
    lower = name.lower()
    if any(b in lower for b in big_brands):
        return 80
    if any(b in lower for b in mid_brands):
        return 55
    return 35


def enrich_with_demand(programs, skip_network=False):
    """Add search demand estimates to each program. Rate-limited."""
    print("[3/3] Estimating search demand...")
    total = len(programs)
    for i, p in enumerate(programs):
        if skip_network:
            p["demand_score"] = _heuristic_interest(p["name"])
        else:
            p["demand_score"] = estimate_search_interest(p["name"])
            # Rate limit network calls
            if (i + 1) % 5 == 0:
                time.sleep(1.0)
        if (i + 1) % 10 == 0:
            print(f"  Estimated demand for {i+1}/{total} products...")
    return programs


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _extract_pct(text):
    """Pull the first percentage number from a string."""
    m = re.search(r'(\d{1,3})', text)
    return int(m.group(1)) if m else 0


def score_program(p):
    """
    Score a program on a 0-100 scale.
    commission_score: 0-50 (higher % is better, recurring gets 2x multiplier)
    demand_score:     0-50 (from search interest)
    """
    pct = p.get("commission_pct", 0)
    flat = p.get("commission_flat", 0)
    # Normalize: treat $100+ flat as ~20%, $200+ as ~30%, $500+ as ~50%
    if flat > 0 and pct == 0:
        pct = min(50, flat // 10)

    commission_raw = min(pct, 100)
    multiplier = 2.0 if p.get("recurring") else 1.0
    commission_score = min(50, (commission_raw * multiplier) / 2.0)

    demand = p.get("demand_score", 35)
    demand_score = demand / 2.0  # 0-50

    combined = commission_score + demand_score
    return round(combined, 1)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate(programs):
    """Keep the best entry for each product (by name)."""
    best = {}
    for p in programs:
        key = re.sub(r'[^a-z0-9]', '', p["name"].lower())
        if key not in best:
            best[key] = p
        else:
            # Keep the one with more data (higher commission or better source)
            existing = best[key]
            if p.get("commission_pct", 0) > existing.get("commission_pct", 0):
                best[key] = p
    return list(best.values())


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def filter_programs(programs, category=None, min_commission=0):
    """Filter by category and minimum commission."""
    result = []
    for p in programs:
        if category:
            prog_cat = p.get("category", "").lower()
            filter_cat = category.lower()
            # Exact match or the program category starts with the filter
            if prog_cat != filter_cat and not prog_cat.startswith(filter_cat + "-"):
                continue
        pct = p.get("commission_pct", 0)
        flat = p.get("commission_flat", 0)
        effective = pct if pct > 0 else (flat // 10 if flat > 0 else 0)
        if effective < min_commission:
            continue
        result.append(p)
    return result


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_summary(ranked):
    """Print a human-readable ranked summary."""
    print("\n" + "=" * 72)
    print("  AFFILIATE PRODUCT OPPORTUNITIES — RANKED")
    print("=" * 72)

    if not ranked:
        print("  No products found matching your criteria.")
        return

    print(f"\n  {'#':<4} {'Product':<25} {'Category':<15} {'Commission':<18} {'Recurring':<10} {'Score'}")
    print(f"  {'—'*4} {'—'*25} {'—'*15} {'—'*18} {'—'*10} {'—'*6}")

    for i, p in enumerate(ranked[:40], 1):
        pct = p.get("commission_pct", 0)
        flat = p.get("commission_flat", 0)
        if pct > 0:
            comm_str = f"{pct}%"
        elif flat > 0:
            comm_str = f"${flat} flat"
        else:
            comm_str = "Unknown"

        rec = "Yes" if p.get("recurring") else "No"
        score = p.get("score", 0)
        cat = p.get("category", "—")[:14]
        name = p["name"][:24]

        print(f"  {i:<4} {name:<25} {cat:<15} {comm_str:<18} {rec:<10} {score}")

    # Category breakdown
    cats = {}
    for p in ranked:
        c = p.get("category", "other")
        cats[c] = cats.get(c, 0) + 1
    print(f"\n  Categories: {', '.join(f'{c}({n})' for c, n in sorted(cats.items()))}")
    print(f"  Total programs: {len(ranked)}")

    # Top picks callout
    top = [p for p in ranked[:5]]
    if top:
        print(f"\n  TOP PICKS (highest combined commission + demand):")
        for p in top:
            pct = p.get("commission_pct", 0)
            flat = p.get("commission_flat", 0)
            comm = f"{pct}% recurring" if p.get("recurring") and pct else f"{pct}%" if pct else f"${flat}"
            print(f"    -> {p['name']}: {comm}, demand={p.get('demand_score', '?')}/100, score={p.get('score')}")

    print()


def save_report(ranked):
    """Save the ranked report to JSON."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_programs": len(ranked),
        "programs": ranked,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(report, f, indent=2)

    print(f"  Report saved to: {OUTPUT_FILE}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Discover high-commission affiliate products")
    parser.add_argument("--category", type=str, default=None,
                        help="Filter by category (ai, email, hosting, seo, design, saas, etc.)")
    parser.add_argument("--min-commission", type=int, default=0,
                        help="Minimum commission percentage to include")
    parser.add_argument("--seed-only", action="store_true",
                        help="Use only the curated seed list (offline mode)")
    args = parser.parse_args()

    print(f"SpottedHQ Affiliate Product Discovery — {TODAY}")
    print("-" * 50)

    all_programs = []

    if args.seed_only:
        print("[SEED-ONLY MODE] Using curated seed list...")
        all_programs = [dict(p) for p in SEED_PROGRAMS]
    else:
        # 1. Scrape PartnerStack
        try:
            ps_progs = scrape_partnerstack()
            all_programs.extend(ps_progs)
        except Exception as e:
            print(f"  [ERROR] PartnerStack scrape failed: {e}")

        # 2. Scrape Impact / ShareASale
        try:
            network_progs = scrape_impact()
            all_programs.extend(network_progs)
        except Exception as e:
            print(f"  [ERROR] Network scrape failed: {e}")

        # 3. Always include seed list as baseline
        print("  Adding curated seed list as baseline...")
        all_programs.extend([dict(p) for p in SEED_PROGRAMS])

    # Deduplicate (seed data fills gaps when scraping fails)
    all_programs = deduplicate(all_programs)
    print(f"\n  Total unique programs after dedup: {len(all_programs)}")

    # Filter
    if args.category or args.min_commission:
        all_programs = filter_programs(all_programs, args.category, args.min_commission)
        print(f"  After filtering: {len(all_programs)} programs")

    if not all_programs:
        print("\nNo programs found matching your criteria.")
        return

    # Enrich with demand estimates
    all_programs = enrich_with_demand(all_programs, skip_network=args.seed_only)

    # Score and rank
    for p in all_programs:
        p["score"] = score_program(p)
    ranked = sorted(all_programs, key=lambda x: x["score"], reverse=True)

    # Output
    print_summary(ranked)
    save_report(ranked)


if __name__ == "__main__":
    main()
