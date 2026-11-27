import { renderToStaticMarkup } from "react-dom/server";
import { expect, test } from "vitest";
import {
  builtWidgetOf,
  Canvas,
  captionOf,
  EXAMPLE_QUESTIONS,
  frameHeightOf,
  shownViewOf,
  type Visual,
} from "./Canvas";

const SAMPLE: Visual = {
  title: "Monthly spending",
  html: '<!doctype html><p>CHF 10\'598.77</p><script>parent.postMessage({source: "trustroom-widget", type: "widget-height", height: 240}, "*")</script>',
  caption: "apertus-70b · 8.4 s · figures checked",
};

function html(visual: Visual | null, isLoading = false) {
  return renderToStaticMarkup(
    <Canvas
      visual={visual}
      isLoading={isLoading}
      isBusy={false}
      onAsk={() => undefined}
    />,
  );
}

test("while a version loads it says so instead of the old widget", () => {
  const output = html(SAMPLE, true);

  expect(output).toContain("Loading the visual…");
  expect(output).not.toContain("<iframe");
});

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

test("only a build_widget call with its widget names a widget to show", () => {
  const result = { widget_id: "W-1", version_number: 1, title: "Spending" };

  expect(builtWidgetOf({ tool_name: "build_widget", result })).toEqual({
    widgetId: "W-1",
    version: 1,
    title: "Spending",
  });
  expect(builtWidgetOf({ tool_name: "sum_by_month", result })).toBe(null);
  expect(builtWidgetOf({ tool_name: "build_widget", result: null })).toBe(null);
  expect(
    builtWidgetOf({ tool_name: "build_widget", result: { widget_id: 7 } }),
  ).toBe(null);
});

test("the caption says who drew the widget and whether its labels' figures check out", () => {
  const version = {
    widget_id: "W-1",
    number: 1,
    title: "Spending",
    html: "",
    model: "apertus-70b",
    latency_ms: 8400,
    checks: [{ name: "figures_found", passed: false, detail: "1 of 2 found" }],
  };

  expect(captionOf(version)).toBe(
    "apertus-70b · 8.4 s · a label names a figure not in the data",
  );
  expect(captionOf({ ...version, model: null, checks: [] })).toBe(
    "plain widget · 8.4 s",
  );
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
