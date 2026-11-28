import { describe, expect, it } from "vitest";
import { decisionsOf, type TaggedRow } from "./data";

let next = 0;

function row(fields: Partial<TaggedRow>): TaggedRow {
  next += 1;
  return {
    row_source: "booking",
    row_id: `BK-${next}`,
    category: "groceries",
    category_set_by: "model",
    category_confirmed: false,
    category_certainty: "low",
    category_alternative: null,
    severity: "critical",
    severity_source: "category",
    date: "2026-11-01",
    text: "Einkauf",
    payee: "migros",
    amount_chf: "10.00",
    ...fields,
  };
}

describe("decisionsOf", () => {
  it("asks once per payee, unsure first, with Apertus's two choices", () => {
    const decisions = decisionsOf([
      row({ payee: "kiosk", category_certainty: "medium", amount_chf: "500" }),
      row({ payee: "coop", category_alternative: "shopping" }),
      row({ payee: "coop", category_certainty: "high" }),
      row({ payee: "spar", category_certainty: null }),
    ]);

    expect(decisions.map((decision) => decision.key)).toEqual([
      "coop",
      "spar",
      "kiosk",
    ]);
    expect(decisions[0]).toMatchObject({
      scope: "payee",
      options: ["groceries", "shopping"],
      certainty: "low",
    });
    expect(decisions[0].rows).toHaveLength(2);
    expect(decisions[1].options).toEqual(["groceries"]);
  });

  it("asks per booking when a payee's bookings rightly differ", () => {
    const decisions = decisionsOf([
      row({ payee: "anna", category: "restaurants" }),
      row({ payee: "anna", category: "leisure_travel", row_id: "BK-anna" }),
      row({
        payee: "anna",
        category: "restaurants",
        category_certainty: "high",
      }),
    ]);

    expect(decisions).toHaveLength(2);
    expect(decisions.every((decision) => decision.scope === "booking")).toBe(
      true,
    );
    expect(decisions.map((decision) => decision.key)).toContain(
      "booking:BK-anna",
    );
  });

  it("leaves out what the customer or a rule decided and what Apertus is sure of", () => {
    expect(
      decisionsOf([
        row({ category_set_by: "customer", category_confirmed: true }),
        row({ payee: "bank", category_set_by: "rule" }),
        row({ payee: "sbb", category_certainty: "high" }),
      ]),
    ).toEqual([]);
  });
});
