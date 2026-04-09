"""
Stage 1 debug script — opens LinkedIn job search in a visible browser.
No scraping. Just lets you verify the URL and filters look right.
Run: python -m agent.debug_search
"""
import asyncio
import json
import os
import urllib.parse

from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

COOKIES_FILE = os.path.join(os.path.dirname(__file__), "..", "linkedin_cookies.json")
PAUSE_SECONDS = 60  # how long to keep the browser open so you can inspect


async def main():
    # Load job titles from Supabase profile table
    from config.settings import load_job_titles
    titles = load_job_titles()
    if not titles:
        print("[debug] No job titles found in profile — add them in the dashboard first.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )

        # Load LinkedIn cookies so we appear logged in
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE) as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            print(f"[debug] Loaded {len(cookies)} LinkedIn cookies")
        else:
            print("[debug] WARNING: linkedin_cookies.json not found — will be logged out")

        page = await context.new_page()

        for title in titles:
            encoded = urllib.parse.quote(title)
            url = (
                f"https://www.linkedin.com/jobs/search/"
                f"?keywords={encoded}"
                f"&f_TPR=r3600"  # posted in last 1 hour
                f"&f_AL=true"     # LinkedIn Easy Apply only
                f"&f_E=2"         # entry level only
            )
            print(f"\n[debug] Opening search for: '{title}'")
            print(f"[debug] URL: {url}")

            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(3000)

            current_url = page.url
            print(f"[debug] Landed on: {current_url}")
            print(f"[debug] Keeping browser open for {PAUSE_SECONDS}s — check the filters and results...")
            await asyncio.sleep(PAUSE_SECONDS)

        await browser.close()
        print("\n[debug] Done.")


if __name__ == "__main__":
    asyncio.run(main())
