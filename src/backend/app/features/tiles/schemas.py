"""The tile contract: what a board stores (a template and its arguments) and what it is drawn from.

A tile stores the question, never the answer. `Args` are what the model or the customer chose;
`Payload` is what the server computes from the banking API every time the board is read.
The page mirrors the payloads in `src/frontend/src/board/types.ts`.
"""

import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

# Computed as Decimal, sent as a JSON number.
Chf = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
Name = Annotated[str, Field(min_length=1, max_length=80)]
Flag = Literal["reminder", "provisional"]
SOURCE_ROWS_MAX = 40


class Args(BaseModel):
    # An argument the template does not have is an error the model can correct.
    model_config = ConfigDict(extra="forbid")


class SourceRow(BaseModel):
    # A booking id, a payment's source id, an account id, an ISIN or a document id.
    id: str
    date: datetime.date | None = None
    text: str
    amount_chf: Chf | None = None


class Source(BaseModel):
    """What stands behind a tile's figures; the customer opens it from the link under the tile."""

    # The link's words, such as "Privatkonto and 8 upcoming payments".
    label: str
    kind: Literal["bookings", "payments", "accounts", "positions", "loans", "documents"]
    # The first SOURCE_ROWS_MAX rows; `count` says how many there are.
    rows: list[SourceRow]
    count: int


class Payload(BaseModel):
    # The tile's large figure. The first tile of a board draws it larger, on the dark ground.
    figure_chf: Chf
    source: Source


# --- payday_balance: what is left on the day before the next salary -------------------------


class PaydayBalanceArgs(Args):
    account_id: str = Field(description="The account the salary arrives on, such as ACC-PRIV.")
    expected_from: Name | None = Field(
        default=None,
        description="A counterparty whose regular income has not arrived yet, for a second case "
        "with that money. Leave out when nothing is late.",
    )
    expected_label: Name | None = Field(
        default=None,
        description="What the customer would call that income, with its article, such as "
        "'the child support'. No figures. Only together with expected_from.",
    )


class BalancePoint(BaseModel):
    date: datetime.date
    balance_chf: Chf


class PaydayAlternative(BaseModel):
    counterparty: str
    # The customer's own words for this income, such as "the child support"; None: unknown.
    label: str | None = None
    amount_chf: Chf
    left_chf: Chf
    per_day_chf: Chf


class PaydayBalancePayload(Payload):
    template: Literal["payday_balance"] = "payday_balance"
    account_name: str
    # The next salary's expected date, from the rhythm of the earlier ones.
    payday: datetime.date
    # The day the figure is for: the day before payday.
    day_before: datetime.date
    days: int
    per_day_chf: Chf
    today: datetime.date
    today_balance_chf: Chf
    # The balance after each payment until the day before payday, starting with today.
    points: list[BalancePoint]
    upcoming_count: int
    alternative: PaydayAlternative | None


# --- bills_until_payday: every payment before the next salary, with the balance after it ----


class BillsUntilPaydayArgs(Args):
    account_id: str = Field(description="The account the bills leave from, such as ACC-PRIV.")


class BillRow(BaseModel):
    id: str
    due: datetime.date
    payee: str
    # The few words after the payee, such as "rent for December"; None when the text adds nothing.
    detail: str | None
    amount_chf: Chf
    balance_after_chf: Chf | None
    flag: Flag | None


class BillsUntilPaydayPayload(Payload):
    template: Literal["bills_until_payday"] = "bills_until_payday"
    payday: datetime.date
    rows: list[BillRow]


# --- due_soon: what leaves the accounts in the next days, largest first ---------------------


class DueSoonArgs(Args):
    days: Literal[14, 30, 60, 90] = 30


class DueSoonPayload(Payload):
    template: Literal["due_soon"] = "due_soon"
    days: int
    # The four largest, in order of their due date; `count` is all of them.
    rows: list[BillRow]
    count: int


# --- expected_income: a regular income and whether it came, month by month ------------------


class ExpectedIncomeArgs(Args):
    counterparty: Name = Field(
        description="Who the income comes from, as the bookings name them, such as Patrick Rüegg."
    )


class IncomeMonth(BaseModel):
    # "2026-11"
    month: str
    arrived_on: datetime.date | None
    amount_chf: Chf | None
    state: Literal["on_time", "late", "open"]


class ExpectedIncomePayload(Payload):
    template: Literal["expected_income"] = "expected_income"
    counterparty: str
    # The usual day of the month it arrives on.
    usual_day: int
    status: Literal["arrived", "not_arrived"]
    # The last three months, oldest first, ending with the current one.
    months: list[IncomeMonth]


# --- merchant_spending: what went to a few named merchants in a period ----------------------


class MerchantSpendingArgs(Args):
    merchants: list[Name] = Field(
        min_length=1,
        max_length=6,
        description="Merchants as the bookings name them, such as Lidl, Aldi, Migros.",
    )
    period: Literal["this_month", "last_month", "last_3_months"] = "this_month"


class MerchantRow(BaseModel):
    merchant: str
    amount_chf: Chf
    # Of the largest row, 0 to 1, for the bar.
    share: float
    count: int


class MerchantSpendingPayload(Payload):
    template: Literal["merchant_spending"] = "merchant_spending"
    date_from: datetime.date
    date_to: datetime.date
    # Largest first; a merchant without bookings in the period is left out.
    rows: list[MerchantRow]


# --- savings_goal: a savings account against the goal the bank holds for it -----------------


class SavingsGoalArgs(Args):
    account_id: str = Field(description="A savings account that has a goal, such as ACC-SAV.")


class SavingsGoalPayload(Payload):
    template: Literal["savings_goal"] = "savings_goal"
    account_name: str
    # The goal as the bank words it, and the amount in it.
    goal_text: str
    goal_chf: Chf
    percent: float
    # What came in minus what went out in the current month; negative when money left.
    month_change_chf: Chf
    month: str
    # Money taken out of the account since 1 January: how often and how much.
    withdrawals_this_year: int = 0
    withdrawn_this_year_chf: Chf = Decimal(0)


# --- bill: one payment that is due ------------------------------------------------------------


class BillArgs(Args):
    payment_id: str = Field(description="The source id of an upcoming payment, such as PAY-0244.")


class BillPayload(Payload):
    template: Literal["bill"] = "bill"
    payee: str
    due: datetime.date
    description: str
    flag: Flag | None


# --- net_worth: what the customer owns, split into its parts ---------------------------------


class NetWorthArgs(Args):
    include_pension: bool = Field(
        default=False, description="Whether pillar 3a counts. It is tied up, so usually not."
    )


class WorthPart(BaseModel):
    # "accounts", "securities" or "pension"
    group: Literal["accounts", "securities", "pension"]
    value_chf: Chf
    count: int


class NetWorthPayload(Payload):
    template: Literal["net_worth"] = "net_worth"
    parts: list[WorthPart]
    includes_pension: bool


# --- monthly_spending: spending per month as bars ---------------------------------------------


class MonthlySpendingArgs(Args):
    months: Literal[3, 6, 12] = 6
    merchants: list[Name] | None = Field(
        default=None,
        max_length=6,
        description="Only these merchants. Leave out for all spending.",
    )


class SpendingMonth(BaseModel):
    month: str
    total_chf: Chf
    count: int


class MonthlySpendingPayload(Payload):
    """`figure_chf` is the average per month."""

    template: Literal["monthly_spending"] = "monthly_spending"
    # Whole months only, oldest first.
    months: list[SpendingMonth]
    # The month with the highest total.
    highest: str


# --- income_and_spending: what came in, what went out and what was left, per month -----------


class IncomeAndSpendingArgs(Args):
    months: Literal[3, 6, 12] = 6


class CashflowMonth(BaseModel):
    month: str
    income_chf: Chf
    spending_chf: Chf
    left_chf: Chf


class IncomeAndSpendingPayload(Payload):
    """`figure_chf` is what was left per month on average."""

    template: Literal["income_and_spending"] = "income_and_spending"
    months: list[CashflowMonth]


# --- securities: the depot, its split and what was paid in ------------------------------------


class SecuritiesArgs(Args):
    pass


class AllocationPart(BaseModel):
    label: str
    value_chf: Chf
    weight_pct: float


class SecuritiesPayload(Payload):
    template: Literal["securities"] = "securities"
    invested_chf: Chf
    allocation: list[AllocationPart]
    positions: int


# --- regular_payments: a few named payees the customer pays every month ----------------------


class RegularPaymentsArgs(Args):
    payees: list[Name] = Field(
        min_length=1,
        max_length=8,
        description="Payees as the upcoming payments name them, such as Fitnesspark, Swisscom.",
    )


class RegularPaymentRow(BaseModel):
    payee: str
    amount_chf: Chf
    next_due: datetime.date


class RegularPaymentsPayload(Payload):
    """`figure_chf` is the sum of one run of each payee."""

    template: Literal["regular_payments"] = "regular_payments"
    rows: list[RegularPaymentRow]


# --- pillar_3a: paid in this year against the year's maximum ----------------------------------


class Pillar3aArgs(Args):
    pass


class PlannedTransfer(BaseModel):
    id: str
    date: datetime.date
    amount_chf: Chf


class Pillar3aPayload(Payload):
    """`figure_chf` is what the standing orders leave missing to the maximum this year.

    The one-off transfers in `planned` are what covers it; negative is over the maximum.
    """

    template: Literal["pillar_3a"] = "pillar_3a"
    year: int
    maximum_chf: Chf
    # Paid into the 3a account this year until today, without interest.
    paid_chf: Chf
    # What the standing orders still pay in until 31 December.
    standing_orders_chf: Chf
    balance_chf: Chf
    # One-off transfers to the 3a account that are planned until the end of the year.
    planned: list[PlannedTransfer]


# --- account_balances: a few accounts side by side --------------------------------------------


class AccountBalancesArgs(Args):
    account_ids: list[str] = Field(
        min_length=1, max_length=6, description="Account ids, such as ACC-TAX, ACC-RES."
    )


class AccountRow(BaseModel):
    account_id: str
    name: str
    balance_chf: Chf
    purpose: str | None


class AccountBalancesPayload(Payload):
    template: Literal["account_balances"] = "account_balances"
    rows: list[AccountRow]


# --- mortgage: the loans, their interest and what runs out next -------------------------------


class MortgageArgs(Args):
    pass


class Tranche(BaseModel):
    loan_id: str
    product: str
    balance_chf: Chf
    interest_rate: float
    maturity_date: datetime.date | None
    next_interest_date: datetime.date | None
    # From the loan's remarks: the date the bank needs the customer's decision by, and what
    # happens without one, in the bank's words.
    decide_by: datetime.date | None = None
    without_decision: str | None = None


class MortgagePayload(Payload):
    """`figure_chf` is the whole debt."""

    template: Literal["mortgage"] = "mortgage"
    annual_interest_chf: Chf
    tranches: list[Tranche]
    # The tranche that runs out first, when it does within 18 months.
    next_maturity: Tranche | None
    # The tranche whose decision is due first, from today on.
    next_decision: Tranche | None = None


# --- card_bill: the credit card's next statement ----------------------------------------------


class CardBillArgs(Args):
    card_id: str = Field(description="A credit card's id, such as CARD-VISA.")


class CardBillPayload(Payload):
    template: Literal["card_bill"] = "card_bill"
    card_name: str
    period: str
    due: datetime.date | None
    flag: Flag | None
    purchases: int


TEMPLATES: dict[str, tuple[type[Args], type[Payload]]] = {
    "payday_balance": (PaydayBalanceArgs, PaydayBalancePayload),
    "bills_until_payday": (BillsUntilPaydayArgs, BillsUntilPaydayPayload),
    "due_soon": (DueSoonArgs, DueSoonPayload),
    "expected_income": (ExpectedIncomeArgs, ExpectedIncomePayload),
    "merchant_spending": (MerchantSpendingArgs, MerchantSpendingPayload),
    "savings_goal": (SavingsGoalArgs, SavingsGoalPayload),
    "bill": (BillArgs, BillPayload),
    "net_worth": (NetWorthArgs, NetWorthPayload),
    "monthly_spending": (MonthlySpendingArgs, MonthlySpendingPayload),
    "income_and_spending": (IncomeAndSpendingArgs, IncomeAndSpendingPayload),
    "securities": (SecuritiesArgs, SecuritiesPayload),
    "regular_payments": (RegularPaymentsArgs, RegularPaymentsPayload),
    "pillar_3a": (Pillar3aArgs, Pillar3aPayload),
    "account_balances": (AccountBalancesArgs, AccountBalancesPayload),
    "mortgage": (MortgageArgs, MortgagePayload),
    "card_bill": (CardBillArgs, CardBillPayload),
}
Template = Literal[
    "payday_balance",
    "bills_until_payday",
    "due_soon",
    "expected_income",
    "merchant_spending",
    "savings_goal",
    "bill",
    "net_worth",
    "monthly_spending",
    "income_and_spending",
    "securities",
    "regular_payments",
    "pillar_3a",
    "account_balances",
    "mortgage",
    "card_bill",
]
AnyPayload = Annotated[
    PaydayBalancePayload
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
    | CardBillPayload,
    Field(discriminator="template"),
]
