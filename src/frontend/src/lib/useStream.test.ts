import { expect, test } from "vitest";
import { readEvents } from "./useStream";

test("reads complete events and keeps the unfinished one for the next chunk", () => {
  const { events, rest } = readEvents(
    'event: tool_call\ndata: {"id":"1"}\n\nevent: token\ndata: {"text":"Gr\u00fcezi"}\n\nevent: tok',
  );

  expect(events).toEqual([
    { event: "tool_call", data: '{"id":"1"}' },
    { event: "token", data: '{"text":"Gr\u00fcezi"}' },
  ]);
  expect(rest).toBe("event: tok");
});

test("finishes an event that arrived in two chunks", () => {
  const first = readEvents('event: token\ndata: {"te');
  const second = readEvents(first.rest + 'xt":"a"}\n\n');

  expect(first.events).toEqual([]);
  expect(second).toEqual({
    events: [{ event: "token", data: '{"text":"a"}' }],
    rest: "",
  });
});

test("skips comment blocks and joins data that spans lines", () => {
  const { events } = readEvents(
    ': keep-alive\n\nevent: done\ndata: {"a":\ndata: 1}\n\n',
  );

  expect(events).toEqual([{ event: "done", data: '{"a":\n1}' }]);
});
