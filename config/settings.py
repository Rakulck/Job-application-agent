import os
from dotenv import load_dotenv

load_dotenv()

ROLE_KEYWORDS = {
    "frontend_developer": ["frontend developer", "front-end developer", "frontend dev"],
    "software_developer": ["software developer", "software engineer", "software dev"],
    "web_developer": ["web developer", "web dev", "web engineer"],
    "react_developer": ["react developer", "react dev", "react engineer", "react js developer"],
    "fullstack_developer": ["full stack developer", "fullstack developer", "full-stack developer", "full stack engineer"],
    "mobile_developer": ["mobile developer", "ios developer", "android developer", "react native developer", "flutter developer"],
}

HOURS_OLD = 1               # maps to f_TPR=r3600 (last 1 hour)
RESULTS_PER_SEARCH = 50     # LinkedIn shows 25/page — this = max 2 pages
MAX_APPLICANTS = 100
LINKEDIN_EXPERIENCE_LEVEL = [2]  # 2 = Entry level (LinkedIn f_E filter)
APPLY_DELAY_MIN = 8   # seconds between applications
APPLY_DELAY_MAX = 15
MIN_ATS_SCORE = 90    # score base first; skip tailoring if >= 90


def load_job_titles() -> list:
    """Fetch job_titles from Supabase profile table. Returns empty list if none set."""
    try:
        from supabase import create_client
        client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        row = client.table("profile").select("job_titles").eq("id", 1).single().execute()
        titles = row.data.get("job_titles") or []
        if not titles:
            print("[settings] no job titles found in profile — add roles in the dashboard Profile section")
        return titles
    except Exception as e:
        print(f"[settings] could not load job titles from profile: {e}")
        return []
