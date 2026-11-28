# Boards gate, apertus

3 of 8 acceptable.

- lukas: 0 of 2
- jana: 2 of 2
- daniela: 1 of 2
- marco: 0 of 2

OpenRouter: 16 calls sent, 0 from cache, 57854 tokens in, 144424 out, about $0.2062

## lukas-1-r1: NOT acceptable

Asked: We want to go to Japan in 2027. Keep an eye on that for me.

- kind: 
- question: We want to go to Japan in 2027. Keep an eye on that for me.
- 28.8 s, server

**Sparkonto Langfristig**

- Sparkonto Langfristig (savings_goal): 37'566.29
- Regular payments (regular_payments): 5'067.65

- judge about_customer: The regular-payments tile lists his real upcoming bills (rent, gym, mobile, health insurance), but none of it is about the Japan 2027 request, so this off-topic strong signal does not belong on the board.
- judge coherent: The board pairs the Japan savings goal with an unrelated list of everyday upcoming bills, so it does not tell one story that is only about the request.
- service tiles_resolved: 4 of 5 resolved; dropped: Sparkonto Langfristig; Bill, due 10.12.; Bill, due 23.12.
- service titles_checked: default title for: Bill, due 10.12.; Bill, due 23.12.
- service planned_by_model: The model did not answer in time; this board holds what your request names word for word.

## lukas-1-r2: NOT acceptable

Asked: What do my subscriptions cost me?

- kind: 
- question: What do my subscriptions cost me?
- 3.2 s, apertus-v1-5-70b

**Subscriptions**


- judge hero_question: There is no first tile at all, and since Lukas's accounts hold monthly streaming, news and gym subscription payments, the request was directly answerable, so an empty board with a 'nothing yet' line does not answer it.
- judge about_customer: The board's only content asserts that nothing in Lukas's accounts is about subscriptions, which is false for this customer, whose bookings include recurring streaming, news and gym subscription costs every month.
- judge not_empty_or_repeated: The board is entirely empty and pointless even though the data holds plenty about subscription costs, which is the extreme case of an empty tile.
- judge coherent: The board's single message — that the accounts say nothing about subscriptions — tells a false story for a customer whose monthly subscriptions are plainly visible in his data.

## jana-1-r1: acceptable

Asked: How do I get my emergency fund to 10'000?

- kind: 
- question: How do I get my emergency fund to 10'000?
- 28.6 s, server

**Sparkonto**

- Sparkonto (savings_goal): 4'919.20
- Regular payments (regular_payments): 250.00

- service tiles_resolved: 2 of 3 resolved; dropped: Sparkonto
- service planned_by_model: The model did not answer in time; this board holds what your request names word for word.

## jana-1-r2: acceptable

Asked: When have I repaid my parents?

- kind: 
- question: When have I repaid my parents?
- 5.1 s, apertus-v1-5-70b

**Parents' loan**

- Regular payments (regular_payments): 150.00
- Repaid each month (monthly_spending): 125.00

- service tiles_resolved: 2 of 3 resolved; dropped: Parents' loan

## daniela-1-r1: NOT acceptable

Asked: What does Lina cost me every month?

- kind: 
- question: What does Lina cost me every month?
- 3.1 s, apertus-v1-5-70b

**Lina**

- Where the money goes (monthly_spending): 312.18
- Lina (regular_payments): 729.60

- judge hero_question: The hero's CHF 312 a month is dominated by the flat 271.40 Assura payment that appears every single month — Daniela's own health insurance, which the persona calls "my health insurance" and which rises to 289.60 exactly as she says it does every year — so the figure is not Lina's monthly cost and the generic title "Where the money goes" never presents it as one.
- judge about_customer: Both tiles are anchored on Assura-Basis, the customer's own health insurance and a strong recurring signal that is not about what Lina costs, while only the swim school, pediatrician and dentist rows genuinely serve the request.
- judge titles: "Where the money goes" is generic phrasing that uses none of the customer's words — no Lina, no cost, no month — on the tile that must answer her question, and "Lina" is a bare label that does not say the tile lists two upcoming bills.
- judge coherent: Because the mother's own insurance premium dominates both tiles, the board tells two stories at once — Lina's costs and Daniela's health-insurance bills — instead of being about the request and nothing else.
- service tiles_resolved: 4 of 5 resolved; dropped: Bill, due 30.11.; Bill, due 30.11.; Bill, due 23.12.
- service titles_checked: default title for: Lina's monthly costs (December/January 2026/27): CHF 1'555.20 per month (incl. dentist bill); Bill, due 30.11.; Bill, due 23.12.

## daniela-1-r2: acceptable

Asked: Which bills and reminders are open?

- kind: 
- question: Which bills and reminders are open?
- 1.5 s, apertus-v1-5-70b

**Open bills**

- Bill, due 30.11. (bill): 440.00
- Bill, due 10.12. (bill): 348.00
- Bills until payday (bills_until_payday): 2'950.20

- service titles_checked: default title for: Bill, due 30.11.; Bill, due 10.12.

## marco-1-r1: NOT acceptable

Asked: What does the house cost us?

- kind: 
- question: What does the house cost us?
- 4.7 s, apertus-v1-5-70b

**The house**

- Where the money goes (monthly_spending): 1'120.83
- The house (regular_payments): 2'581.40
- Mortgage (mortgage): 862'500.00
- Sparkonto Haus (savings_goal): 19'350.30

- judge hero_question: The hero charts only the payments to the bank — mortgage interest and amortisation averaging about CHF 1'121 a month — under the generic title 'Where the money goes', so it answers what the mortgage costs rather than what the house costs, which the persona defines as the yearly total including maintenance, insurance and the house account.
- judge titles: The hero title 'Where the money goes' uses none of Marco's terms and does not say the tile shows the mortgage cost, and 'The house' merely repeats the board name over a list of upcoming payments, so the titles do not match what the tiles show.
- service titles_checked: default title for: Monthly house costs (utilities, insurance, taxes, etc.) per month approx. CHF 2'500–3'000 (based on recent bills and standing orders). See breakdown below for actual amounts due soon and last year's spending pattern for comparison.; Bill, due 15.01.

## marco-1-r2: NOT acceptable

Asked: What should we decide about the mortgage?

- kind: 
- question: What should we decide about the mortgage?
- 28.2 s, server

**Mortgage**

- Mortgage (mortgage): 862'500.00
- Each month (monthly_spending): 1'120.83
- Regular payments (regular_payments): 1'050.00
- Your accounts (account_balances): 18'338.26

- judge about_customer: The first three tiles are about the mortgage, but 'Your accounts' shows only the private account balance, which says nothing about the mortgage decision (the savings that could pay down the tranche sit in the «House», «Family» and 3a accounts, none of which appear), so it reads as filler on a request board.
- judge titles: 'Each month' names no content and mislabels what are actually quarterly interest charges, and 'Your accounts' is plural for a tile that lists a single account.
- judge not_empty_or_repeated: 'Each month' and 'Regular payments' are both filtered to ti&m Demo Bank AG, so two of the four tiles repeat the same bank-payment stream, the second adding only one thin row whose 31.12.2026 due date the hero already shows.
- judge coherent: Tiles 1–3 tell a mortgage status-and-cost story that never frames the pending decision (no deadline, no options, no pay-down funds), and the private-account balance at the end belongs to a different story, so the board is not about the request and nothing else.
- service planned_by_model: The model did not answer in time; this board holds what your request names word for word.

