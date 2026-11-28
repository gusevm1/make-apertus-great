# Boards gate, apertus

11 of 12 acceptable.

- lukas: 2 of 3
- jana: 3 of 3
- daniela: 3 of 3
- marco: 3 of 3

OpenRouter: 25 calls sent, 0 from cache, 99975 tokens in, 173560 out, about $0.2500

## lukas-1: acceptable

- kind: A young professional building wealth with a large investment portfolio and multiple savings pots.
- question: What is my net worth today and how should I allocate it between my goals and future growth?
- 7.6 s, apertus-v1-5-70b

**Net Worth & Allocation**

- What you own (net_worth): 131'212.64
- Regular income from Sara Keller (expected_income): 2'200.00
- Visa Gold, November (card_bill): 3'301.74
- Pillar 3a, 2026 (pillar_3a): 58.00
- Securities (securities): 72'512.96

- service tiles_resolved: 2 of 7 resolved; dropped: Monthly salary from Limmatblau Versicherungen AG; Total monthly income overview; Projected cash flow before next salary; Upcoming salary deposit on 24.12.2026; Monthly spending average vs income
- service boards_full: Net Worth & Allocation: 3 added

## lukas-2: acceptable

- kind: A young professional building wealth with a large investment portfolio and multiple savings pots.
- question: What is my net worth today and how should I allocate it between my goals and future growth?
- 7.6 s, apertus-v1-5-70b

**Net Worth & Allocation**

- What you own (net_worth): 131'212.64
- Regular income from Sara Keller (expected_income): 2'200.00
- Visa Gold, November (card_bill): 3'301.74
- Pillar 3a, 2026 (pillar_3a): 58.00
- Securities (securities): 72'512.96

- service tiles_resolved: 2 of 7 resolved; dropped: Monthly salary from Limmatblau Versicherungen AG; Total monthly income overview; Projected cash flow before next salary; Upcoming salary deposit on 24.12.2026; Monthly spending average vs. income
- service boards_full: Net Worth & Allocation: 3 added

## lukas-3: NOT acceptable

- kind: A young professional building wealth with a large investment portfolio and multiple savings pots.
- question: What do I actually own and where is the money going, so I can keep growing it while hitting my goals?
- 6.8 s, apertus-v1-5-70b

**Where the money goes and what you own**

- What you own (net_worth): 131'212.64
- Regular partner support (expected_income): 2'200.00
- Japan trip pot nearly full (savings_goal): 37'566.29
- Savings accounts at a glance (account_balances): 48'983.35
- Monthly cash flow trend (income_and_spending): -199.61
- Due in the next 30 days (due_soon): 8'302.59

- judge titles: 'Japan trip pot nearly full' contradicts its own figure: CHF 37'566 against a CHF 12'000 goal (313%) means the pot is already more than three times covered, not nearly full.
- service titles_checked: default title for: Upcoming bills in the next 30 days

## jana-1: acceptable

- kind: Young professional starting out with negative cash flow
- question: Will my money last until the next salary arrives?
- 6.9 s, apertus-v1-5-70b

**Will my money last until the next salary?**

- What is left after all bills are paid (income_and_spending): 250.82
- Loan repayment to Andrea Widmer (regular_payments): 150.00
- Savings progress toward emergency fund (savings_goal): 4'919.20
- Bill from Steuerverwaltung des Kantons Bern (bill): 1'180.00
- Due in the next 30 days (due_soon): 3'155.45
- Pillar 3a, 2026 (pillar_3a): 3'658.00

- service titles_checked: default title for: Upcoming tax bill due 30 November; Bills due in the next 30 days; Pillar 3a retirement savings gap

## jana-2: acceptable

- kind: Young professional starting out with negative cash flow
- question: Will my money last until the next salary arrives?
- 5.1 s, apertus-v1-5-70b

**Will my money last until the next salary?**

- What is left after all bills are paid (income_and_spending): 250.82
- Loan repayment to Andrea Widmer (regular_payments): 150.00
- Savings progress toward emergency fund (savings_goal): 4'919.20
- Bill from Steuerverwaltung des Kantons Bern (bill): 1'180.00
- Due in the next 30 days (due_soon): 3'155.45
- Pillar 3a, 2026 (pillar_3a): 3'658.00

- service titles_checked: default title for: Upcoming tax bill due 30 November; Bills due in the next 30 days; Pillar 3a retirement savings gap

## jana-3: acceptable

- kind: Young professional starting out with negative cash flow
- question: Will my money last until the next salary arrives?
- 5.2 s, apertus-v1-5-70b

**Will my money last until the next salary?**

- What is left after all bills are paid (income_and_spending): 250.82
- Savings progress toward emergency fund (savings_goal): 4'919.20
- Bill from Steuerverwaltung des Kantons Bern (bill): 1'180.00
- Due in the next 30 days (due_soon): 3'155.45
- Pillar 3a, 2026 (pillar_3a): 3'658.00

- service tiles_resolved: 5 of 6 resolved; dropped: Loan repayment to Andrea Widmer
- service titles_checked: default title for: Upcoming tax bill due 30 November; Bills due in the next 30 days; Pillar 3a retirement savings gap

## daniela-1: acceptable

- kind: single mother with tight month-to-month cash flow
- question: Will the money last until the next salary arrives?
- 7.2 s, apertus-v1-5-70b

**Will the money last until the next salary?**

- What's left the day before the salary (payday_balance): 124.96
- Savings pots overview (account_balances): 3'754.75
- Bills due before next salary (bills_until_payday): 2'950.20
- Late expected transfer from Patrick Rüegg (expected_income): 1'050.00
- Upcoming dentist bill for Lina (bill): 440.00

- service tiles_resolved: 5 of 7 resolved; dropped: Separate savings accounts; Notgroschen progress

## daniela-2: acceptable

- kind: single mother with tight month-to-month cash flow
- question: Will the money last until the next salary arrives?
- 6.0 s, apertus-v1-5-70b

**Will the money last until the next salary?**

- What's left the day before the salary (payday_balance): 124.96
- Savings pots overview (account_balances): 3'754.75
- Bills due before next salary (bills_until_payday): 2'950.20
- Late expected transfer from Patrick Rüegg (expected_income): 1'050.00
- Upcoming dentist bill for Lina (bill): 440.00

- service tiles_resolved: 5 of 7 resolved; dropped: Separate savings accounts; Notgroschen progress

## daniela-3: acceptable

- kind: single mother with tight month-to-month cash flow
- question: Will the money last until the next salary arrives?
- 5.8 s, apertus-v1-5-70b

**Will the money last until the next salary?**

- What's left the day before the salary (payday_balance): 124.96
- Savings pots overview (account_balances): 3'754.75
- Bills due before next salary (bills_until_payday): 2'950.20
- Late expected transfer from Patrick Rüegg (expected_income): 1'050.00
- Upcoming dentist bill for Lina (bill): 440.00

- service tiles_resolved: 5 of 7 resolved; dropped: Separate savings accounts; Notgroschen progress

## marco-1: acceptable

- kind: A family carrying a house with a major financial decision ahead
- question: What should we do with the maturing mortgage tranche and how do we keep the house secure?
- 6.7 s, apertus-v1-5-70b

**Mortgage Maturity Decision**

- Mortgage (mortgage): 862'500.00
- Regular family support from Simone (expected_income): 2'600.00
- Savings pots for house and family (account_balances): 83'484.90
- Monthly cash flow trend (income_and_spending): -246.13
- Due in the next 30 days (due_soon): 6'566.00

- service tiles_resolved: 5 of 7 resolved; dropped: Current balances of savings accounts; Monthly salary and support schedule
- service titles_checked: default title for: The mortgage that matures in March 2027; Upcoming bills in the next 30 days

## marco-2: acceptable

- kind: A family with a house and children who must decide on their mortgage renewal
- question: What should we do with the mortgage tranche that expires in March 2027?
- 6.3 s, apertus-v1-5-70b

**Mortgage Renewal Decision**

- Mortgage (mortgage): 862'500.00
- Regular family support from Simone (expected_income): 2'600.00
- Savings pots for house and family (account_balances): 83'484.90
- Monthly cash flow trend (income_and_spending): -246.13
- Upcoming bills in the next month (due_soon): 6'566.00

- service tiles_resolved: 5 of 7 resolved; dropped: Current balances of savings accounts; Pillar 3a account balance
- service titles_checked: default title for: The mortgage that matures in March 2027

## marco-3: acceptable

- kind: A family with a house and children who must decide on their mortgage renewal
- question: What should we do with the mortgage tranche that expires in March 2027?
- 5.6 s, apertus-v1-5-70b

**Mortgage Renewal Decision**

- Mortgage (mortgage): 862'500.00
- Regular household support from Simone (expected_income): 2'600.00
- Savings pots for house and family (account_balances): 83'484.90
- Monthly cash flow trend (income_and_spending): -246.13
- Due in the next 30 days (due_soon): 6'566.00

- service tiles_resolved: 5 of 7 resolved; dropped: Current balances of savings accounts; Monthly salary and partner support
- service titles_checked: default title for: The mortgage that matures in March 2027; Upcoming bills in the next 30 days

