"""
scheduler.py — runs the full pipeline every 60 minutes:
  scrape (parallel per role) -> tailor -> build PDF -> apply (sequential)

Usage:
    python scheduler.py
"""

import asyncio
import signal
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from agent.scraper import scrape_for_role
from agent.tailor import run_tailor
from agent.resume_builder import run_builder
from agent.linkedin_filler import run_filler
from config.settings import ROLE_KEYWORDS, load_job_titles

_shutdown = False


def _handle_signal(sig, frame):
    global _shutdown
    print("\n[scheduler] shutdown signal received — stopping after current cycle")
    _shutdown = True
    sys.exit(0)


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ---------------------------------------------------------------------------
# Role grouping helper
# ---------------------------------------------------------------------------

def group_titles_by_role(titles: list) -> dict:
    """Split job titles into role buckets using ROLE_KEYWORDS."""
    groups = {
        "frontend_developer": [],
        "software_developer": [],
        "web_developer": [],
        "react_developer": [],
        "fullstack_developer": [],
    }
    for title in titles:
        t = title.lower()
        if any(kw in t for kw in ROLE_KEYWORDS.get("react_developer", [])):
            groups["react_developer"].append(title)
        elif any(kw in t for kw in ROLE_KEYWORDS.get("frontend_developer", [])):
            groups["frontend_developer"].append(title)
        elif any(kw in t for kw in ROLE_KEYWORDS.get("web_developer", [])):
            groups["web_developer"].append(title)
        elif any(kw in t for kw in ROLE_KEYWORDS.get("fullstack_developer", [])):
            groups["fullstack_developer"].append(title)
        else:
            groups["software_developer"].append(title)
    return groups


# ---------------------------------------------------------------------------
# Parallel scrape step
# ---------------------------------------------------------------------------

async def _scrape_all_roles(role_groups: dict) -> dict:
    """Run one scraper per role concurrently. Returns per-role job counts."""
    tasks = {
        role: scrape_for_role(role, titles)
        for role, titles in role_groups.items()
        if titles  # skip empty buckets
    }

    if not tasks:
        print("[scheduler] no role groups to scrape")
        return {}

    print(f"[scheduler] launching {len(tasks)} parallel scrapers: {list(tasks.keys())}")

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    counts = {}
    for role, result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            print(f"[scheduler] scraper:{role} ERROR — {result}")
            counts[role] = 0
        else:
            counts[role] = len(result) if result else 0
            print(f"[scheduler] scraper:{role} done — {counts[role]} new jobs saved")

    return counts


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline():
    start = datetime.now()
    print(f"\n[scheduler] === pipeline started at {start.strftime('%Y-%m-%d %H:%M:%S')} ===")

    # ── Step 1: Parallel scraping (one browser per role) ─────────────────────
    print("[scheduler] step 1/4 — scraping LinkedIn (parallel per role)...")
    total_scraped = 0
    try:
        titles = load_job_titles()
        if titles:
            role_groups = group_titles_by_role(titles)
            print(f"[scheduler] role groups: { {r: len(t) for r, t in role_groups.items()} }")
            counts = asyncio.run(_scrape_all_roles(role_groups))
            total_scraped = sum(counts.values())
            print(f"[scheduler] scraping complete — {total_scraped} new jobs total {counts}")
        else:
            print("[scheduler] no job titles configured — skipping scrape")
    except Exception as e:
        print(f"[scheduler] scraper error: {e}")

    # ── Skip remaining steps if no jobs were scraped ────────────────────────────
    if total_scraped == 0:
        print("[scheduler] no new jobs found — skipping tailor/builder/filler stages")
        elapsed = (datetime.now() - start).seconds
        mins, secs = divmod(elapsed, 60)
        print(f"[scheduler] === pipeline complete in {mins}m {secs}s ===\n")
        return

    # ── Step 2: Tailor resumes with Groq ─────────────────────────────────────
    print("[scheduler] step 2/4 — tailoring resumes...")
    try:
        run_tailor()
    except Exception as e:
        print(f"[scheduler] tailor error: {e}")

    # ── Step 3: Build PDFs ────────────────────────────────────────────────────
    print("[scheduler] step 3/4 — building PDFs...")
    try:
        run_builder()
    except Exception as e:
        print(f"[scheduler] builder error: {e}")

    # ── Step 4: Apply (sequential — one at a time for LinkedIn safety) ────────
    print("[scheduler] step 4/4 — applying to jobs (sequential)...")
    try:
        asyncio.run(run_filler())
    except Exception as e:
        print(f"[scheduler] filler error: {e}")

    elapsed = (datetime.now() - start).seconds
    mins, secs = divmod(elapsed, 60)
    print(f"[scheduler] === pipeline complete in {mins}m {secs}s ===\n")


if __name__ == "__main__":
    print("[scheduler] starting — pipeline runs every 60 minutes")
    print("[scheduler] running first cycle immediately...")

    run_pipeline()

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_pipeline,
        trigger=IntervalTrigger(minutes=60),
        id="pipeline",
        name="Full job application pipeline",
        max_instances=1,   # never overlap runs
        coalesce=True,     # skip missed runs if still running
    )

    print("[scheduler] next run in 60 minutes. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("[scheduler] stopped")
