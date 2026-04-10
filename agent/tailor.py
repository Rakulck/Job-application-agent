import os
import json
from groq import Groq
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

groq = Groq(api_key=GROQ_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

RESUMES_DIR = os.path.join(os.path.dirname(__file__), "..", "resumes")

# ---------------------------------------------------------------------------
# Location mapping — snap job location to nearest preferred city
# ---------------------------------------------------------------------------

PREFERRED_CITIES = [
    ("Seattle, WA",       47.6062, -122.3321),
    ("San Francisco, CA", 37.7749, -122.4194),
    ("Washington, DC",    38.9072,  -77.0369),
    ("New York, NY",      40.7128,  -74.0060),
    ("Dallas, TX",        32.7767,  -96.7970),
    ("Houston, TX",       29.7604,  -95.3698),
    ("Herndon, VA",       38.9696,  -77.3861),
]

# Keyword → preferred city (checked in order; first match wins)
LOCATION_KEYWORDS = {
    # Seattle metro
    "seattle":        "Seattle, WA",
    "bellevue":       "Seattle, WA",
    "redmond":        "Seattle, WA",
    "tacoma":         "Seattle, WA",
    "kirkland":       "Seattle, WA",
    "bothell":        "Seattle, WA",
    # SF / Bay Area
    "san francisco":  "San Francisco, CA",
    "bay area":       "San Francisco, CA",
    "san jose":       "San Francisco, CA",
    "oakland":        "San Francisco, CA",
    "palo alto":      "San Francisco, CA",
    "mountain view":  "San Francisco, CA",
    "sunnyvale":      "San Francisco, CA",
    "santa clara":    "San Francisco, CA",
    "silicon valley": "San Francisco, CA",
    # Herndon / NoVA (before generic DC so these win)
    "herndon":        "Herndon, VA",
    "reston":         "Herndon, VA",
    "mclean":         "Herndon, VA",
    "fairfax":        "Herndon, VA",
    "arlington":      "Herndon, VA",
    "tysons":         "Herndon, VA",
    "chantilly":      "Herndon, VA",
    "ashburn":        "Herndon, VA",
    # DC metro
    "washington, dc": "Washington, DC",
    "washington dc":  "Washington, DC",
    ", dc":           "Washington, DC",
    "maryland":       "Washington, DC",
    "bethesda":       "Washington, DC",
    "silver spring":  "Washington, DC",
    # NYC metro
    "new york":       "New York, NY",
    "nyc":            "New York, NY",
    "brooklyn":       "New York, NY",
    "manhattan":      "New York, NY",
    "queens":         "New York, NY",
    "jersey city":    "New York, NY",
    "hoboken":        "New York, NY",
    "newark":         "New York, NY",
    # Dallas metro
    "dallas":         "Dallas, TX",
    "fort worth":     "Dallas, TX",
    "plano":          "Dallas, TX",
    "irving":         "Dallas, TX",
    "frisco":         "Dallas, TX",
    "richardson":     "Dallas, TX",
    # Houston metro
    "houston":        "Houston, TX",
    "sugar land":     "Houston, TX",
    "the woodlands":  "Houston, TX",
    "katy":           "Houston, TX",
}

_REMOTE_SIGNALS = {"remote", "united states", "us", "anywhere", "nationwide", ""}


def _haversine(lat1, lon1, lat2, lon2):
    import math
    R = 3958.8  # miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def map_to_preferred_location(job_location: str) -> str:
    """Snap job_location string to the nearest city in PREFERRED_CITIES."""
    loc = (job_location or "").strip().lower()

    # Remote / empty → default
    if loc in _REMOTE_SIGNALS or "remote" in loc:
        return "Seattle, WA"

    # Keyword match (fast path, no network)
    for keyword, city in LOCATION_KEYWORDS.items():
        if keyword in loc:
            return city

    # Geocode fallback
    try:
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderTimedOut
        geolocator = Nominatim(user_agent="job_application_agent", timeout=5)
        geo = geolocator.geocode(job_location)
        if geo:
            nearest = min(PREFERRED_CITIES, key=lambda c: _haversine(geo.latitude, geo.longitude, c[1], c[2]))
            return nearest[0]
    except Exception:
        pass

    return "Seattle, WA"


# ---------------------------------------------------------------------------
# Load base resume
# ---------------------------------------------------------------------------

def load_base_resume(role: str) -> dict:
    """Load the base resume JSON for the given role (frontend/fullstack/mobile).
    Checks profile.base_resume first; falls back to local file.
    Overlays personal_info from the Supabase profile table if available."""
    base = None

    # Prefer resume uploaded via dashboard
    try:
        row = supabase.table("profile").select("base_resume, role_resumes, personal_info").eq("id", 1).single().execute()
        role_resumes = row.data.get("role_resumes") or {}
        if role_resumes.get(role):
            base = role_resumes[role]
            print(f"[tailor] using role-specific resume for '{role}' from Supabase profile")
        elif row.data.get("base_resume"):
            base = row.data["base_resume"]
            print(f"[tailor] using base resume from Supabase profile")
        personal = row.data.get("personal_info") or {}
    except Exception as e:
        print(f"[tailor] could not load profile from Supabase: {e}")
        personal = {}

    # Fall back to local JSON file
    if base is None:
        path = os.path.join(RESUMES_DIR, f"base_{role}.json")
        with open(path, "r", encoding="utf-8") as f:
            base = json.load(f)

    # Overlay personal_info fields
    for field in ["name", "email", "phone", "linkedin", "portfolio", "github", "location"]:
        if personal.get(field):
            base[field] = personal[field]

    return base


# ---------------------------------------------------------------------------
# Groq tailoring
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a professional resume writer. Your job is to rewrite resume content to match a job description.

STRICT RULES:
- Only rewrite: summary, bullet points under each experience, and the skills list
- Do NOT change: name, email, phone, linkedin, portfolio, github, location, company names, job titles, dates, education
- Do NOT add formatting instructions, markdown, or symbols
- Do NOT invent experience or skills the candidate does not have
- Keep bullets concise, achievement-oriented, and ATS-friendly
- Output ONLY valid JSON — no explanation, no markdown, no code fences
- Output must have the exact same structure as the input JSON
- The experience array MUST contain the EXACT SAME NUMBER of entries as the input — do not add or remove jobs
- Skills must be individual technology/tool names only (e.g. "React.js", "TypeScript") — no sentences, no category labels, no compound strings longer than 25 characters
- Do NOT invent skills. Only use skills that appear in the input skills list"""

def tailor_resume(base: dict, jd: str, hint_keywords: list[str] = None) -> dict:
    """Send base resume + JD to Groq and return tailored resume dict.

    Args:
        base: Base resume JSON dict
        jd: Job description text
        hint_keywords: Optional list of keywords to prioritize in tailoring
    """

    hint_text = ""
    if hint_keywords:
        hint_text = f"\n\nPrioritize incorporating these keywords naturally: {', '.join(hint_keywords)}"

    user_prompt = f"""Here is the candidate's base resume JSON:
{json.dumps(base, indent=2)}

Here is the job description:
{jd[:3000]}{hint_text}

Rewrite the resume to match this job description. Follow all rules. Return only the updated JSON."""

    response = groq.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=2500,
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    tailored = json.loads(raw)

    # Safety: restore locked fields from base resume
    locked = ["name", "email", "phone", "linkedin", "portfolio", "github"]
    for field in locked:
        if field in base:
            tailored[field] = base[field]

    # Restore company names, titles, dates inside experience
    # If Groq dropped entries, pad back to full base length
    base_exps = base.get("experience", [])
    tailored_exps = tailored.get("experience", [])
    while len(tailored_exps) < len(base_exps):
        tailored_exps.append({})
    tailored["experience"] = tailored_exps

    for i, exp in enumerate(base_exps):
        tailored["experience"][i]["company"] = exp["company"]
        tailored["experience"][i]["title"] = exp["title"]
        tailored["experience"][i]["location"] = exp["location"]
        tailored["experience"][i]["start_date"] = exp["start_date"]
        tailored["experience"][i]["end_date"] = exp["end_date"]
        # If Groq dropped this entry entirely, restore original bullets
        if not tailored["experience"][i].get("bullets"):
            tailored["experience"][i]["bullets"] = exp.get("bullets", [])

    # Restore education entirely
    if "education" in base:
        tailored["education"] = base["education"]

    # Sanitize and deduplicate skills: remove hallucinated long strings, drop duplicates
    if "skills" in tailored and isinstance(tailored["skills"], list):
        seen = set()
        clean = []
        for s in tailored["skills"]:
            s_stripped = s.strip()
            if len(s_stripped) > 30:
                # Drop hallucinated long strings
                continue
            key = s_stripped.lower()
            if key not in seen:
                seen.add(key)
                clean.append(s_stripped)
        tailored["skills"] = clean

    return tailored


def _resume_to_text(resume: dict) -> str:
    """Flatten resume JSON to plain text for ATS scoring."""
    parts = []

    # Summary
    if resume.get("summary"):
        parts.append(resume["summary"])

    # Experience bullets
    if resume.get("experience"):
        for exp in resume["experience"]:
            if exp.get("bullets"):
                parts.extend(exp["bullets"])

    # Skills
    if resume.get("skills"):
        if isinstance(resume["skills"], dict):
            # Categorized skills
            for category, skills_list in resume["skills"].items():
                if isinstance(skills_list, list):
                    parts.extend(skills_list)
        elif isinstance(resume["skills"], list):
            parts.extend(resume["skills"])

    return " ".join(parts)


ATS_SYSTEM_PROMPT = """You are an ATS (Applicant Tracking System) expert. Your job is to score how well a resume matches a job description.

SCORING RULES:
- Score from 0-100 based on keyword/skill overlap
- Identify keywords from the JD that ARE present in the resume
- Identify keywords from the JD that are MISSING from the resume
- Return ONLY valid JSON with no explanation

Output format:
{
  "score": <int 0-100>,
  "matched_keywords": [<list of JD keywords found in resume>],
  "missing_keywords": [<list of JD keywords missing from resume>]
}"""


def score_ats(tailored_resume: dict, jd_text: str, client=None) -> dict:
    """Score how well tailored resume matches the job description.

    Returns:
        {"score": int, "matched_keywords": list, "missing_keywords": list}
    """
    if client is None:
        client = groq

    resume_text = _resume_to_text(tailored_resume)
    jd_excerpt = jd_text[:3000]

    user_prompt = f"""Resume content:
{resume_text}

Job description:
{jd_excerpt}

Score this resume against the job description."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": ATS_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=500,
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        return json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        print(f"[score_ats] error scoring: {e}")
        return {"score": None, "matched_keywords": [], "missing_keywords": []}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def _parse_retry_seconds(error_str: str) -> float | None:
    """Parse 'Please try again in Xm Y.Zs' from a Groq 429 error string."""
    import re
    m = re.search(r"try again in (\d+)m([\d.]+)s", str(error_str))
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    m = re.search(r"try again in ([\d.]+)s", str(error_str))
    if m:
        return float(m.group(1))
    return None


def run_tailor(job_id: str = None, limit: int = 10):
    """Tailor resumes for all pending jobs (or a specific job_id for testing).

    Args:
        job_id: Tailor a single job by ID (for testing).
        limit:  Max number of jobs to process in this run (avoids exhausting
                the Groq daily token quota in one shot).
    """
    import time

    if job_id:
        resp = supabase.table("jobs").select("*").eq("job_id", job_id).execute()
        jobs = resp.data
    else:
        # Only jobs that don't have a tailored resume yet
        all_jobs = supabase.table("jobs").select("*").order("created_at", desc=True).execute().data
        tailored_ids = {
            r["job_id"]
            for r in supabase.table("resumes").select("job_id").execute().data
        }
        # Also skip jobs already marked rejected in applications table
        rejected_ids = {
            r["job_id"]
            for r in supabase.table("applications").select("job_id").eq("status", "rejected").execute().data
        }
        jobs = [j for j in all_jobs if j["job_id"] not in tailored_ids and j["job_id"] not in rejected_ids]

    if not jobs:
        print("[tailor] no pending jobs found")
        return

    if limit:
        jobs = jobs[:limit]

    print(f"[tailor] tailoring {len(jobs)} jobs")

    from config.settings import MIN_ATS_SCORE

    for job in jobs:
        jid = job["job_id"]
        title = job["title"]
        company = job["company"]
        jd = job.get("jd_text", "")
        role = job.get("detected_role", "software_developer")

        print(f"[tailor] {company} — {title} (role: {role})")

        if not jd.strip():
            print(f"[tailor] no JD text — skipping {jid}")
            continue

        # --- Step 1: Score the base resume BEFORE tailoring ---
        try:
            base = load_base_resume(role)
            base_ats_result = score_ats(base, jd)
            base_score = base_ats_result.get("score", None)
            if base_score is not None:
                print(f"[ATS] Base score: {base_score}/100 for {company}")
            else:
                print(f"[ATS] Base score: unable to calculate for {company}")
        except Exception as e:
            print(f"[tailor] error scoring base resume for {jid}: {e}")
            base_score = None
            base = None

        # If base already meets threshold, skip tailoring entirely
        if base_score is not None and base_score >= MIN_ATS_SCORE:
            print(f"[tailor] base score {base_score} >= {MIN_ATS_SCORE} — applying directly without tailoring")
            if base is None:
                try:
                    base = load_base_resume(role)
                except Exception as e:
                    print(f"[tailor] could not load base resume for {jid}: {e}")
                    continue
            base["location"] = map_to_preferred_location(job.get("location", ""))
            supabase.table("resumes").insert({
                "job_id": jid,
                "role": role,
                "tailored_json": base,
                "ats_score": base_score,
                "missing_keywords": base_ats_result.get("missing_keywords", []),
            }).execute()
            score_str = f"{base_score}/100" if base_score is not None else "N/A"
            print(f"[tailor] saved base resume (score: {score_str}) for {jid}")
            continue

        best_resume = None
        best_score = None
        best_missing_keywords = []

        # Try tailoring up to 2 times
        for attempt_num in range(1, 3):
            try:
                base = load_base_resume(role)
                hint_keywords = best_missing_keywords if attempt_num == 2 else None
                tailored = tailor_resume(base, jd, hint_keywords=hint_keywords)

                # Snap location to nearest preferred city
                tailored["location"] = map_to_preferred_location(job.get("location", ""))

                # Score this attempt
                ats_result = score_ats(tailored, jd)
                current_score = ats_result.get("score")
                missing = ats_result.get("missing_keywords", [])

                if current_score is not None:
                    print(f"[ATS] Attempt {attempt_num} score: {current_score}/100 for {company}")
                else:
                    print(f"[ATS] Attempt {attempt_num}: unable to calculate score for {company}")

                # Keep the best scoring version (ignore None scores in comparison)
                if current_score is not None and (best_score is None or current_score > best_score):
                    best_score = current_score
                    best_resume = tailored
                    best_missing_keywords = missing

                # If score is good or on final attempt, stop retrying
                if (current_score is not None and current_score >= MIN_ATS_SCORE) or attempt_num == 2:
                    break

            except json.JSONDecodeError as e:
                print(f"[tailor] JSON parse error for {jid}: {e}")
                if attempt_num == 1:
                    continue  # try again
                break
            except Exception as e:
                err_str = str(e)
                if "rate_limit_exceeded" in err_str:
                    wait_secs = _parse_retry_seconds(err_str)
                    if wait_secs and wait_secs <= 120 and attempt_num == 1:
                        print(f"[tailor] rate limited — waiting {wait_secs:.0f}s then retrying {jid}...")
                        time.sleep(wait_secs + 2)
                        continue  # retry once
                    # Groq quota exhausted — fall back to base resume so pipeline keeps moving
                    print(f"[tailor] Groq quota exhausted — using base resume as-is for {jid}")
                    base = load_base_resume(role)
                    base["location"] = map_to_preferred_location(job.get("location", ""))
                    best_resume = base
                    best_score = None
                    break
                print(f"[tailor] error for {jid}: {e}")
                if attempt_num == 1:
                    continue  # try again
                break

        # Always save, even if best_resume is None (fallback to base)
        if best_resume is None:
            try:
                base = load_base_resume(role)
                base["location"] = map_to_preferred_location(job.get("location", ""))
                best_resume = base
            except Exception as e:
                print(f"[tailor] could not load base resume for {jid}: {e}")
                continue

        # Insert resume with ATS score
        supabase.table("resumes").insert({
            "job_id": jid,
            "role": role,
            "tailored_json": best_resume,
            "ats_score": best_score,
            "missing_keywords": best_missing_keywords,
        }).execute()

        score_str = f"{best_score}/100" if best_score is not None else "N/A"
        print(f"[tailor] saved resume (score: {score_str}) for {jid}")

    print("[tailor] done")



if __name__ == "__main__":
    import sys
    jid = sys.argv[1] if len(sys.argv) > 1 else None
    run_tailor(job_id=jid)
