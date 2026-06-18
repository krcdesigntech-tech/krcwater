-- 수자원법령 RAG — Supabase schema
-- Supabase SQL Editor 에 그대로 실행. (idempotent 하게 작성)

-- ─────────────────────────────────────────────
-- pgvector 확장
-- ─────────────────────────────────────────────
create extension if not exists vector;

-- ─────────────────────────────────────────────
-- documents : litt.ly 링크 1개 = 원문 문서 1건
-- ─────────────────────────────────────────────
create table if not exists public.documents (
  id           uuid primary key default gen_random_uuid(),
  source_url   text not null unique,
  title        text,
  law_name     text,                       -- 법령명
  doc_type     text,                       -- 법률/시행령/시행규칙/고시 등
  raw_text     text,                       -- 추출 본문
  content_hash text,                       -- 본문 해시(변경/중복 감지)
  fetched_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index if not exists idx_documents_law on public.documents (law_name);

-- updated_at 자동 갱신
create or replace function public.set_updated_at() returns trigger as $$
begin new.updated_at = now(); return new; end $$ language plpgsql;

drop trigger if exists trg_documents_updated on public.documents;
create trigger trg_documents_updated before update on public.documents
  for each row execute function public.set_updated_at();

-- ─────────────────────────────────────────────
-- chunks : 검색 단위(조문) + 임베딩
-- ─────────────────────────────────────────────
create table if not exists public.chunks (
  id          uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.documents(id) on delete cascade,
  chunk_index int  not null,
  article_no  text,                        -- 제○조 (감지된 경우)
  content     text not null,
  embedding   vector(768),                 -- text-embedding-004 = 768d
  created_at  timestamptz not null default now(),
  unique (document_id, chunk_index)
);
create index if not exists idx_chunks_doc on public.chunks (document_id);
-- 코사인 거리 기반 HNSW (pgvector)
create index if not exists idx_chunks_vec on public.chunks
  using hnsw (embedding vector_cosine_ops);

-- ─────────────────────────────────────────────
-- 유사도 검색 RPC : /api/ask 서버리스 함수가 호출
-- ─────────────────────────────────────────────
create or replace function public.match_chunks(
  query_embedding vector(768),
  match_count int default 8
)
returns table (
  id          uuid,
  document_id uuid,
  content     text,
  article_no  text,
  source_url  text,
  law_name    text,
  similarity  float
)
language sql stable
as $$
  select c.id, c.document_id, c.content, c.article_no,
         d.source_url, d.law_name,
         1 - (c.embedding <=> query_embedding) as similarity
  from public.chunks c
  join public.documents d on d.id = c.document_id
  where c.embedding is not null
  order by c.embedding <=> query_embedding
  limit match_count;
$$;

-- ─────────────────────────────────────────────
-- ingestion_runs : 수집 실행 로그(모니터링)
-- ─────────────────────────────────────────────
create table if not exists public.ingestion_runs (
  id           uuid primary key default gen_random_uuid(),
  started_at   timestamptz not null default now(),
  finished_at  timestamptz,
  links_found  int default 0,
  docs_fetched int default 0,
  docs_changed int default 0,
  chunks_upserted int default 0,
  embed_calls  int default 0,
  errors       int default 0,
  notes        text
);

-- ─────────────────────────────────────────────
-- RLS : anon/authenticated 읽기 전용, 쓰기는 service_role(RLS 우회)
-- ─────────────────────────────────────────────
alter table public.documents      enable row level security;
alter table public.chunks         enable row level security;
alter table public.ingestion_runs enable row level security;

drop policy if exists anon_read_documents on public.documents;
create policy anon_read_documents on public.documents
  for select to anon, authenticated using (true);

drop policy if exists anon_read_chunks on public.chunks;
create policy anon_read_chunks on public.chunks
  for select to anon, authenticated using (true);
-- ingestion_runs 는 정책 없음 = anon 차단. service_role 은 RLS 우회.

-- match_chunks 실행 권한 (anon/authenticated 가 RPC 호출 가능하도록)
grant execute on function public.match_chunks(vector, int) to anon, authenticated;
