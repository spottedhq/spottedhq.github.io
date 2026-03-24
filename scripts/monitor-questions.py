#!/opt/homebrew/bin/python3
"""
Reddit Question Monitor for SpottedHQ

Monitors target subreddits for high-intent questions (product recommendations,
comparisons, alternatives) that we can answer with helpful blog-linked replies.

Usage:
    python3 monitor-questions.py
    python3 monitor-questions.py --hours 48
    python3 monitor-questions.py --min-score 5

Output:
    data/questions-YYYY-MM-DD.json
"""

import json
import re
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SUBREDDITS = [
    "SaaS",
    "Entrepreneur",
    "smallbusiness",
    "artificial",
    "ChatGPT",
    "productivity",
    "marketing",
]

# Patterns that signal buying intent or comparison research.
# Each is compiled case-insensitive. The raw string is stored alongside
# so we can log which pattern matched.
INTENT_PATTERNS = [
    r"best\s+\w+.*?\s+for\b",
    r"\w+\s+vs\.?\s+\w+",
    r"alternative\s+to\b",
    r"alternatives?\s+for\b",
    r"recommend\w*\s+\w*\s*tool",
    r"recommend\w*\s+\w*\s*software",
    r"recommend\w*\s+\w*\s*app",
    r"recommend\w*\s+\w*\s*platform",
    r"looking\s+for\s+(a\s+)?",
    r"which\s+\w+\s+should\s+I",
    r"what\s+\w+\s+(do\s+you|should\s+I)\s+use",
    r"anyone\s+(use|tried|using)\b",
    r"switch(ed|ing)?\s+from\b",
    r"moved?\s+from\b.*\s+to\b",
    r"what('s|\s+is)\s+the\s+best\b",
    r"top\s+\d+\s+\w+\s+(tools?|apps?|software|platforms?)",
    r"need\s+(a\s+)?(tool|app|software|platform)\b",
    r"suggestions?\s+for\b",
]

COMPILED_PATTERNS = [(p, re.compile(p, re.IGNORECASE)) for p in INTENT_PATTERNS]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

REQUEST_DELAY = 2.5          # seconds between requests
POSTS_PER_SUBREDDIT = 100    # Reddit returns max 100 per page
DEFAULT_HOURS = 48           # look-back window
DEFAULT_MIN_SCORE = 1        # minimum upvotes to include

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ---------------------------------------------------------------------------
# Reddit fetching
# ---------------------------------------------------------------------------

def fetch_subreddit_new(subreddit: str, limit: int = POSTS_PER_SUBREDDIT) -> list[dict]:
    """Fetch recent posts from a subreddit using the public JSON API."""
    url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        children = data.get("data", {}).get("children", [])
        return [c["data"] for c in children if c.get("kind") == "t3"]
    except urllib.error.HTTPError as e:
        print(f"  [!] HTTP {e.code} fetching r/{subreddit} — skipping")
        return []
    except Exception as e:
        print(f"  [!] Error fetching r/{subreddit}: {e}")
        return []


# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------

def match_intent(title: str) -> list[str]:
    """Return list of matched pattern strings for a post title."""
    matched = []
    for raw_pattern, compiled in COMPILED_PATTERNS:
        if compiled.search(title):
            matched.append(raw_pattern)
    return matched


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(hours: int = DEFAULT_HOURS, min_score: int = DEFAULT_MIN_SCORE):
    now = datetime.now(timezone.utc)
    cutoff_ts = now.timestamp() - (hours * 3600)
    today = datetime.now().strftime("%Y-%m-%d")
    results = []

    print(f"Monitoring {len(SUBREDDITS)} subreddits for high-intent questions")
    print(f"Look-back window: {hours}h | Min score: {min_score}")
    print(f"Cutoff: {datetime.fromtimestamp(cutoff_ts, tz=timezone.utc).isoformat()}")
    print()

    for i, sub in enumerate(SUBREDDITS):
        if i > 0:
            time.sleep(REQUEST_DELAY)

        print(f"  Fetching r/{sub} ...", end=" ", flush=True)
        posts = fetch_subreddit_new(sub)
        matched_count = 0

        for post in posts:
            created = post.get("created_utc", 0)
            if created < cutoff_ts:
                continue

            title = post.get("title", "")
            patterns = match_intent(title)
            if not patterns:
                continue

            score = post.get("score", 0)
            if score < min_score:
                continue

            matched_count += 1
            results.append({
                "title": title,
                "url": f"https://www.reddit.com{post.get('permalink', '')}",
                "subreddit": sub,
                "score": score,
                "num_comments": post.get("num_comments", 0),
                "matched_patterns": patterns,
                "created_utc": created,
                "created_iso": datetime.fromtimestamp(created, tz=timezone.utc).isoformat(),
                "selftext_snippet": (post.get("selftext", "") or "")[:300],
            })

        print(f"{len(posts)} posts, {matched_count} matched")

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)

    # Save
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    outfile = DATA_DIR / f"questions-{today}.json"
    with open(outfile, "w") as f:
        json.dump({
            "generated": now.isoformat(),
            "params": {"hours": hours, "min_score": min_score},
            "count": len(results),
            "questions": results,
        }, f, indent=2, ensure_ascii=False)

    print()
    print(f"Found {len(results)} high-intent questions")
    print(f"Saved to {outfile}")

    # Print top results as a quick summary
    if results:
        print()
        print("=" * 70)
        print("TOP QUESTIONS")
        print("=" * 70)
        for q in results[:20]:
            print()
            print(f"  [{q['score']:>3} pts | {q['num_comments']:>2} comments] r/{q['subreddit']}")
            print(f"  {q['title']}")
            print(f"  {q['url']}")
            print(f"  Patterns: {', '.join(q['matched_patterns'][:3])}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Monitor Reddit for high-intent questions")
    parser.add_argument("--hours", type=int, default=DEFAULT_HOURS,
                        help=f"Look-back window in hours (default: {DEFAULT_HOURS})")
    parser.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE,
                        help=f"Minimum post score to include (default: {DEFAULT_MIN_SCORE})")
    args = parser.parse_args()

    run(hours=args.hours, min_score=args.min_score)
