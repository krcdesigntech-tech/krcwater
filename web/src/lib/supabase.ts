import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.PUBLIC_SUPABASE_URL;
const anon = import.meta.env.PUBLIC_SUPABASE_ANON_KEY;

/**
 * env 미설정 시 createClient 가 throw → SSR 500. Supabase 셋업 전에도 UI 가
 * 빈 데이터로 렌더되도록 안전한 스텁을 쓴다. env 가 채워지면 실클라이언트로 전환.
 * (발주공고 web/src/lib/supabase.ts 패턴 차용)
 */
function makeStub() {
  const builder: any = {};
  const ret = () => builder;
  for (const m of ["select", "eq", "order", "limit", "range"]) builder[m] = ret;
  builder.then = (resolve: (v: any) => void) => resolve({ data: [], count: 0, error: null });
  return { from: () => builder } as any;
}

if (!url || !anon) {
  console.warn("[supabase] PUBLIC_SUPABASE_URL / PUBLIC_SUPABASE_ANON_KEY 미설정 — 빈 데이터 스텁");
}

// anon 키 + RLS(읽기 전용)
export const supabase: any = url && anon ? createClient(url, anon) : makeStub();
