#!/opt/homebrew/bin/python3
"""
generate-pins.py — Generate Pinterest-ready pin images for SpottedHQ blog posts.

Produces 1000x1500px pins in two styles:
  - compare: "[Tool A] vs [Tool B]" with VS badge
  - best-of: "Best [Category] for [Use Case]"

Usage:
  python3 generate-pins.py --type compare --input data/comparisons.csv --output static/pins/
  python3 generate-pins.py --type bestof --input data/best-of.csv --output static/pins/
  python3 generate-pins.py --type compare --slug "notion-vs-coda" --input data/comparisons.csv
  python3 generate-pins.py --from-markdown content/compare/notion-vs-coda.md --output static/pins/
"""

import argparse
import csv
import os
import re
import sys
import textwrap
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow not installed. Run: pip install --break-system-packages --user Pillow")
    sys.exit(1)

# --- Design constants ---
WIDTH, HEIGHT = 1000, 1500
BG_COLOR = "#1a1a2e"
TEXT_COLOR = "#ffffff"
ACCENT_COLOR = "#e94560"
ACCENT_DARK = "#c73a52"
SUBTLE_COLOR = "#8888aa"
CARD_COLOR = "#16213e"

# Font paths (macOS)
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
FONT_REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_IMPACT = "/System/Library/Fonts/Supplemental/Impact.ttf"
FONT_NARROW_BOLD = "/System/Library/Fonts/Supplemental/Arial Narrow Bold.ttf"

# Fallbacks
if not os.path.exists(FONT_BOLD):
    FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
if not os.path.exists(FONT_IMPACT):
    FONT_IMPACT = FONT_BOLD


def load_font(path, size):
    """Load a font, falling back to default if not found."""
    try:
        return ImageFont.truetype(path, size)
    except (OSError, IOError):
        return ImageFont.load_default()


def slugify(text):
    """Convert text to a filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-")


def draw_rounded_rect(draw, xy, radius, fill):
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = xy
    draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill)
    draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill)
    draw.pieslice([x0, y0, x0 + 2 * radius, y0 + 2 * radius], 180, 270, fill=fill)
    draw.pieslice([x1 - 2 * radius, y0, x1, y0 + 2 * radius], 270, 360, fill=fill)
    draw.pieslice([x0, y1 - 2 * radius, x0 + 2 * radius, y1], 90, 180, fill=fill)
    draw.pieslice([x1 - 2 * radius, y1 - 2 * radius, x1, y1], 0, 90, fill=fill)


def wrap_text_to_fit(draw, text, font_path, max_width, max_font_size, min_font_size=28):
    """Find the largest font size that fits text within max_width, with wrapping.
    Returns (font, wrapped_lines)."""
    for size in range(max_font_size, min_font_size - 1, -2):
        font = load_font(font_path, size)
        # Estimate chars per line
        avg_char_w = font.getlength("M")
        chars_per_line = max(1, int(max_width / avg_char_w))
        lines = textwrap.wrap(text, width=chars_per_line)
        # Check all lines fit
        fits = all(font.getlength(line) <= max_width for line in lines)
        if fits and len(lines) <= 4:
            return font, lines
    # Return smallest size as last resort
    font = load_font(font_path, min_font_size)
    avg_char_w = font.getlength("M")
    chars_per_line = max(1, int(max_width / avg_char_w))
    lines = textwrap.wrap(text, width=chars_per_line)
    return font, lines


def draw_centered_text(draw, text, y, font, fill, max_width=None):
    """Draw text centered horizontally at y. Returns the y coordinate below the text."""
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    x = (WIDTH - tw) // 2
    draw.text((x, y), text, font=font, fill=fill)
    # Use bbox[3] which is the full descent from the origin
    return y + bbox[3]


def generate_comparison_pin(row, output_dir):
    """Generate a comparison pin: Tool A vs Tool B."""
    tool_a = row["tool_a"].strip()
    tool_b = row["tool_b"].strip()
    category = row.get("category", "").strip()
    tool_a_best = row.get("tool_a_best_for", "").strip()
    tool_b_best = row.get("tool_b_best_for", "").strip()
    tool_a_price = row.get("tool_a_price", "").strip()
    tool_b_price = row.get("tool_b_price", "").strip()

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # --- Top accent bar ---
    draw.rectangle([0, 0, WIDTH, 8], fill=ACCENT_COLOR)

    # --- Category label ---
    y = 60
    cat_font = load_font(FONT_NARROW_BOLD, 28)
    cat_text = category.upper().replace("-", " ") if category else "COMPARISON"
    draw_rounded_rect(draw, (WIDTH // 2 - 120, y - 5, WIDTH // 2 + 120, y + 35), 16, ACCENT_COLOR)
    bbox = cat_font.getbbox(cat_text)
    tw = bbox[2] - bbox[0]
    draw.text(((WIDTH - tw) // 2, y), cat_text, font=cat_font, fill=TEXT_COLOR)

    # --- Tool A name ---
    y = 140
    name_font_a, lines_a = wrap_text_to_fit(draw, tool_a, FONT_BOLD, WIDTH - 120, 72, 40)
    for line in lines_a:
        y = draw_centered_text(draw, line, y, name_font_a, TEXT_COLOR) + 8
    y += 20

    # --- Tool A price tag ---
    if tool_a_price:
        price_font = load_font(FONT_REGULAR, 28)
        y = draw_centered_text(draw, tool_a_price, y, price_font, SUBTLE_COLOR) + 15

    # --- VS badge ---
    vs_center_y = 420
    badge_r = 55
    # Outer ring
    draw.ellipse(
        [WIDTH // 2 - badge_r - 4, vs_center_y - badge_r - 4,
         WIDTH // 2 + badge_r + 4, vs_center_y + badge_r + 4],
        fill=TEXT_COLOR
    )
    # Inner circle
    draw.ellipse(
        [WIDTH // 2 - badge_r, vs_center_y - badge_r,
         WIDTH // 2 + badge_r, vs_center_y + badge_r],
        fill=ACCENT_COLOR
    )
    vs_font = load_font(FONT_IMPACT, 56)
    vs_bbox = vs_font.getbbox("VS")
    vs_w = vs_bbox[2] - vs_bbox[0]
    vs_h = vs_bbox[3] - vs_bbox[1]
    draw.text(
        (WIDTH // 2 - vs_w // 2, vs_center_y - vs_h // 2 - 4),
        "VS", font=vs_font, fill=TEXT_COLOR
    )

    # --- Horizontal divider lines around VS ---
    line_y = vs_center_y
    draw.line([(60, line_y), (WIDTH // 2 - badge_r - 20, line_y)], fill=ACCENT_COLOR, width=2)
    draw.line([(WIDTH // 2 + badge_r + 20, line_y), (WIDTH - 60, line_y)], fill=ACCENT_COLOR, width=2)

    # --- Tool B name ---
    y = 510
    name_font_b, lines_b = wrap_text_to_fit(draw, tool_b, FONT_BOLD, WIDTH - 120, 72, 40)
    for line in lines_b:
        y = draw_centered_text(draw, line, y, name_font_b, TEXT_COLOR) + 8
    y += 20

    # --- Tool B price tag ---
    if tool_b_price:
        price_font = load_font(FONT_REGULAR, 28)
        y = draw_centered_text(draw, tool_b_price, y, price_font, SUBTLE_COLOR) + 15

    # --- Best-for cards ---
    card_top = 750
    card_h = 200
    card_margin = 40
    card_w = (WIDTH - card_margin * 3) // 2

    for i, (label, best_for) in enumerate([(tool_a, tool_a_best), (tool_b, tool_b_best)]):
        if not best_for:
            continue
        cx = card_margin + i * (card_w + card_margin)
        draw_rounded_rect(draw, (cx, card_top, cx + card_w, card_top + card_h), 16, CARD_COLOR)

        # Card header
        header_font = load_font(FONT_BOLD, 22)
        header_text = f"BEST FOR"
        hbox = header_font.getbbox(header_text)
        hw = hbox[2] - hbox[0]
        draw.text((cx + (card_w - hw) // 2, card_top + 20), header_text, font=header_font, fill=ACCENT_COLOR)

        # Best-for text (wrapped)
        bf_font = load_font(FONT_REGULAR, 22)
        avg_cw = bf_font.getlength("M")
        chars = max(1, int((card_w - 30) / avg_cw))
        bf_lines = textwrap.wrap(best_for, width=chars)
        by = card_top + 65
        for bline in bf_lines[:4]:
            blbox = bf_font.getbbox(bline)
            blw = blbox[2] - blbox[0]
            draw.text((cx + (card_w - blw) // 2, by), bline, font=bf_font, fill=TEXT_COLOR)
            by += 30

    # --- Bottom section: year + tagline ---
    y = 1050
    tagline_font = load_font(FONT_BOLD, 32)
    tagline = f"Which One Should You Pick in 2026?"
    draw_centered_text(draw, tagline, y, tagline_font, TEXT_COLOR)

    # --- Decorative bottom accent line ---
    draw.rectangle([80, 1160, WIDTH - 80, 1162], fill=ACCENT_COLOR)

    # --- Branding ---
    brand_font = load_font(FONT_BOLD, 40)
    dot_font = load_font(FONT_BOLD, 40)
    brand_text = "SpottedHQ"
    brand_y = 1350
    bbox = brand_font.getbbox(brand_text)
    bw = bbox[2] - bbox[0]

    # Accent dot before brand
    dot_w = dot_font.getlength("● ")
    total_w = dot_w + bw
    start_x = (WIDTH - total_w) // 2
    draw.text((start_x, brand_y), "● ", font=dot_font, fill=ACCENT_COLOR)
    draw.text((start_x + dot_w, brand_y), brand_text, font=brand_font, fill=TEXT_COLOR)

    # Tagline under brand
    sub_font = load_font(FONT_REGULAR, 22)
    sub_text = "spottedhq.com"
    sub_bbox = sub_font.getbbox(sub_text)
    sub_w = sub_bbox[2] - sub_bbox[0]
    draw.text(((WIDTH - sub_w) // 2, brand_y + 55), sub_text, font=sub_font, fill=SUBTLE_COLOR)

    # --- Bottom accent bar ---
    draw.rectangle([0, HEIGHT - 8, WIDTH, HEIGHT], fill=ACCENT_COLOR)

    # Save
    slug = slugify(f"{tool_a}-vs-{tool_b}")
    filename = f"pin-compare-{slug}.png"
    filepath = os.path.join(output_dir, filename)
    img.save(filepath, "PNG", quality=95)
    print(f"  ✓ {filename}")
    return filepath


def generate_bestof_pin(row, output_dir):
    """Generate a best-of pin: Best [Category] for [Use Case]."""
    category_name = row["category_name"].strip()
    use_case = row["use_case"].strip()
    seo_category = row.get("seo_category", "").strip()
    tags = row.get("tags", "").strip()

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # --- Top accent bar ---
    draw.rectangle([0, 0, WIDTH, 8], fill=ACCENT_COLOR)

    # --- Category tag at top ---
    y = 80
    cat_font = load_font(FONT_NARROW_BOLD, 26)
    cat_label = seo_category.upper().replace("-", " ") if seo_category else "GUIDE"
    draw_rounded_rect(draw, (WIDTH // 2 - 100, y - 5, WIDTH // 2 + 100, y + 32), 14, ACCENT_COLOR)
    cbox = cat_font.getbbox(cat_label)
    cw = cbox[2] - cbox[0]
    draw.text(((WIDTH - cw) // 2, y), cat_label, font=cat_font, fill=TEXT_COLOR)

    # --- Big "BEST" word ---
    y = 220
    best_font = load_font(FONT_IMPACT, 140)
    best_text = "BEST"
    bbox = best_font.getbbox(best_text)
    bw = bbox[2] - bbox[0]
    draw.text(((WIDTH - bw) // 2, y), best_text, font=best_font, fill=ACCENT_COLOR)

    # --- Category name ---
    y = 400
    cat_name_font, cat_lines = wrap_text_to_fit(draw, category_name, FONT_BOLD, WIDTH - 120, 64, 36)
    for line in cat_lines:
        y = draw_centered_text(draw, line, y, cat_name_font, TEXT_COLOR) + 10

    # --- "for" connector ---
    y += 30
    for_font = load_font(FONT_REGULAR, 36)
    draw_centered_text(draw, "for", y, for_font, SUBTLE_COLOR)

    # --- Use case ---
    y += 70
    uc_font, uc_lines = wrap_text_to_fit(draw, use_case, FONT_BOLD, WIDTH - 120, 60, 36)
    for line in uc_lines:
        y = draw_centered_text(draw, line, y, uc_font, ACCENT_COLOR) + 10

    # --- Decorative elements ---
    # Diamond separator — flows from content above
    y += 50
    diamond_y = max(y, 820)  # minimum position to keep layout balanced
    draw.polygon(
        [(WIDTH // 2, diamond_y - 12), (WIDTH // 2 + 12, diamond_y),
         (WIDTH // 2, diamond_y + 12), (WIDTH // 2 - 12, diamond_y)],
        fill=ACCENT_COLOR
    )
    draw.line([(100, diamond_y), (WIDTH // 2 - 30, diamond_y)], fill=ACCENT_COLOR, width=2)
    draw.line([(WIDTH // 2 + 30, diamond_y), (WIDTH - 100, diamond_y)], fill=ACCENT_COLOR, width=2)

    # --- Tags display ---
    y = diamond_y + 40
    if tags:
        tag_list = [t.strip() for t in tags.split(",")][:4]
        tag_font = load_font(FONT_REGULAR, 22)
        tag_y = y
        # Calculate total width
        tag_padding = 20
        tag_gap = 12
        tag_widths = []
        for t in tag_list:
            tw = tag_font.getlength(f"#{t}")
            tag_widths.append(tw + tag_padding * 2)
        total_tags_w = sum(tag_widths) + tag_gap * (len(tag_list) - 1)
        tx = (WIDTH - total_tags_w) // 2

        for i, t in enumerate(tag_list):
            tw = tag_widths[i]
            draw_rounded_rect(draw, (tx, tag_y, tx + tw, tag_y + 38), 12, CARD_COLOR)
            tbox = tag_font.getbbox(f"#{t}")
            text_w = tbox[2] - tbox[0]
            draw.text((tx + (tw - text_w) // 2, tag_y + 6), f"#{t}", font=tag_font, fill=SUBTLE_COLOR)
            tx += tw + tag_gap
        y = tag_y + 60

    # --- "2026 Guide" label ---
    y += 40
    guide_font = load_font(FONT_BOLD, 34)
    draw_centered_text(draw, "2026 Guide", y, guide_font, TEXT_COLOR)

    # --- Decorative bottom accent line ---
    draw.rectangle([80, 1160, WIDTH - 80, 1162], fill=ACCENT_COLOR)

    # --- Branding ---
    brand_font = load_font(FONT_BOLD, 40)
    dot_font = load_font(FONT_BOLD, 40)
    brand_text = "SpottedHQ"
    brand_y = 1350
    bbox = brand_font.getbbox(brand_text)
    bw = bbox[2] - bbox[0]
    dot_w = dot_font.getlength("● ")
    total_w = dot_w + bw
    start_x = (WIDTH - total_w) // 2
    draw.text((start_x, brand_y), "● ", font=dot_font, fill=ACCENT_COLOR)
    draw.text((start_x + dot_w, brand_y), brand_text, font=brand_font, fill=TEXT_COLOR)

    sub_font = load_font(FONT_REGULAR, 22)
    sub_text = "spottedhq.com"
    sub_bbox = sub_font.getbbox(sub_text)
    sub_w = sub_bbox[2] - sub_bbox[0]
    draw.text(((WIDTH - sub_w) // 2, brand_y + 55), sub_text, font=sub_font, fill=SUBTLE_COLOR)

    # --- Bottom accent bar ---
    draw.rectangle([0, HEIGHT - 8, WIDTH, HEIGHT], fill=ACCENT_COLOR)

    # Save
    slug = slugify(f"best-{category_name}-for-{use_case}")
    filename = f"pin-bestof-{slug}.png"
    filepath = os.path.join(output_dir, filename)
    img.save(filepath, "PNG", quality=95)
    print(f"  ✓ {filename}")
    return filepath


def parse_markdown_frontmatter(md_path):
    """Extract frontmatter from a Hugo markdown file. Returns dict."""
    with open(md_path, "r") as f:
        content = f.read()

    # Match YAML frontmatter between ---
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    fm = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if ":" in line:
            key, val = line.split(":", 1)
            val = val.strip().strip('"').strip("'")
            fm[key.strip()] = val
    return fm


def generate_from_markdown(md_path, output_dir):
    """Auto-detect pin type from markdown frontmatter and generate."""
    fm = parse_markdown_frontmatter(md_path)
    if not fm:
        print(f"  ✗ No frontmatter found in {md_path}")
        return None

    # Detect type from path or frontmatter
    path_lower = md_path.lower()
    if "/compare/" in path_lower or "tool_a" in fm or " vs " in fm.get("title", "").lower():
        # Build a comparison row from frontmatter
        title = fm.get("title", "")
        # Try to extract tool names from title like "Notion vs Coda"
        vs_match = re.match(r"(.+?)\s+vs\.?\s+(.+)", title, re.IGNORECASE)
        if vs_match:
            row = {
                "tool_a": vs_match.group(1).strip(),
                "tool_b": vs_match.group(2).strip(),
                "category": fm.get("category", fm.get("seo_category", "")),
                "tool_a_price": fm.get("tool_a_price", ""),
                "tool_b_price": fm.get("tool_b_price", ""),
                "tool_a_best_for": fm.get("tool_a_best_for", ""),
                "tool_b_best_for": fm.get("tool_b_best_for", ""),
            }
            return generate_comparison_pin(row, output_dir)
        else:
            print(f"  ✗ Could not parse comparison from title: {title}")
            return None

    elif "/best/" in path_lower or "best" in fm.get("title", "").lower():
        title = fm.get("title", "")
        best_match = re.match(r"best\s+(.+?)\s+for\s+(.+)", title, re.IGNORECASE)
        if best_match:
            row = {
                "category_name": best_match.group(1).strip(),
                "use_case": best_match.group(2).strip(),
                "seo_category": fm.get("category", fm.get("seo_category", "")),
                "tags": fm.get("tags", ""),
            }
            return generate_bestof_pin(row, output_dir)
        else:
            print(f"  ✗ Could not parse best-of from title: {title}")
            return None
    else:
        print(f"  ✗ Could not detect pin type for: {md_path}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Generate Pinterest pin images for SpottedHQ")
    parser.add_argument("--type", choices=["compare", "bestof"], help="Pin type to generate")
    parser.add_argument("--input", help="Path to CSV input file")
    parser.add_argument("--output", default="static/pins/", help="Output directory (default: static/pins/)")
    parser.add_argument("--slug", help="Generate pin for a single row matching this slug (e.g. 'notion-vs-coda')")
    parser.add_argument("--from-markdown", help="Generate pin from a Hugo markdown file's frontmatter")
    args = parser.parse_args()

    # Resolve output dir relative to project root
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent  # spottedhq/
    output_dir = (project_root / args.output).resolve() if not os.path.isabs(args.output) else Path(args.output)
    os.makedirs(output_dir, exist_ok=True)

    # From markdown mode
    if args.from_markdown:
        md_path = args.from_markdown
        if not os.path.isabs(md_path):
            md_path = str(project_root / md_path)
        print(f"Generating pin from markdown: {md_path}")
        result = generate_from_markdown(md_path, str(output_dir))
        if result:
            print(f"\nDone. Pin saved to {result}")
        return

    # CSV mode — require --type and --input
    if not args.type or not args.input:
        parser.error("Either --from-markdown or both --type and --input are required")

    input_path = args.input
    if not os.path.isabs(input_path):
        input_path = str(project_root / input_path)

    if not os.path.exists(input_path):
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    print(f"Reading: {input_path}")
    print(f"Output:  {output_dir}")
    print(f"Type:    {args.type}")
    print()

    with open(input_path, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    generated = 0
    for row in rows:
        # Skip empty rows
        if not any(v.strip() for v in row.values() if v):
            continue

        # Slug filter
        if args.slug:
            if args.type == "compare":
                row_slug = slugify(f"{row['tool_a']}-vs-{row['tool_b']}")
            else:
                row_slug = slugify(f"best-{row['category_name']}-for-{row['use_case']}")
            if row_slug != args.slug:
                continue

        if args.type == "compare":
            generate_comparison_pin(row, str(output_dir))
        elif args.type == "bestof":
            generate_bestof_pin(row, str(output_dir))
        generated += 1

    print(f"\nDone. Generated {generated} pin(s) in {output_dir}")


if __name__ == "__main__":
    main()
