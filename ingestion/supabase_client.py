"""Supabase 클라이언트 + documents/chunks upsert, run 로그 헬퍼.

발주공고 ingestion/supabase_client.py 패턴 차용.
service_role 키 사용(RLS 우회) — 수집 측 전용, 절대 클라이언트 노출 금지.
"""
from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

_client: Optional[Client] = None


def get_client() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_URL or not SERVICE_KEY:
            raise RuntimeError(
                "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 가 설정되지 않았습니다."
            )
        _client = create_client(SUPABASE_URL, SERVICE_KEY)
    return _client


def get_document(source_url: str) -> dict | None:
    res = (
        get_client()
        .table("documents")
        .select("id, content_hash")
        .eq("source_url", source_url)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def upsert_document(row: dict) -> dict:
    """source_url 기준 upsert. 반환: 저장된 행(id 포함)."""
    res = (
        get_client()
        .table("documents")
        .upsert(row, on_conflict="source_url")
        .execute()
    )
    return res.data[0] if res.data else {}


def replace_chunks(document_id: str, chunks: list[dict]) -> int:
    """문서의 기존 청크 삭제 후 새 청크 일괄 삽입. 반환: 삽입 건수."""
    client = get_client()
    client.table("chunks").delete().eq("document_id", document_id).execute()
    if not chunks:
        return 0
    rows = [{**c, "document_id": document_id} for c in chunks]
    client.table("chunks").insert(rows).execute()
    return len(rows)


def log_run(**fields) -> None:
    get_client().table("ingestion_runs").insert(fields).execute()
