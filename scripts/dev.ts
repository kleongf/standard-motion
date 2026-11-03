// `pnpm dev`: run backend (with reload) and frontend until interrupted.
import { FRONTEND_URL, serveUntilInterrupted, startServers } from "./servers.ts";

const servers = await startServers({ reload: true });
console.log(`\nStandard Motion is up at ${FRONTEND_URL}\n`);
await serveUntilInterrupted(servers);
