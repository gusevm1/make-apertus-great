import type { TraceStep } from "../lib/useStream";
import { CheckIcon } from "./icons";

const ACTORS = { server: "Server", apertus: "Apertus" } as const;

/** How a board was built, step by step: what the server read and computed, what Apertus answered. */
export function BuildTrace({
  steps,
  isLive,
  isOpen,
}: {
  steps: TraceStep[];
  isLive: boolean;
  isOpen: boolean;
}) {
  const seconds = steps.reduce((sum, step) => sum + (step.seconds ?? 0), 0);
  const hasFailed = steps.some((step) => step.has_failed);
  let note = `${steps.length} steps · ${seconds.toFixed(1)} s`;
  if (isLive) note = "running";
  else if (hasFailed) note += " · Apertus did not answer in time";
  return (
    <details className="trace" open={isOpen}>
      <summary>
        <b>{isLive ? "Building your board" : "How this board was built"}</b>
        <span>{note}</span>
      </summary>
      <p className="lead">
        The server reads and computes every figure. Apertus decides what matters
        and names it.
      </p>
      <ol aria-live={isLive ? "polite" : undefined}>
        {steps.map((step) => (
          <Step key={step.name} step={step} />
        ))}
      </ol>
    </details>
  );
}

function Step({ step }: { step: TraceStep }) {
  let state = "running";
  if (step.has_failed) state = "failed";
  else if (step.is_done) state = "done";
  return (
    <li data-actor={step.actor} data-state={state}>
      <span className="dot" aria-hidden="true" />
      {/* What Apertus answered is the part to read; the server's steps open on demand. */}
      <details open={step.actor === "apertus" && step.is_done}>
        <summary>
          <span className="who">{ACTORS[step.actor]}</span>
          {step.seconds === null ? (
            <span className="busy" role="status" aria-label="Running" />
          ) : (
            <span className="secs">{step.seconds.toFixed(1)} s</span>
          )}
          <b>{step.title}</b>
          {step.summary !== null && <span className="out">{step.summary}</span>}
        </summary>
        <p className="reads">
          <b>{step.actor === "apertus" ? "Was given" : "Reads"}</b>
          {step.reads}
        </p>
        {step.items.length > 0 && (
          <dl>
            {step.items.map((item, index) => (
              // The list is fixed once the step is done, so its order identifies a line.
              <div key={index} data-mark={item.mark ?? undefined}>
                <dt>{item.label}</dt>
                <dd>
                  {item.mark === "kept" && <CheckIcon />}
                  {item.text}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </details>
    </li>
  );
}
