"""Extract text from PDF bytes or HTML."""

from __future__ import annotations

import re

import pymupdf
from bs4 import BeautifulSoup


def extract_text_from_pdf(data: bytes) -> str:
    doc = pymupdf.open(stream=data, filetype="pdf")
    parts: list[str] = []
    try:
        for page in doc:
            parts.append(page.get_text("text"))
    finally:
        doc.close()
    return _clean_text("\n".join(parts))


def extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n")
    return _clean_text(text)


def chunk_text(text: str, chunk_size: int = 2500, overlap: int = 200) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        # try to break on paragraph/sentence
        if end < len(text):
            window = text[start:end]
            break_at = max(window.rfind("\n\n"), window.rfind(". "))
            if break_at > chunk_size // 3:
                end = start + break_at + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


def _clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
