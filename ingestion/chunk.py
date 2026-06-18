"""본문을 RAG 검색 단위로 청킹.

한국 법령 본문은 `제○조` 경계가 자연스러운 검색 단위 → 조 단위 우선 분할.
조 경계가 없거나 한 조가 너무 길면 문자 길이 기준으로 추가 분할(+오버랩).
반환: [{"chunk_index", "article_no", "content"}, ...]
"""
from __future__ import annotations

import re

# 줄머리의 "제12조", "제12조의2" 등
_ARTICLE = re.compile(r"(?m)^\s*(제\s*\d+\s*조(?:\s*의\s*\d+)?)")

MAX_CHARS = 1400   # 한 청크 목표 상한(한국어 기준 ~700토큰 내외)
OVERLAP = 150      # 길이 분할 시 겹침


def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_CHARS:
        return [text]
    out, start = [], 0
    while start < len(text):
        end = min(start + MAX_CHARS, len(text))
        # 가능하면 줄바꿈/마침표 경계에서 끊기
        if end < len(text):
            window = text[start:end]
            cut = max(window.rfind("\n"), window.rfind(". "), window.rfind("다. "))
            if cut > MAX_CHARS // 2:
                end = start + cut + 1
        out.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - OVERLAP, start + 1)
    return [c for c in out if c]


def _article_segments(text: str) -> list[tuple[str | None, str]]:
    matches = list(_ARTICLE.finditer(text))
    if not matches:
        return [(None, text)]
    segs: list[tuple[str | None, str]] = []
    # 첫 조문 앞 서두(제목/개정문 등)
    if matches[0].start() > 0:
        head = text[: matches[0].start()].strip()
        if head:
            segs.append((None, head))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        art = re.sub(r"\s+", "", m.group(1))  # "제 12 조" → "제12조"
        segs.append((art, text[start:end].strip()))
    return segs


def chunk_text(raw_text: str) -> list[dict]:
    chunks: list[dict] = []
    idx = 0
    for article_no, seg in _article_segments(raw_text):
        for piece in _split_long(seg):
            if not piece:
                continue
            chunks.append({"chunk_index": idx, "article_no": article_no, "content": piece})
            idx += 1
    return chunks
