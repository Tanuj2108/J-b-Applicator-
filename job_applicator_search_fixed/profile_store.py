"""Local, single-user profile storage for the hackathon demo."""

import json
from pathlib import Path

PROFILE_PATH = Path(__file__).resolve().parent / "profile.json"
PROFILE_FIELDS = (
    "first_name", "last_name", "email", "phone", "address", "city", "state", "postal_code", "country",
    "linkedin", "experience", "role", "bio", "skills", "job_type", "salary_min", "salary_max",
    "salary_currency", "work_mode", "earliest_start", "branch_of_study", "graduation_year",
    "highest_qualification", "resume_text", "cover_letter_notes", "company_career_urls",
)


def empty_profile() -> dict[str, str]:
    return {field: "" for field in PROFILE_FIELDS}


def load_profile() -> dict[str, str]:
    if not PROFILE_PATH.exists():
        return empty_profile()
    try:
        with PROFILE_PATH.open(encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return empty_profile()
    except (OSError, ValueError):
        return empty_profile()
    profile = {
        field: str(data.get(field) or "").strip()
        for field in PROFILE_FIELDS
    }
    # Preserve a profile created by the first version of the app.
    if not profile["first_name"] and data.get("name"):
        first, _, last = str(data["name"]).strip().partition(" ")
        profile["first_name"], profile["last_name"] = first, last
    if not profile["salary_min"] and data.get("salary_range"):
        import re
        old_range = str(data["salary_range"])
        values = re.findall(r"\d+(?:\.\d+)?", old_range)
        if len(values) >= 2:
            multiplier = 100000 if re.search(r"\b(?:lpa|lakhs?)\b", old_range, re.I) else 1
            profile["salary_min"], profile["salary_max"] = [str(int(float(value) * multiplier)) for value in values[:2]]
    return profile


def save_profile(profile: dict[str, str]) -> dict[str, str]:
    clean = {field: str(profile.get(field) or "").strip() for field in PROFILE_FIELDS}
    temporary = PROFILE_PATH.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(clean, handle, indent=2, ensure_ascii=False)
    temporary.replace(PROFILE_PATH)
    return clean


def clear_profile() -> None:
    PROFILE_PATH.unlink(missing_ok=True)
