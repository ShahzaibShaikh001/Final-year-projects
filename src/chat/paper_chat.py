"""Chat about a paper using public abstract + metadata only (no PDF download)."""

from __future__ import annotations

from src.chat.groq_client import chat_completion
from src.models import Paper


def answer_about_paper(
    paper: Paper,
    question: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    system = (
        "You are a careful research assistant. Answer using ONLY the paper's "
        "public title, authors, year, source, link, and abstract/snippet. "
        "Do not invent methods, results, or details that are not in that text. "
        "If something is not in the abstract, say clearly that the abstract "
        "does not include it and suggest the user open the paper link. "
        "Be concise. For summary requests, write a clear plain-language overview "
        "from the abstract."
    )
    meta = (
        f"Title: {paper.title}\n"
        f"Authors: {paper.authors or 'n/a'}\n"
        f"Year: {paper.year or 'n/a'}\n"
        f"Source: {paper.source or 'n/a'}\n"
        f"URL: {paper.url or paper.pdf_url or 'n/a'}\n"
        f"DOI: {paper.doi or 'n/a'}\n"
        f"Abstract / public snippet:\n{paper.abstract or '(no abstract available)'}\n"
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]

    if history:
        for turn in history[-6:]:
            role = turn.get("role")
            content = turn.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    messages.append(
        {
            "role": "user",
            "content": f"Paper metadata and abstract:\n{meta}\n\nQuestion: {question}",
        }
    )
    return chat_completion(messages, temperature=0.2, max_tokens=500)
