# Job Applying Agent — Project Bible

## What This Is
A fully automated LinkedIn job applying agent. It scrapes LinkedIn every 60 minutes
for fresh job postings, tailors the user's resume to each job description using Groq AI,
and applies via LinkedIn Easy Apply using Playwright browser automation.
Results are stored in Supabase and displayed on a React dashboard.

---

## Absolute Rules — Never Break These

- NEVER apply to jobs with 100 or more applicants (filter before applying)
- NEVER apply to third-party/staffing agency postings (detect via company name + JD signals)
- ONLY apply via LinkedIn Easy Apply (jobs that stay on LinkedIn, no external redirects)
- NEVER hardcode API keys — always read from .env
- NEVER send formatting instructions to Groq — Groq only rewrites words/content
- NEVER let Groq touch resume formatting — python-docx owns all formatting
- ALWAYS deduplicate jobs by (company_name + job_title) before applying
- ALWAYS keep nulls for num_applicants (apply if count not shown — likely fresh post)
- ALWAYS log every action to Supabase (applied / failed / skipped / captcha_blocked)

---

## Tech Stack

| Layer | Tool |
|---|---|
| Job scraping | python-jobspy |
| Full JD fetching | Playwright |
| Resume content rewriting | Groq API (llama-3.3-70b-versatile) |
| Resume formatting + export | python-docx + WeasyPrint |
| Form filling + submission | Playwright |
| Scheduling | APScheduler |
| Database + storage | Supabase (Postgres + Storage) |
| Frontend dashboard | React + Supabase JS client |
| Hosting | Oracle Cloud free tier (later) |

---

## Environment Variables (.env)

```
GROQ_API_KEY=
SUPABASE_URL=
SUPABASE_ANON_KEY=
LINKEDIN_EMAIL=
LINKEDIN_PASSWORD=
```

---

## Project Structure

```
job-agent/
├── CLAUDE.md                      ← this file
├── .env                           ← never commit this
├── requirements.txt
├── config/
│   ├── settings.py                ← job titles, search config
│   ├── screening_answers.py       ← hardcoded Easy Apply Q&A answers
│   └── blacklist.py               ← third-party company + JD signal lists
├── resumes/
│   ├── base_frontend.json         ← structured base resume
│   ├── base_fullstack.json
│   └── base_mobile.json
├── agent/
│   ├── scraper.py                 ← Session 2
│   ├── tailor.py                  ← Session 3
│   ├── resume_builder.py          ← Session 4
│   ├── linkedin_filler.py         ← Session 5
│   └── scheduler.py               ← Session 6
├── output/                        ← generated resumes saved locally
├── frontend/                      ← Session 8 — React dashboard
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── JobTable.jsx
│   │   │   ├── StatusBadge.jsx
│   │   │   ├── ResumePreview.jsx
│   │   │   └── StatsBar.jsx
│   │   └── lib/
│   │       └── supabase.js
│   └── package.json
└── supabase/
    └── schema.sql                 ← Session 7 — run this in Supabase SQL editor
```

---

## Supabase Schema (Session 7)

Run this in the Supabase SQL editor:

```sql
-- Jobs table
create table jobs (
  id uuid default gen_random_uuid() primary key,
  job_id text unique,
  title text,
  company text,
  location text,
  portal text default 'linkedin',
  jd_text text,
  num_applicants integer,
  job_url text,
  easy_apply boolean,
  detected_role text,         -- frontend / fullstack / mobile
  created_at timestamp default now()
);

-- Applications table
create table applications (
  id uuid default gen_random_uuid() primary key,
  job_id text references jobs(job_id),
  status text,                -- applied / failed / skipped / captcha_blocked / manual
  resume_version text,        -- frontend / fullstack / mobile
  resume_pdf_url text,        -- Supabase storage URL
  error_message text,
  applied_at timestamp default now()
);

-- Resumes table (stores each tailored resume JSON)
create table resumes (
  id uuid default gen_random_uuid() primary key,
  job_id text references jobs(job_id),
  role text,
  tailored_json jsonb,
  pdf_url text,
  created_at timestamp default now()
);
```

---

## Build Sessions — Do These In Order

### Session 1 — Project Setup
```
Create the full folder structure above.
Create requirements.txt with all dependencies.
Create .env template (empty values).
Create config/settings.py, config/blacklist.py, config/screening_answers.py with placeholders.
Create three base resume JSON files in resumes/ with this exact structure (see Resume JSON Format below).
Install all dependencies with pip.
Verify imports work.
```

### Session 2 — scraper.py
```
Build agent/scraper.py that does the following in order:

1. Use jobspy to search LinkedIn for each job title in settings.JOB_TITLES
   - hours_old=1
   - easy_apply=True  
   - No location filter — get jobs everywhere
   - results_wanted=50 per search title

2. Combine all results into one DataFrame, deduplicate by (company + title)

3. Apply filters in this exact order:
   a. easy_apply == True only
   b. num_applicants < 100 (keep rows where num_applicants is null/NaN)
   c. company name not in blacklist.COMPANY_BLACKLIST (case-insensitive)

4. For each remaining job, launch Playwright to fetch the full job description:
   - Open job_url in headless browser
   - Extract the full JD text from the page
   - Close browser
   - If JD fetch fails, log and skip that job

5. After fetching full JD, apply Layer 2 filter:
   - Check JD text for any phrase in blacklist.JD_SIGNALS (case-insensitive)
   - Skip job if any signal found

6. Detect which role this job is for based on title:
   - Contains "frontend" or "front-end" or "react" or "vue" or "angular" → frontend
   - Contains "mobile" or "ios" or "android" or "react native" or "flutter" → mobile
   - Everything else → fullstack

7. Save each passing job to Supabase jobs table
   - Skip if job_id already exists in Supabase (already seen)

8. Return list of job dicts for next step in pipeline

Logging: print every filter decision with reason. Use try/except around every external call.
```

### Session 3 — tailor.py
```
Build agent/tailor.py that does the following:

1. Load base resume JSON from resumes/ based on detected_role
   - frontend → base_frontend.json
   - fullstack → base_fullstack.json
   - mobile → base_mobile.json

2. Build Groq prompt (see Groq Prompt Template below)

3. Call Groq API:
   - model: llama-3.3-70b-versatile
   - max_tokens: 1000
   - Return JSON only — no markdown, no explanation, no preamble

4. Parse response as JSON
   - If parse fails, retry once
   - If retry fails, log error and skip this job

5. Validate returned JSON has all required fields (same structure as input)

6. Save tailored JSON to Supabase resumes table

7. Return tailored resume JSON for next step

Important: Groq receives ONLY text content. No formatting instructions.
Send only the fields that change: summary, location, skills, experience bullets.
Never send the full resume if only bullets need changing — keep tokens minimal.
```

### Session 4 — resume_builder.py
```
Build agent/resume_builder.py that does the following:

1. Take tailored resume JSON as input

2. Build .docx using python-docx with these EXACT formatting rules (never deviate):
   - Font: Calibri throughout
   - Name: 16pt bold, centered
   - Contact line: 10pt, centered (email | phone | location | LinkedIn)
   - Section headers: 11pt bold, all caps, left aligned, with bottom border line
   - Body text: 10.5pt, left aligned
   - Bullet points: 10.5pt, hanging indent 0.15 inches
   - Margins: 1 inch all sides
   - Section order: Contact → Summary → Skills → Experience → Education
   - NO tables, NO text boxes, NO columns, NO images (ATS killers)
   - Consistent 6pt spacing after each section
   - Skills displayed as comma-separated single line (not bullets)
   - Experience: Company name bold left, dates right on same line, title italic below

3. Save .docx to output/{job_id}.docx

4. Convert .docx to .pdf using WeasyPrint
   Save to output/{job_id}.pdf

5. Upload PDF to Supabase Storage bucket named "resumes"

6. Update Supabase resumes table with pdf_url

7. Return local pdf path for Playwright to upload

Always generate a fresh resume per job. Never reuse a previous PDF.
```

### Session 5 — linkedin_filler.py
```
Build agent/linkedin_filler.py that does the following:

1. Load LinkedIn session:
   - Check if cookies file exists (linkedin_cookies.json)
   - If yes, load cookies into Playwright context
   - If no, do full login with LINKEDIN_EMAIL + LINKEDIN_PASSWORD from .env
   - Save cookies after login for reuse

2. Open job URL in Playwright

3. Click Easy Apply button

4. Handle multi-step Easy Apply modal:
   Step through each page of the modal until Submit button appears.
   On each page:
   a. Fill text fields (name, email, phone) from screening_answers.py
   b. Upload resume PDF when file upload field appears
   c. Answer dropdown/radio questions using screening_answers.py
   d. Answer any unrecognised question with a sensible default from screening_answers.py
   e. Click Next to proceed

5. On final page click Submit

6. Detect outcome:
   - Success: "Application submitted" confirmation visible
   - CAPTCHA: captcha element detected → log status = captcha_blocked, stop
   - Already applied: "You already applied" message → log status = skipped
   - Error: any exception → log status = failed with error message

7. Update Supabase applications table with result

8. Add random delay between 8-15 seconds between each application (bot detection avoidance)

9. Save/refresh cookies after each session

Use playwright-stealth to reduce bot detection.
Use headless=False during development so you can see what's happening.
Switch to headless=True for production.
```

### Session 6 — scheduler.py
```
Build agent/scheduler.py that does the following:

1. Set up APScheduler with BackgroundScheduler

2. Define run_pipeline() function that chains in order:
   a. scraper.run() → returns list of new jobs
   b. For each job:
      - tailor.run(job) → returns tailored_json
      - resume_builder.run(tailored_json, job) → returns pdf_path
      - linkedin_filler.run(job, pdf_path)
   c. Log pipeline completion to console with counts

3. Schedule run_pipeline() every 60 minutes

4. Run once immediately on startup

5. Keep process alive

Add try/except around the full pipeline so one failure doesn't kill the scheduler.
Log start time, end time, and summary counts (scraped / filtered / applied / failed) each run.
```

### Session 7 — Supabase Setup
```
1. Run supabase/schema.sql in the Supabase SQL editor
2. Create a storage bucket named "resumes" (public read)
3. Verify all three tables exist: jobs, applications, resumes
4. Test insert and select from Python using supabase-py
```

### Session 8 — React Frontend Dashboard
```
Build frontend/ as a React app using Vite.

Design: Clean, minimal, dark theme. Professional. Data-dense but readable.

Pages / components:

1. StatsBar (top of page)
   - Total applied today
   - Total applied all time  
   - Success rate
   - Jobs in queue

2. JobTable (main view)
   - Columns: Company | Title | Location | Role | Status | Applied At | Resume
   - Status shown as coloured badge (applied=green, failed=red, skipped=gray, captcha=yellow)
   - Click Resume column to preview which version was used
   - Filter by: status / role / date range
   - Sort by applied_at descending by default

3. ResumePreview (modal/side panel)
   - Shows tailored resume JSON fields for that job
   - Link to download the PDF from Supabase storage

4. Realtime updates
   - Use Supabase JS realtime subscription on applications table
   - New applications appear instantly without page refresh

Use @supabase/supabase-js for all data fetching.
Read SUPABASE_URL and SUPABASE_ANON_KEY from .env (VITE_ prefix for Vite).
No backend server needed — query Supabase directly from React.
```

---

## Resume JSON Format (Base Structure)

All three base resume files must follow this exact structure:

```json
{
  "name": "YOUR NAME",
  "email": "your@email.com",
  "phone": "555-555-5555",
  "linkedin": "linkedin.com/in/yourhandle",
  "location": "City, State",
  "summary": "One paragraph professional summary.",
  "skills": ["Skill1", "Skill2", "Skill3"],
  "experience": [
    {
      "company": "Company Name",
      "title": "Job Title",
      "location": "City, State",
      "start_date": "Jan 2022",
      "end_date": "Present",
      "bullets": [
        "Did X which resulted in Y",
        "Built Z using A and B"
      ]
    }
  ],
  "education": [
    {
      "school": "University Name",
      "degree": "Bachelor of Science in Computer Science",
      "graduation": "May 2020"
    }
  ]
}
```

---

## Groq Prompt Template (used in tailor.py)

```
You are a professional resume tailoring assistant. 
Your job is to rewrite resume content to match a job description for ATS optimization.

Rules:
- Rewrite experience bullets to mirror keywords and language from the job description
- Rewrite the summary to align with the role and company
- Update the location field to the closest major neighborhood or suburb of: {job_location}
- Keep all facts truthful — do not invent experience, companies, or skills
- Only add skills that are genuinely present in the base resume
- Do not change company names, dates, or job titles
- Do not add formatting, markdown, or explanation
- Return ONLY valid JSON matching the exact same structure as the input

Base resume JSON:
{resume_json}

Job description:
{job_description}

Job location: {job_location}

Return only the updated JSON. No explanation. No markdown. No preamble.
```

---

## config/settings.py Contents

```python
JOB_TITLES = [
    "Frontend Developer",
    "Full Stack Developer", 
    "React Developer",
    "Mobile Developer"
]

ROLE_KEYWORDS = {
    "frontend": ["frontend", "front-end", "react", "vue", "angular", "ui developer"],
    "mobile": ["mobile", "ios", "android", "react native", "flutter"],
    "fullstack": []  # fallback
}

HOURS_OLD = 1
RESULTS_PER_SEARCH = 50
MAX_APPLICANTS = 100
APPLY_DELAY_MIN = 8   # seconds between applications
APPLY_DELAY_MAX = 15
```

---

## config/blacklist.py Contents

```python
COMPANY_BLACKLIST = [
    "dice", "indeed", "ziprecruiter", "staffing", "recruiting",
    "talent", "infosys", "wipro", "tata consultancy", "cognizant",
    "hcl", "tek systems", "kforce", "robert half", "insight global",
    "cybercoders", "hired", "toptal", "gun.io", "experis",
    "modis", "apex systems", "staffmark", "kelly services"
]

JD_SIGNALS = [
    "our client",
    "on behalf of our client",
    "w2 only",
    "c2c",
    "corp to corp",
    "contract to hire",
    "submit your resume to",
    "our client is looking",
    "must be willing to relocate at your own expense",
    "third party agencies"
]
```

---

## config/screening_answers.py Contents

```python
ANSWERS = {
    "years_of_experience": "5",
    "work_authorization": "Yes",
    "require_sponsorship": "No",
    "expected_salary": "120000",
    "salary_expectation": "120000",
    "notice_period": "2 weeks",
    "willing_to_relocate": "Yes",
    "degree": "Bachelor's",
    "remote_preference": "Yes",
    "phone": "YOUR_PHONE",
    "email": "YOUR_EMAIL",
    "name": "YOUR_NAME",
    "linkedin": "YOUR_LINKEDIN_URL",
    "website": "",
    "gender": "Prefer not to say",
    "ethnicity": "Prefer not to say",
    "veteran_status": "I am not a veteran",
    "disability_status": "No, I don't have a disability"
}

# Fallback for any unknown question
DEFAULT_ANSWER = "Yes"
```

---

## requirements.txt

```
python-jobspy
playwright
playwright-stealth
groq
python-docx
weasyprint
supabase
apscheduler
python-dotenv
pandas
```

---

## Key Decisions Already Made

- Location is NOT a search filter — it comes from job data and is used only to personalise the resume header and tone
- Groq receives only text content to rewrite, never formatting instructions
- python-docx owns 100% of resume formatting — hardcoded and consistent every time
- SQLite was considered but Supabase chosen for frontend dashboard realtime support
- Telegram alerts skipped for now — dashboard handles status visibility
- headless=False during development, headless=True for production
- One LinkedIn account, rate limited to 8-15 second delays between applications
- Apply even when num_applicants is null (likely a very fresh post)
