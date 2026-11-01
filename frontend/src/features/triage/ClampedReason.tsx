// The Reason on one line, times in it seeking. The full text stays in the DOM (clamped by CSS);
// More shows it, and appears only when the line overflows.
import { useLayoutEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

import { SeekableText } from "./SeekableText";
import type { TextSpan } from "./useTriage";

export function ClampedReason(props: { spans: TextSpan[]; onSeek: (t: number) => void }) {
  const ref = useRef<HTMLParagraphElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [overflows, setOverflows] = useState(false);
  useLayoutEffect(() => {
    const el = ref.current;
    if (el && !expanded) setOverflows(el.scrollHeight > el.clientHeight + 1);
  }, [props.spans, expanded]);
  return (
    <div className="mt-2 flex items-baseline gap-1.5">
      <p
        ref={ref}
        className={cn(
          "min-w-0 flex-1 text-[13px] leading-snug text-muted-foreground",
          !expanded && "line-clamp-1",
        )}
        data-testid="reason"
      >
        <SeekableText spans={props.spans} onSeek={props.onSeek} />
      </p>
      {(overflows || expanded) && (
        <button
          type="button"
          aria-expanded={expanded}
          onClick={() => {
            setExpanded(!expanded);
          }}
          className="shrink-0 self-end text-xs font-semibold text-primary hover:underline"
        >
          {expanded ? "Less" : "More"}
        </button>
      )}
    </div>
  );
}
