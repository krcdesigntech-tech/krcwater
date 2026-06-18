import { useState } from "react";

type Source = {
  law_name: string | null;
  article_no: string | null;
  source_url: string;
  similarity: number;
};

export default function Chat() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function ask(e: React.FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q || loading) return;
    setLoading(true);
    setAnswer("");
    setSources([]);
    setError("");
    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      if (!res.ok || !res.body) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.error || `오류 ${res.status}`);
      }
      const b64 = res.headers.get("x-sources");
      if (b64) {
        try {
          setSources(JSON.parse(decodeURIComponent(escape(atob(b64)))));
        } catch {
          /* ignore */
        }
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        setAnswer((prev) => prev + decoder.decode(value, { stream: true }));
      }
    } catch (err: any) {
      setError(String(err?.message ?? err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 760, margin: "0 auto" }}>
      <form onSubmit={ask} style={{ display: "flex", gap: 8 }}>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="수자원 법령에 대해 질문하세요 (예: 하천 점용허가 기준은?)"
          style={{ flex: 1, padding: "12px 14px", fontSize: 16, borderRadius: 8, border: "1px solid #ccc" }}
        />
        <button
          type="submit"
          disabled={loading}
          style={{ padding: "12px 20px", fontSize: 16, borderRadius: 8, border: 0, background: "#1f6feb", color: "#fff", cursor: "pointer" }}
        >
          {loading ? "검색 중…" : "질문"}
        </button>
      </form>

      {error && <p style={{ color: "#c00", marginTop: 16 }}>⚠ {error}</p>}

      {answer && (
        <div style={{ marginTop: 24, padding: 20, background: "#f6f8fa", borderRadius: 10, whiteSpace: "pre-wrap", lineHeight: 1.7 }}>
          {answer}
        </div>
      )}

      {sources.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>출처</div>
          <ol style={{ paddingLeft: 20, color: "#444", fontSize: 14 }}>
            {sources.map((s, i) => (
              <li key={i} style={{ marginBottom: 4 }}>
                <a href={s.source_url} target="_blank" rel="noopener noreferrer">
                  {s.law_name || s.source_url}
                </a>
                {s.article_no ? ` · ${s.article_no}` : ""}
                <span style={{ color: "#999" }}> (유사도 {s.similarity})</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
