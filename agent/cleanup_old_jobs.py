#!/usr/bin/env python3
"""
Cleanup script: Remove jobs scraped before today from Supabase.
Cascades delete to applications and resumes tables.
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

# Force UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_KEY not found in .env")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def cleanup_old_jobs():
    """Delete jobs created before today."""
    today = datetime.now().date().isoformat()
    print(f"[cleanup] Removing jobs created before {today}...")

    try:
        # Get list of job IDs to delete (handle UTC timezone)
        # Use format: YYYY-MM-DDTHH:MM:SS+00:00 for UTC comparison
        cutoff_time = f"{today}T00:00:00+00:00"
        jobs_response = supabase.table("jobs").select("job_id").lt("created_at", cutoff_time).execute()
        job_ids = [j["job_id"] for j in jobs_response.data]
        count = len(job_ids)

        if count == 0:
            print(f"[cleanup] No jobs found before {today}")
            return 0

        print(f"[cleanup] Found {count} jobs to delete")

        # Delete in order of dependencies: resumes → applications → jobs
        print(f"[cleanup] Deleting resumes...")
        supabase.table("resumes").delete().in_("job_id", job_ids).execute()

        print(f"[cleanup] Deleting applications...")
        supabase.table("applications").delete().in_("job_id", job_ids).execute()

        print(f"[cleanup] Deleting jobs...")
        supabase.table("jobs").delete().in_("job_id", job_ids).execute()

        print(f"[cleanup] [OK] Deleted {count} old jobs and related records")
        return count

    except Exception as e:
        print(f"[cleanup] ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    count = cleanup_old_jobs()
    if count == 0:
        print(f"[cleanup] No old jobs to remove. Database is clean.")
    else:
        print(f"[cleanup] Done. Removed {count} old jobs and all related records (applications, resumes).")
