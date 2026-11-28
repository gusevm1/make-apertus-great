import type { AnyPayload, Template, Tile } from "./types";

/** One place in a column: a tile, or two small tiles side by side. */
export type Unit = { tiles: [Tile] | [Tile, Tile] };

export interface Columns {
  left: Unit[];
  right: Unit[];
}

const SMALL: ReadonlySet<Template> = new Set([
  "savings_goal",
  "bill",
  "regular_payments",
  "pillar_3a",
  "card_bill",
]);

export function isSmall(template: Template): boolean {
  return SMALL.has(template);
}

// About how tall each tile is drawn at 1440 px, so the two columns come out even.
function heightOf(payload: AnyPayload): number {
  switch (payload.template) {
    case "bills_until_payday":
      return 160 + 35 * payload.rows.length;
    case "due_soon":
      return 170 + 36 * payload.rows.length;
    case "merchant_spending":
      return 170 + 29 * payload.rows.length;
    case "account_balances":
      return 170 + 34 * payload.rows.length;
    case "regular_payments":
      return 160 + 34 * payload.rows.length;
    case "mortgage":
      return 200 + 34 * payload.tranches.length;
    case "payday_balance":
      return 330;
    case "monthly_spending":
    case "income_and_spending":
      return 300;
    case "net_worth":
      return 275;
    case "savings_goal":
      return 255;
    case "expected_income":
      return 230;
    case "pillar_3a":
      return 230;
    case "securities":
    case "bill":
    case "card_bill":
      return 220;
  }
}

const GAP = 20;

function unitHeight(unit: Unit): number {
  return Math.max(...unit.tiles.map((tile) => heightOf(tile.payload))) + GAP;
}

/** Two small tiles that follow each other share a row; the first tile, the hero, never does. */
export function unitsOf(tiles: Tile[]): Unit[] {
  const units: Unit[] = [];
  let index = 0;
  while (index < tiles.length) {
    const tile = tiles[index];
    const next = tiles[index + 1];
    const canPair =
      index > 0 &&
      next !== undefined &&
      isSmall(tile.template) &&
      isSmall(next.template);
    units.push({ tiles: canPair ? [tile, next] : [tile] });
    index += canPair ? 2 : 1;
  }
  return units;
}

/**
 * The left column takes the first units, the right column the rest, split where the two come out
 * most even. Reading order stays top to bottom, left then right, and the hero stays top left.
 */
export function columnsOf(tiles: Tile[]): Columns {
  const units = unitsOf(tiles);
  if (units.length <= 1) return { left: units, right: [] };
  const heights = units.map(unitHeight);
  const total = heights.reduce((sum, height) => sum + height, 0);
  let bestSplit = 1;
  let bestDifference = Infinity;
  let leftHeight = 0;
  for (let split = 1; split < units.length; split += 1) {
    leftHeight += heights[split - 1];
    const difference = Math.abs(leftHeight - (total - leftHeight));
    if (difference < bestDifference) {
      bestDifference = difference;
      bestSplit = split;
    }
  }
  return { left: units.slice(0, bestSplit), right: units.slice(bestSplit) };
}
