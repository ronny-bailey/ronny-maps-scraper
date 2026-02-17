#!/usr/bin/env python3
"""
Google Maps Business Lead Scraper
Scrapes Google Maps for business leads, extracts contact info,
visits websites for emails, and saves to CSV.

Usage:
    python scraper.py --industry "dentists" --city "auckland"
    python scraper.py --industry "plumbers" --city "london" --max-results 100
    python scraper.py --industry "lawyers" --city "sydney" --visible
"""

import argparse
import csv
import re
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    print("ERROR: Playwright not installed. Run: pip3 install playwright && playwright install chromium")
    sys.exit(1)


EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
JUNK_EMAILS = {
    "sentry@", "webpack@", "noreply@", "no-reply@", "example@",
    "test@", "wixpress.com", "@sentry.", "@github.", "wix.com",
}

# Skip nationwide franchises / multi-branch corporates (customize per industry)
SKIP_FRANCHISES = [
    # Add franchise names to skip here, e.g.:
    # "big chain dental",
    # "national plumbing co",
]

# Industry-specific exclusion keywords — businesses that appear in Google Maps
# but are NOT the target industry
INDUSTRY_EXCLUSIONS = {
    "dentists": [
        "vasectomy", "eye institute", "eye clinic", "ophthalmol",
        "hospital", "medical centre", "medical center", "health board",
        "pharmacy", "chemist", "vet ", "veterinar", "animal",
        "beauty", "skin clinic", "dermatol", "cosmetic surgery",
        "radiology", "pathology", "lab ", "laboratory",
        "physiother", "osteopath", "chiropr", "podiatr",
        "mental health", "counsell", "psycholog",
        "school", "university", "college",
    ],
    "plumbers": [
        "dentist", "dental", "doctor", "medical", "hospital",
        "lawyer", "accountant", "real estate",
    ],
    "electricians": [
        "dentist", "dental", "doctor", "medical", "hospital",
        "lawyer", "accountant", "real estate",
    ],
    "lawyers": [
        "dentist", "dental", "plumber", "electrician",
        "doctor", "medical", "hospital",
    ],
}


def is_junk_email(email: str) -> bool:
    email_lower = email.lower()
    return any(j in email_lower for j in JUNK_EMAILS) or email_lower.endswith((".png", ".jpg"))


def extract_emails_from_text(text: str) -> list[str]:
    found = EMAIL_RE.findall(text)
    return [e for e in set(found) if not is_junk_email(e)]


def scrape_google_maps(industry: str, city: str, max_results: int = 50, visible: bool = False) -> list[dict]:
    """Scrape Google Maps for businesses matching industry + city."""
    query = f"{industry} {city}"
    leads = []
    seen = set()

    print(f"🔍 Searching: {query}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not visible, slow_mo=200)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        page = context.new_page()

        url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
        print(f"🌐 Opening: {url}")

        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
        except PWTimeout:
            print("⚠️  Page load timed out, continuing anyway...")

        # Accept cookies if prompted
        try:
            page.click('button:has-text("Accept all")', timeout=5000)
        except (PWTimeout, Exception):
            pass

        # Wait for results
        print("⏳ Waiting for results...")
        try:
            page.wait_for_selector('div[role="feed"], div[role="article"], a[href*="/maps/place/"]', timeout=30000)
        except PWTimeout:
            print("⚠️  Results panel not found, trying to continue...")

        # Scroll the results panel to load more
        print(f"📜 Scrolling to load results (target: {max_results})...")
        scroll_attempts = min(max_results * 3, 300)
        feed = page.query_selector('div[role="feed"]')

        for i in range(scroll_attempts):
            if feed:
                feed.evaluate("el => el.scrollTop = el.scrollHeight")
            else:
                page.keyboard.press("PageDown")
            time.sleep(0.5)

            if i % 20 == 0 and i > 0:
                current_listings = page.query_selector_all('a[href*="/maps/place/"]')
                print(f"  ... scrolled {i}x, found {len(current_listings)} listings so far")
                if len(current_listings) >= max_results:
                    print(f"  ✓ Reached target of {max_results}")
                    break

            # Check for "end of results"
            end_marker = page.query_selector('span:has-text("end of results"), p:has-text("end of results")')
            if end_marker:
                print("  ✓ Reached end of results")
                break

        # Get all listing links
        listings = page.query_selector_all('a[href*="/maps/place/"]')
        print(f"\n📋 Found {len(listings)} listings. Extracting details...")

        for idx, listing in enumerate(listings[:max_results]):
            try:
                listing.scroll_into_view_if_needed()
                listing.click()
                time.sleep(2)

                # Extract business name
                name_el = page.query_selector('h1.DUwDvf, h1.fontHeadlineLarge')
                name = name_el.inner_text().strip() if name_el else ""
                if not name:
                    continue

                # Extract phone
                phone = ""
                phone_el = page.query_selector('button[data-tooltip="Copy phone number"], button[aria-label*="Phone"]')
                if phone_el:
                    phone_text = phone_el.get_attribute("aria-label") or phone_el.inner_text()
                    phone_match = re.search(r"[\d\s\-\+\(\)]{7,}", phone_text)
                    phone = phone_match.group(0).strip() if phone_match else ""

                # Extract address
                address = ""
                addr_el = page.query_selector('button[data-item-id="address"], button[aria-label*="Address"]')
                if addr_el:
                    address = (addr_el.get_attribute("aria-label") or addr_el.inner_text()).replace("Address: ", "").strip()

                # Extract website URL
                website = ""
                web_el = page.query_selector('a[data-item-id="authority"], a[aria-label*="Website"]')
                if web_el:
                    website = web_el.get_attribute("href") or ""

                # Try to find email on the Maps page itself
                body_text = page.inner_text("body")
                emails = extract_emails_from_text(body_text)

                # If no email found and there's a website, visit it
                if not emails and website:
                    try:
                        web_page = context.new_page()
                        web_page.goto(website, timeout=15000, wait_until="domcontentloaded")
                        time.sleep(2)
                        web_text = web_page.inner_text("body")
                        emails = extract_emails_from_text(web_text)

                        # Also check common contact pages
                        if not emails:
                            for contact_path in ["/contact", "/contact-us", "/about", "/about-us"]:
                                try:
                                    contact_url = website.rstrip("/") + contact_path
                                    web_page.goto(contact_url, timeout=10000, wait_until="domcontentloaded")
                                    time.sleep(1)
                                    contact_text = web_page.inner_text("body")
                                    emails = extract_emails_from_text(contact_text)
                                    if emails:
                                        break
                                except Exception:
                                    continue

                        web_page.close()
                    except Exception as e:
                        print(f"    ⚠️  Could not visit website for {name}: {e}")
                        try:
                            web_page.close()
                        except Exception:
                            pass

                email = emails[0] if emails else ""

                # Skip franchises
                name_lower = name.lower()
                if any(skip in name_lower for skip in SKIP_FRANCHISES):
                    print(f"    ⏭️  Skipping franchise: {name}")
                    continue

                # Skip non-industry businesses
                industry_lower = industry.lower()
                exclusions = INDUSTRY_EXCLUSIONS.get(industry_lower, [])
                if any(excl in name_lower for excl in exclusions):
                    print(f"    ⏭️  Skipping non-{industry}: {name}")
                    continue

                # Also check address for hospital indicators
                addr_lower = address.lower()
                if any(x in addr_lower for x in ["hospital", "dhb", "health board"]):
                    if industry_lower == "dentists":
                        print(f"    ⏭️  Skipping hospital-based: {name}")
                        continue

                # Dedup by name + phone
                key = f"{name}|{phone}"
                if key in seen:
                    continue
                seen.add(key)

                lead = {
                    "name": name,
                    "website": website,
                    "email": email,
                    "phone": phone,
                    "address": address,
                    "source": "Google Maps",
                }
                leads.append(lead)
                status = "📧" if email else ("📞" if phone else "⚠️")
                print(f"  {status} [{idx+1}/{min(len(listings), max_results)}] {name} | {email or phone or 'no contact'}")

            except Exception as e:
                print(f"  ❌ Error on listing {idx+1}: {e}")
                continue

        browser.close()

    return leads


def save_leads(leads: list[dict], industry: str, city: str, output_dir: str):
    """Save leads to CSV files — one for email leads, one for phone-only."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    tag = f"{industry.replace(' ', '_')}_{city.replace(' ', '_')}"
    header = ["name", "website", "email", "phone", "address", "source"]

    full = [l for l in leads if l["email"]]
    cold = [l for l in leads if not l["email"] and l["phone"]]

    full_path = out / f"full_leads_{tag}.csv"
    cold_path = out / f"cold_call_{tag}.csv"

    for path, data in [(full_path, full), (cold_path, cold)]:
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(data)

    print(f"\n✅ DONE — {len(leads)} total businesses scraped")
    print(f"   📧 {len(full)} with email → {full_path}")
    print(f"   📞 {len(cold)} phone-only → {cold_path}")
    return full_path, cold_path


def main():
    parser = argparse.ArgumentParser(description="Scrape business leads from Google Maps")
    parser.add_argument("--industry", required=True, help="Business type (e.g. dentists, plumbers, lawyers)")
    parser.add_argument("--city", required=True, help="City name (e.g. auckland, london, sydney)")
    parser.add_argument("--max-results", type=int, default=50, help="Max businesses to scrape (default: 50)")
    parser.add_argument("--output-dir", default=str(Path.home() / "leads"), help="Output directory (default: ~/leads/)")
    parser.add_argument("--visible", action="store_true", help="Show the browser window (default: headless)")
    args = parser.parse_args()

    leads = scrape_google_maps(args.industry, args.city, args.max_results, args.visible)
    if leads:
        save_leads(leads, args.industry, args.city, args.output_dir)
    else:
        print("⚠️  No leads found. Try a different industry or city.")


if __name__ == "__main__":
    main()
