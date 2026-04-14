"""
scheduler.py — runs the full pipeline every 60 minutes:
  scrape (parallel per role) -> build PDF -> apply (sequential)

Usage:
    python scheduler.py
"""

import asyncio
import os
import signal
import sys
import threading
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
from supabase import create_client

from agent.scraper import scrape_for_role
from agent.resume_builder import run_builder
from agent.linkedin_filler import run_filler
from config.settings import ROLE_KEYWORDS, load_job_titles

load_dotenv()

_supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
_pipeline_lock = threading.Lock()  # prevents overlapping runs
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
    if not _pipeline_lock.acquire(blocking=False):
        print("[scheduler] pipeline already running — skipping")
        return
    try:
        _run_pipeline_inner()
    finally:
        _pipeline_lock.release()


def _run_pipeline_inner():
    start = datetime.now()
    print(f"\n[scheduler] === pipeline started at {start.strftime('%Y-%m-%d %H:%M:%S')} ===")

    # ── Step 1: Parallel scraping (one browser per role) ─────────────────────
    print("[scheduler] step 1/3 — scraping LinkedIn (parallel per role)...")
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

    if total_scraped == 0:
        print("[scheduler] no new jobs scraped — continuing to process any pending jobs in DB")

    # ── Step 2: Build PDFs (merged tailor + build) ────────────────────────────
    print("[scheduler] step 2/3 — building PDFs...")
    try:
        run_builder()
    except Exception as e:
        print(f"[scheduler] builder error: {e}")

    # ── Step 3: Apply (sequential — one at a time for LinkedIn safety) ────────
    print("[scheduler] step 3/3 — applying to jobs (sequential)...")
    try:
        asyncio.run(run_filler())
    except Exception as e:
        print(f"[scheduler] filler error: {e}")

    elapsed = (datetime.now() - start).seconds
    mins, secs = divmod(elapsed, 60)
    print(f"[scheduler] === pipeline complete in {mins}m {secs}s ===\n")


def check_dashboard_trigger():
    """Poll Supabase every 15s. If dashboard set pipeline_trigger=true, run pipeline."""
    if _pipeline_lock.locked():
        return  # pipeline already running — ignore
    try:
        row = _supabase.table("profile").select("pipeline_trigger").eq("id", 1).single().execute()
        if row.data and row.data.get("pipeline_trigger"):
            # Reset the flag immediately so double-clicks don't queue twice
            _supabase.table("profile").update({"pipeline_trigger": False}).eq("id", 1).execute()
            print("[scheduler] dashboard trigger received — starting pipeline...")
            threading.Thread(target=run_pipeline, daemon=True).start()
    except Exception as e:
        print(f"[scheduler] trigger poll error: {e}")


if __name__ == "__main__":
    print("[scheduler] starting — pipeline runs every 60 minutes, polls dashboard trigger every 15s")
    print("[scheduler] running first cycle immediately...")

    run_pipeline()

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_pipeline,
        trigger=IntervalTrigger(minutes=60),
        id="pipeline",
        name="Full job application pipeline",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        check_dashboard_trigger,
        trigger=IntervalTrigger(seconds=15),
        id="trigger_poll",
        name="Dashboard trigger poll",
        max_instances=1,
        coalesce=True,
    )

    print("[scheduler] next scheduled run in 60 minutes. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("[scheduler] stopped")
