import type { APIRoute } from "astro";
import { createClient } from "@supabase/supabase-js";

export const prerender = false;

// 서버 전용 env (브라우저 노출 안 됨)
const SUPABASE_URL = import.meta.env.SUPABASE_URL || import.meta.env.PUBLIC_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.SUPABASE_ANON_KEY || import.meta.env.PUBLIC_SUPABASE_ANON_KEY;
const GEMINI_API_KEY = import.meta.env.GEMINI_API_KEY;
const OPENROUTER_API_KEY = import.meta.env.OPENROUTER_API_KEY;

// OpenRouter 무료 모델 폴백 체인 (앞에서부터 시도, 유료 전환 없음)
// gemma-3-27b:free 는 2026 무료 중단됨 → gemma-4-31b:free 가 후속 무료 모델.
const MODELS = [
  "google/gemma-4-31b-it:free",
  "meta-llama/llama-3.3-70b-instruct:free",
  "qwen/qwen3-next-80b-a3b-instruct:free",
];

const SYSTEM_PROMPT =
  "너는 한국 수자원 관련 법령 도우미다. 아래 '근거 조문'에 담긴 내용만 사용해 한국어로 정확히 답한다. " +
  "답변에는 근거가 된 법령명과 조문(예: 제12조)을 함께 인용한다. " +
  "근거 조문에 답이 없으면 추측하지 말고 '제공된 법령에서 근거를 찾지 못했습니다'라고 답한다.";

type Match = {
  content: string;
  article_no: string | null;
  source_url: string;
  law_name: string | null;
  similarity: number;
};

async function embedQuery(text: string): Promise<number[]> {
  const url =
    `https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key=${GEMINI_API_KEY}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      model: "models/gemini-embedding-001",
      content: { parts: [{ text }] },
      taskType: "RETRIEVAL_QUERY",
      outputDimensionality: 768,
    }),
  });
  if (!res.ok) throw new Error(`Gemini embed ${res.status}: ${await res.text()}`);
  const json = await res.json();
  return json.embedding.values as number[];
}

async function openrouterStream(messages: any[]): Promise<Response> {
  let lastErr = "";
  for (const model of MODELS) {
    const res = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${OPENROUTER_API_KEY}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({ model, messages, stream: true, temperature: 0.2 }),
    });
    if (res.ok && res.body) return res;
    lastErr = `${model} → ${res.status} ${await res.text().catch(() => "")}`;
  }
  throw new Error(`모든 무료 모델 실패: ${lastErr}`);
}

export const POST: APIRoute = async ({ request }) => {
  try {
    const { question } = await request.json();
    if (!question || typeof question !== "string") {
      return new Response(JSON.stringify({ error: "question 누락" }), { status: 400 });
    }
    if (!GEMINI_API_KEY || !OPENROUTER_API_KEY || !SUPABASE_URL || !SUPABASE_ANON_KEY) {
      return new Response(JSON.stringify({ error: "서버 env 미설정" }), { status: 500 });
    }

    // 1) 질문 임베딩 → 2) pgvector 검색
    const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
    const queryEmbedding = await embedQuery(question);
    const { data, error } = await supabase.rpc("match_chunks", {
      query_embedding: queryEmbedding,
      match_count: 8,
    });
    if (error) throw new Error(`match_chunks: ${error.message}`);
    const matches = (data ?? []) as Match[];

    // 3) 컨텍스트 + 인용 메타 조립
    const context = matches
      .map((m, i) => `[${i + 1}] ${m.law_name ?? ""} ${m.article_no ?? ""}\n${m.content}`)
      .join("\n\n---\n\n");
    const sources = matches.map((m) => ({
      law_name: m.law_name,
      article_no: m.article_no,
      source_url: m.source_url,
      similarity: Number(m.similarity?.toFixed(3) ?? 0),
    }));

    const messages = [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: `근거 조문:\n${context}\n\n질문: ${question}` },
    ];

    // 4) OpenRouter 스트리밍 → 5) SSE 파싱해 토큰만 클라이언트로 흘림
    const upstream = await openrouterStream(messages);
    const reader = upstream.body!.getReader();
    const decoder = new TextDecoder();
    const encoder = new TextEncoder();

    const stream = new ReadableStream({
      async pull(controller) {
        const { done, value } = await reader.read();
        if (done) {
          controller.close();
          return;
        }
        for (const line of decoder.decode(value).split("\n")) {
          const t = line.trim();
          if (!t.startsWith("data:")) continue;
          const payload = t.slice(5).trim();
          if (payload === "[DONE]") continue;
          try {
            const delta = JSON.parse(payload).choices?.[0]?.delta?.content;
            if (delta) controller.enqueue(encoder.encode(delta));
          } catch {
            /* keep-alive 등 비-JSON 라인 무시 */
          }
        }
      },
      cancel() {
        reader.cancel();
      },
    });

    // 출처는 헤더(base64 JSON)로 전달 — 스트림 본문은 순수 답변 텍스트만
    return new Response(stream, {
      headers: {
        "content-type": "text/plain; charset=utf-8",
        "x-sources": Buffer.from(JSON.stringify(sources)).toString("base64"),
        "cache-control": "no-store",
      },
    });
  } catch (e: any) {
    return new Response(JSON.stringify({ error: String(e?.message ?? e) }), { status: 500 });
  }
};
