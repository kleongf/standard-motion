// Playwright's web server: the app on its own ports, against a fresh data dir and synthetic
// droid_100 Episodes, so e2e runs never touch real data or a dev server already running. Meta
// calls are served from replies recorded on those Episodes (backend/tests/record_meta.py).
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

import { PORT_OFFSET, serveUntilInterrupted, startServers } from "./servers.ts";

const E2E_FRONTEND_PORT = 5174 + PORT_OFFSET;
const root = resolve("artifacts", "e2e-data");

rmSync(root, { recursive: true, force: true });
// Spark's recorded replies, plus the scripted answers to visual Criteria, the scripted voice turn,
// the scripted Spark Reason, the interview specs' scripted compiles and the dry-run spec's
// scripted compile and visual answers (written free by backend/tests/record_visual.py,
// record_voice.py, record_reason.py, record_interview.py and record_dry_run.py: answers about test
// patterns would mean nothing, a live microphone never captures the same bytes twice, and the
// recorded compile's Criteria never disagree).
const recordings = resolve("backend", "tests", "recordings");
const replay = resolve(root, "replay.jsonl");
mkdirSync(root, { recursive: true });
writeFileSync(
  replay,
  [
    "fixture_episodes.jsonl",
    "visual_answers.jsonl",
    "voice_answers.jsonl",
    "reason_answers.jsonl",
    "interview_answers.jsonl",
    "dry_run_answers.jsonl",
  ]
    .map((name) => readFileSync(resolve(recordings, name), "utf8"))
    .join(""),
);
const fixtures = ["run", "--project", "backend", "winnow", "fixtures", resolve(root, "droid_100")];
execFileSync("uv", [...fixtures, "--episodes", "24"], { stdio: "inherit" });

const servers = await startServers({
  frontendPort: E2E_FRONTEND_PORT,
  backendPort: 8001 + PORT_OFFSET,
  // With no key, e2e can never reach the Meta API; replay answers instead.
  env: {
    DATA_DIR: resolve(root, "data"),
    DROID100_ROOT: resolve(root, "droid_100"),
    MODEL_API_KEY: "",
    META_REPLAY: replay,
  },
});
await serveUntilInterrupted(servers);
