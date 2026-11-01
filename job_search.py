"""Search LinkedIn first, then only company career domains supplied by the user."""

import re
from urllib.parse import urlsplit, urlunsplit

BLOCKED_HOSTS = {
    "instagram.com", "youtube.com", "youtu.be", "tiktok.com", "facebook.com",
    "x.com", "twitter.com", "reddit.com", "indeed.com", "glassdoor.com",
}


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def _within(host: str, allowed: str) -> bool:
    return host == allowed or host.endswith("." + allowed)


def company_domains(raw: str) -> list[str]:
    domains = []
    for line in raw.splitlines():
        value = line.strip()
        if not value:
            continue
        if not value.startswith("https://"):
            raise ValueError("Company career links must start with https://.")
        host = _host(value)
        if not host or "." not in host or any(_within(host, blocked) for blocked in BLOCKED_HOSTS):
            raise ValueError(f"Enter an official company career link, not {value!r}.")
        if host not in domains:
            domains.append(host)
    return domains


def allowed_application_url(url: str, profile: dict[str, str]) -> bool:
    host = _host(url)
    if not url.startswith("https://"):
        return False
    if _within(host, "linkedin.com"):
        return "/jobs/" in urlsplit(url).path.lower()
    return any(_within(host, domain) for domain in company_domains(profile.get("company_career_urls", "")))


def _canonical(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def _annual_pay(text: str, currency: str) -> tuple[float, float] | None:
    """Recognize only explicit yearly figures; other salary formats stay unverified."""
    if currency == "INR":
        match = re.search(r"(?:₹\s*)?(\d+(?:\.\d+)?)\s*(?:-|to|–)\s*(?:₹\s*)?(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?\s*(?:per\s*annum|a\s*year))", text, re.I)
        if match:
            return float(match[1]) * 100000, float(match[2]) * 100000
    symbols = {"USD": r"\$", "GBP": "£", "EUR": "€", "INR": "₹"}
    symbol = symbols.get(currency)
    if symbol:
        match = re.search(rf"{symbol}\s*([\d,]+)\s*(?:-|to|–)\s*{symbol}?\s*([\d,]+)\s*(?:per\s*year|/year|annually|p\.a\.)", text, re.I)
        if match:
            return float(match[1].replace(",", "")), float(match[2].replace(",", ""))
    return None


def _job_title_from_url(url: str) -> str:
    slug = urlsplit(url).path.rsplit("/", 1)[-1]
    slug = re.sub(r"-\d+$", "", slug)
    return slug.replace("-at-", " at ").replace("-", " ").strip().title() or "LinkedIn job"


def search_jobs(profile: dict[str, str], api_key: str, limit: int = 12) -> list[dict[str, str]]:
    from tinyfish import TinyFish

    role = profile["role"].strip()
    city = profile["city"].strip()
    kind = profile["job_type"].strip()
    mode = profile.get("work_mode", "").strip()
    currency = profile.get("salary_currency", "INR")
    minimum = float(profile["salary_min"])
    maximum = float(profile["salary_max"])
    company_hosts = company_domains(profile.get("company_career_urls", ""))
    client = TinyFish(api_key=api_key)
    found: dict[str, dict] = {}

    def add(url: str, title: str, snippet: str, source: str, applyable: bool = True) -> None:
        if not url.startswith("https://") or not allowed_application_url(url, profile):
            return
        canonical = _canonical(url)
        if canonical in found:
            return
        text = f"{title} {snippet}"
        pay = _annual_pay(text, currency)
        if pay and (pay[1] < minimum or pay[0] > maximum):
            return
        words = set(re.findall(r"[a-z0-9]+", role.lower())) - {"and", "the", "for"}
        score = sum(3 for word in words if word in text.lower())
        score += 2 if city and city.lower() in text.lower() else 0
        score += 2 if source == "LinkedIn" else 0
        found[canonical] = {
            "title": title, "url": canonical, "snippet": snippet[:500], "score": score,
            "salary_status": "In range" if pay else "Salary not verified",
            "source": source, "applyable": applyable,
        }

    # Broad search finds LinkedIn job category pages. Fetch exposes their individual /jobs/view links.
    terms = " ".join(x for x in (role, kind, city, mode) if x)
    response = client.search.query(terms, include_domains="linkedin.com")
    category_pages = []
    individual_links = []
    for item in getattr(response, "results", []) or []:
        url = str(getattr(item, "url", "") or "")
        if not allowed_application_url(url, profile):
            continue
        if "/jobs/view/" in urlsplit(url).path.lower():
            individual_links.append(url)
            add(url, str(getattr(item, "title", "") or _job_title_from_url(url)), str(getattr(item, "snippet", "") or ""), "LinkedIn")
        elif len(category_pages) < 2:
            category_pages.append(url)
    if category_pages:
        try:
            pages = client.fetch.get_contents(category_pages, format="markdown", links=True, image_links=False, per_url_timeout_ms=30000)
            for page in getattr(pages, "results", []) or []:
                for link in getattr(page, "links", []) or []:
                    if "/jobs/view/" in urlsplit(link).path.lower() and allowed_application_url(link, profile):
                        individual_links.append(link)
        except Exception:
            pass  # Show the LinkedIn category page as a fallback below.
    seen = set()
    detail_urls = []
    for url in individual_links:
        canonical = _canonical(url)
        if canonical not in seen:
            seen.add(canonical)
            detail_urls.append(canonical)
        if len(detail_urls) >= limit:
            break
    fetched_urls = set()
    if detail_urls:
        try:
            details = client.fetch.get_contents(detail_urls[:10], format="markdown", links=False, image_links=False, per_url_timeout_ms=30000)
            for page in getattr(details, "results", []) or []:
                url = str(getattr(page, "url", "") or "")
                fetched_urls.add(_canonical(url))
                title = str(getattr(page, "title", "") or _job_title_from_url(url))
                snippet = str(getattr(page, "description", "") or "")
                if not snippet:
                    snippet = str(getattr(page, "text", "") or "")[:500]
                found.pop(_canonical(url), None)
                add(url, title, snippet, "LinkedIn")
        except Exception:
            pass
    for url in detail_urls:
        if _canonical(url) not in fetched_urls:
            add(url, _job_title_from_url(url), "Open the listing to verify details.", "LinkedIn")
    if not found and category_pages:
        url = category_pages[0]
        add(url, "Browse LinkedIn jobs", "TinyFish found a job results page, but could not extract individual listings.", "LinkedIn", applyable=False)

    for domain in company_hosts:
        response = client.search.query(f"{role} {kind} {city} careers", include_domains=domain)
        for item in getattr(response, "results", []) or []:
            url = str(getattr(item, "url", "") or "")
            if _within(_host(url), domain):
                add(url, str(getattr(item, "title", "") or url), str(getattr(item, "snippet", "") or ""), "Company career site")
    return sorted(found.values(), key=lambda job: job["score"], reverse=True)[:limit]
