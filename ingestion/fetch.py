"""링크별 문서 fetch + 본문 텍스트 추출.

- text/html  → trafilatura 로 본문 추출
- application/pdf → pymupdf 로 텍스트 추출
반환: {"title", "raw_text", "content_hash"} 또는 None(실패/빈본문).
"""
from __future__ import annotations

import hashlib
import io
import re

import requests

USER_AGENT = "krc-wrmo-rag-bot/0.1 (+water-resources law RAG)"
TIMEOUT = 30
_WS = re.compile(r"[ \t]+")
_NL = re.compile(r"\n{3,}")


def _clean(s: str) -> str:
    s = _WS.sub(" ", s)
    s = _NL.sub("\n\n", s)
    return s.strip()


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", "ignore")).hexdigest()


def _extract_html(html: str, url: str) -> tuple[str | None, str]:
    import trafilatura

    text = trafilatura.extract(html, url=url, favor_recall=True) or ""
    # 제목
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()
    return (title or None), text


def _extract_pdf(data: bytes) -> tuple[str | None, str]:
    import fitz  # pymupdf

    title = None
    parts: list[str] = []
    with fitz.open(stream=io.BytesIO(data), filetype="pdf") as doc:
        title = (doc.metadata or {}).get("title") or None
        for pg in doc:
            parts.append(pg.get_text("text"))
    return title, "\n".join(parts)


def fetch_document(url: str) -> dict | None:
    headers = {"User-Agent": USER_AGENT}
    r = requests.get(url, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    ctype = r.headers.get("content-type", "").lower()

    if "pdf" in ctype or url.lower().endswith(".pdf"):
        title, text = _extract_pdf(r.content)
    else:
        title, text = _extract_html(r.text, url)

    text = _clean(text or "")
    if len(text) < 50:  # 본문이라 부르기 어려운 경우 스킵
        return None
    return {"title": title, "raw_text": text, "content_hash": content_hash(text)}
