"""Separate reusable form answers from actions that need the user."""

MANUAL_TERMS = (
    "password", "credential", "sign-in", "sign in", "login", "log in", "authentication",
    "resume", "résumé", "cv", "upload", "attachment", "file", "captcha",
    "manual completion", "manual handling", "other application fields",
)


def needs_manual_action(label: str) -> bool:
    text = str(label).lower()
    return any(term in text for term in MANUAL_TERMS)


def split_missing_fields(fields: list[str] | None) -> tuple[list[str], list[str]]:
    questions, manual = [], []
    for field in fields or []:
        label = str(field).strip()
        if not label:
            continue
        (manual if needs_manual_action(label) else questions).append(label)
    return questions, manual
