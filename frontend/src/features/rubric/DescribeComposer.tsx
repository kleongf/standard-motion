// The composer at the foot of the Describe conversation. Before there is a draft it holds the
// Description, to compile. After, the curator talks to Spark in their own words (ChatInput), and
// opens the Description to edit it directly (DescriptionEditor), from its bubble or from here.
import type { Question } from "../interview/useInterview";
import { ChatInput } from "./ChatInput";
import { DescriptionEditor, type Selection } from "./DescriptionEditor";
import { useDraft } from "./useDraft";

/** What the composer is doing: talking to Spark, or editing the Description (maybe with some of
 * its words selected). */
export type ComposerMode = { kind: "chat" } | { kind: "edit"; selection: Selection | null };

export function DescribeComposer(props: {
  mode: ComposerMode;
  onMode: (mode: ComposerMode) => void;
  onCompiled: () => void;
  question: Question | null;
  text: { pending: boolean; error: Error | null };
  onSendText: (text: string, questionKey: string | null, sent: () => void) => void;
}) {
  const draft = useDraft();
  const { mode, onMode } = props;
  const chat = () => {
    onMode({ kind: "chat" });
  };
  return (
    <div className="sticky bottom-0 z-10 bg-gradient-to-t from-background from-75% to-transparent pt-6 pb-5">
      <div className="mx-auto max-w-3xl px-6">
        {!draft.isSuccess ? null : !draft.data ? (
          <DescriptionEditor onSent={props.onCompiled} />
        ) : mode.kind === "edit" ? (
          <DescriptionEditor
            onSent={() => {
              chat();
              props.onCompiled();
            }}
            onCancel={chat}
            selection={mode.selection}
          />
        ) : (
          <ChatInput
            question={props.question}
            pending={props.text.pending}
            error={props.text.error}
            onSend={props.onSendText}
            onEditDescription={() => {
              onMode({ kind: "edit", selection: null });
            }}
          />
        )}
      </div>
    </div>
  );
}
