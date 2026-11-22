"""Research Paper Search + Chat — Streamlit UI (links + abstract chat)."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path when launched via streamlit
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from src.chat.clarify import clarify_prompt
from src.chat.paper_chat import answer_about_paper
from src.config import (
    DEFAULT_PAPER_COUNT,
    DEFAULT_YEAR_FROM,
    GROQ_API_KEY,
    MAX_PAPER_COUNT,
    MIN_PAPER_COUNT,
)
from src.models import Paper
from src.search.merge import search_papers

st.set_page_config(
    page_title="Research Paper Search + Chat",
    page_icon="📄",
    layout="wide",
)


def _init_state() -> None:
    defaults = {
        "clarify": None,
        "papers": [],
        "selected_idx": None,
        "chat_history": [],
        "last_search_query": "",
        "resolved_year": None,
        "resolved_count": DEFAULT_PAPER_COUNT,
        "phase": "search",  # search | clarify | results | chat
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _reset_downstream() -> None:
    st.session_state.papers = []
    st.session_state.selected_idx = None
    st.session_state.chat_history = []


def _run_search(query: str, year: int | None, count: int) -> None:
    with st.spinner("Searching Google Scholar and IEEE Access…"):
        papers = search_papers(query, year=year, count=count)
    st.session_state.papers = [p.to_dict() for p in papers]
    st.session_state.last_search_query = query
    st.session_state.resolved_year = year
    st.session_state.resolved_count = count
    st.session_state.selected_idx = None
    st.session_state.chat_history = []
    st.session_state.phase = "results"


def main() -> None:
    _init_state()

    st.title("Research Paper Search + Chat")
    st.caption(
        "Search open-access papers on Google Scholar & IEEE Access, open the links, "
        "and chat using the public abstract via Groq."
    )

    if not GROQ_API_KEY:
        st.error(
            "Missing `GROQ_API_KEY`. Copy `.env.example` to `.env` and add your Groq API key."
        )
        st.stop()

    with st.sidebar:
        st.header("Search options")
        year_enabled = st.checkbox("Filter by year", value=False)
        year = None
        if year_enabled:
            year = st.number_input(
                "Year",
                min_value=1990,
                max_value=2100,
                value=DEFAULT_YEAR_FROM,
                step=1,
            )
            year = int(year)

        count = st.number_input(
            "Number of papers (default 1)",
            min_value=MIN_PAPER_COUNT,
            max_value=MAX_PAPER_COUNT,
            value=DEFAULT_PAPER_COUNT,
            step=1,
        )
        count = int(count)
        st.markdown("---")
        st.markdown(
            "Tip: you can also say *“latest 5 papers on radiology”* in the prompt."
        )
        st.caption("Chat answers use the public abstract only — no PDF download.")
        if st.button("Clear session", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    prompt = st.text_area(
        "What papers are you looking for?",
        placeholder="e.g. latest papers in radiology, transformers for ECG classification…",
        height=100,
    )

    col_a, _ = st.columns([1, 3])
    with col_a:
        find_clicked = st.button("Find papers", type="primary", use_container_width=True)

    if find_clicked:
        if not prompt.strip():
            st.warning("Enter a research topic or question first.")
        else:
            _reset_downstream()
            with st.spinner("Understanding your request…"):
                result = clarify_prompt(prompt, year_hint=year, count_hint=count)
            st.session_state.clarify = result.to_dict()

            if result.status == "ready":
                use_year = result.year if result.year is not None else year
                use_count = result.count if result.count else count
                if result.message:
                    st.info(result.message)
                _run_search(result.search_query, use_year, use_count)
            else:
                st.session_state.phase = "clarify"

    # Clarification UI
    clarify = st.session_state.clarify
    if st.session_state.phase == "clarify" and clarify:
        st.subheader("Let’s clarify your topic")
        if clarify.get("message"):
            st.write(clarify["message"])
        if clarify.get("question"):
            st.write(clarify["question"])

        topics = clarify.get("suggested_topics") or []
        if topics:
            st.markdown("**Suggested topics**")
            cols = st.columns(min(len(topics), 4))
            for i, topic in enumerate(topics):
                with cols[i % len(cols)]:
                    if st.button(topic, key=f"topic_{i}", use_container_width=True):
                        with st.spinner("Understanding your request…"):
                            result = clarify_prompt(
                                topic, year_hint=year, count_hint=count
                            )
                        st.session_state.clarify = result.to_dict()
                        if result.status == "ready":
                            use_year = result.year if result.year is not None else year
                            use_count = result.count if result.count else count
                            _run_search(result.search_query, use_year, use_count)
                        else:
                            st.session_state.phase = "clarify"
                        st.rerun()

        refined = st.text_input("Or type a clearer topic", key="refined_topic")
        if st.button("Search with refined topic"):
            if refined.strip():
                with st.spinner("Understanding your request…"):
                    result = clarify_prompt(
                        refined, year_hint=year, count_hint=count
                    )
                st.session_state.clarify = result.to_dict()
                if result.status == "ready":
                    use_year = result.year if result.year is not None else year
                    use_count = result.count if result.count else count
                    _run_search(result.search_query, use_year, use_count)
                else:
                    st.session_state.phase = "clarify"
                st.rerun()

    # Results
    papers_data = st.session_state.papers or []
    if papers_data:
        st.subheader("Results")
        st.caption(
            f"Query: **{st.session_state.last_search_query}** · "
            f"requested {st.session_state.resolved_count} · "
            f"found {len(papers_data)}"
            + (
                f" · year {st.session_state.resolved_year}"
                if st.session_state.resolved_year
                else ""
            )
        )
        if len(papers_data) < st.session_state.resolved_count:
            st.warning(
                f"Only {len(papers_data)} open-access paper(s) found "
                f"(requested {st.session_state.resolved_count})."
            )

        for idx, pdata in enumerate(papers_data):
            paper = Paper.from_dict(pdata)
            with st.container(border=True):
                left, right = st.columns([4, 1])
                with left:
                    st.markdown(f"**{idx + 1}. {paper.title}**")
                    meta_bits = [
                        paper.source,
                        str(paper.year) if paper.year else None,
                        paper.authors[:80] + ("…" if len(paper.authors) > 80 else "")
                        if paper.authors
                        else None,
                    ]
                    st.caption(" · ".join(b for b in meta_bits if b))
                    if paper.abstract:
                        st.write(
                            paper.abstract[:320]
                            + ("…" if len(paper.abstract) > 320 else "")
                        )
                    links = []
                    if paper.url:
                        links.append(f"[Open paper]({paper.url})")
                    if paper.pdf_url and paper.pdf_url != paper.url:
                        links.append(f"[PDF link]({paper.pdf_url})")
                    if links:
                        st.markdown(" · ".join(links))
                with right:
                    if st.button("Chat", key=f"chat_{idx}", use_container_width=True):
                        st.session_state.selected_idx = idx
                        st.session_state.chat_history = []
                        st.session_state.phase = "chat"
                        st.rerun()

    # Chat panel — abstract only
    if st.session_state.selected_idx is not None and papers_data:
        idx = st.session_state.selected_idx
        if 0 <= idx < len(papers_data):
            paper = Paper.from_dict(papers_data[idx])
            st.markdown("---")
            st.subheader(f"Chat with: {paper.title}")
            link = paper.url or paper.pdf_url
            st.caption(
                f"{paper.source} · {paper.year or 'n/a'}"
                + (f" · [Open paper]({link})" if link else "")
                + " · answers from public abstract"
            )
            if not paper.abstract:
                st.warning(
                    "No public abstract was found for this result. "
                    "Open the link to read the paper; chat may be limited."
                )

            starters = st.columns(3)
            starter_prompts = [
                "Summarize this paper from the abstract.",
                "What does the abstract say about methods?",
                "What are the main findings in the abstract?",
            ]
            for i, sp in enumerate(starter_prompts):
                with starters[i]:
                    if st.button(sp, key=f"starter_{i}", use_container_width=True):
                        _ask(paper, sp)

            for turn in st.session_state.chat_history:
                with st.chat_message(turn["role"]):
                    st.markdown(turn["content"])

            question = st.chat_input("Ask about this paper (from the abstract)…")
            if question:
                _ask(paper, question)


def _ask(paper: Paper, question: str) -> None:
    st.session_state.chat_history.append({"role": "user", "content": question})
    with st.spinner("Thinking…"):
        try:
            answer = answer_about_paper(
                paper,
                question,
                history=st.session_state.chat_history[:-1],
            )
        except Exception as exc:  # noqa: BLE001
            answer = f"Sorry — I couldn’t answer that ({exc})."
    st.session_state.chat_history.append({"role": "assistant", "content": answer})
    st.rerun()


if __name__ == "__main__":
    main()
