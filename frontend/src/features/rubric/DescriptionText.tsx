// The compiled Description: each Phrase tinted by its status and linked to its section, and each
// meaningful word outside every Phrase highlighted, so nothing written is silently ignored.
import { cn } from "@/lib/utils";

import { descriptionSegments } from "./descriptionSegments";
import { PHRASE_LABELS, PHRASE_TONES } from "./phraseTones";
import type { RubricDraft } from "./useDraft";

export function phraseAnchor(index: number): string {
  return `phrase-${String(index)}`;
}

export function scrollToAnchor(id: string): void {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function DescriptionText(props: { draft: RubricDraft }) {
  const { description, phrases, uncovered } = props.draft;
  const segments = descriptionSegments(description, phrases, uncovered);
  return (
    <p className="text-[15px] leading-8" data-testid="compiled-description">
      {segments.map((segment, i) => {
        const phrase = segment.phrase === undefined ? undefined : phrases[segment.phrase];
        if (phrase && segment.phrase !== undefined) {
          const anchor = phraseAnchor(segment.phrase);
          return (
            <a
              key={i}
              href={`#${anchor}`}
              title={PHRASE_LABELS[phrase.status]}
              data-status={phrase.status}
              className={cn(
                "rounded box-decoration-clone px-0.5 py-0.5 underline-offset-4 hover:underline",
                PHRASE_TONES[phrase.status],
              )}
              onClick={(e) => {
                e.preventDefault();
                scrollToAnchor(anchor);
              }}
            >
              {segment.text}
            </a>
          );
        }
        if (segment.uncovered) {
          return (
            <mark
              key={i}
              data-testid="uncovered-word"
              title="In no Phrase: nothing checks it"
              className="bg-transparent text-inherit underline decoration-amber-500 decoration-wavy decoration-2 underline-offset-4"
            >
              {segment.text}
            </mark>
          );
        }
        return <span key={i}>{segment.text}</span>;
      })}
    </p>
  );
}
