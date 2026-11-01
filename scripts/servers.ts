// Starts the backend and frontend dev servers and waits until both answer.
import { spawn, type ChildProcess } from "node:child_process";

// WINNOW_PORT_OFFSET shifts every port, so several worktrees can run the app side by side.
export const PORT_OFFSET = Number(process.env.WINNOW_PORT_OFFSET ?? "0");
export const FRONTEND_URL = `http://127.0.0.1:${String(5173 + PORT_OFFSET)}`;

export interface Servers {
  stop: () => void;
}

export interface ServerOptions {
  reload?: boolean;
  frontendPort?: number;
  backendPort?: number;
  env?: Record<string, string>; // extra environment for the backend (e.g. DATA_DIR)
}

async function isUp(healthUrl: string): Promise<boolean> {
  try {
    return (await fetch(healthUrl)).ok;
  } catch {
    return false;
  }
}

export async function startServers(options: ServerOptions = {}): Promise<Servers> {
  const frontendPort = options.frontendPort ?? 5173 + PORT_OFFSET;
  const backendPort = options.backendPort ?? 8000 + PORT_OFFSET;
  // Proxied through the frontend, so it only answers once both are up.
  const healthUrl = `http://127.0.0.1:${String(frontendPort)}/api/health`;
  if (await isUp(healthUrl)) return { stop: () => undefined }; // reuse servers someone else started

  const backendArgs = ["run", "--project", "backend", "uvicorn", "winnow.app:app"];
  backendArgs.push("--host", "127.0.0.1", "--port", String(backendPort));
  if (options.reload) backendArgs.push("--reload", "--reload-dir", "backend/src");
  const backendEnv = { ...process.env, ...options.env };
  const frontendArgs = ["--filter", "winnow-frontend", "dev", "--port", String(frontendPort)];
  const frontendEnv = {
    ...process.env,
    WINNOW_BACKEND_URL: `http://127.0.0.1:${String(backendPort)}`,
  };

  const children: ChildProcess[] = [
    spawn("uv", backendArgs, { stdio: "inherit", env: backendEnv }),
    spawn("pnpm", frontendArgs, { stdio: "inherit", env: frontendEnv }),
  ];
  const stop = () => {
    for (const child of children) child.kill("SIGTERM");
  };

  const deadline = Date.now() + 60_000;
  while (!(await isUp(healthUrl))) {
    if (Date.now() > deadline) {
      stop();
      throw new Error(`Servers did not come up at ${healthUrl} within 60s`);
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  return { stop };
}

/** Keep running until interrupted, then stop the servers. */
export async function serveUntilInterrupted(servers: Servers): Promise<never> {
  for (const signal of ["SIGINT", "SIGTERM"] as const) {
    process.on(signal, () => {
      servers.stop();
      process.exit(0);
    });
  }
  return new Promise<never>(() => undefined);
}
