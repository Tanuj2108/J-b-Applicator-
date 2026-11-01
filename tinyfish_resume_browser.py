"""Attach the saved résumé in a remote TinyFish Browser API session."""

import json
import os
import sys
import time
from pathlib import Path
from urllib.request import urlopen

from browser_apply import REQUEST_PATH, close_remote_session, read_status, write_status
from resume_browser import attach_to_page
from resume_store import load_resume_info


def find_inspector_url(base_url: str) -> str:
    """Find TinyFish's live browser inspector for the application page."""
    with urlopen(base_url.rstrip("/") + "/pages", timeout=10) as response:
        pages = json.load(response)
    if not isinstance(pages, list):
        return ""
    for page in pages:
        if page.get("url") in ("", "about:blank", "about:newtab"):
            continue
        inspector = str(page.get("devtoolsFrontendUrl") or "")
        if inspector.startswith("https://"):
            return inspector
    return ""


def run_remote(url: str, file_path: Path, run_id: str, api_key: str) -> None:
    from playwright.sync_api import Error as PlaywrightError, sync_playwright
    from tinyfish import TinyFish

    info = load_resume_info()
    if not info:
        raise ValueError("The saved résumé file is missing or has changed.")
    original_name = str(info["name"])
    content = file_path.read_bytes()
    client = TinyFish(api_key=api_key, timeout=90.0)
    session = client.browser.sessions.create(url=url, timeout_seconds=900)
    session_id = session.session_id
    try:
        write_status(run_id, "starting", "TinyFish browser started. Preparing the review link…", session_id=session_id)
        inspector = ""
        for _ in range(20):
            try:
                inspector = find_inspector_url(session.base_url)
            except (OSError, ValueError):
                pass
            if inspector:
                break
            time.sleep(1)
        if inspector:
            write_status(run_id, "waiting_for_form", "Open the TinyFish browser link, then sign in or navigate to the application form.", inspector_url=inspector)
        else:
            write_status(run_id, "waiting_for_form", "TinyFish browser is open, but its review link is not ready yet. Refresh status shortly.")
        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(session.cdp_url, timeout=30000)
            try:
                context = browser.contexts[0]
                attached = False
                deadline = time.monotonic() + 1800
                last_inspector_check = 0.0
                while browser.is_connected() and time.monotonic() < deadline:
                    if not inspector and time.monotonic() - last_inspector_check > 5:
                        last_inspector_check = time.monotonic()
                        try:
                            inspector = find_inspector_url(session.base_url)
                            if inspector:
                                write_status(run_id, "waiting_for_form", "Open the TinyFish browser link, then sign in or navigate to the application form.", inspector_url=inspector)
                        except (OSError, ValueError):
                            pass
                    if not attached:
                        for page in context.pages:
                            if page.is_closed():
                                continue
                            try:
                                outcome = attach_to_page(page, file_path, original_name, content)
                                if outcome is None:
                                    continue
                                if outcome == "no_match":
                                    message = "File controls are present, but none clearly accepts this résumé. Use the TinyFish browser link to select the correct control yourself."
                                    if read_status().get("message") != message:
                                        write_status(run_id, "waiting_for_form", message)
                                    continue
                                if outcome == "file_selected":
                                    write_status(run_id, "file_selected", "Résumé selected in the TinyFish browser. Check that the job site accepted it before submitting.")
                                else:
                                    write_status(run_id, "upload_unverified", "Résumé was sent to the file control, but the site cleared it. Check the filename on the page before submitting.")
                                attached = True
                                break
                            except PlaywrightError:
                                continue
                    try:
                        if context.pages:
                            context.pages[0].wait_for_timeout(1000)
                        else:
                            time.sleep(1)
                    except PlaywrightError:
                        if not browser.is_connected():
                            break
                        time.sleep(1)
            finally:
                if browser.is_connected():
                    browser.close()
    finally:
        try:
            close_remote_session(api_key, session_id)
            write_status(run_id, "closed", "TinyFish browser session closed. The app did not click Submit.")
        except Exception as exc:
            write_status(run_id, "error", f"TinyFish browser may still be running. Close session {session_id} in the TinyFish dashboard. {type(exc).__name__}: {exc}")


def main() -> None:
    if len(sys.argv) != 2:
        return
    run_id = sys.argv[1]
    try:
        request = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
        if request.get("run_id") != run_id or request.get("mode") != "tinyfish":
            raise ValueError("Browser request was replaced before it started.")
        api_key = os.getenv("TINYFISH_API_KEY", "").strip()
        if not api_key:
            raise ValueError("TinyFish API key is not available to the browser helper.")
        run_remote(str(request["url"]), Path(request["resume_path"]), run_id, api_key)
    except Exception as exc:
        write_status(run_id, "error", f"TinyFish browser attachment failed: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
