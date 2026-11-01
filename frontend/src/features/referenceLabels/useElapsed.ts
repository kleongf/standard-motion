// The per-Episode timer: seconds since the Episode opened, ticking once a second for display;
// `read()` gives the exact value to save. Remount (key by Episode) to restart it.
import { useCallback, useEffect, useState } from "react";

export function useElapsed(): { seconds: number; read: () => number } {
  const [started] = useState(() => performance.now());
  const read = useCallback(() => (performance.now() - started) / 1000, [started]);
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const id = setInterval(() => {
      setSeconds(Math.floor(read()));
    }, 1000);
    return () => {
      clearInterval(id);
    };
  }, [read]);
  return { seconds, read };
}

export function clock(seconds: number): string {
  const s = Math.floor(seconds);
  return `${String(Math.floor(s / 60))}:${String(s % 60).padStart(2, "0")}`;
}
