// URL search params as app state, so reloads and links land on the same view. Every hook
// instance stays in sync: navigating fires one event they all listen to.
import { useEffect, useState } from "react";

const CHANGE = "standard-motion:navigate";

function current(): URLSearchParams {
  return new URLSearchParams(globalThis.location.search);
}

/** Set (string) or remove (null) params, adding a history entry. */
export function navigate(updates: Record<string, string | null>): void {
  const url = new URL(globalThis.location.href);
  for (const [key, value] of Object.entries(updates)) {
    if (value === null) url.searchParams.delete(key);
    else url.searchParams.set(key, value);
  }
  globalThis.history.pushState(null, "", url);
  globalThis.dispatchEvent(new Event(CHANGE));
}

export function useSearchParams(): URLSearchParams {
  const [params, setParams] = useState(current);
  useEffect(() => {
    const sync = () => {
      setParams(current());
    };
    globalThis.addEventListener("popstate", sync);
    globalThis.addEventListener(CHANGE, sync);
    return () => {
      globalThis.removeEventListener("popstate", sync);
      globalThis.removeEventListener(CHANGE, sync);
    };
  }, []);
  return params;
}
