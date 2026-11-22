"""Google Scholar open-access paper search."""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import CONTACT_EMAIL, SERPAPI_KEY
from src.models import Paper

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def search_scholar(
    query: str,
    *,
    year: Optional[int] = None,
    limit: int = 10,
) -> list[Paper]:
    """Search Google Scholar; prefer open-access / PDF links."""
    if not query.strip():
        return []

    if SERPAPI_KEY:
        try:
            papers = _search_serpapi(query, year=year, limit=limit)
            if papers:
                return papers
        except Exception:
            pass

    try:
        papers = _search_scholar_html(query, year=year, limit=limit)
        if papers:
            return papers
    except Exception:
        pass

    return _search_semantic_scholar_fallback(query, year=year, limit=limit)


def _search_serpapi(query: str, *, year: Optional[int], limit: int) -> list[Paper]:
    params: dict = {
        "engine": "google_scholar",
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": min(limit * 2, 20),
    }
    if year is not None:
        params["as_ylo"] = year
        params["as_yhi"] = year

    with httpx.Client(timeout=30.0) as client:
        resp = client.get("https://serpapi.com/search", params=params)
        resp.raise_for_status()
        data = resp.json()

    papers: list[Paper] = []
    for item in data.get("organic_results") or []:
        pdf_url = ""
        resources = item.get("resources") or []
        for res in resources:
            link = res.get("link") or ""
            if link.lower().endswith(".pdf") or "pdf" in (res.get("file_format") or "").lower():
                pdf_url = link
                break
        if not pdf_url:
            for res in resources:
                if res.get("link"):
                    pdf_url = res["link"]
                    break

        # Prefer items with some free full-text signal
        link = item.get("link") or ""
        if not pdf_url and not _looks_open(item):
            # still keep if we have a link; OA filter applied later softly
            pass

        year_val = _parse_year(str(item.get("publication_info", {}).get("summary", "")))
        if year_val is None:
            year_val = _parse_year(str(item.get("year") or ""))

        papers.append(
            Paper(
                title=(item.get("title") or "").strip(),
                authors=_authors_from_serpapi(item),
                year=year_val,
                abstract=(item.get("snippet") or "").strip(),
                source="Google Scholar",
                url=link,
                pdf_url=pdf_url,
            )
        )
        if len(papers) >= limit:
            break

    return _prefer_open_access(papers, limit)


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4), reraise=True)
def _search_scholar_html(query: str, *, year: Optional[int], limit: int) -> list[Paper]:
    params = f"q={quote_plus(query)}&hl=en"
    if year is not None:
        params += f"&as_ylo={year}&as_yhi={year}"

    url = f"https://scholar.google.com/scholar?{params}"
    with httpx.Client(timeout=30.0, headers=_HEADERS, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        html = resp.text

    if "unusual traffic" in html.lower() or "captcha" in html.lower():
        raise RuntimeError("Google Scholar blocked the request")

    soup = BeautifulSoup(html, "lxml")
    papers: list[Paper] = []

    for result in soup.select("div.gs_r.gs_or.gs_scl"):
        title_el = result.select_one("h3.gs_rt a")
        if not title_el:
            title_el = result.select_one("h3.gs_rt")
        if not title_el:
            continue

        title = title_el.get_text(" ", strip=True)
        title = re.sub(r"^\[.*?\]\s*", "", title).strip()
        link = title_el.get("href") if title_el.name == "a" else ""

        pdf_url = ""
        pdf_el = result.select_one("div.gs_or_ggsm a")
        if pdf_el and pdf_el.get("href"):
            pdf_url = pdf_el["href"]

        meta = result.select_one("div.gs_a")
        meta_text = meta.get_text(" ", strip=True) if meta else ""
        authors = meta_text.split("-")[0].strip() if meta_text else ""
        year_val = _parse_year(meta_text)

        snippet_el = result.select_one("div.gs_rs")
        abstract = snippet_el.get_text(" ", strip=True) if snippet_el else ""

        papers.append(
            Paper(
                title=title,
                authors=authors,
                year=year_val,
                abstract=abstract,
                source="Google Scholar",
                url=link or "",
                pdf_url=pdf_url,
            )
        )
        if len(papers) >= limit * 2:
            break

    return _prefer_open_access(papers, limit)


def _search_semantic_scholar_fallback(
    query: str, *, year: Optional[int], limit: int
) -> list[Paper]:
    """Fallback OA academic search when Scholar is blocked / no SerpAPI.

    Tries OpenAlex first (reliable free OA index), then Semantic Scholar.
    Results are returned under the Google Scholar search lane.
    """
    papers = _search_openalex(query, year=year, limit=limit)
    if papers:
        return papers
    return _search_semantic_scholar(query, year=year, limit=limit)


def _search_openalex(query: str, *, year: Optional[int], limit: int) -> list[Paper]:
    filters = ["is_oa:true"]
    if year is not None:
        filters.append(f"publication_year:{year}")

    params = {
        "search": query,
        "filter": ",".join(filters),
        "per_page": min(limit * 2, 25),
        "mailto": CONTACT_EMAIL,
    }
    with httpx.Client(timeout=30.0, headers=_HEADERS) as client:
        resp = client.get("https://api.openalex.org/works", params=params)
        if resp.status_code >= 400:
            return []
        data = resp.json()

    papers: list[Paper] = []
    for item in data.get("results") or []:
        title = (item.get("display_name") or "").strip()
        if not title:
            continue
        oa = item.get("open_access") or {}
        primary = item.get("primary_location") or {}
        landing = (primary.get("landing_page_url") or "").strip()
        best = item.get("best_oa_location") or {}
        pdf_url = (
            (best.get("pdf_url") or "").strip()
            or (primary.get("pdf_url") or "").strip()
            or (oa.get("oa_url") or "").strip()
        )
        if not landing:
            landing = (best.get("landing_page_url") or item.get("id") or "").strip()

        authors = ", ".join(
            ((a.get("author") or {}).get("display_name") or "")
            for a in (item.get("authorships") or [])
        )
        authors = ", ".join(part.strip() for part in authors.split(",") if part.strip())

        doi = (item.get("doi") or "").replace("https://doi.org/", "").strip()
        y = item.get("publication_year")
        abstract = _openalex_abstract(item.get("abstract_inverted_index"))

        papers.append(
            Paper(
                title=title,
                authors=authors,
                year=int(y) if y else None,
                abstract=abstract,
                source="Google Scholar",
                url=landing or (f"https://doi.org/{doi}" if doi else pdf_url),
                pdf_url=pdf_url if pdf_url.lower().endswith(".pdf") or "pdf" in pdf_url.lower() else pdf_url,
                doi=doi,
            )
        )
        if len(papers) >= limit:
            break
    return _prefer_open_access(papers, limit)


def _openalex_abstract(inverted: Optional[dict]) -> str:
    if not inverted or not isinstance(inverted, dict):
        return ""
    # Reconstruct from inverted index: {word: [positions]}
    try:
        max_pos = max(pos for positions in inverted.values() for pos in positions)
        words = [""] * (max_pos + 1)
        for word, positions in inverted.items():
            for pos in positions:
                words[pos] = word
        return " ".join(words).strip()
    except Exception:
        return ""


def _search_semantic_scholar(query: str, *, year: Optional[int], limit: int) -> list[Paper]:
    params: dict = {
        "query": query,
        "limit": min(limit * 3, 30),
        "fields": "title,authors,year,abstract,url,openAccessPdf,externalIds",
        "openAccessPdf": "",
    }
    with httpx.Client(timeout=30.0, headers=_HEADERS) as client:
        resp = client.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params=params,
        )
        if resp.status_code == 429:
            return []
        if resp.status_code >= 400:
            return []
        data = resp.json()

    papers: list[Paper] = []
    for item in data.get("data") or []:
        y = item.get("year")
        if year is not None and y is not None and abs(int(y) - int(year)) > 1:
            continue
        oa = item.get("openAccessPdf") or {}
        pdf_url = (oa.get("url") or "").strip()
        if not pdf_url:
            continue
        authors = ", ".join(
            a.get("name", "") for a in (item.get("authors") or []) if a.get("name")
        )
        ext = item.get("externalIds") or {}
        papers.append(
            Paper(
                title=(item.get("title") or "").strip(),
                authors=authors,
                year=int(y) if y else None,
                abstract=(item.get("abstract") or "").strip(),
                source="Google Scholar",
                url=(item.get("url") or pdf_url),
                pdf_url=pdf_url,
                doi=(ext.get("DOI") or ""),
            )
        )
        if len(papers) >= limit:
            break
    return papers


def _prefer_open_access(papers: list[Paper], limit: int) -> list[Paper]:
    with_pdf = [p for p in papers if p.pdf_url]
    without = [p for p in papers if not p.pdf_url]
    ordered = with_pdf + without
    # Keep only OA-leaning: must have pdf_url OR known OA host in url
    filtered = [
        p
        for p in ordered
        if p.pdf_url or _url_looks_oa(p.url)
    ]
    if not filtered:
        filtered = with_pdf or ordered[:limit]
    return filtered[:limit]


def _looks_open(item: dict) -> bool:
    resources = item.get("resources") or []
    return bool(resources)


def _url_looks_oa(url: str) -> bool:
    if not url:
        return False
    u = url.lower()
    hints = (
        "arxiv.org",
        "biorxiv.org",
        "medrxiv.org",
        "pmc.ncbi.nlm.nih.gov",
        "nih.gov",
        "openaccess",
        "mdpi.com",
        "plos.org",
        "frontiersin.org",
        "hindawi.com",
        "ieee.org/document",  # may still be paywalled; soft signal
    )
    return any(h in u for h in hints)


def _authors_from_serpapi(item: dict) -> str:
    info = item.get("publication_info") or {}
    authors = info.get("authors")
    if isinstance(authors, list):
        names = [a.get("name", "") for a in authors if isinstance(a, dict)]
        return ", ".join(n for n in names if n)
    summary = info.get("summary") or ""
    return summary.split("-")[0].strip() if summary else ""


def _parse_year(text: str) -> Optional[int]:
    match = re.search(r"\b(19|20)\d{2}\b", text or "")
    if match:
        return int(match.group(0))
    return None
