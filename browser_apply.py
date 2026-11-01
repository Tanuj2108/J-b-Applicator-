"""Start and monitor a TinyFish Browser API session that attaches the saved résumé."""

import json
import importlib.util
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from resume_store import PRIVATE_DIR, load_resume_info


VENDOR_DIR = Path(__file__).resolve().parent / ".deps"
if VENDOR_DIR.is_dir() and str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))

STATUS_PATH = PRIVATE_DIR / "browser_status.json"
REQUEST_PATH = PRIVATE_DIR / "browser_request.json"
ACTIVE_STATES = {"starting", "waiting_for_form", "file_selected", "upload_unverified"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_status(run_id: str, state: str, message: str, **extra: object) -> None:
    PRIVATE_DIR.mkdir(mode=0o700, exist_ok=True)
    current = read_status()
    if current and current.get("run_id") != run_id:
        return
    if current.get("state") == "closed":
        return
    payload = {**current, "run_id": run_id, "state": state, "message": message, "updated_at": _now(), **extra}
    temporary = STATUS_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(STATUS_PATH)


def read_status() -> dict:
    try:
        data = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _pid_running(pid: object) -> bool:
    try:
        value = int(pid)
        if value <= 0:
            return False
        if os.name == "nt":
            import ctypes

            kernel = ctypes.windll.kernel32
            handle = kernel.OpenProcess(0x1000, False, value)
            if not handle:
                return kernel.GetLastError() == 5
            try:
                exit_code = ctypes.c_ulong()
                if not kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return True
                return exit_code.value == 259
            finally:
                kernel.CloseHandle(handle)
        os.kill(value, 0)
        return True
    except PermissionError:
        return True
    except (OSError, TypeError, ValueError):
        return False


def choose_upload_input(inputs: list[dict[str, str]], suffix: str) -> int | None:
    """Pick only a clearly matching résumé control, or the sole file control."""
    compatible = []
    for index, item in enumerate(inputs):
        accept = item.get("accept", "").lower().replace(" ", "")
        if accept and "*/*" not in accept and not any(
            token in accept for token in (suffix, "application/pdf" if suffix == ".pdf" else "text/plain")
        ):
            continue
        hint = item.get("hint", "").lower()
        if any(term in hint for term in ("cover letter", "cover_letter", "coverletter", "photo", "avatar")):
            continue
        score = 1 if any(term in hint for term in ("resume", "résumé", "curriculum vitae")) else 0
        if not score and ("cv" in hint.split() or "cv_" in hint or "_cv" in hint):
            score = 1
        compatible.append((index, score))
    matches = [index for index, score in compatible if score]
    if len(matches) == 1:
        return matches[0]
    if len(compatible) == 1 and len(inputs) == 1:
        return compatible[0][0]
    return None


def launch_remote_browser(url: str, api_key: str) -> dict:
    """Open a TinyFish Browser API session in a background helper."""
    if not api_key.strip():
        raise ValueError("Add TINYFISH_API_KEY to .env and restart the app.")
    if importlib.util.find_spec("playwright") is None:
        raise ValueError("Browser support is not installed. Run: python -m pip install -r requirements.txt")
    info = load_resume_info()
    if not info:
        raise ValueError("Save a valid résumé file in the Profile tab first.")
    current = read_status()
    if current.get("mode") == "tinyfish" and current.get("state") in ACTIVE_STATES and _pid_running(current.get("pid")):
        return current
    if current.get("state") != "closed" and current.get("session_id"):
        close_remote_session(api_key, str(current["session_id"]))
    run_id = uuid.uuid4().hex
    PRIVATE_DIR.mkdir(mode=0o700, exist_ok=True)
    path = PRIVATE_DIR / ("resume" + str(info["suffix"]))
    STATUS_PATH.write_text(json.dumps({"run_id": run_id, "state": "starting", "mode": "tinyfish", "message": "Starting TinyFish browser…", "updated_at": _now()}), encoding="utf-8")
    REQUEST_PATH.write_text(json.dumps({"run_id": run_id, "url": url, "resume_path": str(path), "mode": "tinyfish"}), encoding="utf-8")
    browser_temp = PRIVATE_DIR / "browser_tmp"
    browser_temp.mkdir(mode=0o700, exist_ok=True)
    browser_env = os.environ.copy()
    browser_env.update({"TMP": str(browser_temp), "TEMP": str(browser_temp), "TMPDIR": str(browser_temp), "TINYFISH_API_KEY": api_key.strip()})
    helper = Path(__file__).resolve().parent / "tinyfish_resume_browser.py"
    try:
        proc = subprocess.Popen(
            [sys.executable, str(helper), run_id],
            cwd=str(helper.parent),
            env=browser_env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        write_status(run_id, "error", f"Could not start TinyFish browser: {exc}")
        raise
    write_status(run_id, "starting", "Starting TinyFish browser…", pid=proc.pid)
    return read_status()


def close_remote_session(api_key: str, session_id: str) -> None:
    """Stop a metered TinyFish Browser API session."""
    if not session_id or not session_id.startswith(("tf-", "br-")):
        raise ValueError("Invalid TinyFish browser session ID.")
    request = Request(
        "https://api.browser.tinyfish.ai/" + quote(session_id, safe=""),
        headers={"X-API-Key": api_key},
        method="DELETE",
    )
    with urlopen(request, timeout=20):
        pass
