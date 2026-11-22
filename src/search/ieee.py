"""IEEE Access open-access paper search."""

from __future__ import annotations

import re
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import CONTACT_EMAIL, IEEE_API_KEY
from src.models import Paper

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def search_ieee(
    query: str,
    *,
    year: Optional[int] = None,
    limit: int = 10,
) -> list[Paper]:
    if not query.strip():
        return []

    if IEEE_API_KEY:
        try:
            return _search_ieee_api(query, year=year, limit=limit)
        except Exception:
            pass

    try:
        return _search_crossref_ieee_access(query, year=year, limit=limit)
    except Exception:
        return []


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4), reraise=True)
def _search_ieee_api(query: str, *, year: Optional[int], limit: int) -> list[Paper]:
    params: dict = {
        "apikey": IEEE_API_KEY,
        "querytext": query,
        "publication_title": "IEEE Access",
        "open_access": "True",
        "max_records": min(limit * 2, 25),
        "start_record": 1,
        "sort_field": "publication_year",
        "sort_order": "desc",
    }
    if year is not None:
        params["start_year"] = year
        params["end_year"] = year

    with httpx.Client(timeout=30.0, headers=_HEADERS) as client:
        resp = client.get(
            "https://ieeexploreapi.ieee.org/api/v1/search/articles",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()

    papers: list[Paper] = []
    for item in data.get("articles") or []:
        authors = _format_ieee_authors(item.get("authors"))
        pdf_url = item.get("pdf_url") or ""
        html_url = item.get("html_url") or ""
        abstract_url = item.get("abstract_url") or ""
        doi = item.get("doi") or ""
        url = html_url or abstract_url
        if not url and doi:
            url = f"https://doi.org/{doi}"
        if not pdf_url and doi:
            # IEEE OA often available via Xplore document page
            pdf_url = ""

        year_val = None
        py = item.get("publication_year") or item.get("publication_date")
        if py:
            m = re.search(r"(19|20)\d{2}", str(py))
            if m:
                year_val = int(m.group(0))

        papers.append(
            Paper(
                title=(item.get("title") or "").strip(),
                authors=authors,
                year=year_val,
                abstract=(item.get("abstract") or "").strip(),
                source="IEEE Access",
                url=url or "",
                pdf_url=pdf_url,
                doi=doi,
            )
        )
        if len(papers) >= limit:
            break
    return papers


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4), reraise=True)
def _search_crossref_ieee_access(
    query: str, *, year: Optional[int], limit: int
) -> list[Paper]:
    """Fallback: Crossref restricted to IEEE Access + Unpaywall OA PDF."""
    filters = ["container-title:IEEE Access"]
    if year is not None:
        filters.append(f"from-pub-date:{year}")
        filters.append(f"until-pub-date:{year}")

    params = {
        "query": query,
        "filter": ",".join(filters),
        "rows": min(limit * 3, 30),
        "select": "DOI,title,author,published-print,published-online,abstract,URL,container-title,link",
        "mailto": CONTACT_EMAIL,
    }

    with httpx.Client(timeout=30.0, headers=_HEADERS) as client:
        resp = client.get("https://api.crossref.org/works", params=params)
        resp.raise_for_status()
        items = (resp.json().get("message") or {}).get("items") or []

        papers: list[Paper] = []
        for item in items:
            titles = item.get("title") or []
            title = titles[0].strip() if titles else ""
            if not title:
                continue
            container = " ".join(item.get("container-title") or []).lower()
            if "ieee access" not in container and "ieee access" not in title.lower():
                # Crossref filter is soft; enforce
                if "ieee" not in container:
                    continue

            doi = item.get("DOI") or ""
            authors = _format_crossref_authors(item.get("author") or [])
            year_val = _crossref_year(item)
            abstract = _strip_jats(item.get("abstract") or "")
            url = item.get("URL") or (f"https://doi.org/{doi}" if doi else "")

            pdf_url = _pdf_from_crossref_links(item.get("link") or [])
            if not pdf_url and doi:
                pdf_url = _unpaywall_pdf(client, doi) or ""

            # IEEE Access is an open-access journal; keep DOI hits even without PDF yet
            if not doi and not pdf_url:
                continue

            papers.append(
                Paper(
                    title=title,
                    authors=authors,
                    year=year_val,
                    abstract=abstract,
                    source="IEEE Access",
                    url=url,
                    pdf_url=pdf_url or "",
                    doi=doi,
                )
            )
            if len(papers) >= limit:
                break

        # Second pass: fill missing PDFs via Unpaywall
        for paper in papers:
            if paper.pdf_url or not paper.doi:
                continue
            pdf = _unpaywall_pdf(client, paper.doi)
            if pdf:
                paper.pdf_url = pdf
        return papers


def _unpaywall_pdf(client: httpx.Client, doi: str) -> Optional[str]:
    try:
        resp = client.get(
            f"https://api.unpaywall.org/v2/{doi}",
            params={"email": CONTACT_EMAIL},
            timeout=15.0,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        best = data.get("best_oa_location") or {}
        return best.get("url_for_pdf") or best.get("url") or None
    except Exception:
        return None


def _pdf_from_crossref_links(links: list) -> str:
    for link in links:
        if not isinstance(link, dict):
            continue
        ctype = (link.get("content-type") or "").lower()
        url = link.get("URL") or ""
        if "pdf" in ctype or url.lower().endswith(".pdf"):
            return url
    return ""


def _format_ieee_authors(authors_field) -> str:
    if not authors_field:
        return ""
    if isinstance(authors_field, dict):
        authors = authors_field.get("authors") or []
    elif isinstance(authors_field, list):
        authors = authors_field
    else:
        return str(authors_field)
    names = []
    for a in authors:
        if isinstance(a, dict):
            names.append(a.get("full_name") or a.get("author_name") or "")
        else:
            names.append(str(a))
    return ", ".join(n for n in names if n)


def _format_crossref_authors(authors: list) -> str:
    names = []
    for a in authors:
        if not isinstance(a, dict):
            continue
        given = a.get("given") or ""
        family = a.get("family") or ""
        name = f"{given} {family}".strip()
        if name:
            names.append(name)
    return ", ".join(names)


def _crossref_year(item: dict) -> Optional[int]:
    for key in ("published-print", "published-online", "created"):
        part = item.get(key) or {}
        date_parts = part.get("date-parts") or []
        if date_parts and date_parts[0]:
            try:
                return int(date_parts[0][0])
            except (TypeError, ValueError, IndexError):
                continue
    return None


def _strip_jats(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()
