import { useEffect, useState } from "react";
import { api, json, type RequestError, requestErrorOf } from "../api";
import { fullDate, money } from "../board/format";
import { SmallIcon } from "../board/icons";
import { sendToHost } from "../host";
import "./alerts.css";

export interface Alert {
  key: string;
  kind: "invoice";
  document_id: string;
  document_name: string;
  document_kind: "invoice" | "reminder";
  payee: string | null;
  amount_chf: string;
  due_date: string | null;
  document_date: string | null;
}

/** Fired when a check is turned on or off, so every list of alerts loads again. */
export const ALERTS_CHANGED = "trustroom:alerts-changed";
const ROWS_SHOWN = 3;

/** The open alerts, loaded again whenever `reloadKey` or a setting changes. */
function useAlerts(token: string, reloadKey: string) {
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [error, setError] = useState<RequestError | null>(null);

  async function load() {
    setError(null);
    try {
      setAlerts(await api<Alert[]>("/api/alerts", token));
    } catch (failure) {
      setError(requestErrorOf(failure));
    }
  }

  useEffect(() => {
    void load();
    const reload = () => void load();
    window.addEventListener(ALERTS_CHANGED, reload);
    return () => window.removeEventListener(ALERTS_CHANGED, reload);
  }, [token, reloadKey]);

  return { alerts, setAlerts, error, load };
}

// The keys shown when the customer hid the box; a key not among them unfolds it again.
function foldedKeys(storageKey: string): string[] | null {
  try {
    const stored = localStorage.getItem(storageKey);
    return stored === null ? null : (JSON.parse(stored) as string[]);
  } catch {
    return null;
  }
}

function storeFolded(storageKey: string, keys: string[] | null) {
  try {
    if (keys === null) localStorage.removeItem(storageKey);
    else localStorage.setItem(storageKey, JSON.stringify(keys));
  } catch {
    // Without storage the box simply opens unfolded next time.
  }
}

/** The box above the board: bills nobody paid yet, with Done and a menu in each row. */
export function NeedsAttention({
  token,
  customerId,
  onOpenSettings,
}: {
  token: string;
  customerId: string;
  onOpenSettings: () => void;
}) {
  const { alerts, setAlerts, error, load } = useAlerts(token, customerId);
  const storageKey = `trustroom:alerts-folded:${customerId}`;
  const [folded, setFolded] = useState(() => foldedKeys(storageKey));
  const [isAllShown, setIsAllShown] = useState(false);

  if (error !== null) {
    return (
      <section className="na-box" aria-label="Needs attention">
        <p className="na-note" role="alert">
          What needs your attention did not load. {error.message}{" "}
          <button type="button" className="na-link" onClick={() => void load()}>
            Try again
          </button>
        </p>
      </section>
    );
  }
  if (alerts === null) {
    return (
      <p className="na-note na-loading" aria-live="polite">
        Checking for unpaid bills…
      </p>
    );
  }
  if (alerts.length === 0) return null;

  const isFolded =
    folded !== null && alerts.every((alert) => folded.includes(alert.key));
  if (isFolded) {
    return (
      <button
        type="button"
        className="na-line"
        onClick={() => {
          storeFolded(storageKey, null);
          setFolded(null);
        }}
      >
        <span className="na-count">{alerts.length}</span>
        {alerts.length === 1 ? "needs attention" : "need attention"}
        <SmallIcon name="chevron" size={10} />
      </button>
    );
  }

  const shown = isAllShown ? alerts : alerts.slice(0, ROWS_SHOWN);
  return (
    <section className="na-box" aria-label="Needs attention">
      <header className="na-head">
        <h2>Needs attention</h2>
        <button
          type="button"
          className="na-link"
          onClick={() => {
            const keys = alerts.map((alert) => alert.key);
            storeFolded(storageKey, keys);
            setFolded(keys);
          }}
        >
          Hide
        </button>
      </header>
      <ul className="na-list">
        {shown.map((alert) => (
          <AlertRow
            key={alert.key}
            token={token}
            alert={alert}
            onGone={() =>
              setAlerts((current) =>
                (current ?? []).filter((other) => other.key !== alert.key),
              )
            }
            onOpenSettings={onOpenSettings}
          />
        ))}
      </ul>
      {alerts.length > ROWS_SHOWN && (
        <button
          type="button"
          className="na-link na-all"
          onClick={() => setIsAllShown(!isAllShown)}
        >
          {isAllShown ? "Show fewer" : `Show all ${alerts.length}`}
        </button>
      )}
    </section>
  );
}

function AlertRow({
  token,
  alert,
  onGone,
  onOpenSettings,
}: {
  token: string;
  alert: Alert;
  onGone: () => void;
  onOpenSettings: () => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  async function send(path: string, init: RequestInit) {
    setIsSending(true);
    setFailure(null);
    try {
      await api(path, token, init);
      return true;
    } catch (error) {
      setFailure(requestErrorOf(error).message);
      return false;
    } finally {
      setIsSending(false);
    }
  }

  async function markDone() {
    const isDone = await send("/api/alert-dismissals", {
      ...json({ key: alert.key }),
      method: "POST",
    });
    if (isDone) onGone();
  }

  async function turnOff() {
    setIsMenuOpen(false);
    const isOff = await send(`/api/alert-settings/${alert.kind}`, {
      ...json({ enabled: false }),
      method: "PATCH",
    });
    if (isOff) window.dispatchEvent(new Event(ALERTS_CHANGED));
  }

  const title =
    alert.document_kind === "reminder"
      ? "Reminder not paid"
      : "Invoice not paid";
  const detail = [
    alert.payee,
    alert.due_date === null ? null : `due ${fullDate(alert.due_date)}`,
  ]
    .filter((part) => part !== null)
    .join(", ");
  return (
    <li className="na-row">
      <button
        type="button"
        className="na-main"
        aria-expanded={isOpen}
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="na-kind">Invoice</span>
        <span className="na-text">
          <b>{title}</b>
          {detail !== "" && <span>{detail}</span>}
          {isOpen && (
            <span className="na-source">
              From {alert.document_name} · no matching booking or pending
              payment
            </span>
          )}
          {failure !== null && (
            <span className="na-error" role="alert">
              {failure}
            </span>
          )}
        </span>
        <span className="na-figure">CHF {money(Number(alert.amount_chf))}</span>
      </button>
      <span className="na-actions">
        <button
          type="button"
          className="na-link"
          disabled={isSending}
          onClick={() => void markDone()}
        >
          Done
        </button>
        <span
          className="na-more"
          onKeyDown={(event) => event.key === "Escape" && setIsMenuOpen(false)}
        >
          <button
            type="button"
            className="na-icon"
            aria-label={`More for ${title}`}
            aria-expanded={isMenuOpen}
            onClick={() => setIsMenuOpen(!isMenuOpen)}
          >
            <SmallIcon name="more" />
          </button>
          {isMenuOpen && (
            <span className="na-menu">
              <button type="button" onClick={() => void turnOff()}>
                Don't show unpaid invoices again
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsMenuOpen(false);
                  onOpenSettings();
                }}
              >
                Alert settings
              </button>
            </span>
          )}
        </span>
      </span>
    </li>
  );
}

/** One line above the chat in the side panel; the alerts themselves are on /trustroom. */
export function AlertLine({
  token,
  reloadKey,
}: {
  token: string;
  reloadKey: string;
}) {
  const { alerts } = useAlerts(token, reloadKey);
  // Loading, a failure and no alerts all leave the chat alone: the full list is on /trustroom.
  if (alerts === null || alerts.length === 0) return null;
  return (
    <button
      type="button"
      className="na-line na-panel"
      onClick={() => sendToHost("navigate", { path: "/trustroom" })}
    >
      <span className="na-count">{alerts.length}</span>
      {alerts.length === 1 ? "needs attention" : "need attention"}
      <SmallIcon name="chevron" size={10} />
    </button>
  );
}
