import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, expect, test, vi } from "vitest";
import type { ToolCall } from "../api";
import { Answer } from "./Answer";

const CALL: ToolCall = {
  id: "call-1",
  message_id: "message-1",
  tool_name: "list_accounts",
  title: "Read your accounts",
  round: 0,
  plan: "Read the accounts first.",
  reason: "The question names an account.",
  arguments: {},
  result: { accounts: [] },
  error: null,
  provenance: { model: "apertus", latency_ms: 900 },
};

function html() {
  return renderToStaticMarkup(
    <Answer
      token="token"
      text="You hold two accounts."
      calls={[CALL]}
      provenance={{
        model: "apertus",
        latency_ms: 1200,
        sources: [{ id: "source-1", title: "SNB", url: "https://www.snb.ch" }],
      }}
      proposals={[]}
      onOpenBoard={() => undefined}
    />,
  );
}

function storageWith(value: string | null) {
  return { getItem: () => value, setItem: () => undefined };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

test("an answer hides its trace but keeps its sources by default", () => {
  vi.stubGlobal("localStorage", storageWith(null));
  const output = html();
  expect(output).toContain("You hold two accounts.");
  expect(output).toContain("https://www.snb.ch");
  expect(output).not.toContain('class="trace"');
  expect(output).not.toContain("Read the accounts first.");
});

test("an answer shows its trace in debug mode", () => {
  vi.stubGlobal("localStorage", storageWith("on"));
  const output = html();
  expect(output).toContain('class="trace"');
  expect(output).toContain("Read the accounts first.");
});
