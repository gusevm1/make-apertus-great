import { useState } from "react";
import { failureMessage } from "../api";

export interface StreamToolCall {
  id: string;
  tool_name: string;
  title: string;
  icon: string;
  arguments: Record<string, unknown>;
  reason: string;
  round: number;
  plan: string;
  /** What the customer has to allow before the call runs; null when it runs without asking. */
  confirmation: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
  isRunning: boolean;
}

type ToolCallEvent = Pick<
  StreamToolCall,
  | "id"
  | "tool_name"
  | "title"
  | "icon"
  | "arguments"
  | "reason"
  | "round"
  | "plan"
  | "confirmation"
>;
type ToolResultEvent = Pick<StreamToolCall, "id" | "result" | "error">;

interface SseEvent {
  event: string;
  data: string;
}

interface StreamState {
  status: "idle" | "streaming" | "error";
  text: string;
  toolCalls: StreamToolCall[];
  /** The planning round in progress, from the last `planning` event. */
  round: number | null;
  startedAt: number | null;
  /** Time from `start` to the last tool result. */
  workedMs: number | null;
  error: string | null;
}

const IDLE: StreamState = {
  status: "idle",
  text: "",
  toolCalls: [],
  round: null,
  startedAt: null,
  workedMs: null,
  error: null,
};
const EVENT_PREFIX = "event: ";
const DATA_PREFIX = "data: ";

/** Splits buffered SSE text into its complete events and the unfinished rest. */
export function readEvents(buffer: string): {
  events: SseEvent[];
  rest: string;
} {
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";
  const events = blocks.flatMap((block) => {
    const lines = block.split("\n");
    const event = lines.find((line) => line.startsWith(EVENT_PREFIX));
    if (event === undefined) return [];
    const data = lines
      .filter((line) => line.startsWith(DATA_PREFIX))
      .map((line) => line.slice(DATA_PREFIX.length))
      .join("\n");
    return [{ event: event.slice(EVENT_PREFIX.length), data }];
  });
  return { events, rest };
}

/** Reads one `?stream=true` response: tool events and tokens land in state, `start` resolves with the `done` payload. */
export function useStream<TDone>() {
  const [state, setState] = useState<StreamState>(IDLE);

  function handleEvent({ event, data: raw }: SseEvent): TDone | null {
    if (event === "token") {
      const data: { text: string } = JSON.parse(raw);
      setState((current) => ({ ...current, text: current.text + data.text }));
    } else if (event === "planning") {
      const data: { round: number } = JSON.parse(raw);
      setState((current) => ({ ...current, round: data.round }));
    } else if (event === "tool_call") {
      const data: ToolCallEvent = JSON.parse(raw);
      const toolCall = { ...data, result: null, error: null, isRunning: true };
      setState((current) => ({
        ...current,
        toolCalls: [...current.toolCalls, toolCall],
      }));
    } else if (event === "tool_result") {
      const data: ToolResultEvent = JSON.parse(raw);
      setState((current) => ({
        ...current,
        workedMs:
          current.startedAt === null ? null : Date.now() - current.startedAt,
        toolCalls: current.toolCalls.map((toolCall) =>
          toolCall.id === data.id
            ? { ...toolCall, ...data, isRunning: false }
            : toolCall,
        ),
      }));
    } else if (event === "error") {
      const data: { message: string } = JSON.parse(raw);
      throw new Error(data.message);
    } else if (event === "done") {
      const data: TDone = JSON.parse(raw);
      return data;
    }
    return null;
  }

  async function start(
    url: string,
    token: string,
    body: unknown,
  ): Promise<TDone | null> {
    setState({ ...IDLE, status: "streaming", startedAt: Date.now() });
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });
      if (!response.ok || response.body === null) {
        throw new Error(await failureMessage(response));
      }
      const reader = response.body
        .pipeThrough(new TextDecoderStream())
        .getReader();
      let buffer = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        const { events, rest } = readEvents(buffer + value);
        buffer = rest;
        for (const event of events) {
          const result = handleEvent(event);
          if (result !== null) return result;
        }
      }
      throw new Error("The answer stopped before it was finished.");
    } catch (error) {
      // The backend stores nothing from a failed turn, so its tool calls and text go too.
      const message =
        error instanceof Error ? error.message : "The stream failed.";
      setState({ ...IDLE, status: "error", error: message });
      return null;
    }
  }

  function reset() {
    setState(IDLE);
  }

  return { ...state, start, reset };
}
