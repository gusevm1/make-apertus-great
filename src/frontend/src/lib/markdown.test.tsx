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

test("links only web addresses and shows where they go", () => {
  expect(html("[your e-banking](https://evil.ch/login)")).toContain(
    '<a href="https://evil.ch/login" target="_blank" rel="noreferrer">your e-banking</a> <span class="link-host">(evil.ch)</span>',
  );
  expect(html("[click](javascript:alert(1))")).not.toContain("<a");
});

test("links a view of the TrustRoom itself in the same frame", () => {
  expect(html("Check them in the [category center](#categories).")).toContain(
    '<a href="#categories">category center</a>.',
  );
  expect(html("[x](#javascript:alert(1))")).not.toContain("<a");
  expect(html("[x](#Categories)")).not.toContain("<a");
  expect(html("[x](#settings)")).not.toContain("<a");
});

test("shows a fenced block as text, HTML and markdown inside it untouched", () => {
  expect(
    html(
      "Here:\n```html\n<script>alert(1)</script>\n  **not bold**\n```\nDone.",
    ),
  ).toBe(
    '<div class="markdown"><p>Here:</p>' +
      "<pre><code>&lt;script&gt;alert(1)&lt;/script&gt;\n  **not bold**</code></pre>" +
      "<p>Done.</p></div>",
  );
});

test("shows a fence that is still streaming as code so far", () => {
  expect(html("```\nlet x = 1")).toBe(
    '<div class="markdown"><pre><code>let x = 1</code></pre></div>',
  );
});

test("nests indented items under their category, across blank lines", () => {
  const answer =
    "* **Accounts** (CHF 58,699.68)  \n  - Privatkonto: CHF 9,716.33  \n  - Sparkonto Steuern: CHF 4,638.04  \n\n* **Pension** (CHF 55,899.65)  \n  - Vorsorgekonto Säule 3a: CHF 55,899.65";

  expect(html(answer)).toBe(
    '<div class="markdown"><ul>' +
      "<li><strong>Accounts</strong> (CHF 58,699.68)<ul><li>Privatkonto: CHF 9,716.33</li><li>Sparkonto Steuern: CHF 4,638.04</li></ul></li>" +
      "<li><strong>Pension</strong> (CHF 55,899.65)<ul><li>Vorsorgekonto Säule 3a: CHF 55,899.65</li></ul></li>" +
      "</ul></div>",
  );
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

test("takes – and • as list markers, nested by indent", () => {
  expect(html("• Einnahmen\n  – Lohn: CHF 6,500.00\n– Ausgaben")).toBe(
    '<div class="markdown"><ul>' +
      "<li>Einnahmen<ul><li>Lohn: CHF 6,500.00</li></ul></li>" +
      "<li>Ausgaben</li></ul></div>",
  );
});

test("draws nothing for a line that is only a marker", () => {
  expect(html("- Miete: –CHF 1,850.00\n-\n– \n•\n- Coop: –CHF 87.40")).toBe(
    '<div class="markdown"><ul>' +
      "<li>Miete: –CHF 1,850.00</li><li>Coop: –CHF 87.40</li></ul></div>",
  );
});

test("keeps a sentence with a dash in the middle as text", () => {
  expect(html("Miete – CHF 1,850.00\n–CHF 87.40 an Coop")).toBe(
    '<div class="markdown"><p>Miete – CHF 1,850.00<br/>–CHF 87.40 an Coop</p></div>',
  );
});
