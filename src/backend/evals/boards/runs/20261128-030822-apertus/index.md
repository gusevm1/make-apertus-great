# Boards gate, apertus

4 of 12 acceptable.

- lukas: 1 of 3
- jana: 1 of 3
- daniela: 1 of 3
- marco: 1 of 3

OpenRouter: 16 calls sent, 0 from cache, 69771 tokens in, 144440 out, about $0.2071

## lukas-1: acceptable

- kind: A young professional building wealth with a large investment portfolio and multiple savings pots.
- question: What is my total net worth and how should I allocate it between current goals and long-term growth?
- 7.3 s, apertus-v1-5-70b

**Overview**

- What you own (net_worth): 131'212.64
- Visa Gold bill reminder (card_bill): 3'301.74
- Pillar 3a gap (pillar_3a): 58.00
- Securities value (securities): 72'512.96
- Bills until payday (due_soon): 8'302.59
- Rising fixed costs (regular_payments): 213.00
- Savings pots (account_balances): 48'983.35

## lukas-2: NOT acceptable

- kind: A young professional building wealth with a large investment portfolio and multiple savings pots.
- question: What is my total net worth and how should I allocate it between current goals and long-term growth?
- 7.3 s, apertus-v1-5-70b

**Overview**

- What you own (net_worth): 131'212.64
- Visa Gold bill reminder (card_bill): 3'301.74
- Pillar 3a gap (pillar_3a): 58.00
- Securities value (securities): 72'512.96
- Bills until payday (due_soon): 8'302.59
- Rising fixed costs (regular_payments): 213.00
- Savings pots (account_balances): 48'983.35

- judge titles: «Rising fixed costs» claims a rise the tile never shows (it lists only two current amounts with due dates), and «Bills until payday» borrows paycheck-to-paycheck framing that is not this well-off customer's term.

## lukas-3: NOT acceptable

- kind: A young professional building wealth with a large investment portfolio and multiple savings pots.
- question: What is my total net worth and how should I allocate it between current goals and long-term growth?
- 7.3 s, apertus-v1-5-70b

**Overview**

- What you own (net_worth): 131'212.64
- Visa Gold bill reminder (card_bill): 3'301.74
- Pillar 3a gap (pillar_3a): 58.00
- Securities value (securities): 72'512.96
- Bills until payday (due_soon): 8'302.59
- Rising fixed costs (regular_payments): 213.00
- Savings pots (account_balances): 48'983.35

- judge titles: 'Rising fixed costs' asserts a rise the tile never shows (only the two December amounts 119 and 94, with no year-over-year comparison), and 'Bills until payday' labels what is actually a 30-day due list, so titles do not reliably match what the tiles show.

## jana-1: acceptable

- kind: Young professional starting out with negative cash flow
- question: Will my money last until the next payday and what do I need to cut?
- 5.5 s, apertus-v1-5-70b

**Every month**

- What is left at month's end (income_and_spending): 250.82
- Loan to Andrea Widmer (regular_payments): 150.00
- Emergency fund (savings_goal): 4'919.20
- Provisional tax bill (bill): 1'180.00
- Pillar 3a savings gap (pillar_3a): 3'658.00
- Bills before payday (due_soon): 3'155.45

## jana-2: NOT acceptable

Error: Apertus timed out

## jana-3: NOT acceptable

Error: Apertus timed out

## daniela-1: NOT acceptable

Error: Apertus timed out

## daniela-2: NOT acceptable

Error: Apertus timed out

## daniela-3: acceptable

- kind: single mother with tight month-to-month cash flow
- question: Will the money last until the next salary arrives?
- 162.0 s, apertus-v1-5-70b

**Until payday**

- What's left before payday (payday_balance): 124.96
- Child support pending (expected_income): 1'050.00
- Dentist bill due (bill): 440.00
- Emergency fund (savings_goal): 284.25
- Bills until payday (bills_until_payday): 2'950.20
- Monthly cash shortfall (income_and_spending): -370.77
- Savings pots (account_balances): 3'754.75

## marco-1: NOT acceptable

- kind: A family carrying a house with a decision ahead
- question: What should we do with the maturing mortgage tranche and how do we keep the house secure?
- 141.0 s, apertus-v1-5-70b

**The house**

- The mortgage (mortgage): 862'500.00
- Pillar 3a savings (pillar_3a): 58.00
- House reserve nearly met (savings_goal): 19'350.30
- Car instalments left (regular_payments): 489.00
- Bills due this month (due_soon): 6'566.00
- Monthly cash shortfall (income_and_spending): -246.13
- Savings pots (account_balances): 83'484.90

- judge titles: "Bills due this month" heads a 30-day window whose visible dues run into late December (21 and 23 December) and "Car instalments left" sits on a tile showing only the next CHF 489 instalment rather than instalments remaining, so two titles do not match what their tiles show.

## marco-2: NOT acceptable

- kind: Family carrying a house with a decision ahead
- question: What should we do with the maturing mortgage tranche and how do we keep the house secure?
- 133.2 s, apertus-v1-5-70b

**The house**

- The mortgage (mortgage): 862'500.00
- Pillar 3a savings (pillar_3a): 58.00
- House reserve (savings_goal): 19'350.30
- Car instalments (regular_payments): 489.00
- Bills until payday (due_soon): 6'566.00
- Cash flow (income_and_spending): -246.13
- Savings pots (account_balances): 83'484.90

- judge titles: 'Bills until payday' mislabels a next-30-days due list and borrows the payday framing of a different kind of customer, so one title neither matches what its tile shows nor uses this customer's terms.

## marco-3: acceptable

- kind: Family carrying a house with a decision ahead
- question: What should we do with the maturing mortgage tranche and how do we keep the house secure?
- 76.1 s, apertus-v1-5-70b

**The house**

- The mortgage (mortgage): 862'500.00
- Pillar 3a savings (pillar_3a): 58.00
- House reserve nearly met (savings_goal): 19'350.30
- Car instalments left (regular_payments): 489.00
- Bills due this month (due_soon): 6'566.00
- Monthly cash shortfall (income_and_spending): -246.13
- Savings pots (account_balances): 83'484.90

