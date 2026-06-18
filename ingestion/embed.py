"""Google Gemini text-embedding-004 임베딩 (무료 티어, 768차원).

무료 한도(분당/일 1,500) 보호: 배치 호출 + 429/일시오류 백오프 재시도.
google-genai SDK 사용 (GEMINI_API_KEY).
"""
from __future__ import annotations

import os
import time

from google import genai
from google.genai import types

MODEL = "text-embedding-004"
DIM = 768
BATCH = 50           # 한 요청에 묶을 텍스트 수
MAX_RETRY = 5

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        key = os.environ.get("GEMINI_API_KEY", "")
        if not key:
            raise RuntimeError("GEMINI_API_KEY 가 설정되지 않았습니다.")
        _client = genai.Client(api_key=key)
    return _client


def _embed_batch(texts: list[str], task_type: str) -> list[list[float]]:
    cfg = types.EmbedContentConfig(task_type=task_type, output_dimensionality=DIM)
    delay = 2.0
    for attempt in range(MAX_RETRY):
        try:
            res = _get_client().models.embed_content(model=MODEL, contents=texts, config=cfg)
            return [e.values for e in res.embeddings]
        except Exception as e:  # noqa: BLE001 — rate limit/일시오류 백오프
            if attempt == MAX_RETRY - 1:
                raise
            print(f"  embed 재시도 {attempt + 1}/{MAX_RETRY} ({e}); {delay:.0f}s 대기")
            time.sleep(delay)
            delay = min(delay * 2, 30)
    return []


def embed_documents(texts: list[str]) -> list[list[float]]:
    """문서 청크 임베딩 (task_type=RETRIEVAL_DOCUMENT). 입력 순서 보존."""
    out: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        out.extend(_embed_batch(texts[i : i + BATCH], "RETRIEVAL_DOCUMENT"))
    return out


def embed_query(text: str) -> list[float]:
    """단일 질의 임베딩 (task_type=RETRIEVAL_QUERY)."""
    return _embed_batch([text], "RETRIEVAL_QUERY")[0]
