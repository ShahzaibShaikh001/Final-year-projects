"""Query intelligence: clarify vague prompts before searching."""

from __future__ import annotations

from typing import Optional

from src.chat.groq_client import chat_completion, parse_json_response
from src.config import DEFAULT_PAPER_COUNT, MAX_PAPER_COUNT, MIN_PAPER_COUNT
from src.models import ClarifyResult

_SYSTEM = """You are a research-search query intelligence assistant.
The user wants to find open-access academic papers on Google Scholar and IEEE Access.

Decide if their prompt is clear enough to search, or needs clarification.

Rules:
- status "ready" when the topic is specific enough to search (field + focus is fine).
- status "needs_clarification" when the prompt is empty, nonsense, too vague
  (e.g. "papers", "something interesting", "help"), or ambiguous across unrelated fields.
- Always produce a crisp academic search_query when ready (keywords, no fluff).
- If the user mentions a year or "latest"/"recent", set year (integer). For "latest"/"recent"
  without a year, set year to the current calendar year they likely mean, or leave null
  and note recency in search_query with terms like "recent".
- If they ask for N papers ("5 papers", "seven papers"), set count to that integer (1-20).
- When clarifying: ask ONE short question AND provide 2-4 concrete suggested_topics
  the user could pick (specific, searchable).
- message: brief friendly note shown to the user.

Respond ONLY with JSON:
{
  "status": "ready" | "needs_clarification",
  "search_query": "string",
  "year": null or int,
  "count": null or int,
  "question": "string",
  "suggested_topics": ["..."],
  "message": "string"
}
"""


def clarify_prompt(
    prompt: str,
    *,
    year_hint: Optional[int] = None,
    count_hint: Optional[int] = None,
) -> ClarifyResult:
    user_bits = [f"User prompt: {prompt.strip() or '(empty)'}"]
    if year_hint is not None:
        user_bits.append(f"UI year filter hint: {year_hint}")
    if count_hint is not None:
        user_bits.append(f"UI paper count hint: {count_hint}")

    raw = chat_completion(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": "\n".join(user_bits)},
        ],
        temperature=0.2,
        max_tokens=400,
        json_mode=True,
    )
    data = parse_json_response(raw)
    return _to_result(data, year_hint=year_hint, count_hint=count_hint)


def _clamp_count(value: Optional[int], fallback: Optional[int]) -> Optional[int]:
    n = value if value is not None else fallback
    if n is None:
        return None
    try:
        n_int = int(n)
    except (TypeError, ValueError):
        return fallback
    return max(MIN_PAPER_COUNT, min(MAX_PAPER_COUNT, n_int))


def _to_result(
    data: dict,
    *,
    year_hint: Optional[int],
    count_hint: Optional[int],
) -> ClarifyResult:
    status = data.get("status") or "needs_clarification"
    if status not in ("ready", "needs_clarification"):
        status = "needs_clarification"

    year = data.get("year")
    if year is None:
        year = year_hint
    else:
        try:
            year = int(year)
        except (TypeError, ValueError):
            year = year_hint

    count = _clamp_count(data.get("count"), count_hint)
    topics = data.get("suggested_topics") or []
    if not isinstance(topics, list):
        topics = []
    topics = [str(t).strip() for t in topics if str(t).strip()][:4]

    search_query = str(data.get("search_query") or "").strip()
    if status == "ready" and not search_query:
        status = "needs_clarification"

    return ClarifyResult(
        status=status,  # type: ignore[arg-type]
        search_query=search_query,
        year=year,
        count=count if count is not None else DEFAULT_PAPER_COUNT,
        question=str(data.get("question") or "").strip(),
        suggested_topics=topics,
        message=str(data.get("message") or "").strip(),
    )
