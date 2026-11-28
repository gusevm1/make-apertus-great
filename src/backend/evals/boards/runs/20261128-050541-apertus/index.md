# Boards gate, apertus

3 of 8 acceptable.

- lukas: 0 of 2
- jana: 2 of 2
- daniela: 0 of 2
- marco: 1 of 2

OpenRouter: 16 calls sent, 0 from cache, 56104 tokens in, 123170 out, about $0.1764

## lukas-1-r1: NOT acceptable

Asked: We want to go to Japan in 2027. Keep an eye on that for me.

- kind: 
- question: We want to go to Japan in 2027. Keep an eye on that for me.
- 28.7 s, server

**Sparkonto Langfristig**

- Sparkonto Langfristig (savings_goal): 37'566.29
- Regular payments (regular_payments): 4'567.65

- judge about_customer: The second tile lists generic upcoming regular payments (rent, gym, mobile, insurance) that are a strong signal but have nothing to do with the Japan-trip request, and the rubric says such off-request signals do not belong.
- judge coherent: The board is supposed to be about the Japan request and nothing else, but the regular-payments tile is an unrelated bills list that breaks the story.
- service tiles_resolved: 4 of 5 resolved; dropped: Sparkonto Langfristig; Bill, due 10.12.; Bill, due 23.12.
- service titles_checked: default title for: Bill, due 10.12.; Bill, due 23.12.
- service planned_by_model: The model did not answer in time; this board holds what your request names word for word.

## lukas-1-r2: NOT acceptable

Asked: What do my subscriptions cost me?

- kind: 
- question: What do my subscriptions cost me?
- 28.7 s, server

**Regular payments**

- Regular payments (regular_payments): 39.95

- tile_count: tiles per board: [1]
- judge hero_question: The request asks what his subscriptions cost in total, but the hero shows a single upcoming payment to Salt Mobile (CHF 39.95) rather than the cost of his subscriptions.
- judge coherent: A single payee's payment is a fragment, not a story: the data clearly holds far more about the request (gym, streaming, news, internet subscriptions), so the board fails to answer or even sketch the subscription picture.
- service planned_by_model: The model did not answer in time; this board holds what your request names word for word.

## jana-1-r1: acceptable

Asked: How do I get my emergency fund to 10'000?

- kind: 
- question: How do I get my emergency fund to 10'000?
- 28.6 s, server

**Sparkonto**

- Sparkonto (savings_goal): 4'919.20

- service tiles_resolved: 1 of 2 resolved; dropped: Sparkonto
- service planned_by_model: The model did not answer in time; this board holds what your request names word for word.

## jana-1-r2: acceptable

Asked: When have I repaid my parents?

- kind: 
- question: When have I repaid my parents?
- 28.5 s, server

**Regular payments**

- Regular payments (regular_payments): 150.00
- Repaid each month (monthly_spending): 125.00

- service tiles_resolved: 2 of 3 resolved; dropped: Regular payments
- service planned_by_model: The model did not answer in time; this board holds what your request names word for word.

## daniela-1-r1: NOT acceptable

Asked: What does Lina cost me every month?

- kind: 
- question: What does Lina cost me every month?
- 28.2 s, server

**Bill, due 30.11.**

- Bill, due 30.11. (bill): 440.00
- Each month (monthly_spending): 41.84
- Bill, due 23.12. (bill): 289.60

- judge hero_question: The hero is the one-off dentist bill of CHF 440 due 30.11, which says nothing about what Lina costs every month; the only tile that speaks to the request, the CHF 41.84 monthly child-related spending, sits buried in second place.
- judge about_customer: The dentist reminder is this month's strong signal but a one-off bill, and the Assura premium is a shared Daniela-and-Lina bill, so neither tile is about the recurring monthly cost of Lina that the request asks about, and the reminder does not belong on this request board.
- judge titles: The titles are boilerplate due-date labels plus a content-free 'Each month', and on a board answering a question about Lina none of them uses the customer's terms or says what each figure means for Lina.
- judge coherent: Named 'Bill, due 30.11.' and built around two upcoming bills with one spending statistic attached, the board tells a bills-due story rather than the one story the request asks for, what Lina costs each month.
- service tiles_resolved: 4 of 5 resolved; dropped: Bill, due 30.11.; Regular payments
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 23.12.
- service planned_by_model: The model did not answer in time; this board holds what your request names word for word.

## daniela-1-r2: NOT acceptable

Asked: Which bills and reminders are open?

- kind: 
- question: Which bills and reminders are open?
- 28.2 s, server

**Bill, due 30.11.**

- Bill, due 30.11. (bill): 440.00
- Each month (monthly_spending): 351.00

- judge about_customer: The second tile, a twelve-month history of school-care and swim-school spending, is a real signal about Daniela's life but has nothing to do with open bills or reminders, while the data holds more request-relevant items (such as the rent due in the next days) that belong instead.
- judge coherent: The board jumps from the open dentist bill to an unrelated childcare spending trend, so it is not about the request and nothing else.
- service tiles_resolved: 3 of 4 resolved; dropped: Bill, due 30.11.; Regular payments
- service titles_checked: default title for: Bill, due 30.11.
- service planned_by_model: The model did not answer in time; this board holds what your request names word for word.

## marco-1-r1: NOT acceptable

Asked: What does the house cost us?

- kind: 
- question: What does the house cost us?
- 28.2 s, server

**Mortgage**

- Mortgage (mortgage): 862'500.00
- Sparkonto Haus (savings_goal): 19'350.30
- Regular payments (regular_payments): 631.40

- judge hero_question: The hero shows the mortgage balance and tranche maturities — what Marco owes and when the 8-year tranche matures — while the request asks what the house costs per year, which the data could answer directly with interest, amortisation and house-account spending.
- judge about_customer: The Sparkonto Haus savings-goal tile answers the persona's separate reserve-adequacy question (persona B7) rather than the cost request, so a strong signal that is not about the request sits on the board.
- judge coherent: The board sketches general house financing — the debt, a repair reserve and one insurance premium — but never answers what the house costs, and the reserve tile together with the 'Mortgage' framing pulls the board away from the request.
- service tiles_resolved: 3 of 4 resolved; dropped: Sparkonto Haus
- service planned_by_model: The model did not answer in time; this board holds what your request names word for word.

## marco-1-r2: acceptable

Asked: What should we decide about the mortgage?

- kind: 
- question: What should we decide about the mortgage?
- 28.2 s, server

**Mortgage**

- Mortgage (mortgage): 862'500.00
- Regular payments (regular_payments): 1'050.00

- service planned_by_model: The model did not answer in time; this board holds what your request names word for word.

