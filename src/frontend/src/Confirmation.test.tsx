import { renderToStaticMarkup } from "react-dom/server";
import { expect, test } from "vitest";
import { Confirmation } from "./Confirmation";
import type { StreamToolCall } from "./lib/useStream";

const SEARCH: StreamToolCall = {
  id: "call-1",
  tool_name: "search_web",
  title: "Search the web",
  icon: "globe",
  arguments: { query: "SNB Leitzins aktuell", limit: 5 },
  reason: "Current rate.",
  round: 0,
  plan: "Search the web.",
  confirmation: "This sends the query to search engines outside the bank.",
  lines: null,
  is_editable: true,
  result: null,
  error: null,
  isRunning: true,
};

function html(toolCall: StreamToolCall) {
  return renderToStaticMarkup(
    <Confirmation toolCall={toolCall} onAnswer={async () => undefined} />,
  );
}

test("an editable call offers its text arguments as labelled fields", () => {
  const output = html(SEARCH);

  expect(output).toContain('<label for="call-1-query">Query</label>');
  expect(output).toContain(
    '<input id="call-1-query" value="SNB Leitzins aktuell"/>',
  );
  expect(output).toContain("<dt>Limit</dt><dd>5</dd>");
  expect(output).toContain("You can change it first.");
});

test("a call that is not editable shows its arguments as text only", () => {
  const output = html({ ...SEARCH, is_editable: false });

  expect(output).not.toContain("<input");
  expect(output).toContain("<dd>SNB Leitzins aktuell</dd>");
  expect(output).not.toContain("You can change it first.");
});

test("Allow is off while a field is empty", () => {
  const output = html({ ...SEARCH, arguments: { query: " " } });

  expect(output).toContain(
    '<button type="submit" class="primary" disabled="">',
  );
});
