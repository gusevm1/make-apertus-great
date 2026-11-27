import { Fragment } from "react";
import type { ToolCall } from "./api";

type Step = Omit<ToolCall, "message_id"> & { isRunning?: boolean };

interface Props {
  steps: Step[];
}

/** How an answer came about: each round's plan and its tool calls, each opening on click. */
export function Trace({ steps }: Props) {
  return steps.map((step, index) => (
    <Fragment key={step.id}>
      {step.plan !== "" && steps[index - 1]?.round !== step.round && (
        <details className="step">
          <summary>
            {step.round === 0 ? "Plan" : `Plan, round ${step.round + 1}`}
          </summary>
          <p>{step.plan}</p>
        </details>
      )}
      <details className="step">
        <summary>
          {step.title}
          {step.isRunning === true && "…"}
          {step.error !== null && " (failed)"}
        </summary>
        <p>{step.reason}</p>
        {Object.keys(step.arguments).length > 0 && (
          <>
            <p>Asked for</p>
            <pre>{JSON.stringify(step.arguments, null, 2)}</pre>
          </>
        )}
        {step.error !== null && <p>{step.error}</p>}
        {step.result !== null && (
          <>
            <p>Got back</p>
            <pre>{JSON.stringify(step.result, null, 2)}</pre>
          </>
        )}
      </details>
    </Fragment>
  ));
}
