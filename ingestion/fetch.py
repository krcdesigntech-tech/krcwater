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
    # 정적 추출이 빈약하면(JS 렌더 SPA) 헤드리스 렌더 후 재추출
    if len(text) < 200:
        r_title, r_text = _render_and_extract(url)
        if len(r_text) > len(text):
            title, text = (title or r_title), r_text
        text = _clean(text or "")

    if len(text) < 50:  # 본문이라 부르기 어려운 경우 스킵
        return None
    return {"title": title, "raw_text": text, "content_hash": content_hash(text)}


def _render_and_extract(url: str) -> tuple[str | None, str]:
    """JS 렌더링 페이지: Playwright 로 렌더 후 본문 추출(트래필라투라 → 실패 시 body 텍스트)."""
    try:
        from playwright.sync_api import sync_playwright
        import trafilatura
    except Exception:
        return None, ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)
            html = page.content()
            title = page.title()
            body = page.eval_on_selector("body", "el => el.innerText") or ""
            browser.close()
        text = trafilatura.extract(html, url=url, favor_recall=True) or ""
        if len(text) < len(body):
            text = body
        return (title or None), text
    except Exception:
        return None, ""
