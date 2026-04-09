import os
import re
import sys
import json
import random
import signal
import asyncio
import urllib.parse
from datetime import datetime, timezone

# Force UTF-8 output on Windows to prevent charmap encode errors
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
from playwright.async_api import async_playwright
from supabase import create_client
from dotenv import load_dotenv

from config.settings import (
    ROLE_KEYWORDS,
    MAX_APPLICANTS,
    load_job_titles,
)
from config.blacklist import COMPANY_BLACKLIST, JD_SIGNALS, TITLE_SENIORITY_KEYWORDS

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

COOKIES_FILE = os.path.join(os.path.dirname(__file__), "..", "linkedin_cookies.json")

_shutdown = False


def _handle_signal(*_):
    global _shutdown
    print("\n[scraper] shutdown signal received — finishing current job then stopping...")
    _shutdown = True


signal.signal(signal.SIGINT, _handle_signal)
if hasattr(signal, "SIGTERM"):
    signal.signal(signal.SIGTERM, _handle_signal)


# ---------------------------------------------------------------------------
# Cookie loader
# ---------------------------------------------------------------------------

async def _load_linkedin_cookies(context):
    if not os.path.exists(COOKIES_FILE):
        print("[scraper] WARNING: linkedin_cookies.json not found — will appear as guest")
        return False
    try:
        with open(COOKIES_FILE) as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)
        print(f"[scraper] loaded {len(cookies)} LinkedIn cookies")
        return True
    except Exception as e:
        print(f"[scraper] WARNING: could not load cookies: {e}")
        return False


# ---------------------------------------------------------------------------
# Step 1 — Scroll job card list
# ---------------------------------------------------------------------------

CARD_SEL = "[data-occludable-job-id], li[data-job-id], .job-card-container, .jobs-search-results__list-item"


async def _scroll_and_collect_cards(page) -> list:
    """Scroll the left-panel job list until no new cards appear. Returns list of indices."""
    # Wait for at least one job card to appear
    try:
        await page.wait_for_selector(CARD_SEL, timeout=20_000)
    except Exception:
        print("[scraper]   no job cards found on page (selector timed out)")
        return []

    prev_count = 0
    for _ in range(15):  # max 15 scroll attempts
        cards = page.locator(CARD_SEL)
        count = await cards.count()
        if count == prev_count and count > 0:
            break
        prev_count = count
        if count > 0:
            try:
                await cards.nth(count - 1).scroll_into_view_if_needed()
            except Exception:
                pass
            await page.wait_for_timeout(2000)

    final_count = await page.locator(CARD_SEL).count()
    print(f"[scraper]   collected {final_count} job cards after scrolling")
    return list(range(final_count))


# ---------------------------------------------------------------------------
# Step 2 — Click a card and extract all data from the right panel
# ---------------------------------------------------------------------------

async def _extract_card(page, card_idx: int, total: int) -> dict | None:
    """Click job card at index card_idx, extract all data from the detail panel."""
    card = page.locator(CARD_SEL).nth(card_idx)

    # Extract job_id from the card's link href before clicking
    job_id = None
    job_url = ""
    try:
        link = card.locator("a[href*='/jobs/view/']").first
        href = await link.get_attribute("href") or ""
        m = re.search(r'/jobs/view/(\d+)', href)
        if m:
            job_id = m.group(1)
    except Exception:
        pass

    if not job_id:
        try:
            job_id = (
                await card.get_attribute("data-job-id")
                or await card.get_attribute("data-occludable-job-id")
            )
        except Exception:
            pass

    if not job_id:
        print(f"[scraper]   card {card_idx+1}/{total}: SKIP — could not get job_id")
        return None

    job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"

    # Click the card to load detail panel
    try:
        await card.click()
        await page.wait_for_timeout(2500)
    except Exception as e:
        print(f"[scraper]   card {card_idx+1}/{total} (id={job_id}): SKIP — click failed: {e}")
        return None

    # --- Title ---
    title = ""
    for sel in [
        ".job-details-jobs-unified-top-card__job-title h1",
        ".jobs-unified-top-card__job-title h1",
        "h1.t-24",
        "h2.t-24",
    ]:
        el = page.locator(sel)
        if await el.count() > 0:
            title = (await el.first.inner_text()).strip()
            break

    # --- Company ---
    company = ""
    for sel in [
        ".job-details-jobs-unified-top-card__company-name a",
        ".job-details-jobs-unified-top-card__company-name",
        ".jobs-unified-top-card__company-name a",
        ".jobs-unified-top-card__company-name",
    ]:
        el = page.locator(sel)
        if await el.count() > 0:
            company = (await el.first.inner_text()).strip()
            break

    # --- Location + applicants (from metadata area) ---
    location = ""
    num_applicants = None
    try:
        meta_sels = [
            ".job-details-jobs-unified-top-card__primary-description-container",
            ".jobs-unified-top-card__subtitle-primary-grouping",
            ".jobs-unified-top-card__primary-description",
        ]
        full_meta = ""
        for sel in meta_sels:
            el = page.locator(sel)
            if await el.count() > 0:
                full_meta = (await el.first.inner_text()).strip()
                break

        # Meta text is like "San Francisco, CA · 32 applicants · 3 hours ago"
        parts = [p.strip() for p in full_meta.split("·")]
        for part in parts:
            if not location and (
                re.search(r',\s*[A-Z]{2}', part)
                or "remote" in part.lower()
                or "united states" in part.lower()
                or "anywhere" in part.lower()
            ):
                location = part.strip()
            app_match = re.search(r'([\d,]+)\s+applicant', part, re.IGNORECASE)
            if app_match and num_applicants is None:
                num_applicants = int(app_match.group(1).replace(",", ""))
    except Exception:
        pass

    # --- No longer accepting check ---
    try:
        detail = page.locator(".jobs-details__main-content, .jobs-search__job-details, .scaffold-layout__detail")
        if await detail.count() > 0:
            body = (await detail.first.inner_text()).lower()
            if "no longer accepting" in body:
                print(f"[scraper]   card {card_idx+1}/{total} SKIP [{company}] {title} — no longer accepting")
                return None
    except Exception:
        pass

    # --- Easy Apply button check ---
    ea_selectors = [
        "[aria-label*='Easy Apply']",
        "[aria-label*='LinkedIn Apply']",
        "button:has-text('Easy Apply')",
        "button:has-text('LinkedIn Apply')",
        ".jobs-apply-button",
    ]
    has_easy_apply = False
    for sel in ea_selectors:
        if await page.locator(sel).count() > 0:
            has_easy_apply = True
            break

    if not has_easy_apply:
        print(f"[scraper]   card {card_idx+1}/{total} SKIP [{company}] {title} — no Easy Apply button")
        return None

    # --- Full JD ---
    jd = ""
    for sel in [
        ".jobs-description__content",
        ".jobs-description",
        ".description__text",
        "[class*='jobs-description']",
    ]:
        el = page.locator(sel)
        if await el.count() > 0:
            try:
                more_btn = page.locator("button.show-more-less-html__button--more")
                if await more_btn.count() > 0:
                    await page.evaluate(
                        "document.querySelector('button.show-more-less-html__button--more')?.click()"
                    )
                    await page.wait_for_timeout(500)
            except Exception:
                pass
            jd = (await el.first.inner_text()).strip()
            break

    if not jd:
        print(f"[scraper]   card {card_idx+1}/{total} SKIP [{company}] {title} — no JD text")
        return None

    print(
        f"[scraper]   card {card_idx+1}/{total} PASS  [{company}] {title}"
        f" | loc={location} | applicants={num_applicants} | JD={len(jd)}c"
    )
    return {
        "id":              job_id,
        "job_id":          job_id,
        "title":           title,
        "company":         company,
        "location":        location,
        "job_url":         job_url,
        "num_applicants":  num_applicants,
        "is_easy_apply":   True,
        "description":     "",
        "full_description": jd,
        "confirmed_easy_apply": True,
    }


# ---------------------------------------------------------------------------
# Step 3 — Search one title: navigate → scroll → extract all cards
# ---------------------------------------------------------------------------

async def _search_title(title: str, page) -> list[dict]:
    encoded = urllib.parse.quote(title)
    url = (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={encoded}"
        f"&f_TPR=r86400"  # last 24 hours
        f"&f_AL=true"     # Easy Apply only
        f"&f_E=2"         # entry level
    )
    print(f"\n[scraper] Searching: '{title}'")
    print(f"[scraper] URL: {url}")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(5000)  # give React/JS time to render job cards
    except Exception as e:
        print(f"[scraper] ERROR: failed to load search page: {e}")
        return []

    # Login wall check
    if any(x in page.url for x in ("login", "authwall", "signup", "checkpoint")):
        print("[scraper] ERROR: redirected to login — cookies may be expired")
        return []

    card_indices = await _scroll_and_collect_cards(page)
    if not card_indices:
        print(f"[scraper] No job cards found for '{title}'")
        return []

    rows = []
    for idx in card_indices:
        if _shutdown:
            print("[scraper] Stopping early — shutdown requested")
            break
        try:
            row = await _extract_card(page, idx, len(card_indices))
            if row:
                rows.append(row)
        except Exception as e:
            print(f"[scraper]   card {idx+1}: unexpected error — {e}".encode("utf-8", errors="replace").decode("utf-8"))
        await asyncio.sleep(random.uniform(1.5, 3.0))

    print(f"[scraper] '{title}' -> {len(rows)} jobs passed card-level checks")
    return rows


# ---------------------------------------------------------------------------
# Filter
# ---------------------------------------------------------------------------

def is_agency(company: str, description: str) -> bool:
    company_lower = (company or "").lower()
    desc_lower = (description or "").lower()
    for term in COMPANY_BLACKLIST:
        if term in company_lower:
            return True
    for signal in JD_SIGNALS:
        if signal in desc_lower:
            return True
    return False


def filter_jobs(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    before = len(df)
    print(f"\n[scraper] --- filter pass on {before} jobs ---")

    US_STATES = {
        "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
        "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
        "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
        "VA","WA","WV","WI","WY","DC",
    }
    US_KEYWORDS = {"united states", "u.s.", "usa", "remote", "anywhere"}

    def is_non_us(location: str) -> bool:
        loc = (location or "").strip()
        if not loc:
            return False
        loc_lower = loc.lower()
        if any(kw in loc_lower for kw in US_KEYWORDS):
            return False
        if any(f", {st}" in loc for st in US_STATES):
            return False
        if any(st in loc for st in ["Washington", "California", "Texas", "New York",
                                     "Florida", "Illinois", "Virginia", "Maryland",
                                     "Georgia", "Pennsylvania", "Ohio", "Michigan"]):
            return False
        return True

    def is_senior(title: str) -> bool:
        t = (title or "").lower()
        return any(kw in t for kw in TITLE_SENIORITY_KEYWORDS)

    kept = []
    for _, row in df.iterrows():
        title      = str(row.get("title", ""))
        company    = str(row.get("company", ""))
        location   = str(row.get("location", ""))
        applicants = row.get("num_applicants")
        jd         = str(row.get("full_description", ""))
        tag        = f"  [{company}] {title}"

        # Applicant cap
        if pd.notna(applicants) and int(applicants) >= MAX_APPLICANTS:
            print(f"[scraper] SKIP {tag} — too many applicants ({int(applicants)})")
            continue

        # Agency / blacklist (company name + full JD)
        agency_reason = None
        for term in COMPANY_BLACKLIST:
            if term in company.lower():
                agency_reason = f"company contains '{term}'"
                break
        if agency_reason is None:
            for sig in JD_SIGNALS:
                if sig in jd.lower():
                    agency_reason = f"JD signal '{sig}'"
                    break
        if agency_reason:
            print(f"[scraper] SKIP {tag} — {agency_reason}")
            continue

        # Seniority
        if is_senior(title):
            kw = next((k for k in TITLE_SENIORITY_KEYWORDS if k in title.lower()), "?")
            print(f"[scraper] SKIP {tag} — seniority '{kw}'")
            continue

        # US only
        if is_non_us(location):
            print(f"[scraper] SKIP {tag} — non-US location '{location}'")
            continue

        print(f"[scraper] PASS {tag} | loc={location} | applicants={applicants}")
        kept.append(row)

    result = pd.DataFrame(kept).reset_index(drop=True)
    print(f"[scraper] filter: {before} -> {len(result)} jobs passed\n")
    return result


# ---------------------------------------------------------------------------
# Deduplicate
# ---------------------------------------------------------------------------

def detect_role(title: str, description: str) -> str:
    text = (title + " " + description).lower()
    for role, keywords in ROLE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return role
    return "software_developer"


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    df = df.drop_duplicates(subset=["job_url"]).reset_index(drop=True)

    existing_job_ids = {
        r["job_id"]
        for r in supabase.table("jobs").select("job_id").execute().data
    }
    applied_job_ids = {
        r["job_id"]
        for r in supabase.table("applications").select("job_id").execute().data
    }
    skip_ids = existing_job_ids | applied_job_ids

    df = df[~df["job_id"].isin(skip_ids)].reset_index(drop=True)
    print(f"[scraper] dedup: {before} -> {len(df)} new jobs")
    return df


# ---------------------------------------------------------------------------
# Save to Supabase
# ---------------------------------------------------------------------------

def save_jobs(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    inserted = 0
    for _, row in df.iterrows():
        title = str(row.get("title", ""))
        jd    = str(row.get("full_description", ""))
        record = {
            "job_id":         str(row["job_id"])[:255],
            "title":          title,
            "company":        str(row.get("company", "")),
            "location":       str(row.get("location", "")),
            "portal":         "linkedin",
            "jd_text":        jd,
            "job_url":        str(row.get("job_url", "")),
            "easy_apply":     True,
            "num_applicants": (
                int(row["num_applicants"])
                if pd.notna(row.get("num_applicants"))
                else None
            ),
            "detected_role":  detect_role(title, jd),
        }
        try:
            supabase.table("jobs").insert(record).execute()
            inserted += 1
        except Exception as e:
            print(f"[scraper] insert failed for {record['job_url']}: {e}")
    print(f"[scraper] saved {inserted}/{len(df)} jobs to Supabase")
    return inserted


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_scraper(test_limit: int = None):
    print(f"\n[scraper] === run started at {datetime.now(timezone.utc).isoformat()} ===")

    titles = load_job_titles()
    if not titles:
        print("[scraper] No job titles configured — add them in the dashboard Profile section")
        return

    all_rows = []
    seen_ids = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=150)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )
        await _load_linkedin_cookies(context)
        page = await context.new_page()

        try:
            for title in titles:
                if _shutdown:
                    break
                rows = await _search_title(title, page)
                for row in rows:
                    if row["job_id"] not in seen_ids:
                        seen_ids.add(row["job_id"])
                        all_rows.append(row)
        finally:
            await browser.close()
            print("[scraper] browser closed")

    if not all_rows:
        print("[scraper] no jobs found — exiting")
        return

    df = pd.DataFrame(all_rows)
    print(f"\n[scraper] total unique jobs from search: {len(df)}")

    df = filter_jobs(df)
    if df.empty:
        print("[scraper] all jobs filtered out — exiting")
        return

    df = deduplicate(df)
    if df.empty:
        print("[scraper] all jobs already seen — exiting")
        return

    if test_limit:
        df = df.head(test_limit)
        print(f"[scraper] TEST MODE: capped at {test_limit} jobs")

    save_jobs(df)
    print(f"[scraper] === run complete ===\n")


async def scrape_for_role(role: str, titles: list, test_limit: int = None) -> list:
    """
    Scrape LinkedIn for one role using its own isolated browser context.
    Designed to be run concurrently with other roles via asyncio.gather().
    Returns list of job dicts saved to Supabase.
    """
    if not titles:
        print(f"[scraper:{role}] no titles configured — skipping")
        return []

    print(f"\n[scraper:{role}] === starting — titles: {titles} ===")
    all_rows = []
    seen_ids = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=150)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )
        await _load_linkedin_cookies(context)
        page = await context.new_page()

        try:
            for title in titles:
                if _shutdown:
                    break
                rows = await _search_title(title, page)
                for row in rows:
                    if row["job_id"] not in seen_ids:
                        seen_ids.add(row["job_id"])
                        all_rows.append(row)
        finally:
            await browser.close()
            print(f"[scraper:{role}] browser closed")

    if not all_rows:
        print(f"[scraper:{role}] no jobs found")
        return []

    df = pd.DataFrame(all_rows)
    df = filter_jobs(df)
    if df.empty:
        print(f"[scraper:{role}] all jobs filtered out")
        return []

    df = deduplicate(df)
    if df.empty:
        print(f"[scraper:{role}] all jobs already seen")
        return []

    if test_limit:
        df = df.head(test_limit)
        print(f"[scraper:{role}] TEST MODE: capped at {test_limit} job(s)")

    save_jobs(df)
    print(f"[scraper:{role}] === done — {len(df)} new jobs saved ===")
    return df.to_dict("records")


if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    asyncio.run(run_scraper(test_limit=limit))
