# Boards gate, apertus

3 of 12 acceptable.

- lukas: 1 of 3
- jana: 1 of 3
- daniela: 0 of 3
- marco: 1 of 3

OpenRouter: 24 calls sent, 0 from cache, 84444 tokens in, 178955 out, about $0.2564

## lukas-idea1: acceptable

Asked: Big monthly bills. The 5 largest monthly payments add up to 3'520.35 a month.

- kind: 
- question: Big monthly bills. The 5 largest monthly payments add up to 3'520.35 a month.
- 6.3 s, apertus-v1-5-70b

**Big monthly bills**

- Big monthly bills (regular_payments): 3'542.85

- service titles_checked: default title for: Bill, due 14.12.; Bill, due 23.12.

## lukas-idea2: NOT acceptable

Asked: Partner's monthly support. Sara Keller sends about 2'200.00 every month, around day 27.

- kind: 
- question: Partner's monthly support. Sara Keller sends about 2'200.00 every month, around day 27.
- 4.8 s, apertus-v1-5-70b

**Sparkonto Langfristig**

- Sparkonto Langfristig (savings_goal): 37'566.29

- judge hero_question: The request asks about Sara's monthly support of about CHF 2'200 around day 27, but the hero tile shows the long-term savings account and the Japan 2027 goal, which answers a different question entirely.
- judge about_customer: The tile is about Lukas's real Japan savings goal, but it is a strong signal that has nothing to do with the requested partner support and therefore does not belong on this board.
- judge coherent: The board tells one story, but it is the story of the Japan savings goal rather than the requested theme of Sara's monthly support transfers.
- service tiles_resolved: 1 of 2 resolved; dropped: Sparkonto Langfristig

## lukas-idea3: NOT acceptable

Asked: Monthly cash flow. On average -199.61 was left per month over the last 6 months; in 2 months more went out than came in (2026-05, 2026-09).

- kind: 
- question: Monthly cash flow. On average -199.61 was left per month over the last 6 months; in 2 months more went out than came in (2026-05, 2026-09).
- 4.7 s, apertus-v1-5-70b

**Monthly cash flow**

- Monthly cash flow (regular_payments): 4'767.65

- judge hero_question: The request asks for the last six months' cash flow (average -199.61 left per month, two months where more went out than came in), but the hero tile lists upcoming payments due in the next weeks, which does not answer that question.
- judge about_customer: The tile does show Lukas's real payees, but upcoming regular payments are a strong signal about future obligations rather than the requested six-month cash flow analysis, so they do not belong on this board.
- judge titles: The title 'Monthly cash flow' does not match what the tile shows, since the payload is a list of upcoming regular payments and not any cash-flow figure for the last six months.
- judge coherent: A board named for monthly cash flow whose only content is upcoming payments tells a different story from the one requested, and nothing on it addresses the average monthly remainder or the two negative months.
- service titles_checked: default title for: Bill, due 10.12.; Bill, due 14.12.

## jana-idea1: NOT acceptable

Asked: Pillar 3a savings. Paid into pillar 3a in 2026: 3'300.00 of the maximum 7'258.00; after the standing orders 3'658.00 is missing.

- kind: 
- question: Pillar 3a savings. Paid into pillar 3a in 2026: 3'300.00 of the maximum 7'258.00; after the standing orders 3'658.00 is missing.
- 28.2 s, server

**Regular payments**

- Regular payments (regular_payments): 150.00
- Bill, due 30.11. (bill): 1'180.00
- Pillar 3a, 2026 (pillar_3a): 3'658.00
- Each month (monthly_spending): 1'402.27

- judge hero_question: The request asks about pillar 3a savings, but the hero tile shows a 150 CHF regular payment to Andrea Widmer while the pillar 3a figures the request names sit in the third tile.
- judge about_customer: Only the pillar 3a tile is about the request; the parent-loan payment, the Bern tax bill and everyday merchant spending are real in Jana's life but do not belong on a board made for this request.
- judge coherent: A requested board must be about the request and nothing else, but this one mixes a parent repayment, a tax bill, pillar 3a and general spending under a 'Regular payments' label.
- service tiles_resolved: 6 of 7 resolved; dropped: Bill, due 30.11.; Bill, due 14.12.; Regular payments
- service titles_checked: default title for: Bill, due 30.11.
- service planned_by_model: The model did not answer in time; this board holds what your request names word for word.

## jana-idea2: acceptable

Asked: Fixed costs. The 6 largest monthly payments add up to 2'103.25 a month.

- kind: 
- question: Fixed costs. The 6 largest monthly payments add up to 2'103.25 a month.
- 14.8 s, apertus-v1-5-70b

**Fixed costs**

- Fixed costs (regular_payments): 3'220.25

- service tiles_resolved: 4 of 5 resolved; dropped: Bill, due 30.11.; Bill, due 30.11.; Bill, due 14.12.; Due in 30 days
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 14.12.

## jana-idea3: NOT acceptable

Asked: Where the money goes. Spending averaged 5'511.93 a month over the last 6 months, highest in 2026-06.

- kind: 
- question: Where the money goes. Spending averaged 5'511.93 a month over the last 6 months, highest in 2026-06.
- 10.5 s, apertus-v1-5-70b

**Bill, due 30.11.**

- Bill, due 30.11. (bill): 1'180.00
- Bill, due 14.12. (bill): 49.90
- Due in 30 days (due_soon): 3'155.45
- Regular payments (regular_payments): 150.00
- Repaid each month (monthly_spending): 2'238.88

- judge hero_question: The hero is a single provisional tax bill due 30.11., which does not answer 'where the money goes' — the request itself names the figure the data holds (spending averaging 5'511.93 a month, peak in 2026-06) and that appears nowhere on the board, and the loan line cannot rescue it because the request is not about the parents' loan.
- judge about_customer: All tiles are real to Jana's life (taxes, Sunrise, rent, KPT, Activ Fitness, the repayment to her mother), but the two bill tiles and the due-in-30-days list answer 'what must I pay soon' rather than where her money goes, so the strong tax-bill signal does not belong on a board made for this request.
- judge titles: 'Bill, due 30.11.' and 'Bill, due 14.12.' are templated labels that hide the payees a person would name (the tax office, Sunrise), 'Regular payments' is generic for her single repayment to her mother, and 'Repaid each month' misdescribes a tile that shows rent, insurance and taxes, not repayments.
- judge coherent: The board tells one internally sensible story about bills due, fixed payees and the parents' repayment, but that is not the requested story of where her roughly 5'511.93 a month goes, and the quiet line about the loan answers a question she did not ask.
- service tiles_resolved: 6 of 7 resolved; dropped: Bill, due 30.11.; Monthly spending overview
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 14.12.

## daniela-idea1: NOT acceptable

Asked: Fixed costs. The 6 largest monthly payments add up to 2'414.20 a month, half of the income or more.

- kind: 
- question: Fixed costs. The 6 largest monthly payments add up to 2'414.20 a month, half of the income or more.
- 6.5 s, apertus-v1-5-70b

**Fixed costs**

- Fixed costs (regular_payments): 2'628.00
- Bill, due 30.11. (bill): 440.00

- judge about_customer: The dentist bill tile is a real and pressing part of Daniela's life but a one-off bill with a reminder fee, not one of the monthly fixed costs the request is about, so this strong off-request signal does not belong on a requested board.
- judge coherent: The board mixes the requested fixed-costs list with an unrelated one-off dentist bill, so it is not about the request and nothing else.
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 10.12.

## daniela-idea2: NOT acceptable

Asked: Instalments. Instalment plans running: Ratenwerk Finanz AG (20 of 24 paid, 311.20 left).

- kind: 
- question: Instalments. Instalment plans running: Ratenwerk Finanz AG (20 of 24 paid, 311.20 left).
- 28.1 s, server

**Regular payments**

- Regular payments (regular_payments): 77.80

- tile_count: tiles per board: [1]
- service planned_by_model: The model did not answer in time; this board holds what your request names word for word.

## daniela-idea3: NOT acceptable

Asked: Savings pots. 2 savings accounts with their own purpose: Sparkonto Notgroschen (Reserve für Unvorhergesehenes); Jugendsparkonto Lina (Geschenke der Grosseltern für Lina (nicht antasten)).

- kind: 
- question: Savings pots. 2 savings accounts with their own purpose: Sparkonto Notgroschen (Reserve für Unvorhergesehenes); Jugendsparkonto Lina (Geschenke der Grosseltern für Lina (nicht antasten)).
- 11.4 s, apertus-v1-5-70b

**Savings pots**

- Sparkonto Notgroschen (savings_goal): 284.25
- Bill, due 30.11. (bill): 440.00
- Bill, due 10.12. (bill): 348.00

- judge about_customer: The two bill tiles (dentist reminder and Winterthur childcare) are real in Daniela's life but not about the savings-pots request, and the Jugendsparkonto Lina that the request explicitly names is missing entirely even though the bank holds it.
- judge not_empty_or_repeated: No tile is empty or zero and the two bills are different payments, but on a board about two savings pots the two bill tiles carry nothing about the request, making them pointless here.
- judge coherent: The board tells no single story about the savings pots: it is one savings goal followed by two unrelated bills, and the second pot (Lina's account) the request asks for never appears.
- service tiles_resolved: 4 of 6 resolved; dropped: Sparkonto Notgroschen; Bill, due 30.11.; Savings pots
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 10.12.

## marco-idea1: acceptable

Asked: Fixed costs. The 3 largest monthly payments add up to 2'812.60 a month.

- kind: 
- question: Fixed costs. The 3 largest monthly payments add up to 2'812.60 a month.
- 5.3 s, apertus-v1-5-70b

**Fixed costs**

- Fixed costs (regular_payments): 3'108.00

- service titles_checked: default title for: Bill, due 14.12.; Bill, due 15.12.

## marco-idea2: NOT acceptable

Asked: Regular income. Simone Baumann sends about 2'600.00 every month, around day 26.

- kind: 
- question: Regular income. Simone Baumann sends about 2'600.00 every month, around day 26.
- 28.1 s, server

**Regular payments**

- Regular payments (regular_payments): 1'262.30

- judge hero_question: The request asks for Simone Baumann's regular income of about 2'600 arriving around day 26 each month, but the hero tile shows an outgoing insurance payment to Helsana of 1'262.30, which does not answer the request at all.
- judge about_customer: The only tile is an outgoing payment to Helsana Versicherungen, which is not about the requested regular income from Simone Baumann and therefore does not belong on a board made for this request.
- judge coherent: The board tells the story of an upcoming insurance bill instead of the requested story of Simone's monthly household contribution, so it is about something else entirely.
- service titles_checked: default title for: Bill, due 23.12.
- service planned_by_model: The model did not answer in time; this board holds what your request names word for word.

## marco-idea3: NOT acceptable

Asked: Where the money goes. Spending averaged 11'716.70 a month over the last 6 months, highest in 2026-08.

- kind: 
- question: Where the money goes. Spending averaged 11'716.70 a month over the last 6 months, highest in 2026-08.
- 12.8 s, apertus-v1-5-70b

**Sparkonto Haus**

- Sparkonto Haus (savings_goal): 19'350.30
- Regular payments (regular_payments): 489.00
- Bill, due 14.12. (bill): 164.00
- Bill, due 15.12. (bill): 142.70

- judge hero_question: The request asks where the money goes (spending averaging 11'716.70 a month), but the hero shows a savings-goal balance for the house account, which says nothing about spending.
- judge about_customer: The savings-goal hero is a strong signal about the house reserve but not about the spending request, and no tile shows the monthly spending or its categories that the request is about.
- judge titles: Titles like 'Bill, due 14.12.' and 'Bill, due 15.12.' are near-identical template labels that avoid the customer's own terms (Swisscom, Wasser, Leasing) a person would naturally use.
- judge coherent: The board mixes a house-savings goal with a car-lease payment and two small December bills, telling no single story about where the money goes and never showing the 11'716.70 monthly spending the request names.
- service tiles_resolved: 5 of 6 resolved; dropped: Sparkonto Haus; Monthly spending
- service titles_checked: default title for: Bill, due 14.12.; Bill, due 15.12.

