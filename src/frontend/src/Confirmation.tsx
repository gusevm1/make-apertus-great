import { useState } from "react";
import type { StreamToolCall } from "./lib/useStream";

interface Props {
  toolCall: StreamToolCall;
  onAnswer: (isAllowed: boolean) => Promise<void>;
}

/** Asks the customer before a tool call runs, and shows what it would send. */
export function Confirmation({ toolCall, onAnswer }: Props) {
  const [isAnswered, setIsAnswered] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAnswer(isAllowed: boolean) {
    setIsAnswered(true);
    setError(null);
    try {
      await onAnswer(isAllowed);
    } catch (error) {
      setIsAnswered(false);
      setError(
        error instanceof Error ? error.message : "Something went wrong.",
      );
    }
  }

  return (
    <article className="msg confirm" role="group" aria-label={toolCall.title}>
      <strong>{toolCall.title}?</strong>
      {Object.entries(toolCall.arguments).map(([name, value]) => (
        <p key={name}>
          {name}: {String(value)}
        </p>
      ))}
      <p className="hint">{toolCall.confirmation}</p>
      <div>
        <button
          type="button"
          className="primary"
          onClick={() => void handleAnswer(true)}
          disabled={isAnswered}
        >
          Allow
        </button>
        <button
          type="button"
          onClick={() => void handleAnswer(false)}
          disabled={isAnswered}
        >
          Don’t allow
        </button>
      </div>
      {error !== null && <p role="alert">{error}</p>}
    </article>
  );
}
