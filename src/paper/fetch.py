"""Download open-access paper content."""

from __future__ import annotations

from typing import Optional

import httpx

from src.config import CONTACT_EMAIL
from src.models import Paper
from src.paper.extract import extract_text_from_html, extract_text_from_pdf

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


def fetch_paper_text(paper: Paper) -> str:
    """Fetch full text for a paper. Falls back to abstract if download fails."""
    urls = []
    for u in (paper.pdf_url, paper.url):
        if u and u not in urls:
            urls.append(u)
    if paper.doi:
        doi_url = f"https://doi.org/{paper.doi}"
        if doi_url not in urls:
            urls.append(doi_url)
        # Unpaywall
        oa = _unpaywall_url(paper.doi)
        if oa and oa not in urls:
            urls.insert(0, oa)

    errors: list[str] = []
    with httpx.Client(
        timeout=45.0, headers=_HEADERS, follow_redirects=True
    ) as client:
        for url in urls:
            try:
                text = _download_and_extract(client, url)
                if text and len(text) > 200:
                    return text
                if text:
                    errors.append(f"short content from {url}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{url}: {exc}")

    # Fallback: title + abstract so chat still works
    fallback = "\n\n".join(
        part
        for part in (
            f"Title: {paper.title}",
            f"Authors: {paper.authors}" if paper.authors else "",
            f"Year: {paper.year}" if paper.year else "",
            f"Abstract:\n{paper.abstract}" if paper.abstract else "",
            "(Full text could not be downloaded; answering from metadata/abstract only.)",
        )
        if part
    )
    if not paper.abstract and not paper.title:
        raise RuntimeError(
            "Could not download paper text. "
            + ("; ".join(errors[:3]) if errors else "No URLs available.")
        )
    return fallback


def _download_and_extract(client: httpx.Client, url: str) -> str:
    resp = client.get(url)
    resp.raise_for_status()
    ctype = (resp.headers.get("content-type") or "").lower()
    content = resp.content

    if (
        "pdf" in ctype
        or url.lower().endswith(".pdf")
        or content[:4] == b"%PDF"
    ):
        return extract_text_from_pdf(content)

    # HTML
    text = extract_text_from_html(resp.text)
    # Sometimes HTML page links to PDF
    if len(text) < 500:
        pdf_link = _find_pdf_link(resp.text, str(resp.url))
        if pdf_link:
            pdf_resp = client.get(pdf_link)
            pdf_resp.raise_for_status()
            return extract_text_from_pdf(pdf_resp.content)
    return text


def _find_pdf_link(html: str, base_url: str) -> Optional[str]:
    from urllib.parse import urljoin
    import re

    # common patterns
    patterns = [
        r'href=["\']([^"\']+\.pdf[^"\']*)["\']',
        r'content=["\']([^"\']+\.pdf[^"\']*)["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html, flags=re.IGNORECASE)
        if m:
            return urljoin(base_url, m.group(1))
    return None


def _unpaywall_url(doi: str) -> Optional[str]:
    try:
        with httpx.Client(timeout=15.0, headers=_HEADERS) as client:
            resp = client.get(
                f"https://api.unpaywall.org/v2/{doi}",
                params={"email": CONTACT_EMAIL},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            best = data.get("best_oa_location") or {}
            return best.get("url_for_pdf") or best.get("url")
    except Exception:
        return None
