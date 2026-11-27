import { renderToStaticMarkup } from "react-dom/server";
import { expect, test } from "vitest";
import {
  Canvas,
  EXAMPLE_QUESTIONS,
  selectionText,
  type Visual,
} from "./Canvas";

const SAMPLE: Visual = {
  title: "Monthly spending",
  html: '<!doctype html><p>CHF 10\'598.77</p><script>parent.postMessage({source: "trustroom-widget", type: "widget-height", height: 240}, "*")</script>',
};

function html(visual: Visual | null) {
  return renderToStaticMarkup(
    <Canvas
      visual={visual}
      isBusy={false}
      onAsk={() => undefined}
      onSelect={() => undefined}
    />,
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

test("names the selected part with its value the Swiss way", () => {
  expect(
    selectionText({
      component: "bar_chart",
      path: "months[5]",
      label: "Oct 2026",
      value: 10598.77,
    }),
  ).toBe("Oct 2026 · 10'598.77");
  expect(
    selectionText({
      component: "table",
      path: "payments[2]",
      label: null,
      value: null,
    }),
  ).toBe("payments[2]");
});
