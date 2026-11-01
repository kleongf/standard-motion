// Reason and Evidence text: a span with a time is a link that seeks the playhead there.
import type { TextSpan } from "./useTriage";

export function SeekableText(props: { spans: TextSpan[]; onSeek: (t: number) => void }) {
  return (
    <>
      {props.spans.map((span, i) => {
        const { t } = span;
        if (t === null || t === undefined) return <span key={i}>{span.text}</span>;
        return (
          <button
            key={i}
            type="button"
            className="underline decoration-dotted underline-offset-2 hover:decoration-solid"
            onClick={() => {
              props.onSeek(t);
            }}
          >
            {span.text}
          </button>
        );
      })}
    </>
  );
}
