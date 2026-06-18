# 수자원법령 RAG

`litt.ly/krc.wrmo` (KRC 수자원 링크트리)가 가리키는 **수자원 관련 법령·시행령·규칙** 본문을 코퍼스로,
자연어 질문에 **근거 조문을 인용해** 답하는 RAG 사이트. 전(全)클라우드·무료 우선·로컬 실행 없음.

## 아키텍처

```
GitHub Actions (cron, 무료)
  └─ ingestion/ (Python + Playwright)
       litt.ly 스크랩 → 링크 추출 → 문서 fetch(HTML/PDF) → 텍스트 추출
       → 조문 단위 청킹 → Gemini 임베딩(768d) → Supabase 적재

Supabase (무료): Postgres + pgvector
  documents / chunks(vector 768) / match_chunks() RPC / ingestion_runs

Vercel (무료): Astro + React
  채팅 UI(anon 키 + RLS 읽기) + /api/ask 서버리스 함수
  질문 임베딩(Gemini) → pgvector 검색 → OpenRouter Gemma 답변(스트리밍, 인용)
```

- 임베딩: Google Gemini `gemini-embedding-001` (무료, 768차원)
- 답변: OpenRouter `google/gemma-3-27b-it:free` (128k, 무료, 20/분·200/일) + 무료 모델 폴백

## 셋업 (모두 클라우드, 로컬 실행 없음)

1. **Supabase** 프로젝트 생성 → SQL Editor 에 [`db/schema.sql`](db/schema.sql) 실행.
2. **API 키 발급**: Google AI Studio(Gemini, 무료) + OpenRouter.
3. **GitHub**: 이 레포 푸시 → Settings > Secrets 에 `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
   `GEMINI_API_KEY` 등록 → Actions 에서 `ingest` 워크플로 수동 실행(1차 수집).
4. **Vercel**: `web/` 연결 → 환경변수(`PUBLIC_SUPABASE_URL`, `PUBLIC_SUPABASE_ANON_KEY`,
   `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`) 등록 → 배포.
5. (선택) Actions cron 으로 정기 갱신.

## 키 노출 원칙
- 브라우저: `PUBLIC_SUPABASE_ANON_KEY` 만 (RLS 읽기 전용).
- 서버 전용(Actions·Vercel 함수): `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`.
