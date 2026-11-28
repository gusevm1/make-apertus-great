# Boards gate, apertus

1 of 8 acceptable.

- lukas: 0 of 2
- jana: 1 of 2
- daniela: 0 of 2
- marco: 0 of 2

OpenRouter: 16 calls sent, 0 from cache, 64132 tokens in, 61575 out, about $0.0907

## lukas-1-r1: NOT acceptable

Asked: We want to go to Japan in 2027. Keep an eye on that for me.

- kind: A young professional building wealth with a large investment portfolio and multiple savings pots.
- question: We want to go to Japan in 2027. Keep an eye on that for me.
- 9.7 s, apertus-v1-5-70b

**Japan 2027**

- Japan savings pot (account_balances): 37'566.29
- net worth (net_worth): 131'212.64
- Pillar 3a (pillar_3a): 58.00
- Securities value (securities): 72'512.96
- Bills due soon (due_soon): 8'302.59

- judge about_customer: Tiles 2 through 5 (net worth, pillar 3a, securities, bills due) are strong signals about Lukas's general wealth but none is about the Japan trip request, and the rubric says such off-request signals do not belong on a request board.
- judge coherent: Instead of telling one story about the Japan goal, the board mixes that savings pot with an unrelated wealth, pension, portfolio and bills overview, so it is not about the request and nothing else.
- service tiles_resolved: 10 of 11 resolved; dropped: Savings accounts; Japan savings goal; Monthly cash flow; Monthly fixed costs; Partner's regular transfer; Upcoming bills before payday

## lukas-1-r2: NOT acceptable

Asked: What do my subscriptions cost me?

- kind: A young professional building wealth with a large investment portfolio and multiple savings pots.
- question: What do my subscriptions cost me?
- 9.4 s, apertus-v1-5-70b

**Biggest monthly bills**

- Biggest monthly bills (regular_payments): 3'542.85
- Bills due soon (due_soon): 8'302.59
- Monthly cash flow (income_and_spending): -199.61
- Partner's regular transfer (expected_income): 2'200.00

- judge hero_question: The customer asked what his subscriptions cost, but the hero lists the biggest monthly bills led by rent (CHF 2'800) and health insurance, which are not subscriptions, and never totals or isolates his subscription costs.
- judge about_customer: Only three rows of the first tile (gym, Swisscom, Salt) are subscriptions, while the due-soon list, the six-month cash flow and Sara's transfer are strong signals that have nothing to do with the subscription request.
- judge coherent: The board tells a general monthly-bills and cash-flow story rather than being about the request, so as a whole it does not answer what his subscriptions cost him.
- service titles_checked: default title for: Monthly subscriptions and bills

## jana-1-r1: acceptable

Asked: How do I get my emergency fund to 10'000?

- kind: Young professional starting out with negative cash flow
- question: How do I get my emergency fund to 10'000?
- 7.3 s, apertus-v1-5-70b

**Emergency fund progress**

- Emergency fund (savings_goal): 4'919.20
- Loan to Andrea Widmer (regular_payments): 150.00
- Money in vs out (income_and_spending): 250.82
- Tax bill due (bill): 1'180.00
- Bills due soon (due_soon): 3'155.45

- service tiles_resolved: 6 of 7 resolved; dropped: Savings pot balance; Big bills due soon

## jana-1-r2: NOT acceptable

Asked: When have I repaid my parents?

- kind: Young professional starting out with negative cash flow
- question: When have I repaid my parents?
- 6.5 s, apertus-v1-5-70b

**Repaying Parents**

- Loan to Andrea Widmer (regular_payments): 150.00
- Monthly Balance (income_and_spending): 250.82
- Emergency Fund (savings_goal): 4'919.20
- Tax Bill (bill): 1'180.00
- Bills Due Soon (due_soon): 3'155.45

- judge hero_question: The hero only shows the monthly CHF 150 transfer to Andrea Widmer with its next due date, not how much is still owed or when the loan will finally be repaid, so it does not answer "when".
- judge about_customer: Only the first tile is about repaying her parents; the monthly balance, emergency fund, tax bill and upcoming bills are real for Jana but are strong signals that do not belong on a board made for this request.
- judge coherent: The board tells a general monthly-money story (spending, savings, taxes, due bills) with only one tile about the parents' loan, so it is not about the request and nothing else.
- service tiles_resolved: 5 of 6 resolved; dropped: Loan to Andrea Widmer

## daniela-1-r1: NOT acceptable

Asked: What does Lina cost me every month?

- kind: single mother with tight month-to-month cash flow
- question: What does Lina cost me every month?
- 6.6 s, apertus-v1-5-70b

**Lina's monthly costs**

- Bills due before next salary (bills_until_payday): 2'950.20
- Left before payday (payday_balance): 124.96
- Pending support from Patrick (expected_income): 1'050.00
- Dentist bill due soon (bill): 440.00
- Emergency fund (savings_goal): 284.25

- judge hero_question: The hero is a generic list of all bills due before payday (rent, internet, mobile included), which does not answer what Lina costs Daniela each month.
- judge about_customer: Only the dentist bill (Lina's treatment) is about the request; the payday balance, pending child support and emergency fund tiles are real signals for Daniela but not about Lina's monthly costs, so they do not belong on this request board.
- judge coherent: Despite the board name "Lina's monthly costs", the tiles tell her general month story (bills, leftover, support, buffer) rather than being about the request and nothing else.
- service titles_checked: default title for: Money left before next payday

## daniela-1-r2: NOT acceptable

Asked: Which bills and reminders are open?

- kind: single mother with tight month-to-month cash flow
- question: Which bills and reminders are open?
- 5.4 s, apertus-v1-5-70b

**bill**

- bill (bill): 440.00
- Payday balance (payday_balance): 124.96
- income (expected_income): 1'050.00
- Bills due before payday (bills_until_payday): 2'950.20
- Monthly cash flow (income_and_spending): -370.77

- judge about_customer: The monthly cash-flow tile (six months of history) and the child-support income tile are strong signals about Daniela's tight budget but are not about which bills and reminders are open, so they do not belong on this request board.
- judge titles: "bill" and "income" are bare generic labels rather than titles a person wrote in her terms — the dentist's second reminder and Lina's late child support go unnamed.
- judge coherent: The board is meant to be about the open bills and reminders and nothing else, yet the six-month cash-flow history (and to a lesser degree the child-support status) pulls it off into Daniela's general budget story.
- service tiles_resolved: 5 of 6 resolved; dropped: Dentist bill due soon

## marco-1-r1: NOT acceptable

Asked: What does the house cost us?

- kind: Family carrying a house with a decision ahead
- question: What does the house cost us?
- 7.5 s, apertus-v1-5-70b

**The house**

- Your accounts (account_balances): 83'484.90
- Mortgage (mortgage): 862'500.00
- Pillar 3a contributions (pillar_3a): 58.00
- House reserve nearly met (savings_goal): 19'350.30
- Car lease instalments (regular_payments): 489.00

- judge hero_question: The hero shows savings-account balances, which says nothing about what the house costs; the direct answer to the request would be the annual cost of interest, amortisation and maintenance.
- judge about_customer: The Pillar 3a and car-lease tiles are real data from Marco's life but are not about the house's cost, and a request board must leave such off-request signals off.
- judge coherent: The board mixes the house theme (accounts, mortgage, reserve) with retirement saving and the car lease, so it is not about the request and nothing else.
- service tiles_resolved: 8 of 10 resolved; dropped: Bills due soon; Monthly cash flow; Regular partner contribution; Savings pots for house and family; House reserve fund
- service titles_checked: default title for: Savings pots for house and family; Mortgage tranche maturing in March 2027

## marco-1-r2: NOT acceptable

Asked: What should we decide about the mortgage?

- kind: Family carrying a house with a decision ahead
- question: What should we decide about the mortgage?
- 7.0 s, apertus-v1-5-70b

**Mortgage decision**

- Mortgage tranche expiry (mortgage): 862'500.00
- Pillar 3a contributions (pillar_3a): 58.00
- House reserve (savings_goal): 19'350.30
- Car instalments (regular_payments): 489.00
- Bills due soon (due_soon): 6'566.00

- judge about_customer: The pillar 3a contribution top-up, the car lease instalments and the generic bills-due list are real parts of Marco's life but not about the mortgage decision he asked about, and the rubric says a strong signal off the request does not belong on a request board.
- judge titles: The titles are short and free of filler words and each matches its tile's content, though only marginally, because the words are plain and use the customer's own terms such as tranche expiry, house reserve and instalments.
- judge coherent: After the mortgage tile the board wanders into retirement saving, the car lease and everyday bills, so it does not tell the one story of the mortgage decision the request asks for.
- service tiles_resolved: 9 of 10 resolved; dropped: Monthly cash flow; Savings accounts; Regular partner contribution; Savings pots for house and family; House reserve and family savings

