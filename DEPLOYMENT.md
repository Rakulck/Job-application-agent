# Cloud Deployment Plan — Full Reference

**Status:** Approved, not yet implemented  
**Last Updated:** 2026-04-09  
**Owner:** User

---

## Overview

Deploy the entire job application agent to the cloud with zero local machine dependency after initial setup.

- **Python pipeline + Playwright** → Oracle Cloud Free VM (Ubuntu 22.04)
- **FastAPI HTTP server** → Same VM, port 8000 (triggered from React dashboard)
- **APScheduler** → Same VM, auto-runs every 60 min
- **React frontend** → Vercel (free tier)
- **Database + Storage** → Supabase (already set up, no changes)
- **Resume tailoring** → Groq API (already cloud)

---

## Request Flow

### Manual Trigger (from React dashboard)
```
User clicks "Run Now" in React dashboard (Vercel)
        ↓
HTTP POST → http://YOUR_VM_IP:8000/trigger
        (with X-API-Key header for auth)
        ↓
FastAPI on Oracle VM receives request
        ↓
Runs pipeline: scraper → tailor → resume_builder → linkedin_filler
        ↓
Results written to Supabase (jobs + applications tables)
        ↓
React dashboard updates in realtime via Supabase Realtime subscription
```

### Auto-Trigger (every 60 min)
- APScheduler also runs the same pipeline automatically without user action

---

## Hard Problems & Solutions

| Problem | Solution |
|---|---|
| Playwright on headless server | Install Chromium + system deps, use `headless=True` |
| WeasyPrint on Linux | Install system packages: libpango, libcairo, fonts-liberation |
| LinkedIn first login (2FA/CAPTCHA) | Copy `linkedin_cookies.json` from local OR use VNC to log in once |
| LinkedIn bot detection | playwright-stealth + 8-15s delays (already in code) |
| Always-on scheduler | systemd service, auto-restarts on crash |
| Manual trigger from dashboard | FastAPI HTTP endpoint with API key auth |

---

## Step-by-Step Setup (TODO)

### Step 1 — Provision Oracle Cloud Free VM
- [ ] Sign up at cloud.oracle.com
- [ ] Create Ubuntu 22.04 instance (VM.Standard.E2.1.Micro — always free)
- [ ] Download SSH key
- [ ] Note VM IP address

### Step 2 — SSH into VM and install system dependencies
- [ ] Connect via SSH: `ssh -i key.pem ubuntu@VM_IP`
- [ ] Update packages: `sudo apt update && sudo apt upgrade -y`
- [ ] Install Python + build tools: `python3 python3-pip python3-venv git`
- [ ] Install WeasyPrint deps: `libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info fonts-liberation`
- [ ] Install Playwright deps: `libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2`

### Step 3 — Upload project to VM
- [ ] Option A: `scp -r "path/to/job application agent/" ubuntu@VM_IP:~/job-agent/`
- [ ] OR Option B: Push to GitHub, `git clone` on VM

### Step 4 — Set up Python environment on VM
- [ ] Create venv: `python3 -m venv venv`
- [ ] Activate: `source venv/bin/activate`
- [ ] Install deps: `pip install -r requirements.txt`
- [ ] Install Playwright: `playwright install chromium && playwright install-deps chromium`

### Step 5 — Set up .env on VM
- [ ] Create `.env` with all keys:
  - `GROQ_API_KEY`
  - `SUPABASE_URL`
  - `SUPABASE_ANON_KEY`
  - `LINKEDIN_EMAIL`
  - `LINKEDIN_PASSWORD`
  - `TRIGGER_API_KEY` (new — any random string)

### Step 6 — Handle LinkedIn initial login
- [ ] Option A: Copy `linkedin_cookies.json` from local machine via scp
- [ ] OR Option B: Use VNC to log in once, then switch to `headless=True`

### Step 7 — Create FastAPI server files (NEW)
- [ ] Create `api.py` with `/trigger` endpoint
- [ ] Create `start.py` that runs both FastAPI + APScheduler
- [ ] Add to `requirements.txt`: `fastapi uvicorn`

### Step 8 — Modify existing files
- [ ] `agent/linkedin_filler.py`: change `headless=False` → `headless=True`
- [ ] `frontend/src/`: add "Run Now" button that POSTs to `/trigger`
- [ ] Update `.env` with `TRIGGER_API_KEY` and `VITE_API_URL`

### Step 9 — Create systemd service
- [ ] Create `/etc/systemd/system/job-agent.service`
- [ ] Point to `start.py` (not `scheduler.py`)
- [ ] Enable + start: `sudo systemctl enable job-agent && sudo systemctl start job-agent`

### Step 10 — Open port 8000 on Oracle Cloud
- [ ] Oracle Cloud console → VCN → Security List
- [ ] Add Ingress Rule: Protocol TCP, Port 8000, Source 0.0.0.0/0

### Step 11 — Deploy React frontend to Vercel
- [ ] Push `frontend/` to GitHub
- [ ] vercel.com → Import repo → Set root to `frontend/`
- [ ] Add env vars:
  - `VITE_SUPABASE_URL`
  - `VITE_SUPABASE_ANON_KEY`
  - `VITE_API_URL` (http://YOUR_VM_IP:8000)
  - `VITE_TRIGGER_API_KEY` (same as `TRIGGER_API_KEY` on VM)

### Step 12 — Verify deployment
- [ ] `sudo systemctl status job-agent` shows "active (running)"
- [ ] `journalctl -u job-agent -f` shows logs every 60 min
- [ ] Supabase dashboard → `applications` table fills with new rows
- [ ] Vercel dashboard loads and shows jobs in realtime
- [ ] "Run Now" button works and triggers pipeline immediately

---

## Files to Create

### `api.py` (on VM)
```python
from fastapi import FastAPI, Header, HTTPException
from scheduler import run_pipeline
import asyncio, os, threading

app = FastAPI()
API_KEY = os.getenv("TRIGGER_API_KEY")

@app.post("/trigger")
def trigger(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    # Run pipeline in background thread so API returns immediately
    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()
    return {"status": "pipeline started"}

@app.get("/health")
def health():
    return {"status": "ok"}
```

### `start.py` (on VM)
```python
import uvicorn, threading
from apscheduler.schedulers.background import BackgroundScheduler
from scheduler import run_pipeline
from api import app

scheduler = BackgroundScheduler()
scheduler.add_job(run_pipeline, 'interval', minutes=60)
scheduler.start()
run_pipeline()  # run once on startup

uvicorn.run(app, host="0.0.0.0", port=8000)
```

### `/etc/systemd/system/job-agent.service` (on VM)
```ini
[Unit]
Description=Job Application Agent Scheduler
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/job-agent
Environment=PATH=/home/ubuntu/job-agent/venv/bin
ExecStart=/home/ubuntu/job-agent/venv/bin/python start.py
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

---

## Environment Variables

### On VM (`.env`)
```
GROQ_API_KEY=...
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
LINKEDIN_EMAIL=...
LINKEDIN_PASSWORD=...
TRIGGER_API_KEY=random-secret-string-here
```

### On Vercel dashboard (for `frontend/`)
```
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
VITE_API_URL=http://YOUR_VM_IP:8000
VITE_TRIGGER_API_KEY=same-secret-string-as-TRIGGER_API_KEY
```

---

## Frontend Changes Required

### Add "Run Now" button to React dashboard
```jsx
const triggerPipeline = async () => {
  try {
    const res = await fetch(`${import.meta.env.VITE_API_URL}/trigger`, {
      method: 'POST',
      headers: { 'X-API-Key': import.meta.env.VITE_TRIGGER_API_KEY }
    });
    if (res.ok) {
      console.log("Pipeline triggered");
      // Optional: show toast notification
    }
  } catch (err) {
    console.error("Failed to trigger pipeline", err);
  }
};

// In render:
// <button onClick={triggerPipeline}>Run Now</button>
```

---

## Dependencies to Add

Add to `requirements.txt`:
```
fastapi
uvicorn
```

---

## Cost Estimate

| Service | Cost |
|---|---|
| Oracle Cloud VM | $0 (always free tier) |
| Vercel frontend | $0 (free tier) |
| Supabase | $0 (free tier — 500MB DB, 1GB storage) |
| Groq API | $0 (free tier — generous limits) |
| **Total** | **$0/month** |

---

## Verification Checklist

- [ ] VM SSH access works
- [ ] Python venv + all pip packages installed
- [ ] Playwright Chromium installed and working
- [ ] `.env` file created with all required keys
- [ ] `linkedin_cookies.json` exists on VM
- [ ] `api.py` created
- [ ] `start.py` created
- [ ] `requirements.txt` updated with `fastapi` + `uvicorn`
- [ ] `agent/linkedin_filler.py` changed to `headless=True`
- [ ] systemd service file created and enabled
- [ ] systemd service is running and active
- [ ] Port 8000 open on Oracle Cloud
- [ ] React frontend deployed to Vercel
- [ ] Vercel env vars set correctly
- [ ] "Run Now" button added to frontend
- [ ] Manual trigger test: button clicks and pipeline runs
- [ ] Auto trigger test: pipeline runs every 60 min automatically
- [ ] Supabase tables populate with results
- [ ] Dashboard shows realtime updates

---

## Session-by-Session Implementation Plan

**Session A:** VM setup (Steps 1-5)
**Session B:** Python files + systemd (Steps 6-9)
**Session C:** Frontend + deployment (Steps 11-12)
**Session D:** Verification + debugging

---

## Known Issues & Workarounds

None yet. Will update as we discover issues during implementation.

---

## References

- [ARCHITECTURE.md](ARCHITECTURE.md) — original tech stack
- [PROGRESS.md](PROGRESS.md) — session log
- [CLAUDE.md](CLAUDE.md) — project overview
