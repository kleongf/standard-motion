// The Audit Workstation's actions: mark the Episode Good (it meets every Phrase) or Bad, picking
// the Phrase that fails so the mark names why. Marks are `audit` labels: they measure Keep
// precision and never change the Triage decision.
import { useState } from "react";

import { Button } from "@/components/ui/button";

import type { AuditItem } from "./useAudit";

const KIND_TEXT: Record<AuditItem["kind"], string> = {
  keep: "Winnow kept it",
  reject: "Winnow rejected it",
};

export function AuditCall(props: {
  item: AuditItem;
  phrases: string[];
  pending: boolean;
  onGood: () => void;
  onBad: (phrase: string) => void;
}) {
  const { item, phrases, pending } = props;
  const [picking, setPicking] = useState(false);

  return (
    <section aria-label="Your audit" className="rounded-md border bg-muted/30 p-3">
      <div className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
        Audit · {KIND_TEXT[item.kind]}
      </div>
      <p className="mt-1 text-sm leading-snug">Does it meet every Phrase of the Description?</p>
      <MarkLine item={item} />
      {picking ? (
        <div className="mt-2">
          <div className="text-xs text-muted-foreground">Which Phrase fails?</div>
          <ul className="mt-1 space-y-1" aria-label="Failing Phrase">
            {phrases.map((phrase) => (
              <li key={phrase}>
                <Button
                  size="xs"
                  variant="outline"
                  disabled={pending}
                  className="h-auto w-full justify-start py-1 text-left whitespace-normal"
                  onClick={() => {
                    setPicking(false);
                    props.onBad(phrase);
                  }}
                >
                  “{phrase}”
                </Button>
              </li>
            ))}
          </ul>
          <Button
            size="xs"
            variant="ghost"
            className="mt-1.5"
            onClick={() => {
              setPicking(false);
            }}
          >
            Cancel
          </Button>
        </div>
      ) : (
        <div className="mt-2 flex gap-1.5">
          <Button size="xs" variant="outline" disabled={pending} onClick={props.onGood}>
            Good
          </Button>
          <Button
            size="xs"
            variant="outline"
            disabled={pending}
            onClick={() => {
              setPicking(true);
            }}
          >
            Bad…
          </Button>
        </div>
      )}
    </section>
  );
}

function MarkLine(props: { item: AuditItem }) {
  const { mark, failed } = props.item;
  if (mark === null) return null;
  return (
    <p className="mt-1.5 text-xs" data-testid="audit-mark">
      {mark === "good" ? (
        <span className="text-emerald-700 dark:text-emerald-400">Marked Good</span>
      ) : (
        <span className="text-red-700 dark:text-red-400">
          Marked Bad: {failed.map((p) => `“${p}”`).join(", ")}
        </span>
      )}
    </p>
  );
}
