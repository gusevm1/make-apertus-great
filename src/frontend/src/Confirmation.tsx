import { useState } from "react";
import type { SheetLine, StreamToolCall } from "./lib/useStream";

interface Props {
  toolCall: StreamToolCall;
  onAnswer: (isAllowed: boolean) => Promise<void>;
}

/** Asks the customer before a tool call runs, like the e-banking's payment confirmation. */
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
    <section className="sheet" role="group" aria-label={toolCall.title}>
      <h2>{toolCall.title}?</h2>
      <dl className="facts">
        {linesOf(toolCall).map(({ label, value, detail }) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>
              {value}
              {detail !== null && <span className="detail">{detail}</span>}
            </dd>
          </div>
        ))}
      </dl>
      <p className="hint">{toolCall.confirmation}</p>
      {failure !== null && (
        <p className="error-note" role="alert">
          {failure}
        </p>
      )}
      {answer === null ? (
        <div className="sheet-actions">
          <button
            type="button"
            onClick={() => void handleAnswer(false)}
            disabled={isSending}
          >
            Don’t allow
          </button>
          <button
            type="button"
            className="primary"
            onClick={() => void handleAnswer(true)}
            disabled={isSending}
          >
            {isSending ? "Sending…" : "Allow"}
          </button>
        </div>
      ) : (
        <p className="hint">
          {answer ? "Allowed, one moment…" : "Not allowed."}
        </p>
      )}
    </section>
  );
}

/** The server's lines, or the raw arguments for a call that has none, such as a web search. */
function linesOf(toolCall: StreamToolCall): SheetLine[] {
  if (toolCall.lines !== null) {
    return toolCall.lines;
  }
  return Object.entries(toolCall.arguments).map(([name, value]) => ({
    label: labelOf(name),
    value: typeof value === "string" ? value : JSON.stringify(value),
    detail: null,
  }));
}

/** `search_query` → "Search query". */
function labelOf(name: string): string {
  const words = name.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
