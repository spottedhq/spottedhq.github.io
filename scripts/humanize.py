#!/opt/homebrew/bin/python3
"""
SpottedHQ Content Humanizer

Batch-processes blog posts through Claude API to remove AI writing patterns.
Based on Wikipedia's "Signs of AI writing" guide + blader/humanizer skill patterns.

Usage:
    python3 humanize.py                           # humanize all filled comparison pages
    python3 humanize.py --file content/compare/jasper-vs-copyai.md
    python3 humanize.py --section compare          # all comparison pages
    python3 humanize.py --section best             # all best-of pages
    python3 humanize.py --dry-run                  # show what would be processed
    python3 humanize.py --check                    # score pages for AI-ness without rewriting

Requires: ANTHROPIC_API_KEY environment variable
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
CONTENT_DIR = ROOT_DIR / "content"

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5-20251001"  # cheap + fast for batch processing
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

SYSTEM_PROMPT = """You are a writing editor who removes AI-generated patterns from text. Your job is to make comparison articles sound like a knowledgeable human wrote them, not a language model.

## RULES

1. Keep ALL factual content, pricing, features, and product details intact
2. Keep the markdown structure (headings, tables, frontmatter) exactly as-is
3. Only rewrite the prose — the sentences between structural elements
4. Preserve affiliate link placeholders (#) and disclosure footers
5. Do NOT add new information or opinions you aren't sure about
6. Do NOT change the frontmatter block (between --- markers)

## AI PATTERNS TO FIX

### Words to ban or replace:
- "delve/delves" → just say what it does
- "landscape" (abstract) → drop it or be specific
- "tapestry" (abstract) → drop it
- "crucial/pivotal/vital" → "important" or just drop it
- "comprehensive" → "full" or "detailed" or drop
- "robust" → "strong" or be specific
- "leverage" → "use"
- "utilize" → "use"
- "facilitate" → "help" or "let"
- "Additionally" → "Also" or restructure
- "Furthermore" → drop or restructure
- "It's worth noting that" → just say it
- "It's important to note" → just say it
- "stands as / serves as" → "is"
- "boasts" → "has"
- "showcases" → "shows"
- "underscores / highlights" → "shows" or drop
- "garner" → "get"
- "foster" → "build" or "encourage"
- "enhance" → "improve"
- "streamline" → "simplify" or "speed up"
- "seamless" → "smooth" or drop
- "game-changer" → drop or be specific
- "best-in-class" → be specific about what makes it good
- "genuinely" → usually drop

### Structural patterns to fix:
- Rule of three ("X, Y, and Z" for everything) → use natural groupings
- "Not only X, but also Y" → just say both things
- Em dash overuse — use commas or periods instead
- Every paragraph same length → vary between 1-4 sentences
- Formulaic transitions → cut them or vary
- Generic conclusions ("Both are solid choices") → have an actual opinion
- Excessive hedging ("may potentially") → commit to a statement
- Synonym cycling (using different words for the same thing to avoid repetition) → just repeat the word

### Voice guidelines:
- Write like you're explaining to a friend who asked "which one should I get?"
- Have opinions. Pick sides when the data supports it.
- Use "you" naturally. "If you're a small team..." not "For small teams..."
- Short sentences are fine. Mix them with longer ones.
- Start some sentences with "And" or "But" — humans do this.
- It's okay to say "honestly" or "look" occasionally
- Use contractions (don't, won't, it's, that's)
- Cut filler. If a sentence works without a word, drop the word.

## PROCESS

1. Read the full article
2. Rewrite the prose sections to sound human (keep tables, frontmatter, headings intact)
3. Do a final pass: ask yourself "what still sounds AI?" and fix those parts
4. Return the complete article with all formatting preserved

Return ONLY the rewritten article. No commentary, no explanations."""


def extract_frontmatter_and_body(text):
    """Split markdown into frontmatter and body."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return f"---{parts[1]}---", parts[2]
    return "", text


def is_filled_page(filepath):
    """Check if a page has real content (not just template)."""
    try:
        text = filepath.read_text()
        return "<!-- EXPAND" not in text and "<!-- FILL" not in text
    except Exception:
        return False


def call_claude(content, max_retries=3):
    """Call Claude API to humanize content."""
    if not API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    payload = json.dumps({
        "model": MODEL,
        "max_tokens": 8192,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": f"Humanize this article. Return the complete rewritten article with all markdown formatting preserved:\n\n{content}"
            }
        ]
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
    }

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(API_URL, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["content"][0]["text"]
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 429:
                wait = min(30, 5 * (attempt + 1))
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            elif e.code == 529:
                print(f"    API overloaded, waiting 10s...")
                time.sleep(10)
                continue
            else:
                print(f"    API error {e.code}: {body[:200]}")
                return None
        except Exception as e:
            print(f"    Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(3)
            else:
                return None
    return None


def score_ai_patterns(text):
    """Quick score of how AI-like the text sounds. Higher = more AI."""
    ai_words = [
        "delve", "tapestry", "landscape", "crucial", "pivotal", "comprehensive",
        "robust", "leverage", "utilize", "facilitate", "furthermore", "additionally",
        "stands as", "serves as", "boasts", "showcases", "underscores", "highlights",
        "garner", "foster", "enhance", "streamline", "seamless", "game-changer",
        "best-in-class", "genuinely", "it's worth noting", "it's important to note",
        "not only", "vibrant", "testament", "enduring", "nestled", "groundbreaking",
    ]
    text_lower = text.lower()
    score = 0
    found = []
    for word in ai_words:
        count = text_lower.count(word)
        if count > 0:
            score += count
            found.append(f"{word}({count})")

    # Check em dash overuse
    em_dashes = text.count("—")
    if em_dashes > 3:
        score += em_dashes - 3
        found.append(f"em-dashes({em_dashes})")

    return score, found


def humanize_file(filepath, dry_run=False, check_only=False):
    """Humanize a single markdown file."""
    text = filepath.read_text()
    frontmatter, body = extract_frontmatter_and_body(text)

    if check_only:
        score, found = score_ai_patterns(body)
        return score, found

    if dry_run:
        score, found = score_ai_patterns(body)
        return score, found

    # Call Claude to humanize
    result = call_claude(text)
    if result is None:
        return -1, ["API call failed"]

    # Ensure frontmatter is preserved
    result_fm, result_body = extract_frontmatter_and_body(result)
    if not result_fm:
        # Claude dropped the frontmatter, re-add it
        result = frontmatter + "\n" + result

    # Write back
    filepath.write_text(result)

    # Score the result
    new_score, new_found = score_ai_patterns(result)
    return new_score, new_found


def get_files(section=None, single_file=None):
    """Get list of files to process."""
    if single_file:
        p = Path(single_file)
        if not p.is_absolute():
            p = ROOT_DIR / single_file
        return [p] if p.exists() else []

    files = []
    sections = [section] if section else ["compare", "best"]
    for sec in sections:
        sec_dir = CONTENT_DIR / sec
        if sec_dir.exists():
            for f in sorted(sec_dir.glob("*.md")):
                if is_filled_page(f):
                    files.append(f)
    return files


def main():
    parser = argparse.ArgumentParser(description="SpottedHQ Content Humanizer")
    parser.add_argument("--file", help="Single file to humanize")
    parser.add_argument("--section", help="Section to process (compare, best)")
    parser.add_argument("--dry-run", action="store_true", help="Show AI scores without rewriting")
    parser.add_argument("--check", action="store_true", help="Score pages for AI patterns")
    args = parser.parse_args()

    files = get_files(section=args.section, single_file=args.file)
    if not files:
        print("No filled pages found to process.")
        return

    print(f"{'=' * 60}")
    print(f"  SpottedHQ Content Humanizer")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Files to process: {len(files)}")
    print(f"{'=' * 60}\n")

    if args.check or args.dry_run:
        print(f"  {'File':<50} {'Score':>6}  AI Patterns Found")
        print(f"  {'─' * 48} {'─' * 6}  {'─' * 30}")
        total_score = 0
        for f in files:
            score, found = humanize_file(f, check_only=True)
            total_score += score
            indicator = "🔴" if score > 10 else "🟡" if score > 5 else "🟢"
            patterns = ", ".join(found[:5])
            if len(found) > 5:
                patterns += f" +{len(found)-5} more"
            print(f"  {f.stem:<50} {score:>6}  {patterns}")
        print(f"\n  Total AI score: {total_score} across {len(files)} files")
        print(f"  Average: {total_score / len(files):.1f} per file")
        return

    # Actual humanization
    if not API_KEY:
        print("ERROR: Set ANTHROPIC_API_KEY environment variable")
        print("  export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    processed = 0
    failed = 0
    for i, f in enumerate(files, 1):
        # Score before
        before_score, before_found = score_ai_patterns(f.read_text())
        print(f"  [{i}/{len(files)}] {f.stem}")
        print(f"    Before: AI score {before_score} ({', '.join(before_found[:3])})")

        score, found = humanize_file(f)
        if score < 0:
            print(f"    FAILED — skipping")
            failed += 1
        else:
            print(f"    After:  AI score {score}")
            processed += 1

        # Rate limit buffer
        if i < len(files):
            time.sleep(1)

    print(f"\n{'=' * 60}")
    print(f"  Done — {processed} humanized, {failed} failed")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
