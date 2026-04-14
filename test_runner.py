"""
test_runner.py — Run pipeline steps on a single test job
Usage:
    python test_runner.py
"""

import asyncio
from datetime import datetime
from agent.resume_builder import run_builder
from agent.linkedin_filler import run_filler


def test_pipeline():
    """Run full pipeline on the test job: test_ats_001"""
    start = datetime.now()
    print(f"\n[test] === pipeline started at {start.strftime('%Y-%m-%d %H:%M:%S')} ===")
    print("[test] Processing test job: test_ats_001 (Senior React Developer @ TechCorp)")

    # Step 1: Build PDFs (merged tailor + build)
    print("\n[test] step 1/2 — building PDF...")
    try:
        run_builder()
        print("[test] [OK] builder complete")
    except Exception as e:
        print(f"[test] [ERROR] builder error: {e}")
        return

    # Step 2: Apply
    print("\n[test] step 2/2 — applying to job...")
    try:
        asyncio.run(run_filler())
        print("[test] [OK] filler complete")
    except Exception as e:
        print(f"[test] [ERROR] filler error: {e}")
        return

    elapsed = (datetime.now() - start).seconds
    mins, secs = divmod(elapsed, 60)
    print(f"\n[test] === pipeline complete in {mins}m {secs}s ===\n")


if __name__ == "__main__":
    test_pipeline()
