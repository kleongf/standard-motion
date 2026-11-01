// The app's one tab control: a muted pill with the chosen tab raised. Real tab roles, so each
// tab is found by `getByRole("tab", { name })`.
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface TabItem<T extends string> {
  value: T;
  label: ReactNode;
  count?: number;
  disabled?: boolean;
}

export function Tabs<T extends string>(props: {
  label: string;
  items: readonly TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div
      role="tablist"
      aria-label={props.label}
      className="inline-flex items-center gap-0.5 rounded-lg bg-muted p-0.5"
    >
      {props.items.map((item) => {
        const selected = item.value === props.value;
        return (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={selected}
            disabled={item.disabled}
            onClick={() => {
              props.onChange(item.value);
            }}
            className={cn(
              "inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring disabled:pointer-events-none disabled:opacity-50",
              selected && "bg-background font-medium text-foreground shadow-sm",
            )}
          >
            {item.label}
            {item.count !== undefined && (
              <span className="text-xs text-muted-foreground tabular-nums">{item.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
