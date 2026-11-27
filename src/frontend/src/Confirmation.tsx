import { useState, type FormEvent } from "react";
import type { SheetLine, StreamToolCall } from "./lib/useStream";

interface Props {
  toolCall: StreamToolCall;
  /** `edited` holds the arguments as the customer left them, or null when the call's own stand. */
  onAnswer: (
    isAllowed: boolean,
    edited: Record<string, unknown> | null,
  ) => Promise<void>;
}

/** Asks the customer before a tool call runs, like the e-banking's payment confirmation. */
export function Confirmation({ toolCall, onAnswer }: Props) {
  const [texts, setTexts] = useState(() => editableTexts(toolCall));
  const [answer, setAnswer] = useState<boolean | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  // ponytail: every text has to be filled, fine for a search query; an optional one needs the schema
  const isBlank = Object.values(texts).some((text) => text.trim() === "");

  async function handleAnswer(isAllowed: boolean) {
    setIsSending(true);
    setFailure(null);
    try {
      const edited =
        isAllowed && toolCall.is_editable
          ? { ...toolCall.arguments, ...texts }
          : null;
      await onAnswer(isAllowed, edited);
      setAnswer(isAllowed);
    } catch (error) {
      setFailure(
        error instanceof Error ? error.message : "Something went wrong.",
      );
    } finally {
      setIsSending(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    // Enter in a lone text field submits even without a button to press.
    if (answer !== null || isSending || isBlank) return;
    void handleAnswer(true);
  }

  return (
    <form className="sheet" aria-label={toolCall.title} onSubmit={handleSubmit}>
      <h2>{toolCall.title}?</h2>
      <dl className="facts">
        {Object.entries(texts).map(([name, text]) => {
          const id = `${toolCall.id}-${name}`;
          return (
            <div key={name}>
              <dt>
                <label htmlFor={id}>{labelOf(name)}</label>
              </dt>
              <dd>
                <input
                  id={id}
                  value={text}
                  onChange={(event) =>
                    setTexts({ ...texts, [name]: event.target.value })
                  }
                  readOnly={isSending || answer !== null}
                />
              </dd>
            </div>
          );
        })}
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
      <p className="hint">
        {toolCall.confirmation}
        {toolCall.is_editable && " You can change it first."}
      </p>
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
            type="submit"
            className="primary"
            disabled={isSending || isBlank}
          >
            {isSending ? "Sending…" : "Allow"}
          </button>
        </div>
      ) : (
        <p className="hint">
          {answer ? "Allowed, one moment…" : "Not allowed."}
        </p>
      )}
    </form>
  );
}

/** The text arguments the customer may change before allowing the call. */
function editableTexts(toolCall: StreamToolCall): Record<string, string> {
  if (!toolCall.is_editable) return {};
  return Object.fromEntries(
    Object.entries(toolCall.arguments).filter(
      (entry): entry is [string, string] => typeof entry[1] === "string",
    ),
  );
}

/** The server's lines, or the arguments the customer cannot change for a call that has none. */
function linesOf(toolCall: StreamToolCall): SheetLine[] {
  if (toolCall.lines !== null) {
    return toolCall.lines;
  }
  const texts = editableTexts(toolCall);
  return Object.entries(toolCall.arguments)
    .filter(([name]) => !(name in texts))
    .map(([name, value]) => ({
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
