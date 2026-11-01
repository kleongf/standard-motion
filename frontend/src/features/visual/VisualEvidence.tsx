// A visual Criterion's Evidence: the clip Spark watched, and each sample's prompt, answer,
// confidence and what it saw.
import { cn } from "@/lib/utils";

import type { components } from "../../api/schema";
import { STATUS_TEXT } from "../triage/TriageBadge";
import { visualClipUrl } from "./visualClip";

type VisualAnswers = components["schemas"]["VisualAnswers"];
type VisualClip = components["schemas"]["VisualClip"];

function clipText(clip: VisualClip): string {
  const framing = clip.box ? "cropped to the object and its target" : "whole view";
  return `${clip.camera} · ${clip.start.toFixed(1)}–${clip.end.toFixed(1)} s · ${framing}`;
}

export function VisualEvidence(props: { episodeId: string; visual: VisualAnswers }) {
  const { clip, samples } = props.visual;
  return (
    <div className="grid gap-2" data-testid="visual-evidence">
      {clip && (
        <figure className="grid gap-1">
          <video
            aria-label="Clip Spark watched"
            src={visualClipUrl(props.episodeId, clip.name)}
            className="max-h-40 w-fit rounded border bg-black"
            controls
            loop
            muted
            playsInline
            preload="auto"
          />
          <figcaption className="text-xs text-muted-foreground">{clipText(clip)}</figcaption>
        </figure>
      )}
      <ol className="grid gap-1.5" aria-label="Spark's samples">
        {samples.map((s, i) => (
          <li key={s.prompt} className="grid gap-0.5 text-xs">
            <span className="text-muted-foreground">
              {i + 1}. {s.prompt}
            </span>
            {s.reply ? (
              <span>
                <span className={cn("font-medium", STATUS_TEXT[s.reply.answer])}>
                  {s.reply.answer}
                </span>
                <span className="text-muted-foreground tabular-nums">
                  {" "}
                  · confidence {s.reply.confidence.toFixed(2)}
                </span>
                {" · "}
                {s.reply.observation}
              </span>
            ) : (
              <span className={STATUS_TEXT.unsure}>no answer: {s.error}</span>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
