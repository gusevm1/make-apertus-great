import { api, json } from "../api";

export type Certainty = "low" | "medium" | "high";

export interface TaggedRow {
  row_source: string;
  row_id: string;
  category: string;
  category_set_by: "rule" | "model" | "customer";
  category_confirmed: boolean;
  category_certainty: Certainty | null;
  category_alternative: string | null;
  severity: string;
  severity_source: "booking" | "payee" | "category" | "default";
  date: string;
  text: string;
  payee: string;
  amount_chf: string;
}

export interface SpendingCategory {
  name: string;
  description: string;
  custom: boolean;
}

export interface CategorySummary {
  category: string | null;
  total_chf: string;
  row_count: number;
  high: number;
  medium: number;
  low: number;
  unknown: number;
  confirmed: number;
}

export interface SeveritySetting {
  scope: "category" | "payee" | "booking";
  key: string;
  severity: string;
}

export interface PersonalTag {
  id: string;
  name: string;
  description: string;
  spending_count: number;
  spending_total_chf: string;
}

export interface CategorisationRun {
  id: string;
  status: "queued" | "running" | "done" | "failed";
  step: "categories" | "necessity" | "personal_tags";
  step_done: number;
  step_total: number;
  /** How far the run is, 0 to 100, computed by the server. */
  progress: number;
  skipped: number;
}

const count = new Intl.NumberFormat("de-CH");

/** What the run is doing now, in words. */
export function stepText(run: CategorisationRun): string {
  if (run.status === "queued") return "Waiting to start";
  if (run.step === "necessity") return "Rating how much you need each category";
  if (run.step === "personal_tags") return "Finding your personal tags";
  if (run.step_total === 0) return "Reading your bookings";
  return `Sorting your bookings: ${count.format(run.step_done)} of ${count.format(run.step_total)}`;
}

export interface Loaded {
  rows: TaggedRow[];
  categories: SpendingCategory[];
  summaries: CategorySummary[];
  severities: SeveritySetting[];
  tags: PersonalTag[];
}

/** One choice the customer makes: for every booking of a payee, or for one booking. */
export interface Decision {
  id: string;
  scope: "payee" | "booking";
  key: string;
  payee: string;
  rows: TaggedRow[];
  certainty: Certainty | null;
  /** Apertus's category first, then its second choice when it has one. */
  options: string[];
}

const BUILT_IN_LABELS: Record<string, string> = {
  housing: "Housing",
  groceries: "Groceries",
  loan_leasing: "Loans & leasing",
  insurance: "Insurance",
  health: "Health",
  transport: "Transport",
  restaurants: "Restaurants",
  shopping: "Shopping",
  subscriptions_media: "Subscriptions & media",
  leisure_travel: "Leisure & travel",
  taxes: "Taxes",
  children: "Children",
  other: "Other",
};

export const NECESSITIES = [
  { key: "critical", label: "Needed to live" },
  { key: "major", label: "Important to you" },
  { key: "moderate", label: "Normal, could be trimmed" },
  { key: "minor", label: "A nice extra" },
  { key: "negligible", label: "Could go tomorrow" },
] as const;

export const CERTAINTY_LABELS: Record<string, string> = {
  low: "Unsure",
  unknown: "No rating",
  medium: "Fairly sure",
};

export function labelOf(category: string): string {
  return BUILT_IN_LABELS[category] ?? category;
}

export const chf = new Intl.NumberFormat("de-CH", {
  style: "currency",
  currency: "CHF",
  minimumFractionDigits: 2,
});

// Unsure first, then unrated, then fairly sure.
const RANK: Record<string, number> = { low: 0, unknown: 1, medium: 2 };

function rankOf(certainty: Certainty | null): number {
  return RANK[certainty ?? "unknown"] ?? 3;
}

function needsDecision(row: TaggedRow): boolean {
  return (
    row.category_set_by === "model" &&
    !row.category_confirmed &&
    row.category_certainty !== "high"
  );
}

function mostCommon(values: string[]): string | null {
  const counts = new Map<string, number>();
  for (const value of values) counts.set(value, (counts.get(value) ?? 0) + 1);
  let best: string | null = null;
  for (const [value, count] of counts) {
    if (best === null || count > (counts.get(best) ?? 0)) best = value;
  }
  return best;
}

function decisionOf(
  scope: Decision["scope"],
  key: string,
  rows: TaggedRow[],
): Decision {
  const category = mostCommon(rows.map((row) => row.category)) ?? "other";
  const alternative = mostCommon(
    rows
      .map((row) => row.category_alternative)
      .filter((value): value is string => value !== null && value !== category),
  );
  return {
    id: `${scope}:${key}`,
    scope,
    key,
    payee: rows[0].payee,
    rows,
    certainty: rows.reduce<Certainty | null>(
      (worst, row) =>
        rankOf(row.category_certainty) < rankOf(worst)
          ? row.category_certainty
          : worst,
      rows[0].category_certainty,
    ),
    options: alternative === null ? [category] : [category, alternative],
  };
}

/**
 * What the customer still has to decide, unsure first. A payee whose bookings all share one
 * category is one decision for all of them; a payee whose bookings rightly differ, such as
 * payments to a friend, is one decision per unsure booking.
 */
export function decisionsOf(rows: TaggedRow[]): Decision[] {
  const byPayee = new Map<string, TaggedRow[]>();
  for (const row of rows) {
    const list = byPayee.get(row.payee) ?? [];
    list.push(row);
    byPayee.set(row.payee, list);
  }
  const decisions: Decision[] = [];
  for (const [payee, payeeRows] of byPayee) {
    const open = payeeRows.filter(needsDecision);
    if (open.length === 0) continue;
    if (new Set(payeeRows.map((row) => row.category)).size === 1) {
      decisions.push(decisionOf("payee", payee, payeeRows));
      continue;
    }
    for (const row of open)
      decisions.push(
        decisionOf("booking", `${row.row_source}:${row.row_id}`, [row]),
      );
  }
  return decisions.sort(
    (first, second) =>
      rankOf(first.certainty) - rankOf(second.certainty) ||
      second.rows.length - first.rows.length,
  );
}

export async function loadAll(token: string): Promise<Loaded> {
  const [rows, categories, summaries, severities, tags] = await Promise.all([
    api<TaggedRow[]>("/api/transaction-tags", token),
    api<SpendingCategory[]>("/api/categories", token),
    api<CategorySummary[]>("/api/category-summaries", token),
    api<SeveritySetting[]>("/api/severity-settings", token),
    api<PersonalTag[]>("/api/personal-tags", token),
  ]);
  return { rows, categories, summaries, severities, tags };
}

export async function latestRun(
  token: string,
): Promise<CategorisationRun | null> {
  const runs = await api<CategorisationRun[]>("/api/categorisations", token);
  return runs[0] ?? null;
}

/** Has Apertus judge again what the customer has not confirmed, with every category and tag. */
export async function judgeAgain(token: string): Promise<CategorisationRun> {
  return await api<CategorisationRun>(
    "/api/categorisations",
    token,
    json({ scope: "unconfirmed" }),
  );
}

export async function decide(
  token: string,
  decision: Decision,
  category: string,
): Promise<void> {
  await api(
    "/api/category-corrections",
    token,
    json({ scope: decision.scope, key: decision.key, category }),
  );
}

export async function createCategory(
  token: string,
  name: string,
  description: string,
): Promise<SpendingCategory> {
  return await api<SpendingCategory>(
    "/api/categories",
    token,
    json({ name, description }),
  );
}

export async function createTag(
  token: string,
  name: string,
  description: string,
): Promise<void> {
  await api("/api/personal-tags", token, json({ name, description }));
}

export async function setNecessity(
  token: string,
  category: string,
  severity: string,
): Promise<void> {
  await api("/api/severity-settings", token, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scope: "category", key: category, severity }),
  });
}
