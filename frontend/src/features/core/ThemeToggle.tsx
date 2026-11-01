// Light, dark or system, as three icon buttons in the sidebar footer.
import { Monitor, Moon, Sun } from "lucide-react";
import type { ComponentType } from "react";

import { cn } from "@/lib/utils";

import { useTheme, type Theme } from "./theme";

const options: { theme: Theme; label: string; icon: ComponentType<{ className?: string }> }[] = [
  { theme: "light", label: "Light", icon: Sun },
  { theme: "dark", label: "Dark", icon: Moon },
  { theme: "system", label: "System", icon: Monitor },
];

export function ThemeToggle() {
  const [theme, setTheme] = useTheme();
  return (
    <div role="radiogroup" aria-label="Theme" className="flex gap-0.5 rounded-md bg-muted p-0.5">
      {options.map(({ theme: value, label, icon: Icon }) => (
        <button
          key={value}
          type="button"
          role="radio"
          aria-checked={theme === value}
          title={label}
          onClick={() => {
            setTheme(value);
          }}
          className={cn(
            "grid size-6 place-items-center rounded text-muted-foreground hover:text-foreground",
            theme === value && "bg-background text-foreground shadow-sm",
          )}
        >
          <Icon className="size-3.5" />
          <span className="sr-only">{label}</span>
        </button>
      ))}
    </div>
  );
}
