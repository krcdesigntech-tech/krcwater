# 수자원법령 RAG — 에이전트 작업 규칙

이 파일은 Hermes/코딩 에이전트가 이 디렉터리에서 작업할 때 따르는 규칙이다.

## 목표
`litt.ly/krc.wrmo` 가 가리키는 수자원 관련 법령·시행령·규칙 본문을 수집·임베딩하여,
사용자가 자연어로 질문하면 근거 조문을 인용해 답하는 RAG 사이트를 구축·운영한다.

## 아키텍처
- **수집/임베딩**: `ingestion/`(Python + Playwright) → Supabase 적재. **GitHub Actions 에서 실행**(로컬 금지).
- **DB**: Supabase (Postgres + pgvector). 스키마 단일 진실원 = `db/schema.sql`.
- **사이트**: `web/` Astro + React 아일랜드, Vercel SSR 배포.
- **임베딩 모델**: Google Gemini `gemini-embedding-001` (무료, 768d, outputDimensionality=768).
- **답변 모델**: OpenRouter `google/gemma-3-27b-it:free` + 무료 폴백.

## 데이터 흐름
litt.ly 헤드리스 스크랩 → 링크 목록 → 링크별 문서 fetch(HTML=trafilatura / PDF=pymupdf)
→ `제\d+조` 경계 우선 청킹 → Gemini 임베딩 → `documents`/`chunks` 적재.

## 코딩 규칙
- 비밀키는 `.env`(수집)·GitHub Actions secrets·Vercel 환경변수에만. **코드/커밋 하드코딩 금지.**
- 서버 전용 키(`SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`)는
  절대 클라이언트 번들에 노출 금지. 웹 클라이언트는 anon 키 + RLS(읽기 전용)만.
- 무료 한도 보호: 수집 시 `content_hash` 로 변경분만 재임베딩. 임베딩/LLM 호출은 배치·백오프·재시도.
- 스크래핑은 요청 간격(rate limit)·robots/ToS 준수.
- DB 컬럼은 `db/schema.sql` 을 단일 진실원으로 삼는다. ingestion 출력은 그 컬럼과 1:1 대응.

## 검증
- 수집: `python -m ingestion.pipeline --limit 5 --dry-run` 으로 스크랩/추출 확인(임베딩·적재 생략).
- 전체: Actions 로그 + Supabase 행수 + Vercel E2E 질의(근거 조문 인용 확인).
