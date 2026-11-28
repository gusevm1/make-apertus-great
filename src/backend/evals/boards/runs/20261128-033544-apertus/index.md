# Boards gate, apertus

2 of 8 acceptable.

- lukas: 0 of 2
- jana: 0 of 2
- daniela: 1 of 2
- marco: 1 of 2

OpenRouter: 16 calls sent, 0 from cache, 54308 tokens in, 82212 out, about $0.1189

## lukas-1-r1: NOT acceptable

Asked: We want to go to Japan in 2027. Keep an eye on that for me.

- kind: A young professional building wealth with a large investment portfolio and multiple savings pots.
- question: We want to go to Japan in 2027. Keep an eye on that for me.
- 10.0 s, apertus-v1-5-70b

**Japan 2027**

- Bills due soon (due_soon): 8'302.59
- Japan savings goal (savings_goal): 37'566.29
- Regular payments (regular_payments): 3'742.85

- judge hero_question: The request was to keep an eye on the Japan 2027 trip, but the hero is a generic 30-day bills-due list, while the tile that actually answers the request — the Japan savings goal — is pushed to second place.
- judge about_customer: Only the savings-goal tile is about the Japan request; the 'Bills due soon' and 'Regular payments' tiles are strong but off-topic signals about everyday outflows, which the request-run rubric explicitly says do not belong.
- judge coherent: A board named 'Japan 2027' in which two of the three tiles are ordinary upcoming-bills widgets does not tell one story about the requested goal, and the off-topic tiles look like filler added to reach a tile count.
- service tiles_resolved: 3 of 4 resolved; dropped: Japan savings pot
- service titles_checked: default title for: Monthly bills until payday

## lukas-1-r2: NOT acceptable

Asked: What do my subscriptions cost me?

- kind: A young professional building wealth with a large investment portfolio and multiple savings pots.
- question: What do my subscriptions cost me?
- 9.5 s, apertus-v1-5-70b

**Biggest monthly bills**

- Biggest monthly bills (regular_payments): 3'542.85

- tile_count: tiles per board: [1]
- judge hero_question: Lukas asked what his subscriptions cost, but the hero's CHF 3'542.85 headline is dominated by his CHF 2'800 rent and CHF 490 health insurance, so it answers 'what are my biggest bills' instead of the question he actually asked.
- judge about_customer: The payees are all genuinely Lukas's, but rent and health insurance are strong signals that are not about the subscription request and yet take the top two rows of the tile.
- judge coherent: The board tells one story, but it is the story of his largest recurring bills rather than the requested subscriptions story, so it is not about the request.
- service titles_checked: default title for: Monthly subscriptions and bills

## jana-1-r1: NOT acceptable

Asked: How do I get my emergency fund to 10'000?

- kind: Young professional starting out with negative cash flow
- question: How do I get my emergency fund to 10'000?
- 7.3 s, apertus-v1-5-70b

**Emergency fund progress**

- Emergency fund (savings_goal): 4'919.20

- tile_count: tiles per board: [1]
- service tiles_resolved: 2 of 3 resolved; dropped: Big bills due soon; Savings pot balance

## jana-1-r2: NOT acceptable

Asked: When have I repaid my parents?

- kind: Young professional starting out with negative cash flow
- question: When have I repaid my parents?
- 6.5 s, apertus-v1-5-70b

**Repaying Parents**

- Loan to Andrea Widmer (regular_payments): 150.00

- tile_count: tiles per board: [1]
- judge hero_question: The hero shows only the next CHF 150 instalment due 28 December 2026, which says nothing about when the loan from her parents will actually be paid off, so it does not answer 'When have I repaid my parents?'.
- judge titles: 'Loan to Andrea Widmer' reads as a loan Jana gave to her mother rather than the repayment she is making on the loan from her parents, and it does not match a tile showing a recurring payment and next due date.
- service tiles_resolved: 1 of 2 resolved; dropped: Loan to Andrea Widmer

## daniela-1-r1: NOT acceptable

Asked: What does Lina cost me every month?

- kind: single mother with tight month-to-month cash flow
- question: What does Lina cost me every month?
- 7.4 s, apertus-v1-5-70b

**Lina's monthly costs**

- Bills due before payday (bills_until_payday): 2'950.20
- Dentist bill due (bill): 440.00
- Shops in November (merchant_spending): 1'092.35

- judge hero_question: The hero lists every bill due before payday (rent, mobile, internet, washing-machine instalment) totalling CHF 2'950.20, which answers whether her money lasts to payday, not what Lina costs her every month.
- judge about_customer: Only the dentist bill is a Lina cost; the payday-bills tile and the household grocery tile are strong signals about her general budget that do not belong on a board made for the request about Lina's costs.
- judge coherent: Despite its name, the board tells the 'will my money last until payday' story with a grocery aside and never isolates or totals Lina's monthly costs, so it is not about the request and nothing else.
- service titles_checked: default title for: Groceries and food shops monthly spend

## daniela-1-r2: acceptable

Asked: Which bills and reminders are open?

- kind: single mother with tight month-to-month cash flow
- question: Which bills and reminders are open?
- 7.5 s, apertus-v1-5-70b

**bill reminder**

- bill reminder (bill): 440.00
- Bills before next payday (bills_until_payday): 2'950.20

- service tiles_resolved: 2 of 4 resolved; dropped: Dentist bill for Lina due soon; Bills due in next 30 days

## marco-1-r1: NOT acceptable

Asked: What does the house cost us?

- kind: Family carrying a house with a decision ahead
- question: What does the house cost us?
- 6.6 s, apertus-v1-5-70b

**Savings pots**

- Savings pots (account_balances): 83'484.90
- House reserve (savings_goal): 19'350.30

- judge hero_question: The hero shows the balances of the house and family savings accounts, which answers how much the Baumanns have saved, not what the house costs them in interest, amortisation and maintenance as the request asks.
- judge about_customer: Both tiles draw on Marco's real accounts, but neither is about the cost of the house, and the family savings pot (holidays, reserves, children) belongs to a different question entirely.
- judge coherent: The board tells one coherent savings-reserve story, but it is not about the request, and the data holds far more about the house's costs (quarterly interest, amortisation, the CHF 18'000 facade repair, insurance and fees), so the two-tile minimum does not save it.
- service tiles_resolved: 2 of 3 resolved; dropped: Savings pots for house and family

## marco-1-r2: acceptable

Asked: What should we decide about the mortgage?

- kind: Family carrying a house with a decision ahead
- question: What should we decide about the mortgage?
- 7.5 s, apertus-v1-5-70b

**Mortgage decision**

- Mortgage tranche expiry (mortgage): 862'500.00
- Your accounts (account_balances): 83'484.90

- service tiles_resolved: 2 of 3 resolved; dropped: Where savings are going
- service titles_checked: default title for: Savings pots for house and family

