import { defineConfig } from "@playwright/test";

// The e2e server (scripts/e2e-server.ts) runs on its own ports with synthetic Episodes, which
// the specs share out between them (e2e/helpers.ts EPISODES).
const portOffset = Number(process.env.WINNOW_PORT_OFFSET ?? "0");
const baseURL = `http://127.0.0.1:${String(5174 + portOffset)}`;

export default defineConfig({
  testDir: "e2e",
  outputDir: "artifacts/e2e",
  forbidOnly: Boolean(process.env.CI),
  workers: 1, // the tests share one e2e server and its data dir
  reporter: process.env.CI ? "github" : "list",
  use: { baseURL, screenshot: "on", trace: "retain-on-failure" },
  webServer: {
    command: "node scripts/e2e-server.ts",
    url: `${baseURL}/api/health`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
