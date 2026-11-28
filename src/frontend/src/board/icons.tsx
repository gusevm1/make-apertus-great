import type { ReactNode } from "react";
import type { Template } from "./types";

// Drawn as in docs/reference/boards, on a 16 px grid with a 1.5 px stroke.
const CALENDAR = (
  <>
    <rect x="2" y="3" width="12" height="11" rx="2.5" />
    <path d="M2 6.8h12M5.5 1.6v2.6M10.5 1.6v2.6" />
  </>
);
const SHIELD = (
  <path d="M8 1.8 13 3.6v4.1c0 3-2 5.3-5 6.5-3-1.2-5-3.5-5-6.5V3.6Z" />
);
const COLUMNS = <path d="M3 13V8.5M6.4 13V4.5M9.8 13V6.5M13.2 13V3" />;

const TILE_ICONS: Record<Template, ReactNode> = {
  payday_balance: CALENDAR,
  bills_until_payday: (
    <>
      <path d="M5.5 4.5h8M5.5 8h8M5.5 11.5h8" />
      <circle cx="2.6" cy="4.5" r="0.6" fill="currentColor" />
      <circle cx="2.6" cy="8" r="0.6" fill="currentColor" />
      <circle cx="2.6" cy="11.5" r="0.6" fill="currentColor" />
    </>
  ),
  due_soon: CALENDAR,
  expected_income: <path d="M8 2.2v8M4.8 7.2 8 10.4l3.2-3.2M3 13.6h10" />,
  merchant_spending: (
    <>
      <path d="M1.8 2.5h2l1.5 7.6h6.6l1.3-5.3H4.6" />
      <circle cx="6" cy="12.8" r="0.9" />
      <circle cx="11.2" cy="12.8" r="0.9" />
    </>
  ),
  savings_goal: SHIELD,
  bill: <path d="M4 1.8h5.2L12.4 5v9.2H4ZM9 1.8V5h3.4M6.2 8.2h4M6.2 10.8h4" />,
  net_worth: <path d="M2.2 13.2h11.6M3.6 13.2V7.2M8 13.2V2.8M12.4 13.2V9.6" />,
  monthly_spending: COLUMNS,
  income_and_spending: COLUMNS,
  securities: <path d="M2 11.5 6 7.5l2.6 2.6L14 4.7M10.4 4.7H14v3.6" />,
  regular_payments: <path d="M12.8 6.2A5 5 0 1 0 13 9M12.8 2.8v3.4H9.4" />,
  pillar_3a: SHIELD,
  account_balances: (
    <>
      <ellipse cx="8" cy="4.2" rx="5" ry="2.2" />
      <path d="M3 4.2V8c0 1.2 2.2 2.2 5 2.2s5-1 5-2.2V4.2M3 8v3.8c0 1.2 2.2 2.2 5 2.2s5-1 5-2.2V8" />
    </>
  ),
  mortgage: <path d="M2.4 7.4 8 2.6l5.6 4.8v6.2H2.4ZM6.4 13.6V9.8h3.2v3.8" />,
  card_bill: (
    <>
      <rect x="1.8" y="3.4" width="12.4" height="9.2" rx="2" />
      <path d="M1.8 6.6h12.4M4.4 10h2.6" />
    </>
  ),
};

export function TileIcon({ template }: { template: Template }) {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {TILE_ICONS[template] ?? CALENDAR}
    </svg>
  );
}

const SMALL_PATHS = {
  chevron: "M4.5 2.5 8 6l-3.5 3.5",
  plus: "M7 2.5v9M2.5 7h9",
  rename: "M8.6 2.6 11.4 5.4 5 11.8H2.2V9Z",
  ask: "M2 3.8A1.8 1.8 0 0 1 3.8 2h6.4A1.8 1.8 0 0 1 12 3.8v4.4a1.8 1.8 0 0 1-1.8 1.8H6.5L4 12.2V10h-.2A1.8 1.8 0 0 1 2 8.2Z",
  remove: "M2.5 4h9M5.5 4V2.6h3V4M3.6 4l.6 7.4h5.6L10.4 4",
  dashboard:
    "M2 2.5h4.2v4.2H2ZM7.8 2.5H12v4.2H7.8ZM2 7.8h4.2V12H2ZM9.9 7.8V12M7.8 9.9H12",
  earlier: "M7 11.5v-9M3 6.5l4-4 4 4",
  later: "M7 2.5v9M3 7.5l4 4 4-4",
  close: "M3 3l8 8M11 3l-8 8",
  board:
    "M1.5 4.2A2.2 2.2 0 0 1 3.7 2h6.6a2.2 2.2 0 0 1 2.2 2.2v5.6a2.2 2.2 0 0 1-2.2 2.2H3.7a2.2 2.2 0 0 1-2.2-2.2ZM8.8 2v10",
  more: "M3 7h.01M7 7h.01M11 7h.01",
  arrow: "M3 7h8M7.5 3.5 11 7l-3.5 3.5",
  lock: "M2.6 6.2h8.8v6H2.6ZM4.7 6.2V4.4a2.3 2.3 0 0 1 4.6 0v1.8",
  history: "M7 1.8a5.2 5.2 0 1 1 0 10.4A5.2 5.2 0 0 1 7 1.8ZM7 4.3V7l1.9 1.2",
};

export type SmallIconName = keyof typeof SMALL_PATHS;

/** A 14 px outline icon of the toolbar, the dock and the links. */
export function SmallIcon({
  name,
  size = 14,
}: {
  name: SmallIconName;
  size?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox={name === "chevron" ? "0 0 12 12" : "0 0 14 14"}
      fill="none"
      stroke="currentColor"
      strokeWidth={name === "more" ? 2.4 : 1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={SMALL_PATHS[name]} />
    </svg>
  );
}

/** The TrustRoom mark: four tiles, one of them mint. */
export function Mark() {
  return (
    <span className="mark">
      <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
        <rect
          x="1"
          y="1"
          width="5.2"
          height="7.5"
          rx="1.4"
          fill="var(--mint)"
        />
        <rect
          x="7.8"
          y="1"
          width="5.2"
          height="4.2"
          rx="1.4"
          fill="var(--surface)"
        />
        <rect
          x="7.8"
          y="6.8"
          width="5.2"
          height="6.2"
          rx="1.4"
          fill="var(--surface)"
          opacity="0.55"
        />
        <rect
          x="1"
          y="10.1"
          width="5.2"
          height="2.9"
          rx="1.4"
          fill="var(--surface)"
          opacity="0.55"
        />
      </svg>
    </span>
  );
}

export function MicIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="6.5" y="2" width="5" height="9" rx="2.5" />
      <path d="M3.5 9a5.5 5.5 0 0 0 11 0M9 14.5V16" />
    </svg>
  );
}

export function SendIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M8 13V3M3.5 7.5 8 3l4.5 4.5" />
    </svg>
  );
}
