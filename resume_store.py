"""Keep the original résumé file locally, separately from extracted profile text."""

import hashlib
import json
from pathlib import Path


PRIVATE_DIR = Path(__file__).resolve().parent / ".private"
INFO_PATH = PRIVATE_DIR / "resume.json"
MAX_BYTES = 10 * 1024 * 1024


def save_resume(filename: str, content: bytes) -> dict[str, str | int]:
    name = Path(filename).name
    suffix = Path(name).suffix.lower()
    if suffix not in (".pdf", ".txt"):
        raise ValueError("Choose a PDF or TXT résumé file.")
    if not content or len(content) > MAX_BYTES:
        raise ValueError("The résumé file must be between 1 byte and 10 MB.")
    if suffix == ".pdf" and not content[:1024].lstrip().startswith(b"%PDF-"):
        raise ValueError("The selected file is not a valid PDF.")
    if suffix == ".txt":
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("The TXT résumé must use UTF-8 encoding.") from exc
    PRIVATE_DIR.mkdir(mode=0o700, exist_ok=True)
    target = PRIVATE_DIR / ("resume" + suffix)
    temporary = PRIVATE_DIR / ("resume" + suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(target)
    for old_suffix in (".pdf", ".txt"):
        old = PRIVATE_DIR / ("resume" + old_suffix)
        if old != target:
            old.unlink(missing_ok=True)
    info = {"name": name, "size": len(content), "sha256": hashlib.sha256(content).hexdigest(), "suffix": suffix}
    info_tmp = PRIVATE_DIR / "resume.json.tmp"
    info_tmp.write_text(json.dumps(info, indent=2), encoding="utf-8")
    info_tmp.replace(INFO_PATH)
    return info


def load_resume_info() -> dict[str, str | int] | None:
    try:
        info = json.loads(INFO_PATH.read_text(encoding="utf-8"))
        suffix = info["suffix"]
        if suffix not in (".pdf", ".txt"):
            return None
        content = (PRIVATE_DIR / ("resume" + suffix)).read_bytes()
        if len(content) != info["size"] or hashlib.sha256(content).hexdigest() != info["sha256"]:
            return None
        return info
    except (OSError, ValueError, KeyError, TypeError):
        return None


def clear_resume() -> None:
    INFO_PATH.unlink(missing_ok=True)
    for suffix in (".pdf", ".txt"):
        (PRIVATE_DIR / ("resume" + suffix)).unlink(missing_ok=True)
