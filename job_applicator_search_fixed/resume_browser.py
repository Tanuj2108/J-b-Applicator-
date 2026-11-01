"""Select the saved résumé in a browser page's file control."""

from pathlib import Path

from browser_apply import choose_upload_input


INPUT_DETAILS = """els => els.map(el => ({
  accept: el.accept || '',
  hint: [el.name, el.id, el.getAttribute('aria-label'),
    ...Array.from(el.labels || []).map(label => label.innerText),
    (el.parentElement?.innerText || '').slice(0, 160)]
    .filter(Boolean).join(' ')
}))"""


def attach_to_page(page: object, file_path: Path, original_name: str, content: bytes) -> str | None:
    inputs = page.locator('input[type="file"]')
    details = inputs.evaluate_all(INPUT_DETAILS)
    chosen = choose_upload_input(details, file_path.suffix.lower())
    if chosen is None:
        return "no_match" if details else None
    control = inputs.nth(chosen)
    mime_type = "application/pdf" if file_path.suffix.lower() == ".pdf" else "text/plain"
    control.set_input_files({"name": original_name, "mimeType": mime_type, "buffer": content}, timeout=10000)
    selected = control.evaluate("el => Array.from(el.files || []).map(f => ({name: f.name, size: f.size}))")
    if any(item.get("name") == original_name and item.get("size") == len(content) for item in selected):
        return "file_selected"
    return "upload_unverified"
