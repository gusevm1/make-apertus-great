import { renderToStaticMarkup } from "react-dom/server";
import { expect, test } from "vitest";
import { Markdown } from "./markdown";

function html(text: string) {
  return renderToStaticMarkup(<Markdown text={text} />);
}

test("shows bold figures and the accounts as a list", () => {
  const answer =
    "Your total assets are **CHF 187,112.29**.  \n\n**Accounts:**\n* Privatkonto: CHF 9,716.33  \n* Sparkonto Steuern: CHF 4,638.04";

  expect(html(answer)).toBe(
    '<div class="markdown"><p>Your total assets are <strong>CHF 187,112.29</strong>.</p>' +
      "<p><strong>Accounts:</strong></p>" +
      "<ul><li>Privatkonto: CHF 9,716.33</li><li>Sparkonto Steuern: CHF 4,638.04</li></ul></div>",
  );
});

test("keeps HTML in the answer as text", () => {
  const output = html(
    '<script>alert(1)</script> <img src=x onerror="alert(2)">',
  );

  expect(output).not.toContain("<script");
  expect(output).not.toContain("<img");
  expect(output).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
});

test("links only web addresses", () => {
  expect(html("[bank](https://example.ch/a)")).toContain(
    '<a href="https://example.ch/a" target="_blank" rel="noreferrer">bank</a>',
  );
  expect(html("[click](javascript:alert(1))")).not.toContain("<a");
});

test("shows headings, numbered lists, code and italics", () => {
  expect(html("## Plan\n1. one\n2. *two* and `x_y`")).toBe(
    '<div class="markdown"><p><strong>Plan</strong></p>' +
      '<ol start="1"><li>one</li><li><em>two</em> and <code>x_y</code></li></ol></div>',
  );
});

test("leaves half-written and in-word markers alone", () => {
  expect(html("Total **CHF 1")).toBe(
    '<div class="markdown"><p>Total **CHF 1</p></div>',
  );
  expect(html("2 * 3 * 4 and snake_case_name")).toBe(
    '<div class="markdown"><p>2 * 3 * 4 and snake_case_name</p></div>',
  );
});

test("keeps single line breaks inside a paragraph", () => {
  expect(html("line one\nline two")).toBe(
    '<div class="markdown"><p>line one<br/>line two</p></div>',
  );
});
