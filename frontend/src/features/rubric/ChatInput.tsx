// The composer once there is a draft: the curator talks to Spark in their own words. With a
// question open, the words answer it (a chip says which, and can be dismissed); otherwise, or with
// the chip dismissed, they say what to change in the Description, and only the changed Phrases
// recompile. The Description itself is edited from its bubble, or here.
import { CornerDownRight, PencilLine, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";

import { KIND_LABELS } from "../interview/QuestionCard";
import type { Question } from "../interview/useInterview";
import { ComposerBox } from "./ComposerBox";

function ReplyingTo(props: { question: Question; onDismiss: () => void }) {
  return (
    <div className="flex items-center gap-2 border-b px-4 py-2 text-xs text-muted-foreground">
      <CornerDownRight className="size-3.5 shrink-0" />
      <span className="min-w-0 flex-1 truncate" data-testid="replying-to">
        Replying to{" "}
        <span className="font-medium text-foreground">{KIND_LABELS[props.question.kind]}</span>:{" "}
        {props.question.prompt}
      </span>
      <button
        type="button"
        aria-label="Talk about the Description instead"
        title="Talk about the Description instead"
        onClick={props.onDismiss}
        className="rounded p-0.5 hover:bg-muted hover:text-foreground"
      >
        <X className="size-3.5" />
      </button>
    </div>
  );
}

export function ChatInput(props: {
  question: Question | null;
  pending: boolean;
  error: Error | null;
  onSend: (text: string, questionKey: string | null, sent: () => void) => void;
  onEditDescription: () => void;
}) {
  const { question } = props;
  const [text, setText] = useState("");
  // Dismissed for this question only: the next one is replied to again.
  const [dismissed, setDismissed] = useState<string | null>(null);
  const replying = question !== null && dismissed !== question.key;
  const send = () => {
    const words = text.trim();
    if (!words || props.pending) return;
    props.onSend(words, replying ? question.key : null, () => {
      setText("");
    });
  };
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        send();
      }}
    >
      {props.error && <p className="mb-2 text-sm text-destructive">{props.error.message}</p>}
      <ComposerBox
        label="Message Spark"
        value={text}
        placeholder={
          replying ? "Answer in your own words…" : "Tell Spark what to change in the Description…"
        }
        sendLabel={props.pending ? "Spark is reading…" : "Send"}
        pending={props.pending}
        canSend={Boolean(text.trim())}
        onChange={setText}
        onSend={send}
        context={
          replying && (
            <ReplyingTo
              question={question}
              onDismiss={() => {
                setDismissed(question.key);
              }}
            />
          )
        }
      />
      <div className="mt-1.5 flex items-center gap-1.5 px-1 text-xs text-muted-foreground">
        <Button
          type="button"
          size="xs"
          variant="ghost"
          className="ml-auto"
          onClick={props.onEditDescription}
        >
          <PencilLine data-icon="inline-start" />
          Edit the Description
        </Button>
      </div>
    </form>
  );
}
