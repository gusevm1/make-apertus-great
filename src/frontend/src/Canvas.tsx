import { useEffect, useRef, useState } from "react";
import { Icon } from "./Icon";

/** A widget page from our renderer, shown in a sandboxed frame. */
export interface Visual {
  title: string;
  html: string;
}

/** What the customer clicked in a widget, as the widget's bridge reports it. */
export interface Selection {
  component: string;
  path: string;
  label: string | null;
  value: number | null;
}

export const EXAMPLE_QUESTIONS = [
  "Show my monthly spending over the last 6 months as a chart",
  "Create a widget listing the payments due in the next 30 days",
  "Which of my subscriptions got more expensive?",
  "Where does my money go?",
];

export function Canvas({
  visual,
  isBusy,
  onAsk,
  onSelect,
}: {
  visual: Visual | null;
  isBusy: boolean;
  onAsk: (question: string) => void;
  onSelect: (selection: Selection) => void;
}) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(FRAME_HEIGHT_DEFAULT);

  // Only our own frame may resize itself or report a click; the frame's content is untrusted.
  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      const frame = frameRef.current;
      if (frame === null || event.source !== frame.contentWindow) return;
      const message: unknown = event.data;
      if (!isRecord(message) || message.source !== "trustroom-widget") return;
      if (
        message.type === "widget-height" &&
        typeof message.height === "number"
      )
        setHeight(
          Math.min(
            Math.max(message.height, FRAME_HEIGHT_MIN),
            FRAME_HEIGHT_MAX,
          ),
        );
      if (
        message.type === "widget-select" &&
        typeof message.component === "string" &&
        typeof message.path === "string"
      )
        onSelect({
          component: message.component,
          path: message.path,
          label: typeof message.label === "string" ? message.label : null,
          value: typeof message.value === "number" ? message.value : null,
        });
    }
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [onSelect]);

  if (visual === null) {
    return (
      <section className="canvas" aria-label="Visual">
        <div className="card">
          <div className="card-head">
            <h2>Ask for a chart and it appears here</h2>
          </div>
          <ul className="rows">
            {EXAMPLE_QUESTIONS.map((question) => (
              <li key={question}>
                <button
                  type="button"
                  className="row"
                  onClick={() => onAsk(question)}
                  disabled={isBusy}
                >
                  <span className="row-main">{question}</span>
                  <Icon name="chevronRight" size={16} />
                </button>
              </li>
            ))}
          </ul>
        </div>
      </section>
    );
  }

  return (
    <section className="canvas" aria-label="Visual">
      <h2>{visual.title}</h2>
      <iframe
        ref={frameRef}
        title={visual.title}
        srcDoc={visual.html}
        sandbox="allow-scripts"
        style={{ height }}
      />
    </section>
  );
}

/** The selected part as the chip above the input shows it, e.g. "Oct 2026 · 10'598.77". */
export function selectionText(selection: Selection): string {
  const name = selection.label ?? selection.path;
  if (selection.value === null) return name;
  const value = selection.value.toLocaleString("de-CH", {
    maximumFractionDigits: 2,
  });
  return `${name} · ${value}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

const FRAME_HEIGHT_DEFAULT = 320;
const FRAME_HEIGHT_MIN = 80;
const FRAME_HEIGHT_MAX = 2000;
