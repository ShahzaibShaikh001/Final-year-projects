"""Merge and dedupe papers from multiple sources."""

from __future__ import annotations

import re
from typing import Optional

from src.models import Paper
from src.search.ieee import search_ieee
from src.search.scholar import search_scholar


def _normalize_title(title: str) -> str:
    t = title.lower().strip()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t


def merge_papers(scholar: list[Paper], ieee: list[Paper], limit: int) -> list[Paper]:
    """Interleave sources, dedupe by DOI/title, prefer OA PDF."""
    seen_titles: set[str] = set()
    seen_dois: set[str] = set()
    merged: list[Paper] = []

    # Prefer items with pdf_url when sorting within each list
    def rank(p: Paper) -> tuple:
        return (0 if p.pdf_url else 1, -(p.year or 0))

    s_sorted = sorted(scholar, key=rank)
    i_sorted = sorted(ieee, key=rank)

    # Interleave Scholar, IEEE, Scholar, IEEE...
    i = j = 0
    while len(merged) < limit and (i < len(s_sorted) or j < len(i_sorted)):
        for source_list, idx_ref in ((s_sorted, "s"), (i_sorted, "j")):
            if len(merged) >= limit:
                break
            if idx_ref == "s":
                if i >= len(s_sorted):
                    continue
                paper = s_sorted[i]
                i += 1
            else:
                if j >= len(i_sorted):
                    continue
                paper = i_sorted[j]
                j += 1

            key = _normalize_title(paper.title)
            doi = (paper.doi or "").lower().strip()
            if doi and doi in seen_dois:
                continue
            if key and key in seen_titles:
                continue
            if key:
                seen_titles.add(key)
            if doi:
                seen_dois.add(doi)
            if paper.title:
                merged.append(paper)

    return merged[:limit]


def search_papers(
    query: str,
    *,
    year: Optional[int] = None,
    count: int = 1,
) -> list[Paper]:
    """Search both sources and return up to `count` open-access papers."""
    # Fetch extra from each source so merge can fill N after OA filtering
    per_source = max(count, min(count * 2, 15))
    scholar = search_scholar(query, year=year, limit=per_source)
    ieee = search_ieee(query, year=year, limit=per_source)
    return merge_papers(scholar, ieee, count)
