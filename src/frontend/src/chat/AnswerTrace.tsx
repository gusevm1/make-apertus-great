import { checkLabel, decides } from "./checks";
import { CheckIcon } from "./icons";
import type { ChatMessage } from "./types";

/** A tool call as the trace draws it, stored or still streaming. */
export interface TraceCall {
  id: string;
  tool_name: string;
  title: string;
  round: number;
  plan: string;
  reason: string;
  arguments: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string | null;
  /** Who decided the call and how long that took; a streamed call has none yet. */
  provenance?: { model: string; latency_ms: number } | null;
  isRunning?: boolean;
}

const SERVER_MODEL = "server";

/** Everything behind one answer: each plan the model wrote, each call with what went in and came back, each check. */
export function AnswerTrace({
  calls,
  provenance,
  isLive,
}: {
  calls: TraceCall[];
  /** The stored answer's model, time and checks; null while the answer is still being written. */
  provenance: ChatMessage["provenance"];
  isLive: boolean;
}) {
  const rounds = [...new Set(calls.map((call) => call.round))].sort(
    (first, second) => first - second,
  );
  const checks = provenance?.checks ?? [];
  const deciding = checks.filter((check) => decides(check.name));
  const failed = deciding.filter((check) => !check.passed).length;
  const parts = [`${calls.length} ${calls.length === 1 ? "call" : "calls"}`];
  if (checks.length > 0)
    parts.push(
      failed === 0
        ? `${deciding.length} checks passed`
        : `${failed} of ${deciding.length} checks failed`,
    );
  if (provenance !== null) parts.push(seconds(provenance.latency_ms));
  return (
    <details className="trace" open={isLive}>
      <summary>
        <b>{isLive ? "Working on it" : "How this answer was made"}</b>
        <span>{isLive ? "running" : parts.join(" · ")}</span>
      </summary>
      <ol aria-live={isLive ? "polite" : undefined}>
        {rounds.map((round) => (
          <Round
            key={round}
            calls={calls.filter((call) => call.round === round)}
          />
        ))}
        {provenance !== null && (
          <li
            data-actor="apertus"
            data-state={failed === 0 ? "done" : "failed"}
          >
            <span className="dot" aria-hidden="true" />
            <details open={failed > 0}>
              <summary>
                <span className="who">{actorOf(provenance.model)}</span>
                <span className="secs">{seconds(provenance.latency_ms)}</span>
                <b>Wrote the answer</b>
                <span className="out">
                  {provenance.model}
                  {calls.length === 0 && ", without a tool call"}
                </span>
              </summary>
              {checks.length > 0 && (
                <dl>
                  {checks.map((check) => (
                    <div
                      key={check.name}
                      data-mark={check.passed ? "kept" : "dropped"}
                    >
                      <dt>{checkLabel(check.name)}</dt>
                      <dd>
                        {check.passed && <CheckIcon />}
                        {check.detail ??
                          (check.passed ? "passed" : "did not pass")}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
            </details>
          </li>
        )}
      </ol>
    </details>
  );
}

/** One decision of the model: the plan it wrote, then the calls it asked for. */
function Round({ calls }: { calls: TraceCall[] }) {
  const [first] = calls;
  const model = first.provenance?.model ?? null;
  return (
    <>
      <li
        data-actor={model === SERVER_MODEL ? "server" : "apertus"}
        data-state="done"
      >
        <span className="dot" aria-hidden="true" />
        <details open>
          <summary>
            <span className="who">
              {model === null ? "Apertus" : actorOf(model)}
            </span>
            {first.provenance != null && (
              <span className="secs">
                {seconds(first.provenance.latency_ms)}
              </span>
            )}
            <b>Plan, round {first.round + 1}</b>
            <span className="out">{first.plan}</span>
          </summary>
        </details>
      </li>
      {calls.map((call) => (
        <Call key={call.id} call={call} />
      ))}
    </>
  );
}

function Call({ call }: { call: TraceCall }) {
  let state = "done";
  if (call.error !== null) state = "failed";
  else if (call.isRunning === true) state = "running";
  return (
    <li data-actor="server" data-state={state}>
      <span className="dot" aria-hidden="true" />
      <details open={call.error !== null}>
        <summary>
          <span className="who">Tool</span>
          {call.isRunning === true ? (
            <span className="busy" role="status" aria-label="Running" />
          ) : (
            <span className="secs">{call.tool_name}</span>
          )}
          <b>{call.title === "" ? call.tool_name : call.title}</b>
          {/* Closed, the row still says what was sent. */}
          <span className="out">
            {call.error ?? JSON.stringify(call.arguments)}
          </span>
        </summary>
        {call.reason !== "" && (
          <p className="reads">
            <b>Why</b>
            {call.reason}
          </p>
        )}
        <p className="reads">
          <b>Sent</b>
        </p>
        <pre>{pretty(call.arguments)}</pre>
        {call.isRunning !== true && (
          <>
            <p className="reads">
              <b>{call.error === null ? "Came back" : "Failed"}</b>
            </p>
            <pre>{call.error ?? pretty(call.result)}</pre>
          </>
        )}
      </details>
    </li>
  );
}

function actorOf(model: string): string {
  if (model === SERVER_MODEL) return "Server";
  return /apertus/i.test(model) ? "Apertus" : model;
}

function seconds(ms: number): string {
  return `${(ms / 1000).toFixed(1)} s`;
}

function pretty(value: unknown): string {
  return JSON.stringify(value, null, 2);
}
