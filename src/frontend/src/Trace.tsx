import { Fragment } from "react";
import type { ToolCall } from "./api";

type Step = Omit<ToolCall, "message_id"> & {
  isRunning?: boolean;
  confirmation?: string | null;
};

interface Props {
  steps: Step[];
}

/** How an answer came about, as a timeline: each round's plan, then its tool calls, each opening on click. */
export function Trace({ steps }: Props) {
  if (steps.length === 0) return null;
  return (
    <ol className="timeline">
      {steps.map((step, index) => (
        <Fragment key={step.id}>
          {step.plan !== "" && steps[index - 1]?.round !== step.round && (
            <li className="plan">
              <p>
                <strong>
                  {step.round === 0 ? "Plan" : `Plan, round ${step.round + 1}`}
                </strong>{" "}
                {step.plan}
              </p>
            </li>
          )}
          <li className={stateOf(step)}>
            <details>
              <summary>
                <span className="step-title">{step.title}</span>
                <span className="step-state">
                  {STATE_LABELS[stateOf(step)]}
                </span>
                {step.reason !== "" && (
                  <span className="step-reason">{step.reason}</span>
                )}
              </summary>
              {Object.keys(step.arguments).length > 0 && (
                <>
                  <p>Asked for</p>
                  <pre>{JSON.stringify(step.arguments, null, 2)}</pre>
                </>
              )}
              {step.error !== null && (
                <p className="step-error">{step.error}</p>
              )}
              {step.result !== null && (
                <>
                  <p>Got back</p>
                  <pre>{JSON.stringify(step.result, null, 2)}</pre>
                </>
              )}
            </details>
          </li>
        </Fragment>
      ))}
    </ol>
  );
}

type StepState = "waiting" | "running" | "failed" | "done";

const STATE_LABELS: Record<StepState, string> = {
  waiting: "Needs your OK",
  running: "Running",
  failed: "Failed",
  done: "Done",
};

function stateOf(step: Step): StepState {
  if (step.isRunning === true) {
    return (step.confirmation ?? null) !== null ? "waiting" : "running";
  }
  return step.error !== null ? "failed" : "done";
}
