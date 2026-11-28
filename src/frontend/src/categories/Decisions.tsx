import { type KeyboardEvent, type PointerEvent, useRef, useState } from "react";
import { CategoryPicker } from "./CategoryPicker";
import {
  CERTAINTY_LABELS,
  chf,
  type Decision,
  labelOf,
  type SpendingCategory,
} from "./data";

// How far a card is dragged before letting go chooses that side.
const SWIPE_DISTANCE = 96;
const SAMPLE_ROWS = 3;

interface DecisionProps {
  decisions: Decision[];
  categories: SpendingCategory[];
  busyId: string | null;
  onChoose: (decision: Decision, category: string) => void;
  onCreate: (decision: Decision, name: string, description: string) => void;
}

function Pen() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
      <path
        d="M8.6 2.6 11.4 5.4 5 11.8H2.2V9Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function Summary({ decision }: { decision: Decision }) {
  const certainty = decision.certainty ?? "unknown";
  const count = decision.rows.length;
  return (
    <>
      <div className="cat-card-head">
        <b className="cat-payee">{decision.rows[0].payee}</b>
        <span className="cat-certainty" data-certainty={certainty}>
          {CERTAINTY_LABELS[certainty]}
        </span>
      </div>
      <p className="hint">
        {decision.scope === "payee"
          ? `${count} ${count === 1 ? "booking" : "bookings"} · ${chf.format(decision.totalChf)} · decides future bookings of this payee too`
          : `One booking · ${chf.format(decision.totalChf)} · this payee's bookings differ, so each is decided alone`}
      </p>
      <ul className="cat-samples">
        {decision.rows.slice(0, SAMPLE_ROWS).map((row) => (
          <li key={`${row.row_source}:${row.row_id}`}>
            <span className="num">
              {new Date(row.date).toLocaleDateString("de-CH")}
            </span>
            <span className="cat-sample-text">{row.text}</span>
            <span className="num">{chf.format(Number(row.amount_chf))}</span>
          </li>
        ))}
      </ul>
    </>
  );
}

function optionLabel(decision: Decision, index: number): string {
  if (decision.options.length === 1) return labelOf(decision.options[0]);
  return index === 0
    ? `${labelOf(decision.options[0])} (Apertus)`
    : labelOf(decision.options[index]);
}

export function DecisionList({
  decisions,
  categories,
  busyId,
  onChoose,
  onCreate,
}: DecisionProps) {
  const [penId, setPenId] = useState<string | null>(null);
  return (
    <ul className="cat-list">
      {decisions.map((decision) => (
        <li key={decision.id} className="cat-card">
          <Summary decision={decision} />
          <div className="cat-options">
            {decision.options.map((option, index) => (
              <button
                key={option}
                type="button"
                className="button"
                disabled={busyId !== null}
                onClick={() => onChoose(decision, option)}
              >
                {optionLabel(decision, index)}
              </button>
            ))}
            <button
              type="button"
              className="cat-icon-button"
              aria-label={`Another category for ${decision.payee}`}
              aria-expanded={penId === decision.id}
              disabled={busyId !== null}
              onClick={() =>
                setPenId(penId === decision.id ? null : decision.id)
              }
            >
              <Pen />
            </button>
          </div>
          {penId === decision.id && (
            <CategoryPicker
              categories={categories}
              exclude={decision.options}
              isBusy={busyId !== null}
              onPick={(category) => onChoose(decision, category)}
              onCreate={(name, description) =>
                onCreate(decision, name, description)
              }
              onClose={() => setPenId(null)}
            />
          )}
        </li>
      ))}
    </ul>
  );
}

/** One card at a time: drag or press an arrow key towards a category, or open the pen. */
export function SwipeDeck({
  decisions,
  categories,
  busyId,
  onChoose,
  onCreate,
}: DecisionProps) {
  const [offset, setOffset] = useState(0);
  const [isPenOpen, setIsPenOpen] = useState(false);
  const start = useRef<number | null>(null);
  const decision = decisions[0];
  const left = decision.options[0];
  const right = decision.options[1] ?? null;
  const isBusy = busyId !== null;

  function choose(category: string | null) {
    setOffset(0);
    if (category === null || isBusy) return;
    setIsPenOpen(false);
    onChoose(decision, category);
  }

  function handlePointerDown(event: PointerEvent<HTMLDivElement>) {
    if (isBusy || (event.target as HTMLElement).closest("button") !== null)
      return;
    start.current = event.clientX;
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handlePointerMove(event: PointerEvent<HTMLDivElement>) {
    if (start.current === null) return;
    setOffset(event.clientX - start.current);
  }

  function handlePointerUp() {
    if (start.current === null) return;
    start.current = null;
    if (offset <= -SWIPE_DISTANCE) choose(left);
    else if (offset >= SWIPE_DISTANCE) choose(right);
    else setOffset(0);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      choose(left);
    }
    if (event.key === "ArrowRight" && right !== null) {
      event.preventDefault();
      choose(right);
    }
  }

  const leaning =
    offset <= -SWIPE_DISTANCE / 2
      ? "left"
      : offset >= SWIPE_DISTANCE / 2 && right !== null
        ? "right"
        : undefined;

  return (
    <div className="cat-deck">
      <p className="hint cat-deck-count" aria-live="polite">
        {decisions.length} left · drag the card or press ← / →
      </p>
      <div
        key={decision.id}
        className="cat-card cat-swipe"
        data-leaning={leaning}
        tabIndex={0}
        aria-label={`${decision.payee}: ← ${labelOf(left)}${right === null ? "" : `, → ${labelOf(right)}`}`}
        style={{
          transform: `translateX(${offset}px) rotate(${offset / 30}deg)`,
        }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={() => {
          start.current = null;
          setOffset(0);
        }}
        onKeyDown={handleKeyDown}
      >
        <Summary decision={decision} />
      </div>
      <div className="cat-swipe-actions">
        <button
          type="button"
          className="button cat-side"
          data-side="left"
          disabled={isBusy}
          onClick={() => choose(left)}
        >
          ← {optionLabel(decision, 0)}
        </button>
        <button
          type="button"
          className="cat-icon-button"
          aria-label={`Another category for ${decision.payee}`}
          aria-expanded={isPenOpen}
          disabled={isBusy}
          onClick={() => setIsPenOpen(!isPenOpen)}
        >
          <Pen />
        </button>
        {right !== null && (
          <button
            type="button"
            className="button cat-side"
            data-side="right"
            disabled={isBusy}
            onClick={() => choose(right)}
          >
            {optionLabel(decision, 1)} →
          </button>
        )}
      </div>
      {isPenOpen && (
        <CategoryPicker
          categories={categories}
          exclude={decision.options}
          isBusy={isBusy}
          onPick={(category) => choose(category)}
          onCreate={(name, description) => {
            setIsPenOpen(false);
            onCreate(decision, name, description);
          }}
          onClose={() => setIsPenOpen(false)}
        />
      )}
    </div>
  );
}
