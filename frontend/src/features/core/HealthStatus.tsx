import { useHealth } from "./useHealth";

/** Shows only while the backend is unanswered or unreachable. */
export function HealthStatus() {
  const health = useHealth();

  if (health.isPending) return <p>Connecting to backend…</p>;
  if (health.isError) return <p role="alert">Backend unreachable</p>;
  return null;
}
