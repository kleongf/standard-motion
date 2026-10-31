// The pieces of the Describe conversation: Spark's turn (its mark, then prose with no bubble), the
// curator's bubble, and the typing indicator while Spark works.
import { Sparkles } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

function AgentMark() {
  return (
    <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary ring-1 ring-primary/20">
      <Sparkles className="size-3.5" />
    </span>
  );
}

/** Spark's turn. `mark={false}` lines it up under the previous turn, for a card that follows. */
export function AgentRow(props: { children: ReactNode; mark?: boolean; className?: string }) {
  return (
    <div className={cn("flex gap-3", props.className)}>
      {props.mark === false ? <span className="w-7 shrink-0" /> : <AgentMark />}
      <div className="min-w-0 flex-1 text-[15px] leading-relaxed">{props.children}</div>
    </div>
  );
}

export function UserBubble(props: { children: ReactNode; className?: string }) {
  return (
    <div className="flex justify-end">
      <div
        className={cn(
          "max-w-[85%] rounded-2xl rounded-br-md bg-muted px-4 py-2.5 text-[15px] leading-relaxed",
          props.className,
        )}
      >
        {props.children}
      </div>
    </div>
  );
}

export function TypingIndicator(props: { label: string }) {
  return (
    <AgentRow>
      <span className="inline-flex h-7 items-center gap-3 text-sm text-muted-foreground">
        <span className="inline-flex items-center gap-1" aria-hidden>
          {[0, 150, 300].map((delay) => (
            <span
              key={delay}
              className="size-1.5 animate-bounce rounded-full bg-muted-foreground/60"
              style={{ animationDelay: `${String(delay)}ms` }}
            />
          ))}
        </span>
        {props.label}
      </span>
    </AgentRow>
  );
}
