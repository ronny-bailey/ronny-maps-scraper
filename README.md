# Google Maps Lead Scraper

Open-source Google Maps scraper for lead generation. Extracts business names, phone numbers, emails, addresses, and websites — then visits each business's website to find contact emails on `/contact`, `/about`, and other pages.

Built with [Playwright](https://playwright.dev/) for reliable browser automation. No API keys required.

## What It Does

1. Searches Google Maps for `{industry} {city}` (e.g. "dentists auckland")
2. Scrolls through all results to load the full list
3. Clicks each listing to extract: name, phone, address, website
4. Visits each business's website + common contact pages to find email addresses
5. Filters out junk emails, franchises, and off-industry results
6. Saves to CSV — one file for email leads, one for phone-only leads

## Installation

```bash
# Clone
git clone https://github.com/ronny-bailey/ronny-maps-scraper.git
cd ronny-maps-scraper

# Install dependencies
pip install playwright
playwright install chromium
```

## Usage

```bash
# Basic usage
python scraper.py --industry "dentists" --city "auckland"

# More results
python scraper.py --industry "plumbers" --city "london" --max-results 100

# Show the browser (useful for debugging)
python scraper.py --industry "lawyers" --city "sydney" --visible

# Custom output directory
python scraper.py --industry "electricians" --city "melbourne" --output-dir ./my-leads
```

## Output

Two CSV files per run:

| File | Contains |
|------|----------|
| `full_leads_{industry}_{city}.csv` | Leads with email addresses |
| `cold_call_{industry}_{city}.csv` | Phone-only leads (no email found) |

Each row includes: `name`, `website`, `email`, `phone`, `address`, `source`

## Example Output

```
🔍 Searching: dentists auckland
🌐 Opening: https://www.google.com/maps/search/dentists+auckland
⏳ Waiting for results...
📜 Scrolling to load results (target: 50)...
  ... scrolled 20x, found 34 listings so far
  ... scrolled 40x, found 48 listings so far
  ✓ Reached target of 50

📋 Found 50 listings. Extracting details...
  📧 [1/50] Smile Dental Centre | info@smiledental.co.nz
  📧 [2/50] Auckland Family Dentist | hello@akfamilydentist.co.nz
  📞 [3/50] City Dental | 09 123 4567
  ...

✅ DONE — 47 total businesses scraped
   📧 31 with email → ~/leads/full_leads_dentists_auckland.csv
   📞 16 phone-only → ~/leads/cold_call_dentists_auckland.csv
```

## Customization

### Skip Franchises
Add franchise names to the `SKIP_FRANCHISES` list in `scraper.py`:
```python
SKIP_FRANCHISES = [
    "big chain dental",
    "national plumbing co",
]
```

### Industry Filters
Add exclusion keywords per industry in `INDUSTRY_EXCLUSIONS` to filter out irrelevant Google Maps results (e.g. hospitals appearing in dentist searches):
```python
INDUSTRY_EXCLUSIONS = {
    "dentists": ["hospital", "pharmacy", "veterinar", ...],
    "plumbers": ["dentist", "lawyer", ...],
}
```

## How It Works

- **No API keys** — Uses Playwright to automate a real Chromium browser
- **Smart email extraction** — Regex-based email finder with junk filter (skips webpack@, sentry@, noreply@, etc.)
- **Deep contact search** — If no email on the Maps listing, visits the business website + `/contact`, `/contact-us`, `/about`, `/about-us` pages
- **Deduplication** — Prevents duplicate entries by name + phone
- **Rate limiting** — Built-in delays to avoid being blocked

## Requirements

- Python 3.9+
- Playwright (`pip install playwright`)
- Chromium (`playwright install chromium`)

## Limitations

- Google Maps may change their HTML structure — selectors may need updating
- Heavy scraping may trigger CAPTCHAs — use `--visible` to solve manually if needed
- Some businesses don't list emails anywhere online — these become phone-only leads
- Respects Google's rate limits with built-in delays

## License

MIT — do whatever you want with it.

## Built By

[Ronny](https://ronny.co.nz) — AI-powered lead generation for small businesses.
