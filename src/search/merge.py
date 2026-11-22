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


def _is_new(paper: Paper, seen_titles: set[str], seen_dois: set[str]) -> bool:
    key = _normalize_title(paper.title)
    doi = (paper.doi or "").lower().strip()
    if doi and doi in seen_dois:
        return False
    if key and key in seen_titles:
        return False
    return bool(paper.title)


def _mark(paper: Paper, seen_titles: set[str], seen_dois: set[str]) -> None:
    key = _normalize_title(paper.title)
    doi = (paper.doi or "").lower().strip()
    if key:
        seen_titles.add(key)
    if doi:
        seen_dois.add(doi)


def merge_papers(scholar: list[Paper], ieee: list[Paper], limit: int) -> list[Paper]:
    """Balance Scholar and IEEE results.

    When both sources have hits and limit >= 2, guarantee at least one from each.
    Slots are split ~half/half, then remainder filled from whichever still has papers.
    """
    seen_titles: set[str] = set()
    seen_dois: set[str] = set()
    merged: list[Paper] = []

    def rank(p: Paper) -> tuple:
        return (0 if p.pdf_url or p.abstract else 1, -(p.year or 0))

    s_pool = sorted(scholar, key=rank)
    i_pool = sorted(ieee, key=rank)

    def take_from(pool: list[Paper], n: int) -> list[Paper]:
        picked: list[Paper] = []
        for paper in pool:
            if len(picked) >= n:
                break
            if not _is_new(paper, seen_titles, seen_dois):
                continue
            _mark(paper, seen_titles, seen_dois)
            picked.append(paper)
        return picked

    if limit <= 0:
        return []

    # Single result: still prefer interleaving fairness — take newest across both
    if limit == 1:
        candidates = sorted(s_pool + i_pool, key=rank)
        for paper in candidates:
            if _is_new(paper, seen_titles, seen_dois):
                return [paper]
        return []

    # Split slots; when both sources exist, reserve at least 1 each
    if s_pool and i_pool:
        ieee_slots = max(1, limit // 2)
        scholar_slots = max(1, limit - ieee_slots)
    elif i_pool:
        ieee_slots, scholar_slots = limit, 0
    else:
        ieee_slots, scholar_slots = 0, limit

    ieee_picked = take_from(i_pool, ieee_slots)
    scholar_picked = take_from(s_pool, scholar_slots)

    # Interleave for display: Scholar, IEEE, Scholar, IEEE...
    merged = []
    si = ii = 0
    while len(merged) < limit and (si < len(scholar_picked) or ii < len(ieee_picked)):
        if si < len(scholar_picked):
            merged.append(scholar_picked[si])
            si += 1
        if len(merged) >= limit:
            break
        if ii < len(ieee_picked):
            merged.append(ieee_picked[ii])
            ii += 1

    # Fill any remaining slots from leftovers
    if len(merged) < limit:
        for paper in s_pool + i_pool:
            if len(merged) >= limit:
                break
            if not _is_new(paper, seen_titles, seen_dois):
                continue
            _mark(paper, seen_titles, seen_dois)
            merged.append(paper)

    return merged[:limit]


def search_papers(
    query: str,
    *,
    year: Optional[int] = None,
    count: int = 2,
) -> list[Paper]:
    """Search both sources and return up to `count` open-access papers."""
    per_source = max(count, min(count * 2, 15))
    scholar = search_scholar(query, year=year, limit=per_source)
    ieee = search_ieee(query, year=year, limit=per_source)
    return merge_papers(scholar, ieee, count)
