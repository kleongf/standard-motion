// Light, dark, or the OS's choice. `index.html` applies the saved theme before first paint; this
// hook keeps `.dark` on <html> in step after that and remembers the choice in localStorage.
import { useEffect, useState } from "react";

export type Theme = "light" | "dark" | "system";

const KEY = "theme";
const DARK_QUERY = "(prefers-color-scheme: dark)";

export function resolveTheme(theme: Theme, prefersDark: boolean): "light" | "dark" {
  if (theme === "system") return prefersDark ? "dark" : "light";
  return theme;
}

function readTheme(): Theme {
  try {
    const saved = localStorage.getItem(KEY);
    return saved === "light" || saved === "dark" ? saved : "system";
  } catch {
    return "system";
  }
}

function saveTheme(theme: Theme) {
  try {
    if (theme === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, theme);
  } catch {
    // Storage blocked: the choice lasts until reload.
  }
}

export function useTheme(): [Theme, (theme: Theme) => void] {
  const [theme, setTheme] = useState(readTheme);

  useEffect(() => {
    const media = matchMedia(DARK_QUERY);
    const apply = () => {
      const dark = resolveTheme(theme, media.matches) === "dark";
      document.documentElement.classList.toggle("dark", dark);
    };
    apply();
    media.addEventListener("change", apply);
    return () => {
      media.removeEventListener("change", apply);
    };
  }, [theme]);

  const choose = (next: Theme) => {
    saveTheme(next);
    setTheme(next);
  };
  return [theme, choose];
}
