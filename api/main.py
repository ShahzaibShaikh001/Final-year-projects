"""FastAPI backend for Researcher chat frontend."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.chat.clarify import clarify_prompt
from src.chat.paper_chat import answer_about_paper
from src.config import GROQ_API_KEY
from src.models import Paper
from src.search.merge import search_papers

app = FastAPI(title="Researcher API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    year: Optional[int] = None
    count: int = 2
    selected_paper: Optional[dict[str, Any]] = None
    history: list[dict[str, str]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    kind: str
    reply: str
    topics: list[str] = Field(default_factory=list)
    papers: list[dict[str, Any]] = Field(default_factory=list)
    search_query: str = ""
    year: Optional[int] = None
    count: Optional[int] = None


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    paper: dict[str, Any]
    history: list[dict[str, str]] = Field(default_factory=list)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "groq_configured": bool(GROQ_API_KEY)}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY missing in .env")

    text = req.message.strip()
    lower = text.lower()
    wants_new_search = any(
        k in lower
        for k in (
            "find papers",
            "search for",
            "new search",
            "look up",
            "latest papers",
            "find me",
        )
    )

    # Paper Q&A mode
    if req.selected_paper and not wants_new_search:
        paper = Paper.from_dict(req.selected_paper)
        try:
            answer = answer_about_paper(paper, text, history=req.history[-6:])
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return ChatResponse(kind="qa", reply=answer)

    try:
        result = clarify_prompt(text, year_hint=req.year, count_hint=req.count)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    year = result.year if result.year is not None else req.year
    count = int(result.count or req.count)

    if result.status != "ready":
        bits = []
        if result.message:
            bits.append(result.message)
        if result.question:
            bits.append(result.question)
        if result.suggested_topics:
            bits.append("Suggested topics:")
            bits.extend(f"- {t}" for t in result.suggested_topics)
        return ChatResponse(
            kind="clarify",
            reply="\n\n".join(bits) or "Could you clarify the research topic?",
            topics=result.suggested_topics or [],
            year=year,
            count=count,
        )

    try:
        papers = search_papers(result.search_query, year=year, count=count)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Search failed: {exc}") from exc

    paper_dicts = [p.to_dict() for p in papers]
    n_scholar = sum(1 for p in paper_dicts if "scholar" in (p.get("source") or "").lower())
    n_ieee = sum(1 for p in paper_dicts if "ieee" in (p.get("source") or "").lower())
    year_bit = f" · {year}" if year else ""
    lines = [
        result.message or f"Searching for **{result.search_query}**",
        "",
        f"Found **{len(paper_dicts)}** open-access paper(s) "
        f"(asked for {count}{year_bit}).",
        f"Google Scholar **{n_scholar}** · IEEE **{n_ieee}**",
        "",
        "Select a paper, then ask for a summary.",
    ]
    for i, p in enumerate(paper_dicts):
        lines += ["", f"**{i + 1}. {p.get('title') or 'Untitled'}**"]
        meta = " · ".join(
            x
            for x in [
                p.get("source"),
                str(p["year"]) if p.get("year") else None,
                (p.get("authors") or "")[:70] or None,
            ]
            if x
        )
        if meta:
            lines.append(f"*{meta}*")
        abstract = (p.get("abstract") or "").strip()
        if abstract:
            lines.append(abstract[:240] + ("…" if len(abstract) > 240 else ""))
        link = p.get("url") or p.get("pdf_url")
        if link:
            lines.append(f"[Open paper]({link})")

    return ChatResponse(
        kind="results",
        reply="\n\n".join(lines),
        papers=paper_dicts,
        search_query=result.search_query,
        year=year,
        count=count,
    )


@app.post("/api/ask")
def ask(req: AskRequest) -> dict[str, str]:
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY missing in .env")
    paper = Paper.from_dict(req.paper)
    try:
        answer = answer_about_paper(paper, req.question, history=req.history[-6:])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"reply": answer}
