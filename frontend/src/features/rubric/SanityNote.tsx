// The Rubric sanity monitor on a hard Criterion's card: its fail rate over the anchor pool, a
// warning chip when that is under 2% or over 95%, and a popover of the Episodes only this
// Criterion rejects, each opening its Workstation.
import { AlertTriangle } from "lucide-react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

import { navigate } from "../core/url";
import { failRateLine, WARNING_CHIPS, warningNote } from "./sanity";
import type { CriterionPreview } from "./useDraftEdits";

function openWorkstation(episodeId: string) {
  navigate({ page: "episodes", episode: episodeId, t: null, triage: null, queue: null });
}

function OnlyRejects(props: { episodeIds: string[] }) {
  const n = props.episodeIds.length;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="rounded border px-1.5 py-0.5 text-xs underline-offset-2 hover:bg-muted"
          data-testid="only-rejects"
        >
          Only this rejects {n} Episode{n === 1 ? "" : "s"}
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72 text-xs">
        <p className="mb-2 text-muted-foreground">
          Rejected only because of this Criterion: without it each would not be Rejected.
        </p>
        <ul className="grid gap-1">
          {props.episodeIds.map((id) => (
            <li key={id}>
              <button
                type="button"
                className="font-medium tabular-nums underline underline-offset-2"
                onClick={() => {
                  openWorkstation(id);
                }}
              >
                {id}
              </button>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}

export function SanityNote(props: { preview: CriterionPreview }) {
  const { fail_rate: rate, warning, only_rejects: only } = props.preview;
  if (!rate) return null; // soft, or switched off: it never rejects, so nothing to check
  const hasNote = Boolean(warning) || only.length > 0;
  return (
    <div className="mt-1 text-xs" data-testid="sanity">
      <p className="text-muted-foreground tabular-nums" data-testid="fail-rate">
        {failRateLine(rate)}
      </p>
      {hasNote && (
        <div className="mt-1 flex flex-wrap items-center gap-2">
          {warning && (
            <span
              className="inline-flex items-center gap-1 rounded border border-amber-300 bg-amber-50 px-1.5 py-0.5 text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200"
              data-testid="sanity-warning"
            >
              <AlertTriangle className="size-3" />
              {WARNING_CHIPS[warning]}
            </span>
          )}
          {warning && <span className="text-muted-foreground">{warningNote(warning, rate)}</span>}
          {only.length > 0 && <OnlyRejects episodeIds={only} />}
        </div>
      )}
    </div>
  );
}
