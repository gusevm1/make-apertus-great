import type { ReactNode } from "react";
import {
  addDays,
  day,
  daysBetween,
  fullDate,
  money,
  moneyRounded,
  monthName,
  monthShort,
  percent,
} from "./format";
import { SmallIcon } from "./icons";
import type {
  AccountBalancesPayload,
  AnyPayload,
  BillPayload,
  BillRow,
  BillsUntilPaydayPayload,
  CardBillPayload,
  DueSoonPayload,
  ExpectedIncomePayload,
  Flag,
  IncomeAndSpendingPayload,
  MerchantSpendingPayload,
  MonthlySpendingPayload,
  MortgagePayload,
  NetWorthPayload,
  PaydayBalancePayload,
  Pillar3aPayload,
  RegularPaymentsPayload,
  SavingsGoalPayload,
  SecuritiesPayload,
  Source,
  SourceView,
} from "./types";

interface BodyProps<P> {
  payload: P;
  isHero: boolean;
  isSmall: boolean;
  onSource: (view: SourceView) => void;
}

/** What a tile shows under its heading, drawn from the payload the server computed. */
export function TileBody(props: BodyProps<AnyPayload>) {
  const { payload } = props;
  switch (payload.template) {
    case "payday_balance":
      return <PaydayBalance {...props} payload={payload} />;
    case "bills_until_payday":
      return <BillsUntilPayday {...props} payload={payload} />;
    case "due_soon":
      return <DueSoon {...props} payload={payload} />;
    case "expected_income":
      return <ExpectedIncome {...props} payload={payload} />;
    case "merchant_spending":
      return <MerchantSpending {...props} payload={payload} />;
    case "savings_goal":
      return <SavingsGoal {...props} payload={payload} />;
    case "bill":
      return <Bill {...props} payload={payload} />;
    case "net_worth":
      return <NetWorth {...props} payload={payload} />;
    case "monthly_spending":
      return <MonthlySpending {...props} payload={payload} />;
    case "income_and_spending":
      return <IncomeAndSpending {...props} payload={payload} />;
    case "securities":
      return <Securities {...props} payload={payload} />;
    case "regular_payments":
      return <RegularPayments {...props} payload={payload} />;
    case "pillar_3a":
      return <Pillar3a {...props} payload={payload} />;
    case "account_balances":
      return <AccountBalances {...props} payload={payload} />;
    case "mortgage":
      return <Mortgage {...props} payload={payload} />;
    case "card_bill":
      return <CardBill {...props} payload={payload} />;
  }
}

/** The pill at the end of a tile's heading, when the payload has something to flag. */
export function pillOf(payload: AnyPayload): ReactNode {
  switch (payload.template) {
    case "expected_income":
      return payload.status === "not_arrived" ? (
        <Pill tone="warn">Not arrived yet</Pill>
      ) : (
        <Pill tone="soft">Arrived</Pill>
      );
    case "monthly_spending":
    case "income_and_spending":
      return payload.months.length > 1 ? (
        <Pill tone="soft">
          {monthName(payload.months[0].month)} to{" "}
          {monthName(payload.months[payload.months.length - 1].month)}
        </Pill>
      ) : null;
    case "mortgage":
      if (payload.next_decision?.decide_by != null)
        return (
          <Pill tone="warn">
            Decide by {fullDate(payload.next_decision.decide_by)}
          </Pill>
        );
      return payload.next_maturity?.maturity_date != null ? (
        <Pill tone="warn">
          Runs out {fullDate(payload.next_maturity.maturity_date)}
        </Pill>
      ) : null;
    case "bill":
    case "card_bill":
      return payload.flag === null ? null : <FlagPill flag={payload.flag} />;
    default:
      return null;
  }
}

// More bars than this leave no room for a value over each; only the highest keeps it.
const LABELLED_BARS_MAX = 6;

function Pill({
  tone,
  children,
}: {
  tone: "warn" | "bad" | "soft";
  children: ReactNode;
}) {
  return (
    <span className={`pill ${tone}`}>
      {tone !== "soft" && <i />}
      {children}
    </span>
  );
}

function FlagPill({ flag }: { flag: Flag }) {
  return flag === "reminder" ? (
    <Pill tone="bad">Reminder</Pill>
  ) : (
    <Pill tone="soft">provisional</Pill>
  );
}

/** The tile's large figure: 54 px on the hero, 24 px on a small tile, 30 px otherwise. */
function Figure({
  amount,
  isHero,
  isSmall,
}: {
  amount: number;
  isHero: boolean;
  isSmall: boolean;
}) {
  if (isHero) {
    return (
      <div className="heronum num">
        <small>CHF</small>
        {money(amount)}
      </div>
    );
  }
  return (
    <div className={isSmall ? "fig s num" : "fig num"}>
      <small>CHF</small>
      {money(amount)}
    </div>
  );
}

/** The link under a tile that opens the bookings, payments or accounts behind its figures. */
function SourceLink({
  source,
  onSource,
}: {
  source: Source;
  onSource: (view: SourceView) => void;
}) {
  return (
    <button
      className="from"
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onSource({
          title: source.label,
          kind: source.kind,
          rows: source.rows,
          count: source.count,
        });
      }}
    >
      {source.label}
      <SmallIcon name="chevron" size={12} />
    </button>
  );
}

function Track({ share, label }: { share: number; label: string }) {
  const width = Math.min(100, Math.max(0, share * 100));
  return (
    <div className="track" role="img" aria-label={label}>
      <span style={{ width: `${width}%` }} />
    </div>
  );
}

function Split({
  parts,
  label,
}: {
  parts: { share: number; color: string }[];
  label: string;
}) {
  return (
    <div className="split" role="img" aria-label={label}>
      {parts.map((part, index) => (
        <span
          key={index}
          style={{
            width: `${Math.max(0, part.share * 100)}%`,
            background: part.color,
          }}
        />
      ))}
    </div>
  );
}

const PART_COLORS = [
  "var(--part-1)",
  "var(--part-2)",
  "var(--part-3)",
  "var(--part-5)",
];
const ALLOCATION_COLORS = [
  "var(--part-4)",
  "var(--part-3)",
  "var(--part-2)",
  "var(--part-1)",
  "var(--part-5)",
];

// --- payday_balance -------------------------------------------------------------------------

function PaydayBalance({
  payload,
  isHero,
  isSmall,
  onSource,
}: BodyProps<PaydayBalancePayload>) {
  const alternative = payload.alternative;
  const sentence =
    `CHF ${money(payload.per_day_chf)} a day for ${payload.days} days` +
    (alternative === null
      ? "."
      : `, or CHF ${money(alternative.per_day_chf)} with ${incomeName(alternative)}.`);
  return (
    <>
      <div className="herorow">
        <Figure amount={payload.figure_chf} isHero={isHero} isSmall={isSmall} />
        {alternative !== null && (
          <div className="alt num">
            If {incomeName(alternative)} arrives
            <b>CHF {money(alternative.left_chf)}</b>
          </div>
        )}
      </div>
      <p className="note num">{sentence}</p>
      {payload.points.length > 1 && <StepLine payload={payload} />}
      <SourceLink source={payload.source} onSource={onSource} />
    </>
  );
}

const RUN_WIDTH = 512;
const RUN_HEIGHT = 110;
const RUN_TOP = 14;
const RUN_BOTTOM = 100;

/** The balance falling one step per bill, from today to the day before payday. */
function StepLine({ payload }: { payload: PaydayBalancePayload }) {
  const span = Math.max(1, daysBetween(payload.today, payload.day_before));
  const balances = payload.points.map((point) => point.balance_chf);
  const highest = Math.max(...balances);
  const base = Math.min(0, ...balances);
  const range = Math.max(1, highest - base);
  const xOf = (date: string) =>
    Math.min(
      RUN_WIDTH,
      Math.max(0, (daysBetween(payload.today, date) / span) * RUN_WIDTH),
    );
  const yOf = (balance: number) =>
    RUN_BOTTOM - ((balance - base) / range) * (RUN_BOTTOM - RUN_TOP);
  const [first, ...rest] = payload.points;
  let line = `M0,${yOf(first.balance_chf).toFixed(1)}`;
  for (const point of rest) {
    line += ` H${xOf(point.date).toFixed(1)} V${yOf(point.balance_chf).toFixed(1)}`;
  }
  line += ` H${RUN_WIDTH}`;
  const last = payload.points[payload.points.length - 1];
  const middle = addDays(payload.today, Math.round(span / 2));
  return (
    <div className="run">
      <svg
        viewBox={`0 0 ${RUN_WIDTH} ${RUN_HEIGHT}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`Your ${payload.account_name} goes from CHF ${money(first.balance_chf)} today to CHF ${money(last.balance_chf)} on ${day(payload.day_before)}, one step per bill`}
      >
        <path className="area" d={`${line} V${RUN_HEIGHT} H0 Z`} />
        <path className="line" d={line} vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="axis num">
        <span>Today, CHF {money(payload.today_balance_chf)}</span>
        <span>{day(middle)}</span>
        <span>{day(payload.day_before)}</span>
      </div>
    </div>
  );
}

// --- bills_until_payday and due_soon --------------------------------------------------------

function Payee({ row }: { row: BillRow }) {
  return (
    <span className="payee">
      <b>{row.payee}</b>
      {row.flag !== null ? (
        <FlagPill flag={row.flag} />
      ) : (
        row.detail !== null && <span className="d">{row.detail}</span>
      )}
    </span>
  );
}

function BillsUntilPayday({
  payload,
  isHero,
  isSmall,
  onSource,
}: BodyProps<BillsUntilPaydayPayload>) {
  return (
    <>
      {isHero && (
        <Figure amount={payload.figure_chf} isHero isSmall={isSmall} />
      )}
      {payload.rows.length === 0 ? (
        <p className="note">
          No bills fall due before your salary on {day(payload.payday)}
        </p>
      ) : (
        <ul className="bills num">
          <li className="head">
            <span>Due</span>
            <span>To</span>
            <span className="amt">Amount</span>
            <span className="bal">Balance after</span>
          </li>
          {payload.rows.map((row) => (
            <li key={row.id}>
              <time dateTime={row.due}>{day(row.due)}</time>
              <Payee row={row} />
              <span className="amt">{money(row.amount_chf)}</span>
              <span className="bal">
                {row.balance_after_chf === null
                  ? ""
                  : money(row.balance_after_chf)}
              </span>
            </li>
          ))}
        </ul>
      )}
      <div className="sum num">
        <span>
          Together <b>CHF {money(payload.figure_chf)}</b>
        </span>
        <SourceLink source={payload.source} onSource={onSource} />
      </div>
    </>
  );
}

function DueSoon({
  payload,
  isHero,
  isSmall,
  onSource,
}: BodyProps<DueSoonPayload>) {
  return (
    <>
      <Figure amount={payload.figure_chf} isHero={isHero} isSmall={isSmall} />
      {payload.rows.length === 0 ? (
        <p className="note">
          Nothing falls due in the next {payload.days} days.
        </p>
      ) : (
        <ul className="list num">
          {payload.rows.map((row) => (
            <li key={row.id}>
              <time dateTime={row.due}>{day(row.due)}</time>
              <Payee row={row} />
              <span className="amt">{money(row.amount_chf)}</span>
            </li>
          ))}
        </ul>
      )}
      <SourceLink source={payload.source} onSource={onSource} />
    </>
  );
}

// --- expected_income --------------------------------------------------------------------------

function ExpectedIncome({
  payload,
  isHero,
  isSmall,
  onSource,
}: BodyProps<ExpectedIncomePayload>) {
  return (
    <>
      <Figure amount={payload.figure_chf} isHero={isHero} isSmall={isSmall} />
      <div className="months num">
        {payload.months.map((month) => (
          <div
            key={month.month}
            className={month.state === "on_time" ? "mo" : `mo ${month.state}`}
          >
            <i />
            <b>{monthName(month.month)}</b>
            <span>
              {month.arrived_on === null
                ? "nothing so far"
                : `came on ${day(month.arrived_on)}`}
            </span>
          </div>
        ))}
      </div>
      <SourceLink source={payload.source} onSource={onSource} />
    </>
  );
}

// --- merchant_spending ------------------------------------------------------------------------

function MerchantSpending({
  payload,
  isHero,
  isSmall,
  onSource,
}: BodyProps<MerchantSpendingPayload>) {
  return (
    <>
      <Figure amount={payload.figure_chf} isHero={isHero} isSmall={isSmall} />
      {payload.view === "donut" ? (
        <ShopDonut payload={payload} />
      ) : (
        <div className="shops num">
          {payload.rows.map((row) => (
            <div key={row.merchant} className="shop">
              <span>{row.merchant}</span>
              <span className="t">
                <span
                  style={{
                    width: `${Math.min(100, Math.max(0, row.share * 100))}%`,
                  }}
                />
              </span>
              <span className="v">{money(row.amount_chf)}</span>
            </div>
          ))}
        </div>
      )}
      <SourceLink source={payload.source} onSource={onSource} />
    </>
  );
}

const DONUT_COLORS = [...ALLOCATION_COLORS, "var(--muted)"];
// A circle of this radius is 100 long, so a share in percent is its stroke length.
const DONUT_RADIUS = 15.9155;

function ShopDonut({ payload }: { payload: MerchantSpendingPayload }) {
  const total = payload.figure_chf;
  const slices = payload.rows.map((row, index) => ({
    ...row,
    percent: total > 0 ? (row.amount_chf / total) * 100 : 0,
    color: DONUT_COLORS[index % DONUT_COLORS.length],
  }));
  const starts = slices.map((_, index) =>
    slices.slice(0, index).reduce((sum, slice) => sum + slice.percent, 0),
  );
  return (
    <div className="donut num">
      <svg
        viewBox="0 0 42 42"
        role="img"
        aria-label={slices
          .map((slice) => `${slice.merchant} ${percent(slice.percent)}`)
          .join(", ")}
      >
        {slices.map((slice, index) => (
          <circle
            key={slice.merchant}
            cx="21"
            cy="21"
            r={DONUT_RADIUS}
            fill="none"
            stroke={slice.color}
            strokeWidth="6"
            strokeDasharray={`${slice.percent} ${100 - slice.percent}`}
            strokeDashoffset={25 - starts[index]}
          />
        ))}
      </svg>
      <div className="shops">
        {slices.map((slice) => (
          <div key={slice.merchant} className="shop">
            <span>
              <i style={{ background: slice.color }} />
              {slice.merchant}
            </span>
            <span className="v">{money(slice.amount_chf)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- savings_goal and bill --------------------------------------------------------------------

function SavingsGoal({
  payload,
  isHero,
  isSmall,
  onSource,
}: BodyProps<SavingsGoalPayload>) {
  const change = payload.month_change_chf;
  const month = monthName(payload.month);
  let changeSentence = `Nothing went in or out in ${month}.`;
  if (change < 0)
    changeSentence = `CHF ${money(-change)} went out of it in ${month}.`;
  if (change > 0)
    changeSentence = `CHF ${money(change)} went into it in ${month}.`;
  return (
    <>
      <Figure amount={payload.figure_chf} isHero={isHero} isSmall={isSmall} />
      <Track
        share={payload.percent / 100}
        label={`${percent(payload.percent)} of the goal: ${payload.goal_text}`}
      />
      <p className="note num">of CHF {money(payload.goal_chf)}, your goal.</p>
      <p className="note num">{changeSentence}</p>
      <SourceLink source={payload.source} onSource={onSource} />
    </>
  );
}

function Bill({ payload, isHero, isSmall, onSource }: BodyProps<BillPayload>) {
  return (
    <>
      <Figure amount={payload.figure_chf} isHero={isHero} isSmall={isSmall} />
      <p className="note num">
        Due on {day(payload.due)} {payload.description}
      </p>
      <SourceLink source={payload.source} onSource={onSource} />
    </>
  );
}

// --- net_worth and securities -----------------------------------------------------------------

const PART_NAMES = {
  accounts: "Accounts",
  securities: "Securities",
  pension: "Pillar 3a",
};

function NetWorth({
  payload,
  isHero,
  isSmall,
  onSource,
}: BodyProps<NetWorthPayload>) {
  const total = payload.figure_chf;
  const parts = payload.parts.map((part, index) => ({
    ...part,
    share: total > 0 ? part.value_chf / total : 0,
    color: PART_COLORS[index % PART_COLORS.length],
  }));
  return (
    <>
      <Figure amount={total} isHero={isHero} isSmall={isSmall} />
      <Split
        parts={parts}
        label={parts
          .map(
            (part) =>
              `${percent(part.share * 100)} in ${PART_NAMES[part.group]}`,
          )
          .join(", ")}
      />
      <div className="legend num">
        {parts.map((part) => (
          <div key={part.group}>
            <span>
              <i style={{ background: part.color }} />
              {PART_NAMES[part.group]}
            </span>
            <b>{money(part.value_chf)}</b>
          </div>
        ))}
      </div>
      <SourceLink source={payload.source} onSource={onSource} />
    </>
  );
}

function Securities({
  payload,
  isHero,
  isSmall,
  onSource,
}: BodyProps<SecuritiesPayload>) {
  const parts = payload.allocation.map((part, index) => ({
    ...part,
    share: part.weight_pct / 100,
    color: ALLOCATION_COLORS[index % ALLOCATION_COLORS.length],
  }));
  return (
    <>
      <Figure amount={payload.figure_chf} isHero={isHero} isSmall={isSmall} />
      <Split
        parts={parts}
        label={parts
          .map((part) => `${percent(part.weight_pct)} ${part.label}`)
          .join(", ")}
      />
      <div className="key num">
        {parts.map((part) => (
          <span key={part.label}>
            <i style={{ background: part.color }} />
            {part.label} {percent(part.weight_pct)}
          </span>
        ))}
      </div>
      <SourceLink source={payload.source} onSource={onSource} />
    </>
  );
}

// --- monthly_spending and income_and_spending -------------------------------------------------

const BAR_HEIGHT = 104;
// The line view's plot height in px, which its SVG and the dots on the buttons share.
const LINE_HEIGHT = 132;

function barHeight(value: number, highest: number): number {
  if (highest <= 0 || value <= 0) return 2;
  return Math.max(2, Math.round((value / highest) * BAR_HEIGHT));
}

/** The source rows of one month, for a click on its bar. */
function monthView(source: Source, month: string, count: number): SourceView {
  return {
    title: `${monthName(month)} ${month.slice(0, 4)}`,
    kind: source.kind,
    rows: source.rows.filter((row) => row.date?.startsWith(month) === true),
    count,
  };
}

function MonthlySpending({
  payload,
  isHero,
  isSmall,
  onSource,
}: BodyProps<MonthlySpendingPayload>) {
  const highest = Math.max(
    0,
    ...payload.months.map((month) => month.total_chf),
  );
  const top = payload.months.find((month) => month.month === payload.highest);
  const isLine = payload.view === "line";
  return (
    <>
      {isHero && (
        <>
          <Figure amount={payload.figure_chf} isHero isSmall={isSmall} />
          <p className="note">A month on average.</p>
        </>
      )}
      <div
        className={[
          "bars num",
          payload.months.length > LABELLED_BARS_MAX ? "many" : "",
          isLine ? "line" : "",
        ].join(" ")}
        role="group"
        aria-label={
          top === undefined
            ? "Spending per month"
            : `Spending per month, highest in ${monthName(top.month)} with CHF ${money(top.total_chf)}`
        }
      >
        {payload.months.map((month) => (
          <button
            key={month.month}
            type="button"
            className={month.month === payload.highest ? "col hi" : "col"}
            aria-label={`${monthName(month.month)}: CHF ${money(month.total_chf)}, show its bookings`}
            onClick={(event) => {
              event.stopPropagation();
              onSource(monthView(payload.source, month.month, month.count));
            }}
          >
            <span
              className="v"
              style={
                isLine
                  ? { bottom: barHeight(month.total_chf, highest) + 10 }
                  : undefined
              }
            >
              {moneyRounded(month.total_chf)}
            </span>
            <span
              className="b"
              style={
                isLine
                  ? { bottom: barHeight(month.total_chf, highest) - 4 }
                  : { height: barHeight(month.total_chf, highest) }
              }
            />
          </button>
        ))}
        {isLine && (
          <svg
            viewBox={`0 0 ${payload.months.length} ${LINE_HEIGHT}`}
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <polyline
              points={payload.months
                .map(
                  (month, index) =>
                    `${index + 0.5},${LINE_HEIGHT - barHeight(month.total_chf, highest)}`,
                )
                .join(" ")}
            />
          </svg>
        )}
      </div>
      <div className="mlabels" aria-hidden="true">
        {payload.months.map((month) => (
          <span
            key={month.month}
            className={month.month === payload.highest ? "hi" : undefined}
          >
            {monthShort(month.month)}
          </span>
        ))}
      </div>
      <SourceLink source={payload.source} onSource={onSource} />
    </>
  );
}

function IncomeAndSpending({
  payload,
  isHero,
  isSmall,
  onSource,
}: BodyProps<IncomeAndSpendingPayload>) {
  const highest = Math.max(
    0,
    ...payload.months.flatMap((month) => [
      month.income_chf,
      month.spending_chf,
    ]),
  );
  return (
    <>
      <Figure amount={payload.figure_chf} isHero={isHero} isSmall={isSmall} />
      <p className="note">Left a month on average, after spending.</p>
      <div
        className="bars twin num"
        role="group"
        aria-label="Income and spending per month"
      >
        {payload.months.map((month) => (
          <button
            key={month.month}
            type="button"
            className="col"
            aria-label={`${monthName(month.month)}: CHF ${money(month.income_chf)} in, CHF ${money(month.spending_chf)} out, show its bookings`}
            onClick={(event) => {
              event.stopPropagation();
              const view = monthView(payload.source, month.month, 0);
              onSource({ ...view, count: view.rows.length });
            }}
          >
            <span className="pairbars">
              <span
                className="b in"
                style={{ height: barHeight(month.income_chf, highest) }}
              />
              <span
                className="b out"
                style={{ height: barHeight(month.spending_chf, highest) }}
              />
            </span>
          </button>
        ))}
      </div>
      <div className="mlabels num" aria-hidden="true">
        {payload.months.map((month) => (
          <span key={month.month}>
            {monthShort(month.month)}
            <small className={month.left_chf < 0 ? "minus" : undefined}>
              {moneyRounded(month.left_chf)}
            </small>
          </span>
        ))}
      </div>
      <div className="key">
        <span>
          <i className="in" />
          Income
        </span>
        <span>
          <i className="out" />
          Spending
        </span>
        <span>The figure under each month is what was left.</span>
      </div>
      <SourceLink source={payload.source} onSource={onSource} />
    </>
  );
}

// --- key-value tiles: regular_payments, account_balances, mortgage ---------------------------

function RegularPayments({
  payload,
  isHero,
  isSmall,
  onSource,
}: BodyProps<RegularPaymentsPayload>) {
  return (
    <>
      <Figure amount={payload.figure_chf} isHero={isHero} isSmall={isSmall} />
      <div className="kv num">
        {payload.rows.map((row) => (
          <div key={row.payee}>
            <span>{row.payee}</span>
            <b>{money(row.amount_chf)}</b>
          </div>
        ))}
      </div>
      <SourceLink source={payload.source} onSource={onSource} />
    </>
  );
}

function AccountBalances({
  payload,
  isHero,
  isSmall,
  onSource,
}: BodyProps<AccountBalancesPayload>) {
  return (
    <>
      <Figure amount={payload.figure_chf} isHero={isHero} isSmall={isSmall} />
      <div className="kv num">
        {payload.rows.map((row) => (
          <div key={row.account_id}>
            <span title={row.purpose ?? undefined}>{row.name}</span>
            <b>{money(row.balance_chf)}</b>
          </div>
        ))}
      </div>
      <SourceLink source={payload.source} onSource={onSource} />
    </>
  );
}

function Mortgage({
  payload,
  isHero,
  isSmall,
  onSource,
}: BodyProps<MortgagePayload>) {
  return (
    <>
      <Figure amount={payload.figure_chf} isHero={isHero} isSmall={isSmall} />
      <div className="kv num">
        {payload.tranches.map((tranche) => (
          <div key={tranche.loan_id}>
            <span>
              {tranche.product}
              <small>
                {percent(tranche.interest_rate)}
                {tranche.maturity_date !== null &&
                  `, until ${fullDate(tranche.maturity_date)}`}
              </small>
            </span>
            <b>{money(tranche.balance_chf)}</b>
          </div>
        ))}
      </div>
      <p className="note num">
        CHF {money(payload.annual_interest_chf)} interest a year.
      </p>
      {payload.next_decision?.decide_by != null && (
        <p className="note num">
          Decide on the {payload.next_decision.product} by{" "}
          {fullDate(payload.next_decision.decide_by)}.
          {payload.next_decision.without_decision !== null &&
            ` ${payload.next_decision.without_decision}`}
        </p>
      )}
      <SourceLink source={payload.source} onSource={onSource} />
    </>
  );
}

// --- pillar_3a and card_bill ------------------------------------------------------------------

function Pillar3a({
  payload,
  isHero,
  isSmall,
  onSource,
}: BodyProps<Pillar3aPayload>) {
  const maximum = payload.maximum_chf;
  const covered = maximum > 0 ? (maximum - payload.figure_chf) / maximum : 0;
  const next = payload.planned[0];
  let plan = "";
  if (payload.planned.length === 1)
    plan = ` The transfer is planned for ${day(next.date)}`;
  if (payload.planned.length > 1) {
    plan = ` ${payload.planned.length} transfers are planned, the first on ${day(next.date)}`;
  }
  return (
    <>
      <p className="note">Left to pay in for {payload.year}</p>
      <Figure amount={payload.figure_chf} isHero={isHero} isSmall={isSmall} />
      <Track
        share={covered}
        label={`CHF ${money(maximum - payload.figure_chf)} of CHF ${money(maximum)} paid in or planned`}
      />
      <p className="note num">
        {payload.figure_chf > 0
          ? `Of the maximum of CHF ${money(maximum)}.${plan}`
          : `The maximum of CHF ${money(maximum)} for ${payload.year} is reached.${plan}`}
      </p>
      <SourceLink source={payload.source} onSource={onSource} />
    </>
  );
}

function CardBill({
  payload,
  isHero,
  isSmall,
  onSource,
}: BodyProps<CardBillPayload>) {
  const period = /^\d{4}-\d{2}$/.test(payload.period)
    ? monthName(payload.period)
    : payload.period;
  const purchases =
    payload.purchases === 1 ? "1 purchase" : `${payload.purchases} purchases`;
  return (
    <>
      <Figure amount={payload.figure_chf} isHero={isHero} isSmall={isSmall} />
      <p className="note num">
        {payload.card_name}, {period}: {purchases}.
        {payload.due !== null && ` Due on ${day(payload.due)}`}
      </p>
      <SourceLink source={payload.source} onSource={onSource} />
    </>
  );
}

function incomeName(alternative: {
  counterparty: string;
  label?: string | null;
}) {
  return alternative.label ?? `the payment from ${alternative.counterparty}`;
}
