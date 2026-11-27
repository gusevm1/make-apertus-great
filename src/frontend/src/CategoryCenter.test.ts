import { expect, test } from "vitest";
import { reviewGroups } from "./CategoryCenter";

function row(
  rowId: string,
  payee: string,
  category: string,
  fields: Partial<Parameters<typeof reviewGroups>[0][number]> = {},
) {
  return {
    row_source: "booking",
    row_id: rowId,
    category,
    category_model: "apertus",
    category_confirmed: false,
    category_certainty: "high" as const,
    date: "2026-10-30",
    text: `Booking ${rowId}`,
    payee,
    amount_chf: "10.00",
    payee_usual_category: "groceries",
    ...fields,
  };
}

const ROWS = [
  row("1", "migros", "groceries"),
  row("2", "migros", "shopping"),
  row("3", "migros", "groceries", { category_certainty: "low" }),
  row("4", "migros", "shopping", { category_confirmed: true }),
  row("5", "nooch", "other", {
    category_certainty: null,
    payee_usual_category: "other",
  }),
  row("6", "nooch", "other", { payee_usual_category: "other" }),
];

test("reviews unsure rows and rows unlike their payee, not confirmed or sure ones", () => {
  const groups = reviewGroups(ROWS, null);

  expect(groups.map((group) => group.payee)).toEqual(["migros", "nooch"]);
  expect(groups[0].rows.map((each) => each.row_id)).toEqual(["2", "3"]);
  expect(groups[0].rowCount).toBe(4);
  expect(groups[1].rows.map((each) => each.row_id)).toEqual(["5"]);
});

test("keeps to one category when a bar is picked", () => {
  const groups = reviewGroups(ROWS, "shopping");

  expect(groups).toHaveLength(1);
  expect(groups[0].rows.map((each) => each.row_id)).toEqual(["2"]);
});
