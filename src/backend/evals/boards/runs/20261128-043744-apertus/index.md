# Boards gate, apertus

9 of 12 acceptable.

- lukas: 3 of 3
- jana: 1 of 3
- daniela: 3 of 3
- marco: 2 of 3

OpenRouter: 24 calls sent, 0 from cache, 106588 tokens in, 171736 out, about $0.2479

## lukas-1: acceptable

- kind: A young professional building wealth with a large investment portfolio and multiple savings pots.
- question: What is my total net worth and how should I allocate it between my goals and future growth?
- 16.1 s, apertus-v1-5-70b

**Overview**

- What you own (net_worth): 131'212.64
- Visa bill reminder (card_bill): 3'301.74
- Pillar 3a gap (pillar_3a): 58.00
- Investment depot value (securities): 72'512.96
- Bills due soon (due_soon): 8'302.59
- Savings accounts (account_balances): 48'983.35
- Japan fund on track (savings_goal): 37'566.29

Ideas: Big monthly bills; Partner's monthly support; Monthly cash flow

## lukas-2: acceptable

- kind: A young professional building wealth with a large investment portfolio and multiple savings pots.
- question: What is my total net worth and how should I allocate it between my goals and future growth?
- 16.0 s, apertus-v1-5-70b

**Overview**

- What you own (net_worth): 131'212.64
- Credit card bill due (card_bill): 3'301.74
- Pillar 3a gap (pillar_3a): 58.00
- Investment depot value (securities): 72'512.96
- Bills due soon (due_soon): 8'302.59
- Savings accounts (account_balances): 48'983.35
- Japan fund on track (savings_goal): 37'566.29

Ideas: Big monthly bills; Partner's monthly support; Monthly cash flow

## lukas-3: acceptable

- kind: A young professional building wealth with a large investment portfolio and multiple savings pots.
- question: What is my net worth today and how should I allocate it between my goals and future growth?
- 16.0 s, apertus-v1-5-70b

**Overview**

- What you own (net_worth): 131'212.64
- Credit card bill due (card_bill): 3'301.74
- Pillar 3a gap (pillar_3a): 58.00
- Investment depot value (securities): 72'512.96
- Bills due soon (due_soon): 8'302.59
- Savings accounts (account_balances): 48'983.35
- Japan fund on track (savings_goal): 37'566.29

Ideas: Big monthly bills; Partner's regular support; Monthly cash flow

## jana-1: NOT acceptable

- kind: Young professional starting out with negative cash flow
- question: Will my money last until the next payday and what do I need to cut to stay afloat?
- 14.1 s, apertus-v1-5-70b

**Every month**

- What is left at month end (income_and_spending): 250.82
- Emergency fund (savings_goal): 4'919.20
- Provisional tax bill (bill): 1'180.00
- bills (due_soon): 3'155.45
- Grocery spending (merchant_spending): 1'116.38

Ideas: Paying back a loan; Pillar 3a contributions; Fixed costs

- judge titles: Four titles read like a person wrote them and match their tiles, but the lowercase one-word 'bills' looks like a machine placeholder, breaks the title-case style of the board, and does not say what the tile actually shows (payments due in the next 30 days).
- service tiles_resolved: 6 of 7 resolved; dropped: Bills due soon
- service titles_checked: default title for: Loan repayment to Andrea Widmer

## jana-2: NOT acceptable

- kind: Young professional starting out with a negative monthly cash flow
- question: Will my money last until the next payday?
- 12.4 s, apertus-v1-5-70b

**Every month**

- What is left each month (income_and_spending): 250.82
- Loan repayment (regular_payments): 150.00
- Emergency fund (savings_goal): 4'919.20
- Tax bill due (bill): 1'180.00
- bills (due_soon): 3'155.45

Ideas: Pillar 3a savings; Fixed costs; Where the money goes

- judge titles: While the other four titles read naturally, 'bills' is a lowercase one-word label that looks machine-generated rather than written by a person and does not say that the tile shows payments due in the next 30 days.
- service tiles_resolved: 5 of 7 resolved; dropped: Bills due soon; Bills until payday

## jana-3: acceptable

- kind: Young professional starting out with negative cash flow
- question: Will my money last until the next payday and what do I need to cut to stay afloat?
- 10.6 s, apertus-v1-5-70b

**Every month**

- What is left at month end (income_and_spending): 250.82
- Emergency fund (savings_goal): 4'919.20
- Tax bill due (bill): 1'180.00
- bills (due_soon): 3'155.45
- Regular payments (regular_payments): 150.00

Ideas: Pillar 3a savings; Fixed costs; Where the money goes

- service tiles_resolved: 4 of 5 resolved; dropped: Bills due soon
- service boards_full: Until payday: 1 added

## daniela-1: acceptable

- kind: single mother with tight month-to-month cash flow
- question: Will the money last until the next salary arrives?
- 14.2 s, apertus-v1-5-70b

**Until payday**

- What is left before payday (payday_balance): 124.96
- Child support (expected_income): 1'050.00
- Dentist bill due (bill): 440.00
- Emergency fund (savings_goal): 284.25
- Bills until payday (bills_until_payday): 2'950.20
- In and out (income_and_spending): -370.77
- Where the money goes (merchant_spending): 1'312.35

Ideas: Fixed costs; Instalments; Savings pots

## daniela-2: acceptable

- kind: single mother with tight month-to-month cash flow
- question: Will there be enough money on the Privatkonto the day before the next salary arrives?
- 10.4 s, apertus-v1-5-70b

**Until payday**

- What's left before payday (payday_balance): 124.96
- Child support pending (expected_income): 1'050.00
- Dentist bill due (bill): 440.00
- Emergency fund (savings_goal): 284.25
- Bills until payday (bills_until_payday): 2'950.20
- In and out (income_and_spending): -370.77
- Savings pots (account_balances): 3'754.75

Ideas: Fixed costs; Instalments; Bills due soon

## daniela-3: acceptable

- kind: single mother with tight month-to-month cash flow
- question: Will there be enough money on the Privatkonto the day before the next salary arrives?
- 13.1 s, apertus-v1-5-70b

**Until payday**

- What's left before payday (payday_balance): 124.96
- Child support pending (expected_income): 1'050.00
- Dentist bill due (bill): 440.00
- Emergency fund (savings_goal): 284.25
- Bills until payday (bills_until_payday): 2'950.20
- Monthly cash flow (income_and_spending): -370.77

Ideas: Fixed costs; Instalments; Savings pots

- service tiles_resolved: 8 of 9 resolved; dropped: Dentist bill due soon; Fixed monthly bills

## marco-1: acceptable

- kind: Family carrying a house with a decision ahead
- question: What should we do about the mortgage tranche that matures in March 2027?
- 13.2 s, apertus-v1-5-70b

**Mortgage decision**

- The mortgage (mortgage): 862'500.00
- Pillar 3a (pillar_3a): 58.00
- House reserve nearly met (savings_goal): 19'350.30
- Car instalments left (regular_payments): 489.00
- Bills due soon (due_soon): 6'566.00
- Monthly cash shortfall (income_and_spending): -246.13
- Savings pots (account_balances): 83'484.90

Ideas: Fixed costs; Regular income from Simone; Where the money goes

- service tiles_resolved: 8 of 10 resolved; dropped: Regular income from Simone; Upcoming bills; Savings pots

## marco-2: NOT acceptable

- kind: family carrying a house with a decision ahead
- question: What should we do with the maturing mortgage tranche before December 15th?
- 14.7 s, apertus-v1-5-70b

**The house**

- The mortgage (mortgage): 862'500.00
- Pillar 3a (pillar_3a): 58.00
- House reserve nearly met (savings_goal): 19'350.30
- Car loan instalments (regular_payments): 489.00
- Bills due soon (due_soon): 6'566.00
- Monthly cash shortfall (income_and_spending): -246.13
- Savings pots (account_balances): 83'484.90

Ideas: Fixed costs; Regular income; Where the money goes

- judge titles: "Car loan instalments" mislabels his external car lease as a loan — the persona and the payee "Seeblick Auto-Leasing AG" say it is a lease that does not appear under Loans — so one title neither uses the customer's terms nor matches what the tile shows.
- service tiles_resolved: 8 of 10 resolved; dropped: Regular income; Savings pots; Car instalments

## marco-3: acceptable

- kind: family carrying a house with a decision ahead
- question: What should we do about the mortgage tranche that matures in March 2027?
- 13.2 s, apertus-v1-5-70b

**Mortgage decision**

- The mortgage (mortgage): 862'500.00
- Pillar 3a (pillar_3a): 58.00
- House reserve nearly met (savings_goal): 19'350.30
- Car instalments left (regular_payments): 489.00
- Bills due soon (due_soon): 6'566.00
- Monthly cash shortfall (income_and_spending): -246.13
- Savings pots (account_balances): 83'484.90

Ideas: Fixed costs; Regular income from Simone; Where the money goes

- service tiles_resolved: 8 of 10 resolved; dropped: Regular income from Simone; Upcoming bills; Savings pots

