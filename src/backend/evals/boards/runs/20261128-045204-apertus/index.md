# Boards gate, apertus

2 of 12 acceptable.

- lukas: 1 of 3
- jana: 0 of 3
- daniela: 1 of 3
- marco: 0 of 3

OpenRouter: 24 calls sent, 0 from cache, 84583 tokens in, 188939 out, about $0.2704

## lukas-idea1: acceptable

Asked: Big monthly bills. The 5 largest monthly payments add up to 3'520.35 a month.

- kind: 
- question: Big monthly bills. The 5 largest monthly payments add up to 3'520.35 a month.
- 11.9 s, apertus-v1-5-70b

**Big monthly bills**

- Big monthly bills (regular_payments): 3'542.85

- service titles_checked: default title for: Bill, due 14.12.

## lukas-idea2: NOT acceptable

Asked: Partner's monthly support. Sara Keller sends about 2'200.00 every month, around day 27.

- kind: 
- question: Partner's monthly support. Sara Keller sends about 2'200.00 every month, around day 27.
- 6.0 s, apertus-v1-5-70b

**New board**

- Partner's monthly support (expected_income): 2'200.00
- Sparkonto Langfristig (savings_goal): 37'566.29

- judge about_customer: The second tile about the Japan savings goal is a strong real signal but has nothing to do with the request about Sara's monthly support, and the rubric says such a signal does not belong on a requested board.
- judge coherent: The board mixes the requested topic of Sara's transfer with an off-topic Japan savings tile, so it does not tell one story about the request alone.
- service tiles_resolved: 2 of 3 resolved; dropped: Sparkonto Langfristig

## lukas-idea3: NOT acceptable

Asked: Monthly cash flow. On average -199.61 was left per month over the last 6 months; in 2 months more went out than came in (2026-05, 2026-09).

- kind: 
- question: Monthly cash flow. On average -199.61 was left per month over the last 6 months; in 2 months more went out than came in (2026-05, 2026-09).
- 15.0 s, apertus-v1-5-70b

**Monthly cash flow**

- Monthly cash flow (income_and_spending): -199.61
- Monthly cash flow (regular_payments): 3'956.95

- judge about_customer: The second tile lists upcoming payments due in December and January, a strong signal about future bills that is not about the requested 6-month historical cash flow.
- judge titles: The second tile is titled 'Monthly cash flow' but actually shows a list of upcoming payments, so the title does not match what the tile shows and merely repeats the first tile's title.
- judge coherent: The board mixes the requested retrospective monthly cash flow with an unrelated forward-looking bills-due list, so it is not about the request and nothing else.
- service titles_checked: default title for: Bill, due 10.12.

## jana-idea1: NOT acceptable

Asked: Pillar 3a savings gap. Paid into pillar 3a in 2026: 3'300.00 of the maximum 7'258.00; after the standing orders 3'658.00 is missing.

- kind: 
- question: Pillar 3a savings gap. Paid into pillar 3a in 2026: 3'300.00 of the maximum 7'258.00; after the standing orders 3'658.00 is missing.
- 28.1 s, server

**New board**

- Pillar 3a savings gap (pillar_3a): 3'658.00

- tile_count: tiles per board: [1]
- service planned_by_model: The model did not answer in time; this board holds what your request names word for word.

## jana-idea2: NOT acceptable

Asked: Fixed costs. The 6 largest monthly payments add up to 2'103.25 a month.

- kind: 
- question: Fixed costs. The 6 largest monthly payments add up to 2'103.25 a month.
- 7.7 s, apertus-v1-5-70b

**Fixed costs**

- Fixed costs (regular_payments): 3'155.45

- judge hero_question: The hero sums the next occurrences of six upcoming payments to 3'155.45 — including a 1'180 cantonal tax bill that is not a monthly payment — instead of the six largest monthly payments totalling 2'103.25 named in the request, so it contradicts the request rather than answering it.
- service tiles_resolved: 4 of 5 resolved; dropped: Bill, due 30.11.; Bill, due 30.11.; Bill, due 14.12.; Due in 30 days
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 14.12.

## jana-idea3: NOT acceptable

Asked: Where the money goes. Spending averaged 5'511.93 a month over the last 6 months, highest in 2026-06.

- kind: 
- question: Where the money goes. Spending averaged 5'511.93 a month over the last 6 months, highest in 2026-06.
- 8.4 s, apertus-v1-5-70b

**Bill, due 30.11.**

- Bill, due 30.11. (bill): 1'180.00
- Bill, due 14.12. (bill): 49.90
- Due in 30 days (due_soon): 3'155.45
- Regular payments (regular_payments): 150.00
- Repaid each month (monthly_spending): 2'238.88

- judge hero_question: The hero is a single provisional tax bill, which answers "what is due next", not "where the money goes" — the figure the request itself names (spending averaging 5'511.93 a month, highest in June 2026) appears on no tile.
- judge about_customer: Every tile is genuinely Jana's data, but the tiles tell an upcoming-bills and parents'-loan story rather than the request, with the loan disclaimer under the board answering a question about the loan balance that she did not ask.
- judge titles: "Repaid each month" mislabels a tile that counts rent, health insurance, taxes and fitness (not repayments), while "Bill, due 30.11." and "Bill, due 14.12." are interchangeable generic labels that never name the tax or internet bill they show.
- judge not_empty_or_repeated: The two single-bill tiles merely restate payments already listed in "Due in 30 days" — neither carries the reminder that would justify a bill standing beside its list — and a standalone 49.90-franc internet bill is filler.
- judge coherent: The board mixes a 30-day due list, two single bills and the parents'-loan repayment into a bills-and-loan story, never the one story the request asks for: where her roughly 5'512 of monthly spending actually goes.
- service tiles_resolved: 6 of 7 resolved; dropped: Bill, due 30.11.; Monthly spending overview
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 14.12.

## daniela-idea1: NOT acceptable

Asked: Fixed costs. The 6 largest monthly payments add up to 2'414.20 a month, half of the income or more.

- kind: 
- question: Fixed costs. The 6 largest monthly payments add up to 2'414.20 a month, half of the income or more.
- 10.4 s, apertus-v1-5-70b

**Fixed costs**

- Fixed costs (regular_payments): 2'628.00
- Bill, due 30.11. (bill): 440.00

- judge about_customer: The dentist's second reminder is a strong signal in Daniela's life but a one-off bill, not one of the monthly fixed costs the request is about, and a strong signal not about the request does not belong on the board.
- judge coherent: The board should be about the fixed-costs request and nothing else, but the second tile drags in an unrelated one-off bill, while the data holds more that is on-topic such as the fixed costs set against her income that the request itself mentions.
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 10.12.

## daniela-idea2: NOT acceptable

Asked: Instalments. Instalment plans running: Ratenwerk Finanz AG (20 of 24 paid, 311.20 left).

- kind: 
- question: Instalments. Instalment plans running: Ratenwerk Finanz AG (20 of 24 paid, 311.20 left).
- 13.9 s, apertus-v1-5-70b

**Instalments**

- Instalments (regular_payments): 77.80

- tile_count: tiles per board: [1]

## daniela-idea3: acceptable

Asked: Bills due soon. 8 payments of together 2'950.20 are due in the next 30 days.

- kind: 
- question: Bills due soon. 8 payments of together 2'950.20 are due in the next 30 days.
- 11.9 s, apertus-v1-5-70b

**Open bills**

- Open bills (regular_payments): 2'950.20

- service tiles_resolved: 4 of 5 resolved; dropped: Bill, due 30.11.; Bill, due 30.11.; Bill, due 10.12.; Bills until payday
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 10.12.

## marco-idea1: NOT acceptable

Asked: Fixed costs. The 3 largest monthly payments add up to 2'812.60 a month.

- kind: 
- question: Fixed costs. The 3 largest monthly payments add up to 2'812.60 a month.
- 10.0 s, apertus-v1-5-70b

**Fixed costs**

- Fixed costs (regular_payments): 3'108.00

- judge hero_question: The request asks for the three largest monthly payments and their 2'812.60 monthly sum, but the hero lists five payments due in December — mixing monthly and quarterly charges such as the mortgage interest — under a 3'108 total, so it never shows the three largest monthly payments or the requested figure.
- service titles_checked: default title for: Bill, due 14.12.; Bill, due 15.12.

## marco-idea2: NOT acceptable

Asked: Regular income. Simone Baumann sends about 2'600.00 every month, around day 26.

- kind: 
- question: Regular income. Simone Baumann sends about 2'600.00 every month, around day 26.
- 28.1 s, server

**Regular income**

- Regular income (expected_income): 2'600.00

- tile_count: tiles per board: [1]
- service planned_by_model: The model did not answer in time; this board holds what your request names word for word.

## marco-idea3: NOT acceptable

Asked: Where the money goes. Spending averaged 11'716.70 a month over the last 6 months, highest in 2026-08.

- kind: 
- question: Where the money goes. Spending averaged 11'716.70 a month over the last 6 months, highest in 2026-08.
- 12.2 s, apertus-v1-5-70b

**Sparkonto Haus**

- Sparkonto Haus (savings_goal): 19'350.30
- Regular payments (regular_payments): 489.00
- Bill, due 14.12. (bill): 164.00
- Bill, due 15.12. (bill): 142.70

- judge hero_question: The hero shows the house savings goal at 96.8% of CHF 20'000 instead of the requested view of where the money goes, namely the CHF 11'716.70 average monthly spending over the last 6 months with its peak in August 2026.
- judge about_customer: The tiles are real to Marco's life (house reserve, Skoda lease, Swisscom, Wädenswil water) but none addresses the request — no six-month spending, no categories, no August peak — so the off-request savings-goal signal does not belong on this board.
- judge titles: The two bill titles 'Bill, due 14.12.' and 'Bill, due 15.12.' are interchangeable system labels that name no payee, and 'Regular payments' is generic, so the titles neither read like a person wrote them nor use the customer's terms.
- judge coherent: Under the name 'Sparkonto Haus' the board mixes a savings goal with a lease payment and two upcoming bills, telling no story about the requested spending flows and never touching the last six months.
- service tiles_resolved: 5 of 6 resolved; dropped: Sparkonto Haus; Monthly spending
- service titles_checked: default title for: Bill, due 14.12.; Bill, due 15.12.

