// A disagree card's details: the anchor Episode's clip spanning what its Criteria measured, then
// each of the Phrase's Criteria with its result there, so the curator sees what disagrees.
import { cn } from "@/lib/utils";

import { STATUS_TEXT } from "../triage/TriageBadge";
import { AnchorClip } from "./AnchorClip";
import type { DisagreeQuestion } from "./useInterview";

export function DisagreeDetails(props: { question: DisagreeQuestion }) {
  const { question } = props;
  return (
    <>
      <p className="mt-1 text-xs text-muted-foreground">
        {question.episode_id} · “{question.phrase}”
      </p>
      <AnchorClip question={question} />
      <ul className="mt-2 grid gap-1 text-xs" aria-label="Criterion results">
        {question.results.map((r) => (
          <li
            key={r.criterion_id}
            className="flex items-baseline gap-2"
            data-testid="disagree-result"
          >
            <span className={cn("w-8 shrink-0 font-medium", STATUS_TEXT[r.status])}>
              {r.status}
            </span>
            <span className="min-w-0 flex-1 leading-snug">{r.english}</span>
            <span className="shrink-0 font-medium tabular-nums">{r.measurement}</span>
            {r.unconfirmed && <span className={STATUS_TEXT.unsure}>unconfirmed</span>}
          </li>
        ))}
      </ul>
    </>
  );
}
