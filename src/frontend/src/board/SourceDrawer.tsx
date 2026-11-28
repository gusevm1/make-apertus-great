import { useEffect, useRef } from "react";
import { fullDate, money } from "./format";
import { SmallIcon } from "./icons";
import type { Source, SourceView } from "./types";

const KIND_WORDS: Record<Source["kind"], [string, string]> = {
  bookings: ["booking", "bookings"],
  payments: ["payment", "payments"],
  accounts: ["account", "accounts"],
  positions: ["position", "positions"],
  loans: ["loan", "loans"],
  documents: ["document", "documents"],
};

function countOf(count: number, kind: Source["kind"]): string {
  const [one, many] = KIND_WORDS[kind] ?? ["record", "records"];
  return `${count} ${count === 1 ? one : many}`;
}

/** The records behind a tile's figures, opened from the link under the tile. */
export function SourceDrawer({
  view,
  onClose,
}: {
  view: SourceView | null;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const element = dialog.current;
    if (element === null) return;
    if (view !== null && !element.open) element.showModal();
    if (view === null && element.open) element.close();
  }, [view]);

  return (
    <dialog
      ref={dialog}
      className="drawer"
      aria-labelledby="drawer-title"
      onClose={onClose}
      // A click on the backdrop lands on the dialog itself.
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      {view !== null && (
        <>
          <header>
            <div>
              <span className="kicker">Where these figures come from</span>
              <h2 id="drawer-title">{view.title}</h2>
              <p className="num">
                {view.rows.length < view.count
                  ? `The first ${view.rows.length} of ${countOf(view.count, view.kind)}`
                  : countOf(view.rows.length, view.kind)}
              </p>
            </div>
            <button
              type="button"
              className="close"
              aria-label="Close"
              onClick={onClose}
            >
              <SmallIcon name="close" />
            </button>
          </header>
          {view.rows.length === 0 ? (
            <p className="drawer-empty">
              No {KIND_WORDS[view.kind]?.[1] ?? "records"} to show for this part
              of the tile.
            </p>
          ) : (
            <ol className="num">
              {view.rows.map((row, index) => (
                <li key={`${row.id}-${index}`}>
                  <time dateTime={row.date ?? undefined}>
                    {row.date == null ? "" : fullDate(row.date)}
                  </time>
                  <span className="text">
                    {row.text}
                    <small>{row.id}</small>
                  </span>
                  <b>{row.amount_chf == null ? "" : money(row.amount_chf)}</b>
                </li>
              ))}
            </ol>
          )}
          <footer>
            Read from your bank's records when the board opened. The TrustRoom
            computes every figure on the tile from these, never the model.
          </footer>
        </>
      )}
    </dialog>
  );
}
