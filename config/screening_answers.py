import os
from dotenv import load_dotenv

load_dotenv()

# Fallback hardcoded answers (used if Supabase fetch fails)
ANSWERS = {
    "years_of_experience": "3",
    "work_authorization": "Yes",
    "require_sponsorship": "No",
    "expected_salary": "100000",
    "salary_expectation": "100000",
    "notice_period": "2 weeks",
    "willing_to_relocate": "Yes",
    "degree": "Bachelor's",
    "remote_preference": "Yes",
    "phone": "+1 7038593589",
    "email": "rakulck31@gmail.com",
    "name": "Rakul C Kandavel",
    "linkedin": "https://www.linkedin.com/in/rakul-c-kandavel-9011b0191/",
    "website": "https://rakulck31.vercel.app/",
    "gender": "Male",
    "ethnicity": "Asian",
    "veteran_status": "I am not a veteran",
    "disability_status": "No, I don't have a disability",
    "address_line_1": "",
    "address_line_2": "",
    "city": "",
    "state": "",
    "zip_code": "",
}

DEFAULT_ANSWER = "Yes"


def load_answers() -> dict:
    """Fetch screening answers + personal info from Supabase profile table.
    Falls back to hardcoded ANSWERS if fetch fails."""
    try:
        from supabase import create_client
        client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        row = client.table("profile").select("personal_info, screening_answers").eq("id", 1).single().execute()
        data = row.data
        if not data:
            return ANSWERS.copy()

        answers = dict(data.get("screening_answers") or {})
        personal = data.get("personal_info") or {}

        # Merge personal info fields into answers so filler can use them
        field_map = {
            "name": "name",
            "email": "email",
            "phone": "phone",
            "linkedin": "linkedin",
            "portfolio": "website",
            "address_line_1": "address_line_1",
            "address_line_2": "address_line_2",
            "city": "city",
            "state": "state",
            "zip_code": "zip_code",
        }
        for src, dst in field_map.items():
            if personal.get(src):
                answers[dst] = personal[src]

        # Fill any missing keys from hardcoded fallback
        for k, v in ANSWERS.items():
            if k not in answers:
                answers[k] = v

        return answers
    except Exception as e:
        print(f"[profile] could not load from Supabase, using defaults: {e}")
        return ANSWERS.copy()
