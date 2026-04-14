import os
import re
import random
import asyncio
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone

from playwright.async_api import async_playwright, TimeoutError as PWTimeout
from supabase import create_client
from dotenv import load_dotenv

from config.settings import APPLY_DELAY_MIN, APPLY_DELAY_MAX
from config.screening_answers import load_answers, DEFAULT_ANSWER

load_dotenv()

SUPABASE_URL         = os.getenv("SUPABASE_URL")
SUPABASE_KEY         = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
LINKEDIN_EMAIL       = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD    = os.getenv("LINKEDIN_PASSWORD")

_HEADLESS = os.getenv("HEADLESS", "true").lower() != "false"

supabase       = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ---------------------------------------------------------------------------
# LinkedIn login
# ---------------------------------------------------------------------------

COOKIES_FILE = os.path.join(os.path.dirname(__file__), "..", "linkedin_cookies.json")


async def _is_logged_in(page) -> bool:
    """Return True if we're on a logged-in LinkedIn page (not login/signup/authwall)."""
    url = page.url
    blocked = ("login", "signup", "authwall", "checkpoint", "uas/authenticate")
    return any(p in url for p in ("feed", "mynetwork", "jobs", "messaging", "notifications", "/in/")) \
        and not any(b in url for b in blocked)


async def _do_fresh_login(page, context):
    """Perform a full username/password login and save cookies."""
    import json
    print("[filler] logging in to LinkedIn...")
    await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=30_000)
    await page.wait_for_timeout(3000)
    print(f"[filler] login page loaded — url={page.url} title={await page.title()}")

    # Dump page HTML so we can diagnose what LinkedIn is actually rendering
    try:
        html_snippet = (await page.content())[:3000]
        print(f"[filler] page HTML snippet: {html_snippet}")
    except Exception as e:
        print(f"[filler] could not get page HTML: {e}")

    # Take a screenshot for visual debugging
    try:
        import tempfile, pathlib
        shot_path = pathlib.Path(tempfile.gettempdir()) / "linkedin-login-debug.png"
        await page.screenshot(path=str(shot_path), full_page=True)
        print(f"[filler] screenshot saved to {shot_path}")
    except Exception as e:
        print(f"[filler] could not take screenshot: {e}")

    # Wait for the email field — try multiple selectors
    email_sel = None
    pass_sel  = None
    for e_sel, p_sel in [
        ("#username",                   "#password"),
        ("input[name='session_key']",   "input[name='session_password']"),
        ("input[type='email']",         "input[type='password']"),
        ("input[autocomplete='username']", "input[autocomplete='current-password']"),
    ]:
        try:
            await page.wait_for_selector(e_sel, timeout=8_000)
            email_sel = e_sel
            pass_sel  = p_sel
            print(f"[filler] found login form with selector: {e_sel}")
            break
        except Exception:
            print(f"[filler] selector not found: {e_sel}")
    if email_sel is None:
        raise Exception(f"Login form not found — page url={page.url}")
    await page.fill(email_sel, LINKEDIN_EMAIL)
    await page.fill(pass_sel, LINKEDIN_PASSWORD)
    await page.click("button[type='submit']")
    await page.wait_for_timeout(5000)

    if "checkpoint" in page.url or "challenge" in page.url:
        print("[filler] CAPTCHA / checkpoint detected — waiting up to 60s for manual resolution")
        for _ in range(12):
            await page.wait_for_timeout(5000)
            if "feed" in page.url or "mynetwork" in page.url:
                break

    if "feed" in page.url or "mynetwork" in page.url:
        cookies = await context.cookies()
        with open(COOKIES_FILE, "w") as f:
            json.dump(cookies, f)
        print("[filler] login successful — cookies saved")
    else:
        raise Exception(f"Login failed — landed on: {page.url}")


async def login(context, page):
    import json

    # Try loading saved cookies first
    if os.path.exists(COOKIES_FILE):
        with open(COOKIES_FILE, "r") as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)
        await page.goto("https://www.linkedin.com/feed", wait_until="domcontentloaded", timeout=20_000)
        await page.wait_for_timeout(3000)

        # Robust check: verify an actual logged-in DOM element is present
        if await _is_logged_in(page):
            print("[filler] logged in via saved cookies")
            return

        # Cookies expired — delete stale file and re-login
        print("[filler] cookies expired — logging in fresh")
        try:
            os.remove(COOKIES_FILE)
        except Exception:
            pass

    await _do_fresh_login(page, context)


# ---------------------------------------------------------------------------
# Select and prepare resume from local files (no tailoring)
# ---------------------------------------------------------------------------

RESUME_FRONTEND = r"C:\Users\Asus\Downloads\Rakul_Kandavel_Final.docx"
RESUME_FULLSTACK = r"C:\Users\Asus\Downloads\Rakul_Kandavel_SWE (8).docx"

# Keywords to detect resume type
FRONTEND_KEYWORDS = {"react", "frontend", "web", "vue", "angular", "next.js", "typescript", "javascript"}
FULLSTACK_KEYWORDS = {"full-stack", "fullstack", "mobile", "flutter", "react native", "ios", "android", "backend"}


def _select_resume_for_job(job: dict) -> str:
    """
    Select the appropriate resume file based on job title and description.
    Frontend: 'Rakul_Kandavel_Final.docx'
    Fullstack/Mobile/Software Developer: 'Rakul_Kandavel_SWE (8).docx'
    """
    title = (job.get("title", "") or "").lower()
    desc = (job.get("description", "") or "").lower()
    text = f"{title} {desc}"

    # Count keyword matches
    frontend_matches = sum(1 for kw in FRONTEND_KEYWORDS if kw in text)
    fullstack_matches = sum(1 for kw in FULLSTACK_KEYWORDS if kw in text)

    # Default to fullstack if fullstack keywords match better or equal
    if fullstack_matches >= frontend_matches:
        return RESUME_FULLSTACK
    else:
        return RESUME_FRONTEND


def _convert_docx_to_pdf(docx_path: str) -> str:
    """Convert DOCX to PDF using docx2pdf. Returns PDF path."""
    from docx2pdf import convert
    pdf_path = docx_path.replace(".docx", "_temp.pdf")
    convert(docx_path, pdf_path)
    print(f"[filler] converted {docx_path} → {pdf_path}")
    return pdf_path


async def prepare_resume_for_job(job: dict) -> str:
    """
    Select the right local resume and convert to PDF.
    Returns path to PDF file.
    """
    docx_path = _select_resume_for_job(job)
    company = job.get("company", "unknown")
    title = job.get("title", "position")
    print(f"[filler] selected resume: {docx_path} for {company} — {title}")

    pdf_path = _convert_docx_to_pdf(docx_path)
    return pdf_path


# ---------------------------------------------------------------------------
# Field fillers
# ---------------------------------------------------------------------------

@dataclass
class UnknownQuestion:
    label: str
    field_type: str        # 'text' | 'select' | 'radio' | 'number' | 'email' | 'tel'
    options: list[str]     # empty for text fields


def _normalize(text: str) -> str:
    return text.lower().strip()


async def _get_cached_answer(question_label: str) -> str | None:
    """Check if we've answered this question before.
    Priority: 1) cached_answers, 2) unknown_questions (user-provided via dashboard)
    """
    # Check cached_answers first (global reusable answers)
    try:
        response = supabase.table("cached_answers").select("answer").eq(
            "question_label", question_label
        ).single().execute()
        if response.data and response.data.get("answer"):
            print(f"[filler] ✓ cached: '{question_label}'")
            return response.data["answer"]
    except Exception:
        pass

    # Check unknown_questions for user-provided answers (answered via dashboard)
    try:
        response = supabase.table("unknown_questions").select("answer").eq(
            "question_label", question_label
        ).not_("answer", "is", "null").single().execute()
        if response.data and response.data.get("answer"):
            print(f"[filler] ✓ user-provided: '{question_label}'")
            return response.data["answer"]
    except Exception:
        pass

    return None


async def _save_cached_answer(question_label: str, field_type: str, answer: str, options: list[str] = None):
    """Save answer to cache for future use."""
    try:
        supabase.table("cached_answers").upsert({
            "question_label": question_label,
            "field_type": field_type,
            "options": options or [],
            "answer": answer
        }, on_conflict="question_label", ignore_duplicates=True).execute()
    except Exception:
        pass  # already cached = already correct, silently skip


async def _find_answer(label: str, answers: dict) -> tuple[str, bool]:
    """Find answer for label. Returns (value, matched: bool).
    Priority: 1) cached answer, 2) screening_answers (substring + word-based), 3) default
    """
    label_n = _normalize(label)

    # Step 1: Check cache first
    cached = await _get_cached_answer(label)
    if cached:
        return cached, True  # cached answer counts as "matched"

    # Step 2: Check screening_answers - exact substring match
    for key, val in answers.items():
        if key.replace("_", " ") in label_n or label_n in key.replace("_", " "):
            return str(val), True

    # Step 2b: Word-based fallback for questions with filler words (e.g., "years of relevant experience")
    # All significant words (>3 chars) from key must appear in label (handles LinkedIn's variations)
    for key, val in answers.items():
        key_words = [w for w in key.replace("_", " ").split() if len(w) > 3]
        if len(key_words) >= 2 and all(re.search(r'\b' + re.escape(w), label_n) for w in key_words):
            return str(val), True

    # Step 3: Fall back to default
    return DEFAULT_ANSWER, False


async def fill_text_field(page, field, label: str, answers: dict, job_title: str = "", input_type: str = "text") -> "UnknownQuestion | None":
    """Clear and fill a text input. Returns UnknownQuestion if label not recognised."""
    # Auto-fill position fields with the job title being applied for
    if "position" in label.lower() and job_title:
        value = job_title
        matched = True
    else:
        value, matched = await _find_answer(label, answers)

    if not matched:
        return UnknownQuestion(label=label, field_type=input_type, options=[])

    # Click with short timeout; fall back to force-click if a typeahead overlay is blocking
    try:
        await field.click(timeout=3000)
    except Exception:
        try:
            await field.click(force=True, timeout=2000)
        except Exception as e:
            print(f"[filler] text fill error ({label}): {e}")
            return None
    try:
        await field.select_text()
        await field.fill(value)
        # Dismiss any autocomplete/typeahead that opened (would block next field's click)
        await field.press("Escape")
        await page.wait_for_timeout(150)
    except Exception as e:
        print(f"[filler] text fill error ({label}): {e}")

    # Save to cache if we matched an answer from screening_answers (learning)
    if value not in [DEFAULT_ANSWER]:
        await _save_cached_answer(label, "text", value, [])

    return None


async def fill_select(page, field, label: str, answers: dict) -> "UnknownQuestion | None":
    """Select the best matching option in a <select>. Returns UnknownQuestion if label not recognised."""
    answer, matched = await _find_answer(label, answers)
    options = []
    try:
        options = await field.evaluate("el => Array.from(el.options).map(o => o.text)")
    except Exception as e:
        print(f"[filler] select options extract error ({label}): {e}")

    if not matched:
        return UnknownQuestion(label=label, field_type="select", options=options)

    try:
        best = next(
            (o for o in options if answer.lower() in o.lower()),
            next((o for o in options if "yes" in o.lower()), options[1] if len(options) > 1 else options[0])
        )
        await field.select_option(label=best, timeout=3000)
    except Exception as e:
        print(f"[filler] select error ({label}): {e}")

    # Save to cache if we matched an answer from screening_answers (learning)
    if answer not in [DEFAULT_ANSWER]:
        await _save_cached_answer(label, "select", answer, options)

    return None


async def fill_radio(page, group_label: str, options, answers: dict) -> "UnknownQuestion | None":
    """Click the best matching radio button. Returns UnknownQuestion if label not recognised."""
    answer, matched = await _find_answer(group_label, answers)
    option_texts = []
    try:
        for opt in options:
            text = await opt.evaluate("""el => {
                const id = el.id;
                if (id) {
                    const lbl = document.querySelector('label[for="' + id + '"]');
                    if (lbl) return lbl.innerText.trim();
                }
                const sib = el.nextElementSibling;
                if (sib && sib.tagName === 'LABEL') return sib.innerText.trim();
                const parentLbl = el.closest('label');
                if (parentLbl) return parentLbl.innerText.trim();
                return el.getAttribute('value') || '';
            }""")
            option_texts.append(text)
    except Exception as e:
        print(f"[filler] radio extract error ({group_label}): {e}")

    if not matched:
        return UnknownQuestion(label=group_label, field_type="radio", options=option_texts)

    try:
        for i, opt in enumerate(options):
            text = option_texts[i]
            if answer.lower() in text.lower():
                await opt.evaluate("""el => {
                    const id = el.id;
                    const lbl = id ? document.querySelector('label[for="' + id + '"]') : null;
                    if (lbl) lbl.click(); else el.click();
                }""")
                break
        else:
            # Fallback: answer was "Yes" (default) but not explicitly matched
            if options:
                await options[0].evaluate("""el => {
                    const id = el.id;
                    const lbl = id ? document.querySelector('label[for="' + id + '"]') : null;
                    if (lbl) lbl.click(); else el.click();
                }""")
    except Exception as e:
        print(f"[filler] radio click error ({group_label}): {e}")

    # Save to cache if we matched an answer from screening_answers (learning)
    if answer not in [DEFAULT_ANSWER]:
        await _save_cached_answer(group_label, "radio", answer, option_texts)

    return None


# ---------------------------------------------------------------------------
# Modal step filler
# ---------------------------------------------------------------------------

def _clean_label(raw: str) -> str:
    """Return the first non-empty line, stripped. Fixes LinkedIn's doubled label text."""
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    return lines[0] if lines else raw.strip()


async def fill_modal_step(page, pdf_path: str, answers: dict, job_title: str = "") -> list[UnknownQuestion]:
    """Fill all visible fields in the current Easy Apply modal step. Returns list of unrecognised questions."""
    unknown_questions: list[UnknownQuestion] = []

    # Scope all selectors strictly to the Easy Apply modal — never fall back to full page
    modal = page.locator(".jobs-easy-apply-modal, [data-test-modal-id='easy-apply-modal']").first

    if await modal.count() == 0:
        print("[filler] WARNING: Easy Apply modal not found — skipping field fill")
        return []

    # --- Resume upload ---
    # LinkedIn Easy Apply often hides the file input behind an "Upload resume" button
    # (when the user already has a saved resume on their profile). Click that button
    # first so the hidden input becomes active, then set_input_files on it.
    UPLOAD_TRIGGER_SELS = [
        "button:has-text('Upload resume')",
        "button:has-text('Change')",
        "label:has-text('Upload resume')",
        "[aria-label*='upload' i]",
        ".jobs-resume-picker__upload-label",
        "button:has-text('Choose')",
    ]
    for sel in UPLOAD_TRIGGER_SELS:
        try:
            btn = modal.locator(sel)
            if await btn.count() > 0:
                await btn.first.click(timeout=2000)
                await page.wait_for_timeout(1000)
                print(f"[filler] clicked resume trigger: {sel}")
                break
        except Exception:
            pass

    # Now try to upload — Playwright's set_input_files works on hidden inputs too
    file_inputs = page.locator("input[type='file']")   # broader scope: whole page
    if await file_inputs.count() > 0:
        try:
            await file_inputs.first.set_input_files(pdf_path)
            print("[filler] resume uploaded")
            await page.wait_for_timeout(1500)
        except Exception as e:
            print(f"[filler] resume upload error: {e}")
    else:
        print("[filler] WARNING: no file input found — resume may not be uploaded")

    # Text inputs
    inputs = modal.locator("input[type='text'], input[type='tel'], input[type='email'], input[type='number']")
    count = await inputs.count()
    for i in range(count):
        inp = inputs.nth(i)
        try:
            inp_id = await inp.get_attribute("id") or ""
            inp_type = await inp.get_attribute("type") or "text"
            label_el = modal.locator(f"label[for='{inp_id}']")
            label = _clean_label(await label_el.first.inner_text()) if await label_el.count() > 0 else ""
            if not label:
                label = await inp.get_attribute("placeholder") or ""
            val = await inp.input_value()
            if not val.strip():
                result = await fill_text_field(page, inp, label, answers, job_title, input_type=inp_type)
                if result:
                    unknown_questions.append(result)
        except Exception as e:
            pass

    # Selects
    selects = modal.locator("select")
    sel_count = await selects.count()
    for i in range(sel_count):
        sel = selects.nth(i)
        try:
            sel_id = await sel.get_attribute("id") or ""
            label_el = modal.locator(f"label[for='{sel_id}']")
            label = _clean_label(await label_el.first.inner_text()) if await label_el.count() > 0 else ""
            result = await fill_select(page, sel, label, answers)
            if result:
                unknown_questions.append(result)
        except Exception:
            pass

    # Radio buttons — group by name
    radios = modal.locator("input[type='radio']")
    radio_count = await radios.count()
    processed_names = set()
    for i in range(radio_count):
        radio = radios.nth(i)
        try:
            name = await radio.get_attribute("name") or ""
            if name in processed_names:
                continue
            processed_names.add(name)
            group = modal.locator(f"input[type='radio'][name='{name}']")
            legend = modal.locator(f"fieldset:has(input[name='{name}']) legend")
            label = _clean_label(await legend.first.inner_text()) if await legend.count() > 0 else name
            group_items = [group.nth(j) for j in range(await group.count())]
            result = await fill_radio(page, label, group_items, answers)
            if result:
                unknown_questions.append(result)
        except Exception as e:
            print(f"[filler] radio group exception: {e}")

    # Textareas (cover letter etc) — leave blank
    textareas = modal.locator("textarea")
    ta_count = await textareas.count()
    for i in range(ta_count):
        ta = textareas.nth(i)
        try:
            val = await ta.input_value()
            if not val.strip():
                await ta.fill("")
        except Exception:
            pass

    return unknown_questions


# ---------------------------------------------------------------------------
# Apply to a single job
# ---------------------------------------------------------------------------

async def apply_to_job(page, job: dict, answers: dict) -> tuple[str, str, list[UnknownQuestion]]:
    """
    Navigate to job, click Easy Apply, fill modal, submit.
    Selects the appropriate local resume (no tailoring) and uses it directly.
    Returns (status, reason, unknown_questions): status is 'applied'|'failed'|'skipped'|'captcha_blocked'
    """
    url      = job["job_url"]
    job_id   = job["job_id"]
    all_unknown: list[UnknownQuestion] = []

    # Select and prepare the appropriate resume from local files
    try:
        pdf_path = await prepare_resume_for_job(job)
    except Exception as e:
        print(f"[filler] failed to prepare resume for {job_id}: {e}")
        return "skipped", f"resume prep failed: {e}", []

    try:
        # Use search URL with currentJobId — this gives the full LinkedIn experience
        # where the Apply button is visible in the right-side detail panel
        job_id_str = str(job_id)
        search_url = (
            f"https://www.linkedin.com/jobs/search/"
            f"?f_AL=true&currentJobId={job_id_str}"
        )
        await page.goto(search_url, wait_until="domcontentloaded", timeout=40_000)
        await page.wait_for_timeout(4000)

        # Detect login wall
        if "login" in page.url or "signup" in page.url or not await _is_logged_in(page):
            print(f"[filler] session expired — re-logging in")
            await _do_fresh_login(page, page.context)
            await page.goto(search_url, wait_until="domcontentloaded", timeout=40_000)
            await page.wait_for_timeout(4000)

        # Dismiss any overlay
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)
        except Exception:
            pass

        # Check if job is still accepting — scope to right-side detail panel
        detail_panel = page.locator(
            ".scaffold-layout__detail, "
            ".jobs-search__job-details, "
            ".jobs-details"
        )
        panel = detail_panel.first if await detail_panel.count() > 0 else page.locator("body")
        panel_text = (await panel.inner_text()).lower()
        if "no longer accepting" in panel_text:
            print(f"[filler] no longer accepting — skipping {url}")
            return "skipped", "no longer accepting", []

        # Apply button scoped strictly to the RIGHT detail panel only
        # (prevents accidentally clicking buttons in the left job-list)
        APPLY_SELS = (
            "button[aria-label*='Easy Apply'], "
            "button[aria-label*='LinkedIn Apply'], "
            "button[aria-label*='Apply'], "
            ".jobs-apply-button--top-card button, "
            ".jobs-s-apply button, "
            ".jobs-apply-button, "
            "[class*='jobs-apply-button']"
        )
        apply_btn = panel.locator(APPLY_SELS)

        found = False
        for _ in range(6):
            if await apply_btn.count() > 0:
                found = True
                break
            await page.wait_for_timeout(3000)

        if not found:
            btn_info = await page.evaluate("""() =>
                Array.from(document.querySelectorAll('button')).slice(0,20).map(b =>
                    (b.innerText.trim() || b.getAttribute('aria-label') || '(no label)') + ' [' + b.className.slice(0,40) + ']'
                )
            """)
            print(f"[filler] no Apply button found for {url}")
            print(f"[filler]   all buttons: {btn_info}")
            return "skipped", "no apply button found", []

        print(f"[filler] found Apply button — clicking")
        try:
            await apply_btn.first.scroll_into_view_if_needed(timeout=5000)
        except Exception:
            pass
        # JS scroll as extra fallback for viewport issues
        try:
            await apply_btn.first.evaluate("el => el.scrollIntoView({block: 'center'})")
            await page.wait_for_timeout(300)
        except Exception:
            pass
        await page.wait_for_timeout(500)
        try:
            await apply_btn.first.click(timeout=10000)
        except Exception:
            # Force-click as fallback (bypasses actionability checks)
            print(f"[filler] normal click failed — trying force click")
            try:
                await apply_btn.first.click(force=True, timeout=5000)
            except Exception as ce:
                # JS click as last resort
                print(f"[filler] force click also failed — trying JS click")
                try:
                    await apply_btn.first.evaluate("el => el.click()")
                    await page.wait_for_timeout(1000)
                except Exception as je:
                    print(f"[filler] JS click also failed: {je}")
                    return "failed", f"click failed: {str(ce)[:100]}", []

        # Wait for Easy Apply modal to open
        MODAL_SELS = (
            "[data-test-modal-id='easy-apply-modal'], "
            ".jobs-easy-apply-modal, "
            ".jobs-easy-apply-content, "
            "div[aria-label*='Easy Apply'], "
            "[role='dialog']"
        )
        modal_appeared = True
        try:
            await page.wait_for_selector(MODAL_SELS, timeout=20_000)
        except Exception:
            modal_appeared = False

        if not modal_appeared:
            # If we left LinkedIn, this was an external apply redirect
            if "linkedin.com" not in page.url:
                print(f"[filler] redirected off LinkedIn — external apply job, skipping")
                return "skipped", "external apply (redirected off LinkedIn)", []
            print(f"[filler] Easy Apply modal did not open — skipping")
            return "skipped", "easy apply modal did not open", []

        await page.wait_for_timeout(2000)  # Extended wait for modal to fully render

        # Multi-step modal loop
        all_unknown: list[UnknownQuestion] = []
        max_steps = 10
        for step in range(max_steps):
            # Check for captcha
            if await page.locator("iframe[title*='captcha'], #captcha-internal").count() > 0:
                print("[filler] CAPTCHA detected")
                return "captcha_blocked", "captcha", all_unknown

            # Fill current step
            job_title = job.get("title", "")
            step_unknowns = await fill_modal_step(page, pdf_path, answers, job_title)
            all_unknown.extend(step_unknowns)
            await page.wait_for_timeout(1000)

            # Try Submit button first
            submit_btn = page.locator("button[aria-label='Submit application']")
            if await submit_btn.count() > 0:
                # Wait for button to become enabled (LinkedIn disables it until fields valid)
                try:
                    await submit_btn.first.wait_for(state="enabled", timeout=5000)
                except Exception:
                    pass
                # Scroll the modal container down to reveal the button
                try:
                    await page.evaluate("""
                        const modal = document.querySelector('.jobs-easy-apply-modal, .artdeco-modal__content, [class*="easy-apply-modal"]');
                        if (modal) modal.scrollTop = modal.scrollHeight;
                    """)
                    await page.wait_for_timeout(500)
                except Exception:
                    pass
                try:
                    await submit_btn.first.scroll_into_view_if_needed(timeout=5000)
                except Exception:
                    pass
                await page.wait_for_timeout(500)
                try:
                    await submit_btn.first.click(timeout=8000)
                except Exception:
                    await submit_btn.first.evaluate("el => el.click()")
                await page.wait_for_timeout(3000)
                print(f"[filler] submitted application for {job_id}")
                return "applied", "", all_unknown

            # Scroll modal to bottom before looking for navigation buttons
            try:
                await page.evaluate("""
                    const modal = document.querySelector('.jobs-easy-apply-modal, .artdeco-modal__content, [class*="easy-apply-modal"]');
                    if (modal) modal.scrollTop = modal.scrollHeight;
                """)
                await page.wait_for_timeout(300)
            except Exception:
                pass

            # Brief wait for buttons to render before searching
            try:
                await page.wait_for_selector(
                    "button[aria-label*='Next'], button[aria-label*='Continue'], "
                    "button[aria-label*='Review'], button[aria-label='Submit application'], "
                    ".jobs-easy-apply-modal .artdeco-button--primary, "
                    "[role='dialog'] .artdeco-button--primary",
                    timeout=3000
                )
            except Exception:
                pass  # continue to try clicking anyway

            # Try Next / Review / Continue — broad selectors (LinkedIn labels change)
            nav_clicked = False

            next_btn = page.locator(
                "button[aria-label='Continue to next step'], "
                "button[aria-label='Review your application'], "
                "button[aria-label='Next'], "
                "button[aria-label='Continue'], "
                "button[aria-label='Save and continue']"
            )
            if await next_btn.count() > 0:
                try:
                    await next_btn.first.scroll_into_view_if_needed(timeout=5000)
                except Exception:
                    pass
                try:
                    await next_btn.first.click(timeout=8000)
                    await page.wait_for_timeout(1500)
                    nav_clicked = True
                except Exception:
                    pass

            # Text-based fallbacks
            if not nav_clicked:
                for btn_text in ("Review", "Next", "Continue"):
                    text_btn = page.locator(f"button:has-text('{btn_text}')")
                    if await text_btn.count() > 0:
                        try:
                            await text_btn.first.scroll_into_view_if_needed(timeout=5000)
                        except Exception:
                            pass
                        try:
                            await text_btn.first.click(timeout=8000)
                            await page.wait_for_timeout(1500)
                            nav_clicked = True
                        except Exception:
                            pass
                        break

            # CSS primary button fallback
            if not nav_clicked:
                footer_primary = page.locator(
                    ".jobs-easy-apply-modal footer .artdeco-button--primary, "
                    "[role='dialog'] footer .artdeco-button--primary, "
                    ".jobs-easy-apply-modal .artdeco-button--primary, "
                    "[role='dialog'] .artdeco-button--primary"
                )
                if await footer_primary.count() > 0:
                    try:
                        btn_label = await footer_primary.first.get_attribute("aria-label") or await footer_primary.first.inner_text()
                        print(f"[filler] using primary button fallback: '{btn_label.strip()}'")
                    except Exception:
                        pass
                    try:
                        await footer_primary.first.scroll_into_view_if_needed(timeout=5000)
                    except Exception:
                        pass
                    try:
                        await footer_primary.first.click(timeout=8000)
                        await page.wait_for_timeout(1500)
                        nav_clicked = True
                    except Exception:
                        pass

            # JS click as last resort — bypasses all Playwright selector/state checks
            if not nav_clicked:
                try:
                    clicked = await page.evaluate("""() => {
                        const modal = document.querySelector(
                            '.jobs-easy-apply-modal, [data-test-modal-id="easy-apply-modal"], [role="dialog"]'
                        );
                        if (!modal) return null;
                        const btn = modal.querySelector(
                            '.artdeco-button--primary:not([disabled]):not(.artdeco-button--disabled)'
                        );
                        if (!btn) return null;
                        btn.click();
                        return (btn.getAttribute('aria-label') || btn.innerText || 'unknown').trim().slice(0, 60);
                    }""")
                    if clicked:
                        print(f"[filler] JS click fallback succeeded: '{clicked}'")
                        await page.wait_for_timeout(1500)
                        nav_clicked = True
                except Exception as e:
                    print(f"[filler] JS click fallback error: {e}")

            if nav_clicked:
                continue

            # Nothing found — log visible buttons for diagnosis then bail
            try:
                btns = await page.evaluate("""() =>
                    Array.from(document.querySelectorAll('button')).slice(0, 20).map(b =>
                        (b.getAttribute('aria-label') || b.innerText || '').trim().slice(0, 60)
                    ).filter(Boolean)
                """)
                print(f"[filler] no navigation button at step {step} — visible buttons: {btns}")
            except Exception:
                print(f"[filler] no navigation button found at step {step}")
            break

        return "failed", "no navigation button found", all_unknown

    except PWTimeout:
        print(f"[filler] timeout on {url}")
        return "failed", "timeout", all_unknown
    except Exception as e:
        print(f"[filler] error on {url}: {e}")
        return "failed", str(e)[:200], all_unknown
    finally:
        try:
            os.unlink(pdf_path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Log to Supabase
# ---------------------------------------------------------------------------

def log_application(job_id: str, status: str, resume_pdf_url: str = "", error: str = ""):
    try:
        # Delete any previous attempt for this job (skipped/failed) then insert fresh
        supabase_admin.table("applications").delete().eq("job_id", job_id).execute()
        supabase_admin.table("applications").insert({
            "job_id":         job_id,
            "status":         status,
            "resume_pdf_url": resume_pdf_url,
            "error_message":  error,
            "applied_at":     datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        print(f"[filler] log error: {e}")


def log_unknown_questions(job_id: str, unknowns: list[UnknownQuestion]):
    """Log unrecognised form field labels to the database for user review.
    Preserves rows that the user has already answered to avoid asking again."""
    if not unknowns:
        return
    try:
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            {
                "job_id":         job_id,
                "question_label": q.label,
                "field_type":     q.field_type,
                "options":        q.options,
                "answer":         None,
                "detected_at":    now,
            }
            for q in unknowns
            if q.label.strip()
        ]
        if not rows:
            return

        # Fetch labels that already have user-provided answers for this job
        answered_resp = supabase_admin.table("unknown_questions") \
            .select("question_label") \
            .eq("job_id", job_id) \
            .not_("answer", "is", "null") \
            .execute()
        answered_labels = {r["question_label"] for r in (answered_resp.data or [])}

        # Delete only unanswered rows for this job (preserve user answers)
        supabase_admin.table("unknown_questions") \
            .delete() \
            .eq("job_id", job_id) \
            .is_("answer", "null") \
            .execute()

        # Only insert questions that don't already have a user-provided answer
        new_rows = [r for r in rows if r["question_label"] not in answered_labels]
        if new_rows:
            supabase_admin.table("unknown_questions").insert(new_rows).execute()
            print(f"[filler] logged {len(new_rows)} unknown question(s) for {job_id}")
    except Exception as e:
        print(f"[filler] unknown_questions log error: {e}")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def run_filler(test_limit: int = None, job_id: str = None, retry_skipped: bool = False):
    # Apply to jobs using local resumes (no tailoring, no builder step required)
    # Order newest first so fresh jobs are tried before stale old ones
    all_jobs = supabase.table("jobs").select("*").order("created_at", desc=True).execute().data
    all_applications = supabase.table("applications").select("job_id, status").execute().data

    # 'applied' and 'captcha_blocked' are truly done; 'skipped' means confirmed stale — don't retry (unless retry_skipped=True)
    if retry_skipped:
        done_ids = {r["job_id"] for r in all_applications if r["status"] in ("applied", "captcha_blocked")}
    else:
        done_ids = {r["job_id"] for r in all_applications if r["status"] in ("applied", "captcha_blocked", "skipped")}

    if job_id:
        # Single job mode — always retry regardless of status
        pending = [j for j in all_jobs if j["job_id"] == job_id]
    else:
        # Jobs that haven't been successfully applied to yet
        pending = [j for j in all_jobs if j["job_id"] not in done_ids]

    if test_limit:
        pending = pending[:test_limit]

    if not pending:
        print("[filler] no pending jobs to apply to")
        return

    print(f"[filler] applying to {len(pending)} jobs")

    # Load answers fresh from Supabase profile
    answers = load_answers()
    print(f"[filler] loaded {len(answers)} screening answers from profile")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=_HEADLESS,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-extensions",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
        )
        # Mask automation fingerprints
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
            window.chrome = { runtime: {} };
        """)
        page = await context.new_page()

        try:
            await login(context, page)

            for job in pending:
                jid     = job["job_id"]
                title   = job["title"]
                company = job["company"]
                print(f"\n[filler] applying: {company} — {title}")

                # If browser/page crashed, restart it
                try:
                    if not browser.is_connected():
                        raise Exception("browser disconnected")
                    page.url  # quick liveness check
                except Exception:
                    print("[filler] browser crashed — restarting...")
                    try:
                        await browser.close()
                    except Exception:
                        pass
                    browser = await p.chromium.launch(
                        headless=_HEADLESS,
                        args=[
                            "--start-maximized",
                            "--disable-blink-features=AutomationControlled",
                            "--disable-infobars",
                            "--disable-extensions",
                        ],
                    )
                    context = await browser.new_context(
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0.0.0 Safari/537.36"
                        )
                    )
                    page = await context.new_page()
                    await login(context, page)

                status, reason, unknowns = await apply_to_job(page, job, answers)

                log_application(
                    job_id=jid,
                    status=status,
                    resume_pdf_url="",
                    error=reason,
                )
                log_unknown_questions(job_id=jid, unknowns=unknowns)
                print(f"[filler] {jid} -> {status}" + (f" ({reason})" if reason else ""))

                if status == "captcha_blocked":
                    print("[filler] stopping — captcha encountered")
                    break

                # Polite delay between applications
                delay = random.uniform(APPLY_DELAY_MIN, APPLY_DELAY_MAX)
                print(f"[filler] waiting {delay:.1f}s before next application...")
                await asyncio.sleep(delay)

        finally:
            try:
                await browser.close()
            except Exception:
                pass
            print("[filler] browser closed")

    print("[filler] done")


if __name__ == "__main__":
    import sys
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg == "--retry-skipped":
        # Retry N most recent skipped jobs
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        asyncio.run(run_filler(test_limit=limit, retry_skipped=True))
    elif arg and arg.startswith("li-"):
        asyncio.run(run_filler(job_id=arg))
    else:
        asyncio.run(run_filler(test_limit=int(arg) if arg else None))
