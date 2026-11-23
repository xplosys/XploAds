import { defineConfig } from "@playwright/test";

// E2E tests need the API (port 8000, with migrations applied) and the web app (port 3000) running.
// CI starts both via docker compose; locally: `npm run build && npm start` + `uvicorn app.main:app`.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    channel: process.env.PW_CHANNEL || undefined,
    trace: "retain-on-failure",
  },
});
