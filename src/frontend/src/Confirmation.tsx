import { useState } from "react";
import type { StreamToolCall } from "./lib/useStream";

interface Props {
  toolCall: StreamToolCall;
  onAnswer: (isAllowed: boolean) => Promise<void>;
}

/** Asks the customer before a tool call runs, and shows what it would send. */
export function Confirmation({ toolCall, onAnswer }: Props) {
  const [answer, setAnswer] = useState<boolean | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  async function handleAnswer(isAllowed: boolean) {
    setIsSending(true);
    setFailure(null);
    try {
      await onAnswer(isAllowed);
      setAnswer(isAllowed);
    } catch (error) {
      setFailure(
        error instanceof Error ? error.message : "Something went wrong.",
      );
    } finally {
      setIsSending(false);
    }
  }

  return (
    <article className="msg confirm" role="group" aria-label={toolCall.title}>
      <strong>{toolCall.title}?</strong>
      {Object.entries(toolCall.arguments).map(([name, value]) => (
        <p key={name}>
          {name}: {typeof value === "string" ? value : JSON.stringify(value)}
        </p>
      ))}
      <p className="hint">{toolCall.confirmation}</p>
      {answer === null && (
        <div>
          <button
            type="button"
            className="primary"
            onClick={() => void handleAnswer(true)}
            disabled={isSending}
          >
            Allow
          </button>
          <button
            type="button"
            onClick={() => void handleAnswer(false)}
            disabled={isSending}
          >
            Don’t allow
          </button>
        </div>
      )}
      {answer === true && <p className="hint">Allowed, one moment…</p>}
      {answer === false && <p className="hint">Not allowed.</p>}
      {failure !== null && <p role="alert">{failure}</p>}
    </article>
  );
}
