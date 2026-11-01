// What the curator said to Spark in their own words this session, and what Spark said back. The
// effects (an answer, a recompiled Phrase, an edited Description) are saved on the server and show
// in the conversation for good; the words themselves are kept only until the page reloads.
import { useRef, useState } from "react";

import { useSendText } from "../interview/useInterview";

export interface Exchange {
  id: number;
  text: string;
  /** Spark's one line back; null while it reads. */
  reply: string | null;
}

export function useExchanges(onReplied: () => void) {
  const send = useSendText();
  const next = useRef(0);
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const say = (text: string, questionKey: string | null, sent: () => void) => {
    const id = ++next.current;
    setExchanges((all) => [...all, { id, text, reply: null }]);
    onReplied();
    send.mutate(
      { text, question_key: questionKey },
      {
        onSuccess: (reply) => {
          sent();
          setExchanges((all) => all.map((x) => (x.id === id ? { ...x, reply: reply.reply } : x)));
          onReplied();
        },
        // The words stay in the composer to try again; the error shows there.
        onError: () => {
          setExchanges((all) => all.filter((x) => x.id !== id));
        },
      },
    );
  };
  return { exchanges, say, pending: send.isPending, error: send.error };
}
