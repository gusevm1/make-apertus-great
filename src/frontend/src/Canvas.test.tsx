import { renderToStaticMarkup } from "react-dom/server";
import { expect, test } from "vitest";
import {
  Canvas,
  EXAMPLE_QUESTIONS,
  frameHeightOf,
  shownViewOf,
  type Visual,
} from "./Canvas";

const SAMPLE: Visual = {
  title: "Monthly spending",
  html: '<!doctype html><p>CHF 10\'598.77</p><script>parent.postMessage({source: "trustroom-widget", type: "widget-height", height: 240}, "*")</script>',
};

function html(visual: Visual | null) {
  return renderToStaticMarkup(
    <Canvas visual={visual} isBusy={false} onAsk={() => undefined} />,
  );
}

test("without a visual it offers questions to ask and no frame", () => {
  const output = html(null);

  expect(output).toContain("Ask for a chart and it appears here");
  for (const question of EXAMPLE_QUESTIONS)
    expect(output).toContain(
      `<button type="button" class="row"><span class="row-main">${question}</span>`,
    );
  expect(output).not.toContain("<iframe");
});

test("shows the widget page in a sandboxed frame, never as HTML in the page", () => {
  const output = html(SAMPLE);

  expect(output).toContain('sandbox="allow-scripts"');
  expect(output).toContain('title="Monthly spending"');
  expect(output).toContain("srcDoc=");
  expect(output).not.toContain("<script>");
  expect(output).not.toContain("<p>CHF");
});

test("only our own frame resizes itself, to a finite and bounded height", () => {
  const frame = {} as Window;
  const other = {} as Window;
  const message = (height: unknown) => ({
    source: "trustroom-widget",
    type: "widget-height",
    height,
  });

  expect(frameHeightOf({ source: frame, data: message(240) }, frame)).toBe(240);
  expect(frameHeightOf({ source: frame, data: message(10) }, frame)).toBe(80);
  expect(frameHeightOf({ source: frame, data: message(9999) }, frame)).toBe(
    2000,
  );
  expect(frameHeightOf({ source: other, data: message(240) }, frame)).toBe(
    null,
  );
  expect(frameHeightOf({ source: frame, data: message(Infinity) }, frame)).toBe(
    null,
  );
  expect(frameHeightOf({ source: frame, data: message(NaN) }, frame)).toBe(
    null,
  );
  expect(frameHeightOf({ source: frame, data: message(240) }, null)).toBe(null);
  expect(
    frameHeightOf(
      { source: frame, data: { type: "widget-height", height: 240 } },
      frame,
    ),
  ).toBe(null);
});

test("a waiting question or an error shows the chat in a narrow frame", () => {
  expect(
    shownViewOf({ view: "visual", isWaiting: false, hasError: false }),
  ).toBe("visual");
  expect(
    shownViewOf({ view: "visual", isWaiting: true, hasError: false }),
  ).toBe("chat");
  expect(
    shownViewOf({ view: "visual", isWaiting: false, hasError: true }),
  ).toBe("chat");
  expect(shownViewOf({ view: "chat", isWaiting: false, hasError: false })).toBe(
    "chat",
  );
});
