# Boards gate, apertus

10 of 12 acceptable.

- lukas: 3 of 3
- jana: 3 of 3
- daniela: 2 of 3
- marco: 2 of 3

OpenRouter: 24 calls sent, 0 from cache, 98661 tokens in, 141587 out, about $0.2051

## lukas-1: acceptable

- kind: A young professional building wealth with a large portfolio and multiple savings pots
- question: What do I actually own and where is the money going?
- 6.0 s, apertus-v1-5-70b

**Where the money lives and flows**

- What you own (net_worth): 131'212.64
- Regular income from Sara Keller (expected_income): 2'200.00
- Savings pots with their purpose (account_balances): 48'983.35
- Due in the next 30 days (due_soon): 8'302.59
- Japan trip savings are way ahead (savings_goal): 37'566.29
- Monthly cash flow trend (income_and_spending): -199.61

- service titles_checked: default title for: Upcoming bills in the next 30 days

## lukas-2: acceptable

- kind: A young professional building wealth with a large portfolio and multiple savings pots
- question: What do I actually own and where is the money going?
- 6.0 s, apertus-v1-5-70b

**Where the money lives and flows**

- What you own (net_worth): 131'212.64
- Regular income from Sara Keller (expected_income): 2'200.00
- Savings pots with their purpose (account_balances): 48'983.35
- Due in the next 30 days (due_soon): 8'302.59
- Japan trip savings are way ahead (savings_goal): 37'566.29
- Monthly cash flow trend (income_and_spending): -199.61

- service titles_checked: default title for: Upcoming bills in the next 30 days

## lukas-3: acceptable

- kind: A young professional building wealth with a large portfolio and multiple savings pots
- question: What do I actually own and where is the money going?
- 6.0 s, apertus-v1-5-70b

**Where the money is and where it goes**

- What you own (net_worth): 131'212.64
- Regular income from Sara Keller (expected_income): 2'200.00
- Savings pots at a glance (account_balances): 48'983.35
- Due in the next 30 days (due_soon): 8'302.59
- Japan trip savings are on track (savings_goal): 37'566.29
- Monthly cash flow trend (income_and_spending): -199.61

- service titles_checked: default title for: Upcoming bills in the next 30 days

## jana-1: acceptable

- kind: Young professional starting out with negative cash flow
- question: Will my money last until the next salary arrives?
- 6.3 s, apertus-v1-5-70b

**Cash Flow Until Next Salary**

- What is left after all bills are paid (income_and_spending): 250.82
- Loan repayment to Andrea Widmer (regular_payments): 150.00
- Due in the next 30 days (due_soon): 3'155.45
- Bill from Steuerverwaltung des Kantons Bern (bill): 1'180.00
- Savings progress toward emergency fund (savings_goal): 4'919.20
- Pillar 3a, 2026 (pillar_3a): 3'658.00

- service titles_checked: default title for: Upcoming bills in the next 30 days; Provisional tax bill due 30 Nov; Pillar 3a retirement savings gap

## jana-2: acceptable

- kind: Young professional starting out with negative cash flow and upcoming bills
- question: Will my money last until the next salary arrives?
- 5.3 s, apertus-v1-5-70b

**Cash Flow and Immediate Bills**

- What is left after all bills are paid (income_and_spending): 250.82
- Loan repayment to Andrea Widmer (regular_payments): 150.00
- Due in the next 30 days (due_soon): 3'155.45
- Bill from Steuerverwaltung des Kantons Bern (bill): 1'180.00
- Savings progress toward emergency fund (savings_goal): 4'919.20
- Pillar 3a, 2026 (pillar_3a): 3'658.00

- service titles_checked: default title for: Bills due in the next 30 days; Provisional tax bill due 30.11.2026; Pillar 3a retirement savings gap

## jana-3: acceptable

- kind: Young professional starting out with negative cash flow
- question: Will my money last until the next salary arrives?
- 4.8 s, apertus-v1-5-70b

**Cash Flow Until Next Salary**

- What is left after all bills are paid (income_and_spending): 250.82
- Loan repayment to Andrea Widmer (regular_payments): 150.00
- Due in the next 30 days (due_soon): 3'155.45
- Bill from Steuerverwaltung des Kantons Bern (bill): 1'180.00
- Savings progress toward emergency fund (savings_goal): 4'919.20
- Pillar 3a, 2026 (pillar_3a): 3'658.00

- service titles_checked: default title for: Upcoming bills in the next 30 days; Provisional tax bill due 30 November; Pillar 3a retirement savings gap

## daniela-1: acceptable

- kind: single mother with tight monthly cash flow, living on a part-time salary
- question: Will the money last until the next salary arrives?
- 5.6 s, apertus-v1-5-70b

**Cash Flow Until Next Paycheck**

- What is left on the day before the salary (payday_balance): 124.96
- Savings pots overview (account_balances): 3'754.75
- Upcoming bill: Lina's dentist (bill): 440.00
- Bills due before next salary (bills_until_payday): 2'950.20
- Patrick's transfer still pending (expected_income): 1'050.00

- service tiles_resolved: 5 of 6 resolved; dropped: Savings accounts side by side

## daniela-2: NOT acceptable

- kind: single mother with tight monthly cash flow, living on a part-time salary
- question: Will the money last until the next payday?
- 5.5 s, apertus-v1-5-70b

**Cash Flow Until Next Payday**

- What is left the day before the salary (payday_balance): 124.96
- Savings pots overview (account_balances): 3'754.75
- Bills due before next salary (bills_until_payday): 2'950.20
- Patrick's transfer still missing (expected_income): 1'050.00
- Left on 23.12., the day before your salary (payday_balance): 124.96

- resolved: title figure: Left on 23.12., the day before your salary
- judge not_empty_or_repeated: Tiles 1 and 5 are the same payday_balance computation showing the identical figure (CHF 124.96 left on 23.12.) twice in slightly different words, which is a repeat.
- service tiles_resolved: 4 of 6 resolved; dropped: Savings accounts side by side; Reserve vs Lina's gift account
- service boards_full: Cash Flow Until Next Payday: 1 added

## daniela-3: acceptable

- kind: single mother with tight month-to-month cash flow
- question: Will the money last until the next salary arrives?
- 5.8 s, apertus-v1-5-70b

**Cash Flow Until Next Paycheck**

- What is left on the day before the salary (payday_balance): 124.96
- Savings pots overview (account_balances): 3'754.75
- Upcoming bill: Lina's dentist (bill): 440.00
- Bills due before next salary (bills_until_payday): 2'950.20
- Late transfer from Patrick Rüegg (expected_income): 1'050.00

- service tiles_resolved: 5 of 6 resolved; dropped: Savings accounts side by side

## marco-1: NOT acceptable

- kind: Family carrying a house with a major financial decision ahead
- question: Do we have enough left on payday to cover the next mortgage instalment and still keep the house fund safe?
- 4.8 s, apertus-v1-5-70b

**Payday Decision Check**

- Mortgage (mortgage): 862'500.00
- Regular family income (expected_income): 2'600.00
- Monthly cash flow trend (income_and_spending): -246.13
- Due in the next 30 days (due_soon): 6'566.00
- Savings and reserve accounts (account_balances): 83'484.90

- judge titles: The board's own title 'Payday Decision Check' borrows the payday framing that belongs to a different kind of customer and matches nothing in this mortgage-decision board, even though the individual tile titles are short and acceptable.
- service titles_checked: default title for: The mortgage that must be renewed by 15 December; Upcoming bills in next 30 days

## marco-2: acceptable

- kind: A family carrying a house with a major financial decision ahead
- question: Do we have enough cash to refinance the maturing mortgage tranche without straining the family budget?
- 4.5 s, apertus-v1-5-70b

**Refinance Decision Check**

- Mortgage (mortgage): 862'500.00
- Regular family income (expected_income): 2'600.00
- Monthly cash flow trend (income_and_spending): -246.13
- Due in the next 30 days (due_soon): 6'566.00
- Savings and reserve accounts (account_balances): 83'484.90

- service titles_checked: default title for: The mortgage that must be renewed by 15 December 2026; Upcoming bills in next 30 days

## marco-3: acceptable

- kind: A family carrying a house with a major financial decision ahead
- question: Do we have enough cash to refinance the maturing mortgage tranche without jeopardising the family budget?
- 5.2 s, apertus-v1-5-70b

**Refinance Decision Check**

- Mortgage (mortgage): 862'500.00
- Regular family income (expected_income): 2'600.00
- Monthly cash flow trend (income_and_spending): -246.13
- Savings and reserve accounts (account_balances): 83'484.90
- Due in the next 30 days (due_soon): 6'566.00

- service titles_checked: default title for: The mortgage that must be renewed by 15 December 2026; Upcoming bills in next 30 days

