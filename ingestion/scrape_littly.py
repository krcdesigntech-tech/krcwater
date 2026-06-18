"""litt.ly (JS 렌더링 SPA) 페이지에서 링크 목록 추출.

litt.ly 는 링크 카드를 <a> 가 아니라 클릭 div 로 렌더하고, 데이터는 api.litt.ly
응답(JSON)으로 받는다. 그래서 두 경로를 모두 사용한다:
  1) 네트워크 응답 캡처: api.litt.ly 응답 JSON 에서 링크 URL 수집 (가장 확실)
  2) DOM 폴백: a[href] + onclick/data-* 클릭 요소
반환: [{"url": ..., "label": ...}, ...] (litt.ly 내부/소셜/추적 링크 제외).
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

DEFAULT_URL = "https://litt.ly/krc.wrmo"

_SKIP_HOST = re.compile(
    r"(litt\.ly|litt\.link|kakao\.com|kakaocdn|instagram\.com|facebook\.com|youtube\.com|"
    r"youtu\.be|twitter\.com|x\.com|tiktok\.com|threads\.net|naver\.me|band\.us|"
    r"googletagmanager|google-analytics|mixpanel|doubleclick)$",
    re.I,
)


def _walk_urls(obj, found: dict):
    """JSON 트리에서 (url, 근처 title) 쌍을 재귀 수집."""
    if isinstance(obj, dict):
        url = obj.get("url") or obj.get("link") or obj.get("linkUrl") or obj.get("webUrl")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            title = obj.get("title") or obj.get("name") or obj.get("text") or obj.get("label") or ""
            host = urlparse(url).netloc.lower()
            if not _SKIP_HOST.search(host):
                prev = found.get(url)
                if prev is None or len(title) > len(prev["label"]):
                    found[url] = {"url": url, "label": title.strip()}
        for v in obj.values():
            _walk_urls(v, found)
    elif isinstance(obj, list):
        for v in obj:
            _walk_urls(v, found)


def scrape_links(url: str = DEFAULT_URL, timeout_ms: int = 45000) -> list[dict]:
    found: dict[str, dict] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36")

        # 1) api.litt.ly JSON 응답 캡처
        def on_response(resp):
            try:
                if "api.litt" in resp.url and "json" in (resp.headers.get("content-type", "")):
                    _walk_urls(resp.json(), found)
            except Exception:
                pass
        page.on("response", on_response)

        page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        page.wait_for_timeout(3000)

        # 2) DOM 폴백 — a[href] + 클릭 요소의 data-* 속성
        dom = page.eval_on_selector_all(
            "a[href], [data-url], [data-link], [onclick]",
            """els => els.map(e => ({
                href: e.href || e.getAttribute('data-url') || e.getAttribute('data-link') || '',
                text: (e.innerText||'').trim()
            }))""",
        )
        browser.close()

    for a in dom:
        href = (a.get("href") or "").strip()
        if not href.startswith(("http://", "https://")):
            continue
        host = urlparse(href).netloc.lower()
        if _SKIP_HOST.search(host):
            continue
        label = a.get("text") or ""
        prev = found.get(href)
        if prev is None or len(label) > len(prev["label"]):
            found[href] = {"url": href, "label": label}

    return list(found.values())


if __name__ == "__main__":
    for link in scrape_links():
        print(f"- {link['label'][:50]:50}  {link['url']}")
