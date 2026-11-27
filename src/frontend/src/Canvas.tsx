import { useEffect, useRef, useState } from "react";
import type { WidgetVersion } from "./api";
import { Icon } from "./Icon";

/** A widget page from our renderer, shown in a sandboxed frame. */
export interface Visual {
  title: string;
  html: string;
  /** Who drew it and what was checked, such as "apertus-70b · 8.4 s · figures checked". */
  caption: string;
}

export const EXAMPLE_QUESTIONS = [
  "Show my monthly spending over the last 6 months as a chart",
  "Create a widget listing the payments due in the next 30 days",
  "Which of my subscriptions got more expensive?",
  "Where does my money go?",
];

export function Canvas({
  visual,
  isLoading,
  isBusy,
  onAsk,
}: {
  visual: Visual | null;
  isLoading: boolean;
  isBusy: boolean;
  onAsk: (question: string) => void;
}) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(FRAME_HEIGHT_DEFAULT);

  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      const next = frameHeightOf(event, frameRef.current?.contentWindow);
      if (next !== null) setHeight(next);
    }
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  if (isLoading) {
    return (
      <section className="canvas" aria-label="Visual">
        <p className="hint">Loading the visual…</p>
      </section>
    );
  }

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
      <p className="canvas-caption">{visual.caption}</p>
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

export type View = "chat" | "visual";

/** The widget a `build_widget` call made, or null for any other call or a failed one. */
export function builtWidgetOf(call: {
  tool_name: string;
  result: Record<string, unknown> | null;
}): { widgetId: string; version: number; title: string } | null {
  if (call.tool_name !== "build_widget" || call.result === null) return null;
  const { widget_id, version_number, title } = call.result;
  if (typeof widget_id !== "string" || typeof version_number !== "number")
    return null;
  return {
    widgetId: widget_id,
    version: version_number,
    title: typeof title === "string" ? title : "Widget",
  };
}

/** The line under a widget's title: the model, its time and whether the labels' figures check out. */
export function captionOf(version: WidgetVersion): string {
  const parts = [
    version.model ?? "plain widget",
    `${(version.latency_ms / 1000).toFixed(1)} s`,
  ];
  const figures = version.checks.find(
    (check) => check.name === "figures_found",
  );
  if (figures !== undefined) {
    parts.push(
      figures.passed
        ? "figures checked"
        : "a label names a figure not in the data",
    );
  }
  return parts.join(" · ");
}

/** The view a narrow frame shows: a question waiting for an answer, or an error, always shows the chat. */
export function shownViewOf({
  view,
  isWaiting,
  hasError,
}: {
  view: View;
  isWaiting: boolean;
  hasError: boolean;
}): View {
  return isWaiting || hasError ? "chat" : view;
}

/** The frame's new height from a widget's message, or null; only our own frame may resize itself. */
export function frameHeightOf(
  event: Pick<MessageEvent, "source" | "data">,
  frameWindow: Window | null | undefined,
): number | null {
  if (frameWindow === null || frameWindow === undefined) return null;
  if (event.source !== frameWindow) return null;
  const message: unknown = event.data;
  if (typeof message !== "object" || message === null) return null;
  const { source, type, height } = message as Record<string, unknown>;
  if (source !== "trustroom-widget" || type !== "widget-height") return null;
  if (typeof height !== "number" || !Number.isFinite(height)) return null;
  return Math.min(Math.max(height, FRAME_HEIGHT_MIN), FRAME_HEIGHT_MAX);
}

const FRAME_HEIGHT_DEFAULT = 320;
const FRAME_HEIGHT_MIN = 80;
const FRAME_HEIGHT_MAX = 2000;
