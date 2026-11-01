"""Small local JSON stores. No passwords or session cookies belong here."""

import json
from datetime import datetime, timezone
from pathlib import Path

from question_types import needs_manual_action

ROOT = Path(__file__).resolve().parent
ANSWERS_PATH = ROOT / "answers.json"
HISTORY_PATH = ROOT / "application_history.json"


def _read(path: Path, fallback):
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, type(fallback)) else fallback
    except (OSError, ValueError):
        return fallback


def _write(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
    temporary.replace(path)


def load_answers() -> dict[str, str]:
    raw = _read(ANSWERS_PATH, {})
    clean = {str(k): str(v) for k, v in raw.items() if str(k).strip() and str(v).strip() and not needs_manual_action(str(k))}
    if len(clean) != len(raw):
        try:
            _write(ANSWERS_PATH, clean)
        except OSError:
            pass
    return clean


def save_answer(question: str, answer: str) -> None:
    if needs_manual_action(question):
        raise ValueError("Login details and file uploads cannot be saved as reusable answers.")
    answers = load_answers()
    answers[question.strip()] = answer.strip()
    _write(ANSWERS_PATH, answers)


def delete_answer(question: str) -> None:
    answers = load_answers()
    answers.pop(question, None)
    _write(ANSWERS_PATH, answers)


def load_history() -> list[dict]:
    return [item for item in _read(HISTORY_PATH, []) if isinstance(item, dict)]


def save_result(url: str, title: str, result: dict) -> None:
    history = load_history()
    run_id = result.get("run_id")
    if run_id and any(item.get("run_id") == run_id for item in history):
        return
    history.append({
        "url": url,
        "title": title,
        "outcome": result.get("outcome", "failed"),
        "summary": result.get("summary", ""),
        "confirmation": result.get("confirmation", ""),
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    _write(HISTORY_PATH, history)
