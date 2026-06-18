import { defineConfig } from "astro/config";
import react from "@astrojs/react";
import vercel from "@astrojs/vercel/serverless";

// SSR (Vercel) — /api/ask 서버리스 함수에서 RAG 질의 처리
export default defineConfig({
  output: "server",
  adapter: vercel(),
  integrations: [react()],
});
