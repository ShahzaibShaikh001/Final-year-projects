"""Shared data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional


@dataclass
class Paper:
    title: str
    authors: str = ""
    year: Optional[int] = None
    abstract: str = ""
    source: str = ""  # "Google Scholar" | "IEEE Access"
    url: str = ""
    pdf_url: str = ""
    doi: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Paper":
        return cls(
            title=data.get("title") or "",
            authors=data.get("authors") or "",
            year=data.get("year"),
            abstract=data.get("abstract") or "",
            source=data.get("source") or "",
            url=data.get("url") or "",
            pdf_url=data.get("pdf_url") or "",
            doi=data.get("doi") or "",
        )


@dataclass
class ClarifyResult:
    status: Literal["ready", "needs_clarification"]
    search_query: str = ""
    year: Optional[int] = None
    count: Optional[int] = None
    question: str = ""
    suggested_topics: list[str] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
