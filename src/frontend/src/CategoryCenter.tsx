import { useEffect, useRef, useState } from "react";
import { api, json } from "./api";
import { Icon } from "./Icon";

const CATEGORY_NAMES: Record<string, string> = {
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

const CERTAINTIES = [
  { key: "confirmed", label: "Confirmed by you" },
  { key: "high", label: "Sure" },
  { key: "medium", label: "Fairly sure" },
  { key: "low", label: "Unsure" },
  { key: "unknown", label: "No rating" },
] as const;

type CertaintyKey = (typeof CERTAINTIES)[number]["key"];

interface CategorySummary extends Record<CertaintyKey, number> {
  category: string | null;
  total_chf: string;
  row_count: number;
}

interface TaggedRow {
  row_source: string;
  row_id: string;
  category: string;
  category_model: string | null;
  category_confirmed: boolean;
  category_certainty: "low" | "medium" | "high" | null;
  date: string;
  text: string;
  payee: string;
  amount_chf: string;
  payee_usual_category: string;
}

interface PersonalTag {
  id: string;
  name: string;
}

interface Assignment {
  row_source: string;
  row_id: string;
}

interface PayeeGroup {
  payee: string;
  usual: string;
  rowCount: number;
  rows: TaggedRow[];
}

interface Loaded {
  summaries: CategorySummary[];
  rows: TaggedRow[];
  tagsByRow: Map<string, string[]>;
}

const chf = new Intl.NumberFormat("de-CH", {
  style: "currency",
  currency: "CHF",
  minimumFractionDigits: 2,
});

export function CategoryCenter({
  token,
  today,
  onBack,
}: {
  token: string;
  today: string;
  onBack: () => void;
}) {
  const thisYear = Number(today.slice(0, 4));
  const [year, setYear] = useState(thisYear);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [isCategorising, setIsCategorising] = useState(false);
  const [reloads, setReloads] = useState(0);
  const reviewRef = useRef<HTMLElement>(null);

  useEffect(() => {
    let isCurrent = true;
    async function load() {
      setError(null);
      try {
        const next = await loadCenter({ token, year });
        if (isCurrent) setLoaded(next);
      } catch (loadError) {
        if (isCurrent) setError(messageOf(loadError));
      }
    }
    void load();
    return () => {
      isCurrent = false;
    };
  }, [token, year, reloads]);

  async function correct(
    key: string,
    body: { scope: "payee" | "booking"; key: string; category: string },
  ) {
    setBusyKey(key);
    setError(null);
    try {
      await api("/api/category-corrections", token, json(body));
      setReloads((count) => count + 1);
    } catch (correctError) {
      setError(messageOf(correctError));
    } finally {
      setBusyKey(null);
    }
  }

  async function categorise() {
    setIsCategorising(true);
    setError(null);
    try {
      await api("/api/categorisations", token, json({}));
      setReloads((count) => count + 1);
    } catch (categoriseError) {
      setError(messageOf(categoriseError));
    } finally {
      setIsCategorising(false);
    }
  }

  const categorised =
    loaded?.summaries.filter((summary) => summary.category !== null) ?? [];
  const uncategorised = loaded?.summaries.find(
    (summary) => summary.category === null,
  );
  const groups = loaded === null ? [] : reviewGroups(loaded.rows, filter);
  const reviewCount = groups.reduce((sum, group) => sum + group.rows.length, 0);
  const model = loaded?.rows.find(
    (row) => row.category_model !== null,
  )?.category_model;

  return (
    <div className="center">
      <header className="center-bar">
        <button type="button" className="link" onClick={onBack}>
          <Icon name="chevronLeft" size={16} /> Chat
        </button>
        <h1>Categories</h1>
        <div className="seg" role="group" aria-label="Year">
          {[thisYear - 1, thisYear].map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={option === year}
              onClick={() => setYear(option)}
            >
              {option}
            </button>
          ))}
        </div>
      </header>

      {error !== null && (
        <p className="error-note" role="alert">
          {error}
        </p>
      )}

      {loaded === null && error === null && (
        <p className="hint">Loading your categories…</p>
      )}

      {loaded !== null && categorised.length === 0 && (
        <section className="card">
          <h2>No categories yet</h2>
          <p className="hint">
            {uncategorised === undefined
              ? `No spending in ${year}.`
              : `Apertus has not sorted your ${bookings(uncategorised.row_count)} of ${year} yet. That takes a few minutes.`}
          </p>
          {uncategorised !== undefined && (
            <div className="sheet-actions">
              <button
                type="button"
                className="primary"
                onClick={() => void categorise()}
                disabled={isCategorising}
              >
                {isCategorising ? "Sorting your bookings…" : "Sort my bookings"}
              </button>
            </div>
          )}
        </section>
      )}

      {categorised.length > 0 && (
        <section className="card">
          <h2>Spending {year} by category</h2>
          <p className="hint">
            How sure Apertus was about each booking. Pick a category to review
            only its bookings.
          </p>
          <ul className="bars">
            {categorised.map((summary) => (
              <CategoryBar
                key={summary.category}
                summary={summary}
                largest={Number(categorised[0].total_chf)}
                isSelected={filter === summary.category}
                toReview={
                  loaded === null
                    ? 0
                    : reviewGroups(loaded.rows, summary.category).reduce(
                        (sum, group) => sum + group.rows.length,
                        0,
                      )
                }
                onSelect={() => {
                  setFilter(
                    filter === summary.category ? null : summary.category,
                  );
                  reviewRef.current?.scrollIntoView({ behavior: "smooth" });
                }}
              />
            ))}
          </ul>
          {uncategorised !== undefined && (
            <p className="hint">
              {bookings(uncategorised.row_count)} (
              {chf.format(Number(uncategorised.total_chf))}) without a category
              yet.
            </p>
          )}
          <Legend />
        </section>
      )}

      {categorised.length > 0 && loaded !== null && (
        <section className="card" ref={reviewRef}>
          <div className="card-head">
            <h2>
              {reviewCount === 0
                ? "Nothing to review"
                : `Review ${bookings(reviewCount)} at ${groups.length} ${groups.length === 1 ? "payee" : "payees"}`}
            </h2>
            {filter !== null && (
              <button
                type="button"
                className="link"
                onClick={() => setFilter(null)}
              >
                {CATEGORY_NAMES[filter]} only · show all
              </button>
            )}
          </div>
          <p className="hint">
            {reviewCount === 0
              ? "Apertus was sure about every booking here, and each payee's bookings agree."
              : "Unsure, unrated, or not like the payee's other bookings. A payee correction applies to all its bookings, also future ones."}
          </p>
          <ul className="payees">
            {groups.map((group, index) => (
              <PayeeReview
                key={group.payee}
                group={group}
                tagsByRow={loaded.tagsByRow}
                isOpen={index === 0}
                busyKey={busyKey}
                onCorrect={(key, body) => void correct(key, body)}
              />
            ))}
          </ul>
          <p className="hint">
            Suggestions by {model ?? "Apertus"}. Apertus uses your corrections
            as examples the next time it sorts bookings.
          </p>
        </section>
      )}
    </div>
  );
}

function CategoryBar({
  summary,
  largest,
  isSelected,
  toReview,
  onSelect,
}: {
  summary: CategorySummary;
  largest: number;
  isSelected: boolean;
  toReview: number;
  onSelect: () => void;
}) {
  const total = Number(summary.total_chf);
  const width = largest <= 0 ? 0 : Math.max(4, (100 * total) / largest);
  const name = CATEGORY_NAMES[summary.category ?? "other"];
  return (
    <li>
      <button
        type="button"
        className="bar"
        aria-pressed={isSelected}
        onClick={onSelect}
        aria-label={`${name}: ${chf.format(total)}, ${summary.row_count} bookings, ${toReview} to review`}
      >
        <span className="bar-name">{name}</span>
        <span className="stack" style={{ width: `${width}%` }}>
          {CERTAINTIES.map(
            ({ key }) =>
              summary[key] > 0 && (
                <span
                  key={key}
                  className={`certainty-${key}`}
                  style={{ flexGrow: summary[key] }}
                />
              ),
          )}
        </span>
        <span className="bar-total">
          {chf.format(total)}
          {toReview > 0 && <span className="count">{toReview}</span>}
        </span>
      </button>
    </li>
  );
}

function Legend() {
  return (
    <ul className="legend">
      {CERTAINTIES.map(({ key, label }) => (
        <li key={key}>
          <span className={`swatch certainty-${key}`} />
          {label}
        </li>
      ))}
    </ul>
  );
}

function PayeeReview({
  group,
  tagsByRow,
  isOpen,
  busyKey,
  onCorrect,
}: {
  group: PayeeGroup;
  tagsByRow: Map<string, string[]>;
  isOpen: boolean;
  busyKey: string | null;
  onCorrect: (
    key: string,
    body: { scope: "payee" | "booking"; key: string; category: string },
  ) => void;
}) {
  const [choice, setChoice] = useState(group.usual);
  const isBusy = busyKey !== null;
  const payeeKey = `payee:${group.payee}`;
  return (
    <li>
      <details open={isOpen}>
        <summary>
          <strong>{group.payee}</strong>
          <span className="hint">
            usually {CATEGORY_NAMES[group.usual]} · {group.rows.length} of{" "}
            {group.rowCount} to review
          </span>
        </summary>
        <div className="payee-actions">
          <button
            type="button"
            className="primary"
            disabled={isBusy}
            onClick={() =>
              onCorrect(payeeKey, {
                scope: "payee",
                key: group.payee,
                category: group.usual,
              })
            }
          >
            {busyKey === payeeKey
              ? "Saving…"
              : `All are ${CATEGORY_NAMES[group.usual]}`}
          </button>
          <span className="hint">or</span>
          <CategorySelect
            value={choice}
            label={`Category for every booking at ${group.payee}`}
            disabled={isBusy}
            onChange={setChoice}
          />
          <button
            type="button"
            disabled={isBusy || choice === group.usual}
            onClick={() =>
              onCorrect(payeeKey, {
                scope: "payee",
                key: group.payee,
                category: choice,
              })
            }
          >
            Apply to all
          </button>
        </div>
        <ul className="review-rows">
          {group.rows.map((row) => {
            const bookingKey = `${row.row_source}:${row.row_id}`;
            const tags = tagsByRow.get(bookingKey) ?? [];
            return (
              <li key={bookingKey}>
                <span className="hint">{formatDate(row.date)}</span>
                <span className="review-text">
                  {row.text}
                  {tags.map((tag) => (
                    <span key={tag} className="tag">
                      {tag}
                    </span>
                  ))}
                </span>
                <span
                  className={`chip certainty-chip-${row.category_certainty ?? "unknown"}`}
                >
                  {certaintyLabel(row)}
                </span>
                <CategorySelect
                  value={row.category}
                  label={`Category for ${row.text} on ${formatDate(row.date)} only`}
                  disabled={isBusy}
                  onChange={(category) =>
                    onCorrect(bookingKey, {
                      scope: "booking",
                      key: bookingKey,
                      category,
                    })
                  }
                />
                <span className="amount">
                  {chf.format(Number(row.amount_chf))}
                </span>
              </li>
            );
          })}
        </ul>
      </details>
    </li>
  );
}

function CategorySelect({
  value,
  label,
  disabled,
  onChange,
}: {
  value: string;
  label: string;
  disabled: boolean;
  onChange: (category: string) => void;
}) {
  return (
    <select
      value={value}
      aria-label={label}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
    >
      {Object.entries(CATEGORY_NAMES).map(([key, name]) => (
        <option key={key} value={key}>
          {name}
        </option>
      ))}
    </select>
  );
}

async function loadCenter({
  token,
  year,
}: {
  token: string;
  year: number;
}): Promise<Loaded> {
  const period = `from=${year}-01-01&to=${year}-12-31`;
  const [summaries, rows, tags] = await Promise.all([
    api<CategorySummary[]>(`/api/category-summaries?${period}`, token),
    api<TaggedRow[]>("/api/transaction-tags", token),
    api<PersonalTag[]>("/api/personal-tags", token),
  ]);
  const assignments = await Promise.all(
    tags.map((tag) =>
      api<Assignment[]>(`/api/personal-tags/${tag.id}/assignments`, token),
    ),
  );
  const tagsByRow = new Map<string, string[]>();
  tags.forEach((tag, index) => {
    for (const assignment of assignments[index]) {
      const key = `${assignment.row_source}:${assignment.row_id}`;
      tagsByRow.set(key, [...(tagsByRow.get(key) ?? []), tag.name]);
    }
  });
  return {
    summaries,
    rows: rows.filter((row) => row.date.startsWith(String(year))),
    tagsByRow,
  };
}

/** Rows worth a look, by payee, the payees with the most of them first. */
export function reviewGroups(
  rows: TaggedRow[],
  category: string | null,
): PayeeGroup[] {
  const counts = new Map<string, number>();
  for (const row of rows)
    counts.set(row.payee, (counts.get(row.payee) ?? 0) + 1);
  const byPayee = new Map<string, TaggedRow[]>();
  for (const row of rows) {
    if (!needsReview(row)) continue;
    if (category !== null && row.category !== category) continue;
    byPayee.set(row.payee, [...(byPayee.get(row.payee) ?? []), row]);
  }
  return [...byPayee.entries()]
    .map(([payee, payeeRows]) => ({
      payee,
      usual: payeeRows[0].payee_usual_category,
      rowCount: counts.get(payee) ?? payeeRows.length,
      rows: payeeRows,
    }))
    .sort((a, b) => b.rows.length - a.rows.length);
}

function needsReview(row: TaggedRow): boolean {
  if (row.category_confirmed) return false;
  if (row.category !== row.payee_usual_category) return true;
  return row.category_certainty !== "high";
}

function certaintyLabel(row: TaggedRow): string {
  if (row.category_certainty === "low") return "Unsure";
  if (row.category_certainty === "medium") return "Fairly sure";
  if (row.category_certainty === null) return "No rating";
  return "Sure";
}

function bookings(count: number): string {
  return count === 1 ? "1 booking" : `${count} bookings`;
}

function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-");
  return `${day}.${month}.${year}`;
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
