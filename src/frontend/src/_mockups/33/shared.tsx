import { useState, type ReactNode } from "react";
import { Mark, SmallIcon } from "../../board/icons";

export type Flag = {
  id: string;
  kind: "invoice" | "balance" | "price";
  title: string;
  detail: string;
  figure: string;
  source: string;
};

export const FLAGS: Flag[] = [
  {
    id: "f1",
    kind: "invoice",
    title: "Reminder not paid",
    detail: "Zahnarztpraxis Dr. Keller, due 30.11.2026",
    figure: "385.00",
    source: "From Mahnung_Keller.pdf · no matching booking or payment",
  },
  {
    id: "f2",
    kind: "balance",
    title: "Privatkonto low before Christmas",
    detail: "Expected 412.35 on 24.12.2026, below your 1'000.00",
    figure: "412.35",
    source: "Forecast from 14 bookings · usual salary on 25.12.",
  },
  {
    id: "f3",
    kind: "price",
    title: "Swisscom costs more",
    detail: "Monthly 65.00 → 79.90 since October",
    figure: "+14.90",
    source: "3 bookings: 25.09., 25.10., 25.11.2026",
  },
  {
    id: "f4",
    kind: "invoice",
    title: "Invoice not paid",
    detail:
      "AXA Versicherungen AG, Motorfahrzeugversicherung Prämienrechnung 2027, due 15.01.2027",
    figure: "1'184.00",
    source: "From AXA_Praemie_2027.pdf · no matching booking or payment",
  },
];

const KIND_LABEL = {
  invoice: "Invoice",
  balance: "Balance",
  price: "Price",
};

export function useFlags() {
  const [flags, setFlags] = useState(FLAGS);
  return {
    flags,
    remove: (id: string) => setFlags((all) => all.filter((f) => f.id !== id)),
  };
}

/** One flag as an e-banking row: what, figure, and the actions in the row. */
export function FlagRow({ flag, onDone }: { flag: Flag; onDone: () => void }) {
  const [menu, setMenu] = useState(false);
  const [open, setOpen] = useState(false);
  return (
    <li className="f-row">
      <button className="f-main" onClick={() => setOpen(!open)}>
        <span className="f-kind">{KIND_LABEL[flag.kind]}</span>
        <span className="f-text">
          <b>{flag.title}</b>
          <span>{flag.detail}</span>
          {open && <span className="f-source">{flag.source}</span>}
        </span>
        <span className="f-figure">CHF {flag.figure}</span>
      </button>
      <span className="f-actions">
        <button className="f-link">
          <SmallIcon name="ask" size={12} /> Ask
        </button>
        <button className="f-link" onClick={onDone}>
          Done
        </button>
        <span className="f-more">
          <button
            className="f-icon"
            aria-label="More"
            onClick={() => setMenu(!menu)}
          >
            <SmallIcon name="more" size={14} />
          </button>
          {menu && (
            <span className="f-menu">
              <button onClick={onDone}>
                Don't show {KIND_LABEL[flag.kind].toLowerCase()} alerts again
              </button>
              <button>Alert settings</button>
            </span>
          )}
        </span>
      </span>
    </li>
  );
}

/** Up to three rows, the rest behind "Show all". */
export function FlagList({ limit = 3 }: { limit?: number }) {
  const { flags, remove } = useFlags();
  const [all, setAll] = useState(false);
  const shown = all ? flags : flags.slice(0, limit);
  if (flags.length === 0)
    return <p className="f-empty">Nothing needs your attention.</p>;
  return (
    <>
      <ul className="f-list">
        {shown.map((flag) => (
          <FlagRow key={flag.id} flag={flag} onDone={() => remove(flag.id)} />
        ))}
      </ul>
      {flags.length > limit && (
        <button className="f-all" onClick={() => setAll(!all)}>
          {all ? "Show fewer" : `Show all ${flags.length}`}
        </button>
      )}
    </>
  );
}

export function Header({ extra }: { extra?: ReactNode }) {
  return (
    <header className="m-head">
      <span className="m-brand">
        <Mark /> TrustRoom
        <span className="m-private">
          <SmallIcon name="lock" size={12} /> Stays inside the bank
        </span>
      </span>
      <span className="m-toggle">
        <button aria-pressed="true">Board and chat</button>
        <button>Chat</button>
      </span>
      <span className="m-right">
        {extra}
        <button className="m-reset">Reset</button>
        <span className="m-avatar">MB</span>
      </span>
    </header>
  );
}

export function Tiles() {
  return (
    <div className="m-tiles">
      <article className="m-tile" data-hero="">
        <b>The mortgage</b>
        <strong>CHF 862'500.00</strong>
        <span>3 tranches · CHF 8'425.00 interest a year</span>
      </article>
      <article className="m-tile">
        <b>Monthly cash shortfall</b>
        <strong>CHF -246.13</strong>
        <span>Left a month on average, May to October</span>
      </article>
      <article className="m-tile">
        <b>House reserve nearly met</b>
        <strong>CHF 19'350.30</strong>
        <span>Sparkonto Haus · goal CHF 20'000</span>
      </article>
    </div>
  );
}

export function Chat({ top }: { top?: ReactNode }) {
  return (
    <aside className="m-chat">
      <div className="m-chat-title">
        Mortgage interest for my tax return{" "}
        <SmallIcon name="chevron" size={10} />
      </div>
      <div className="m-thread">
        {top}
        <p className="m-q">How much mortgage interest did I pay this year?</p>
        <p className="m-a">
          You paid CHF 7'021.10 interest on your three tranches from January to
          November 2026.
        </p>
      </div>
      <div className="m-compose">Ask, or change the board</div>
    </aside>
  );
}
