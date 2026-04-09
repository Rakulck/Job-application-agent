"""
retry_application.py — Handle retry of failed LinkedIn applications with updated answers.

This script calls run_filler for a specific job_id. Since run_filler automatically
loads screening answers from Supabase profile table, users should update their answers
via the dashboard, then click "Retry" on a failed application.

Usage:
    python -m agent.retry_application --job-id <job_id>
"""

import os
import sys
import asyncio
import json
import argparse

from supabase import create_client
from dotenv import load_dotenv

from agent.linkedin_filler import run_filler

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


async def retry_application(job_id: str) -> dict:
    """
    Retry a failed LinkedIn application.
    run_filler will automatically load the latest screening answers from Supabase.

    Args:
        job_id: The job ID to retry

    Returns:
        dict with success status
    """
    try:
        print(f"[retry] Starting retry for job_id={job_id}")

        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

        # Verify job exists
        job_response = supabase.table("jobs").select("*").eq("job_id", job_id).execute()
        if not job_response.data or len(job_response.data) == 0:
            return {"success": False, "error": f"Job {job_id} not found"}

        job = job_response.data[0]
        print(f"[retry] Job: {job['company']} — {job['title']}")

        # Verify resume exists
        resume_response = (
            supabase.table("resumes")
            .select("pdf_url")
            .eq("job_id", job_id)
            .order("created_at", {"ascending": False})
            .limit(1)
            .execute()
        )
        if not resume_response.data:
            return {"success": False, "error": f"No resume found for job {job_id}"}

        # Call run_filler — it will auto-load answers from Supabase profile
        print(f"[retry] Calling linkedin_filler...")
        await run_filler(job_id=job_id)

        return {"success": True, "job_id": job_id}

    except Exception as e:
        print(f"[retry] Error: {str(e)}", file=sys.stderr)
        return {"success": False, "error": str(e)}


async def main():
    parser = argparse.ArgumentParser(description="Retry a failed LinkedIn application")
    parser.add_argument("--job-id", required=True, help="Job ID to retry")
    args = parser.parse_args()

    result = await retry_application(args.job_id)
    print(json.dumps(result))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
