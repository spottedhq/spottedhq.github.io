# SpottedHQ — Site Operations Guide

## Quick Start

```bash
cd ~/.openclaw/modules/content-affiliate/spottedhq

# Preview locally
hugo server --buildDrafts

# Build for production
hugo --minify
```

## Adding Content

### New comparison page (one-off)
```bash
hugo new compare/tool-a-vs-tool-b.md --kind comparison
# Then edit the generated file
```

### Bulk comparison pages (pSEO)
1. Add rows to `data/comparisons.csv` or `data/comparisons-extended.csv`
2. Run: `python3 scripts/generate-comparisons.py --input data/comparisons.csv --output content/compare/`
3. Fill in the `<!-- EXPAND -->` sections with real data

### Bulk "Best X for Y" pages (pSEO)
1. Add rows to `data/best-of.csv`
2. Run: `python3 scripts/generate-best-of.py --input data/best-of.csv --output content/best/`
3. Fill in tool rankings and details

### New review page
```bash
hugo new compare/tool-name-review.md --kind review
```

## Monitoring & Traffic

### Reddit/Quora question monitor
```bash
python3 scripts/monitor-questions.py              # last 24h, score >= 3
python3 scripts/monitor-questions.py --hours 48    # last 48h
python3 scripts/monitor-questions.py --min-score 5 # higher threshold
# Output: data/questions-YYYY-MM-DD.json
```

### Pinterest pin generator
```bash
python3 scripts/generate-pins.py --type compare --input data/comparisons.csv --output static/pins/
python3 scripts/generate-pins.py --type best-of --input data/best-of.csv --output static/pins/
```

## Email (Beehiiv)

Templates in `email-templates/`:
- `welcome-sequence/` — 5-email onboarding series
- `weekly-newsletter-template.md` — reusable weekly format
- `re-engagement/` — 2-email win-back series

Copy into Beehiiv when account is set up.

## Deployment

Push to `main` branch → GitHub Actions auto-deploys to GitHub Pages.

## Affiliate Links

Replace `#` and `AFFILIATE_LINK` placeholders in content with real links after signing up for programs.

Key programs to join:
- PartnerStack (aggregator for SaaS programs)
- Individual: Notion, HubSpot, Beehiiv, Leadpages, Canva, etc.
- ClickBank (digital products)
