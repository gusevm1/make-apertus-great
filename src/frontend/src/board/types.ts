// Mirrors src/backend/app/features/boards/schemas.py and tiles/schemas.py.
// Amounts are JSON numbers, dates "YYYY-MM-DD", months "YYYY-MM".

import type { TraceStep } from "../lib/useStream";

/** How the model and the server built a board; `model` is "server" when the model did not answer. */
export interface BoardPlan {
  id: string;
  model: string | null;
  trace: TraceStep[];
}

export interface BoardSummary {
  id: string;
  name: string;
  position: number;
  plan_id: string | null;
  tile_count: number;
}

export interface Board {
  id: string;
  name: string;
  position: number;
  plan_id: string | null;
  tiles: Tile[];
  dropped: DroppedTile[];
}

export interface TilePublication {
  tile_id: string;
  dashboard_id: string;
  dashboard_widget_id: string;
}

export interface DroppedTile {
  tile_id: string;
  title: string;
  reason: string;
}

export interface Tile {
  id: string;
  template: Template;
  title: string;
  args: Record<string, unknown>;
  position: number;
  payload: AnyPayload;
}

export interface Idea {
  title: string;
  text: string;
}

export interface BoardPlan {
  id: string;
  kind: string;
  question: string;
  evidence: string[];
  ideas: Idea[];
  model: string | null;
  latency_ms: number;
}

export type Template = AnyPayload["template"];

export type Flag = "reminder" | "provisional";

export interface SourceRow {
  id: string;
  date?: string | null;
  text: string;
  amount_chf?: number | null;
}

export interface Source {
  label: string;
  kind:
    "bookings" | "payments" | "accounts" | "positions" | "loans" | "documents";
  rows: SourceRow[];
  count: number;
}

interface PayloadBase {
  figure_chf: number;
  source: Source;
}

export interface BalancePoint {
  date: string;
  balance_chf: number;
}

export interface PaydayAlternative {
  counterparty: string;
  amount_chf: number;
  left_chf: number;
  per_day_chf: number;
}

export interface PaydayBalancePayload extends PayloadBase {
  template: "payday_balance";
  account_name: string;
  payday: string;
  day_before: string;
  days: number;
  per_day_chf: number;
  today: string;
  today_balance_chf: number;
  points: BalancePoint[];
  upcoming_count: number;
  alternative: PaydayAlternative | null;
}

export interface BillRow {
  id: string;
  due: string;
  payee: string;
  detail: string | null;
  amount_chf: number;
  balance_after_chf: number | null;
  flag: Flag | null;
}

export interface BillsUntilPaydayPayload extends PayloadBase {
  template: "bills_until_payday";
  payday: string;
  rows: BillRow[];
}

export interface DueSoonPayload extends PayloadBase {
  template: "due_soon";
  days: number;
  rows: BillRow[];
  count: number;
}

export interface IncomeMonth {
  month: string;
  arrived_on: string | null;
  amount_chf: number | null;
  state: "on_time" | "late" | "open";
}

export interface ExpectedIncomePayload extends PayloadBase {
  template: "expected_income";
  counterparty: string;
  usual_day: number;
  status: "arrived" | "not_arrived";
  months: IncomeMonth[];
}

export interface MerchantRow {
  merchant: string;
  amount_chf: number;
  share: number;
  count: number;
}

export interface MerchantSpendingPayload extends PayloadBase {
  template: "merchant_spending";
  date_from: string;
  date_to: string;
  rows: MerchantRow[];
}

export interface SavingsGoalPayload extends PayloadBase {
  template: "savings_goal";
  account_name: string;
  goal_text: string;
  goal_chf: number;
  percent: number;
  month_change_chf: number;
  month: string;
}

export interface BillPayload extends PayloadBase {
  template: "bill";
  payee: string;
  due: string;
  description: string;
  flag: Flag | null;
}

export interface WorthPart {
  group: "accounts" | "securities" | "pension";
  value_chf: number;
  count: number;
}

export interface NetWorthPayload extends PayloadBase {
  template: "net_worth";
  parts: WorthPart[];
  includes_pension: boolean;
}

export interface SpendingMonth {
  month: string;
  total_chf: number;
  count: number;
}

export interface MonthlySpendingPayload extends PayloadBase {
  template: "monthly_spending";
  months: SpendingMonth[];
  highest: string;
}

export interface CashflowMonth {
  month: string;
  income_chf: number;
  spending_chf: number;
  left_chf: number;
}

export interface IncomeAndSpendingPayload extends PayloadBase {
  template: "income_and_spending";
  months: CashflowMonth[];
}

export interface AllocationPart {
  label: string;
  value_chf: number;
  weight_pct: number;
}

export interface SecuritiesPayload extends PayloadBase {
  template: "securities";
  invested_chf: number;
  allocation: AllocationPart[];
  positions: number;
}

export interface RegularPaymentRow {
  payee: string;
  amount_chf: number;
  next_due: string;
}

export interface RegularPaymentsPayload extends PayloadBase {
  template: "regular_payments";
  rows: RegularPaymentRow[];
}

export interface PlannedTransfer {
  id: string;
  date: string;
  amount_chf: number;
}

export interface Pillar3aPayload extends PayloadBase {
  template: "pillar_3a";
  year: number;
  maximum_chf: number;
  paid_chf: number;
  balance_chf: number;
  planned: PlannedTransfer[];
  missing_today_chf: number;
}

export interface AccountRow {
  account_id: string;
  name: string;
  balance_chf: number;
  purpose: string | null;
}

export interface AccountBalancesPayload extends PayloadBase {
  template: "account_balances";
  rows: AccountRow[];
}

export interface Tranche {
  loan_id: string;
  product: string;
  balance_chf: number;
  interest_rate: number;
  maturity_date: string | null;
  next_interest_date: string | null;
}

export interface MortgagePayload extends PayloadBase {
  template: "mortgage";
  annual_interest_chf: number;
  tranches: Tranche[];
  next_maturity: Tranche | null;
}

export interface CardBillPayload extends PayloadBase {
  template: "card_bill";
  card_name: string;
  period: string;
  due: string | null;
  flag: Flag | null;
  purchases: number;
}

export type AnyPayload =
  | PaydayBalancePayload
  | BillsUntilPaydayPayload
  | DueSoonPayload
  | ExpectedIncomePayload
  | MerchantSpendingPayload
  | SavingsGoalPayload
  | BillPayload
  | NetWorthPayload
  | MonthlySpendingPayload
  | IncomeAndSpendingPayload
  | SecuritiesPayload
  | RegularPaymentsPayload
  | Pillar3aPayload
  | AccountBalancesPayload
  | MortgagePayload
  | CardBillPayload;

/** What the source drawer lists: a tile's source, or the part of it behind one bar. */
export interface SourceView {
  title: string;
  kind: Source["kind"];
  rows: SourceRow[];
  count: number;
}
