"""litt.ly (JS 렌더링) 페이지를 헤드리스 브라우저로 열어 링크 목록을 추출.

litt.ly 는 SPA 라 requests 로는 빈 페이지만 온다 → Playwright chromium 필수.
반환: [{"url": ..., "label": ...}, ...] (litt.ly 내부/추적 링크 제외, 외부 문서 링크만).
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

DEFAULT_URL = "https://litt.ly/krc.wrmo"

# litt.ly 자체 / 소셜 / 추적성 도메인은 코퍼스 대상이 아님
_SKIP_HOST = re.compile(
    r"(litt\.ly|litt\.link|instagram\.com|facebook\.com|youtube\.com|youtu\.be|"
    r"twitter\.com|x\.com|tiktok\.com|threads\.net|pf\.kakao\.com|open\.kakao\.com)$",
    re.I,
)


def scrape_links(url: str = DEFAULT_URL, timeout_ms: int = 30000) -> list[dict]:
    out: dict[str, dict] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent="krc-wrmo-rag-bot/0.1")
        page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        # 링크 카드가 렌더될 시간 확보
        page.wait_for_timeout(1500)
        anchors = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => ({href: e.href, text: (e.innerText||'').trim()}))",
        )
        browser.close()

    for a in anchors:
        href = (a.get("href") or "").strip()
        if not href.startswith(("http://", "https://")):
            continue
        host = urlparse(href).netloc.lower()
        if _SKIP_HOST.search(host):
            continue
        # 같은 URL 은 라벨이 긴 쪽으로 보존
        prev = out.get(href)
        label = a.get("text") or ""
        if prev is None or len(label) > len(prev["label"]):
            out[href] = {"url": href, "label": label}
    return list(out.values())


if __name__ == "__main__":
    for link in scrape_links():
        print(f"- {link['label'][:50]:50}  {link['url']}")
