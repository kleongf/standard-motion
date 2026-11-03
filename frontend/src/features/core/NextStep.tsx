// A page's "what to do next" line: what's missing here, and a button to the page that supplies it.
import { ArrowRight } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { goTo, type Page } from "./pages";

export function NextStep(props: {
  children?: ReactNode;
  page: Page;
  action: string;
  /** The target page's own params, e.g. the Episode to open there. */
  params?: Record<string, string | null>;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-dashed px-4 py-3 text-sm text-muted-foreground",
        props.className,
      )}
    >
      {props.children && <span className="min-w-0 flex-1">{props.children}</span>}
      <Button
        size="sm"
        variant="outline"
        onClick={() => {
          goTo(props.page, props.params);
        }}
      >
        {props.action}
        <ArrowRight />
      </Button>
    </div>
  );
}
