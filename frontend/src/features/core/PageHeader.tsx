// Every page's shape: one padding and width, a header with the title, an optional one-line
// subtitle, actions on the right and a toolbar row underneath, and section headings to match.
import type { ReactNode } from "react";

import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

import { InfoTip } from "./InfoTip";

/** `content` pages are read top to bottom; `full` pages are workstations that use the width. */
export function Page(props: { width: "content" | "full"; children: ReactNode }) {
  return (
    <div className={cn("px-8 py-6", props.width === "content" && "mx-auto max-w-6xl")}>
      {props.children}
    </div>
  );
}

export function PageHeader(props: {
  title: string;
  subtitle?: ReactNode;
  info?: ReactNode;
  /** 0 to 1. */
  progress?: number | undefined;
  actions?: ReactNode;
  /** A toolbar row under the title: tabs, filters, a Run button. */
  children?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("mb-6", props.className)}>
      <div className="flex items-start gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <h1 className="text-xl font-semibold">{props.title}</h1>
            {props.info && <InfoTip label={props.title}>{props.info}</InfoTip>}
          </div>
          {props.subtitle && (
            <div className="mt-0.5 text-sm text-muted-foreground tabular-nums">
              {props.subtitle}
            </div>
          )}
          {props.progress !== undefined && (
            <Progress value={props.progress * 100} className="mt-2 h-1 max-w-xs" />
          )}
        </div>
        {props.actions && <div className="flex shrink-0 items-center gap-2">{props.actions}</div>}
      </div>
      {props.children && (
        <div className="mt-4 flex flex-wrap items-center gap-2">{props.children}</div>
      )}
    </header>
  );
}

/** A section's heading: its title, a short live fact beside it, the explanation behind an "i". */
export function SectionHeading(props: {
  title: string;
  level?: 2 | 3;
  meta?: ReactNode;
  info?: ReactNode;
  actions?: ReactNode;
}) {
  const Heading = props.level === 3 ? "h3" : "h2";
  return (
    <div className="flex items-center gap-2">
      <Heading className={cn("font-semibold", props.level === 3 ? "text-sm" : "text-base")}>
        {props.title}
      </Heading>
      {props.info && <InfoTip label={props.title}>{props.info}</InfoTip>}
      {props.meta && (
        <span className="text-sm text-muted-foreground tabular-nums">{props.meta}</span>
      )}
      {props.actions && <div className="ml-auto flex items-center gap-2">{props.actions}</div>}
    </div>
  );
}
