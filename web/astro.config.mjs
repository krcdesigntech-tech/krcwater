import { defineConfig } from "astro/config";
import react from "@astrojs/react";
import vercel from "@astrojs/vercel";

// SSR (Vercel) — /api/ask 서버리스 함수에서 RAG 질의 처리
// @astrojs/vercel v8: import 경로가 "/serverless" 없이 "@astrojs/vercel"
export default defineConfig({
  output: "server",
  adapter: vercel(),
  integrations: [react()],
});
