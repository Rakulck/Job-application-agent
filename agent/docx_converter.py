"""Convert DOCX resume files to the standard JSON resume format."""

import re
import json
from docx import Document
from typing import Dict, List, Any


def extract_text_from_docx(docx_path: str) -> str:
    """Extract all text from a DOCX file, preserving structure."""
    try:
        doc = Document(docx_path)
        lines = []
        for para in doc.paragraphs:
            if para.text.strip():
                lines.append(para.text.strip())
        return "\n".join(lines)
    except Exception as e:
        raise ValueError(f"Failed to read DOCX file: {e}")


def parse_resume_docx(docx_path: str) -> Dict[str, Any]:
    """
    Convert a DOCX resume to the standard JSON format.

    Returns a resume dict with structure:
    {
        "name": str,
        "email": str,
        "phone": str,
        "linkedin": str,
        "portfolio": str,
        "github": str,
        "location": str,
        "summary": str,
        "skills": [str, ...],
        "experience": [...],
        "education": [...]
    }
    """
    text = extract_text_from_docx(docx_path)
    lines = text.split("\n")

    # Initialize resume structure with defaults
    resume = {
        "name": "Unknown",
        "email": "",
        "phone": "",
        "linkedin": "",
        "portfolio": "",
        "github": "",
        "location": "",
        "summary": "",
        "skills": [],
        "experience": [],
        "education": []
    }

    # Extract contact info from first 20 lines
    for line in lines[:20]:
        line_lower = line.lower()

        # Email
        if not resume["email"]:
            email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", line)
            if email_match:
                resume["email"] = email_match.group()

        # Phone
        if not resume["phone"]:
            phone_match = re.search(r"\+?1?\s*\(?(\d{3})\)?[\s\.-]?(\d{3})[\s\.-]?(\d{4})", line)
            if phone_match:
                resume["phone"] = phone_match.group().strip()

        # LinkedIn
        if not resume["linkedin"]:
            linkedin_match = re.search(
                r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-]+",
                line,
                re.I
            )
            if linkedin_match:
                resume["linkedin"] = linkedin_match.group()

        # GitHub
        if not resume["github"]:
            github_match = re.search(
                r"(?:https?://)?(?:www\.)?github\.com/[\w\-]+",
                line,
                re.I
            )
            if github_match:
                resume["github"] = github_match.group()

        # Portfolio
        if not resume["portfolio"]:
            if "portfolio" in line_lower:
                url_match = re.search(r"(?:https?://)?[\w\-]+\.(?:com|io|dev|net)", line)
                if url_match:
                    resume["portfolio"] = url_match.group()

    # Extract name (first non-empty line that's not contact info)
    for line in lines[:5]:
        if line.strip() and "@" not in line and "+" not in line:
            resume["name"] = line.strip()
            break

    # Parse sections
    current_section = None
    summary_lines = []
    skill_lines = []
    experience_entries = []
    current_experience = None
    education_entries = []
    current_education = None

    for i, line in enumerate(lines):
        line_clean = line.strip()
        if not line_clean:
            continue

        # Detect section headers
        if re.match(r"^(SUMMARY|PROFESSIONAL SUMMARY|OBJECTIVE|ABOUT)", line_clean, re.I):
            current_section = "summary"
            continue
        elif re.match(r"^(SKILLS|TECHNICAL SKILLS|CORE COMPETENCIES|TECHNOLOGIES)", line_clean, re.I):
            current_section = "skills"
            continue
        elif re.match(r"^(EXPERIENCE|PROFESSIONAL EXPERIENCE|WORK EXPERIENCE|EMPLOYMENT)", line_clean, re.I):
            current_section = "experience"
            current_experience = None
            continue
        elif re.match(r"^(EDUCATION|ACADEMIC BACKGROUND|CERTIFICATIONS)", line_clean, re.I):
            current_section = "education"
            current_education = None
            continue

        # Parse content by section
        if current_section == "summary":
            if line_clean and not re.match(r"^(SUMMARY|PROFESSIONAL SUMMARY|OBJECTIVE|ABOUT|SKILLS|EXPERIENCE|EDUCATION)", line_clean, re.I):
                summary_lines.append(line_clean)

        elif current_section == "skills":
            # Extract skills (comma-separated, bullet points, or single skills)
            if re.match(r"^[-•*]\s+", line_clean):
                skill = re.sub(r"^[-•*]\s+", "", line_clean).strip()
                if skill:
                    skill_lines.append(skill)
            elif "," in line_clean:
                for skill in line_clean.split(","):
                    s = skill.strip()
                    if s:
                        skill_lines.append(s)
            elif not re.match(r"^[A-Z]+", line_clean) and len(line_clean) < 100:
                skill_lines.append(line_clean)

        elif current_section == "experience":
            if re.match(r"^[-•*]\s+", line_clean):
                # Bullet point under current experience
                if current_experience:
                    bullet = re.sub(r"^[-•*]\s+", "", line_clean).strip()
                    if bullet:
                        current_experience["bullets"].append(bullet)
            else:
                # Could be company, title, or dates
                if not current_experience:
                    current_experience = {
                        "company": line_clean,
                        "title": "",
                        "location": "",
                        "start_date": "",
                        "end_date": "",
                        "bullets": []
                    }
                elif not current_experience["title"]:
                    current_experience["title"] = line_clean
                else:
                    # New experience entry
                    if current_experience["company"]:
                        experience_entries.append(current_experience)
                    current_experience = {
                        "company": line_clean,
                        "title": "",
                        "location": "",
                        "start_date": "",
                        "end_date": "",
                        "bullets": []
                    }

        elif current_section == "education":
            if not current_education:
                current_education = {
                    "school": line_clean,
                    "degree": "",
                    "location": "",
                    "graduation": ""
                }
                education_entries.append(current_education)
            elif not current_education["degree"]:
                current_education["degree"] = line_clean
            else:
                # Try to extract graduation date
                if re.search(r"\b(?:20\d{2}|May|June|July|August|September|December|January|February|March|April)\b", line_clean):
                    current_education["graduation"] = line_clean.strip()

    # Finalize current entries
    if current_experience and current_experience.get("company"):
        experience_entries.append(current_experience)

    # Set parsed values
    resume["summary"] = " ".join(summary_lines).strip()
    resume["skills"] = [s for s in skill_lines if s and len(s) > 1][:50]  # Limit to 50
    resume["experience"] = experience_entries
    resume["education"] = education_entries

    return resume


def docx_to_json(docx_path: str) -> Dict[str, Any]:
    """
    Main entry point: convert DOCX resume to JSON format.

    Args:
        docx_path: Path to the DOCX file

    Returns:
        Resume dict in standard JSON format
    """
    return parse_resume_docx(docx_path)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print(json.dumps({"error": "Usage: python docx_converter.py <path_to_docx>"}))
        sys.exit(1)

    docx_path = sys.argv[1]
    result = docx_to_json(docx_path)
    print(json.dumps(result))
