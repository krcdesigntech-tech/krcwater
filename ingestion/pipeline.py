"""수집·임베딩 오케스트레이터 (GitHub Actions 에서 실행).

흐름: litt.ly 스크랩 → 링크별 문서 fetch → content_hash 비교(변경분만) →
      조문 청킹 → Gemini 임베딩 → Supabase 적재.

실행 (프로젝트 루트 = 수자원법령/ 에서):
    python -m ingestion.pipeline                 # 전체 수집·임베딩·적재
    python -m ingestion.pipeline --limit 5       # 앞 5개 링크만
    python -m ingestion.pipeline --dry-run       # 스크랩/추출만(임베딩·DB 생략)
    python -m ingestion.pipeline --force         # content_hash 같아도 재임베딩
"""
from __future__ import annotations

import argparse
import os
import sys
import traceback

from . import fetch as fetchmod
from .chunk import chunk_text
from .scrape_littly import DEFAULT_URL, scrape_links


def run(url: str, limit: int | None, dry: bool, force: bool) -> dict:
    stats = {
        "links_found": 0, "docs_fetched": 0, "docs_changed": 0,
        "chunks_upserted": 0, "embed_calls": 0, "errors": 0,
    }

    print(f"=== litt.ly 스크랩: {url} ===")
    links = scrape_links(url)
    if limit:
        links = links[:limit]
    stats["links_found"] = len(links)
    print(f"  외부 문서 링크 {len(links)}개")

    if dry:
        for ln in links:
            doc = None
            try:
                doc = fetchmod.fetch_document(ln["url"])
            except Exception as e:  # noqa: BLE001
                print(f"  [fetch 실패] {ln['url']} ({e})")
                continue
            if doc:
                stats["docs_fetched"] += 1
                n = len(chunk_text(doc["raw_text"]))
                print(f"  - {(doc['title'] or ln['label'])[:50]:50} | {len(doc['raw_text'])}자 / {n}청크")
        print(f"\n[dry-run] {stats}")
        return stats

    # 실제 적재 경로 — 지연 임포트(키 없을 때 dry-run 가능)
    from . import embed, supabase_client as sb

    for ln in links:
        try:
            doc = fetchmod.fetch_document(ln["url"])
            if not doc:
                continue
            stats["docs_fetched"] += 1

            existing = sb.get_document(ln["url"])
            if existing and not force and existing.get("content_hash") == doc["content_hash"]:
                continue  # 변경 없음 → 임베딩 호출 절약
            stats["docs_changed"] += 1

            chunks = chunk_text(doc["raw_text"])
            vectors = embed.embed_documents([c["content"] for c in chunks])
            stats["embed_calls"] += 1
            for c, v in zip(chunks, vectors):
                c["embedding"] = v

            saved = sb.upsert_document({
                "source_url": ln["url"],
                "title": doc["title"] or ln["label"] or None,
                "law_name": doc["title"] or ln["label"] or None,
                "raw_text": doc["raw_text"],
                "content_hash": doc["content_hash"],
            })
            n = sb.replace_chunks(saved["id"], chunks)
            stats["chunks_upserted"] += n
            print(f"  ✓ {(doc['title'] or ln['label'])[:50]:50} | {n}청크")
        except Exception:  # noqa: BLE001
            stats["errors"] += 1
            traceback.print_exc()

    sb.log_run(finished_at="now()", **stats)
    print(f"\n=== 완료: {stats} ===")
    return stats


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="수자원법령 RAG 수집 파이프라인")
    p.add_argument("--url", default=os.environ.get("LITTLY_URL", DEFAULT_URL))
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)
    run(args.url, args.limit, args.dry_run, args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
