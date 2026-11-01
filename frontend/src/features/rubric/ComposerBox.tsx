// The composer's text box: a growing textarea with a round send button inside it. Enter sends;
// Shift+Enter starts a new line.
import { ArrowUp, Loader2 } from "lucide-react";
import type { ReactNode, Ref } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export function ComposerBox({
  ref,
  ...props
}: {
  id?: string;
  label: string;
  value: string;
  placeholder: string;
  sendLabel: string;
  pending: boolean;
  canSend: boolean;
  onChange: (value: string) => void;
  onSend: () => void;
  ref?: Ref<HTMLTextAreaElement>;
  /** Above the text, inside the box: what the message is about. */
  context?: ReactNode;
}) {
  return (
    <div className="relative rounded-2xl border bg-card shadow-sm focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/30">
      {props.context}
      <Textarea
        ref={ref}
        id={props.id}
        aria-label={props.label}
        value={props.value}
        onChange={(e) => {
          props.onChange(e.target.value);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            props.onSend();
          }
        }}
        rows={1}
        placeholder={props.placeholder}
        className="max-h-48 min-h-14 resize-none border-0 bg-transparent px-4 py-3.5 pr-14 text-[15px] shadow-none focus-visible:ring-0 md:text-[15px] dark:bg-transparent"
      />
      <Button
        type="submit"
        size="icon"
        aria-label={props.sendLabel}
        title={props.sendLabel}
        disabled={!props.canSend || props.pending}
        className="absolute right-2.5 bottom-2.5 rounded-full"
      >
        {props.pending ? <Loader2 className="animate-spin" /> : <ArrowUp />}
      </Button>
    </div>
  );
}
