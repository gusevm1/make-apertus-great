# Boards gate, apertus

4 of 8 acceptable.

- lukas: 1 of 2
- jana: 2 of 2
- daniela: 1 of 2
- marco: 0 of 2

OpenRouter: 16 calls sent, 0 from cache, 54882 tokens in, 135814 out, about $0.1940

## lukas-1-r1: NOT acceptable

Asked: We want to go to Japan in 2027. Keep an eye on that for me.

- kind: 
- question: We want to go to Japan in 2027. Keep an eye on that for me.
- 3.3 s, apertus-v1-5-70b

**Japan 2027**

- Sparkonto Langfristig (savings_goal): 37'566.29
- Bill, due 10.12. (bill): 600.00

- judge about_customer: The second tile is a real bill, but it is a deposit for a holiday apartment in Engadin in January 2027 — a different trip — so it is a strong signal that is not about the Japan request and does not belong on this board.
- judge coherent: A board named 'Japan 2027' that mixes the Japan savings goal with an unrelated Swiss ski-holiday deposit is not about the request and nothing else; the Engadin bill looks like an off-topic tile added to fill the board.
- service tiles_resolved: 2 of 3 resolved; dropped: Sparkonto Langfristig
- service titles_checked: default title for: Bill, due 10.12.

## lukas-1-r2: acceptable

Asked: What do my subscriptions cost me?

- kind: 
- question: What do my subscriptions cost me?
- 5.1 s, apertus-v1-5-70b

**Subscriptions**

- Subscriptions (regular_payments): 252.95

- service titles_checked: default title for: Bill, due 14.12.; Bill, due 12.01.

## jana-1-r1: acceptable

Asked: How do I get my emergency fund to 10'000?

- kind: 
- question: How do I get my emergency fund to 10'000?
- 10.8 s, apertus-v1-5-70b

**Notgroschen**

- Sparkonto (savings_goal): 4'919.20

- service tiles_resolved: 1 of 2 resolved; dropped: Sparkonto

## jana-1-r2: acceptable

Asked: When have I repaid my parents?

- kind: 
- question: When have I repaid my parents?
- 4.4 s, apertus-v1-5-70b

**Parents' loan**

- Regular payments (regular_payments): 150.00
- Repaid each month (monthly_spending): 125.00

- service tiles_resolved: 2 of 3 resolved; dropped: Regular payments

## daniela-1-r1: NOT acceptable

Asked: What does Lina cost me every month?

- kind: 
- question: What does Lina cost me every month?
- 3.3 s, apertus-v1-5-70b

**What Lina costs**

- What Lina costs (regular_payments): 440.00
- Bill, due 10.12. (bill): 348.00

- judge hero_question: The hero shows a single one-off dentist payment of CHF 440 (one payment in November, an open bill on its second reminder), not the recurring monthly costs the request asks about, while the genuinely monthly Lina cost (childcare) is relegated to the second tile as one December bill.
- judge titles: The hero title 'What Lina costs' sits over a single one-off dentist payment, so it mislabels the tile as the answer to the monthly question rather than matching what the tile actually shows.
- judge coherent: As a whole the board is just two upcoming bills — a one-off dentist payment and one month's childcare invoice — with no recurring or monthly view even though the data holds a monthly childcare series, so it never tells the story of what Lina costs each month.
- service tiles_resolved: 3 of 4 resolved; dropped: Bill, due 30.11.; Bill, due 30.11.
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 10.12.

## daniela-1-r2: acceptable

Asked: Which bills and reminders are open?

- kind: 
- question: Which bills and reminders are open?
- 4.2 s, apertus-v1-5-70b

**Open bills**

- Open bills (regular_payments): 440.00
- Bill, due 10.12. (bill): 348.00

- service tiles_resolved: 4 of 5 resolved; dropped: Bill, due 30.11.; Bill, due 30.11.; Bills until payday
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 10.12.

## marco-1-r1: NOT acceptable

Asked: What does the house cost us?

- kind: 
- question: What does the house cost us?
- 8.2 s, apertus-v1-5-70b

**The house**

- The house (regular_payments): 1'681.40
- Mortgage (mortgage): 862'500.00
- Sparkonto Haus (savings_goal): 19'350.30

- judge hero_question: The request asks what the house costs (per year, including interest, amortisation and maintenance), but the hero tile only shows two upcoming payments totalling CHF 1'681.40, not the house's cost; the mortgage tile with its annual interest figure would answer it more directly.

## marco-1-r2: NOT acceptable

Asked: What should we decide about the mortgage?

- kind: 
- question: What should we decide about the mortgage?
- 5.1 s, apertus-v1-5-70b

**Mortgage decision**

- Mortgage (mortgage): 862'500.00
- Regular payments (regular_payments): 1'050.00

- judge about_customer: The second tile is a lone routine interest debit that says nothing about the renewal decision, while the data plainly holds much more about the request (the renewal offer's fixed-vs-SARON options, the 15 December deadline, his savings for a possible paydown), so this filler does not justify a two-tile board.
- judge titles: "Mortgage" is acceptable, but "Regular payments" is a raw template label, plural for a single row, that never names the debit as Marco's quarterly mortgage interest in his own terms.
- judge coherent: The board reduces "what should we decide" to a generic mortgage snapshot padded with a routine payment, with no 15 December deadline, no renewal options and no paydown angle, so it never tells the decision story the request asks for.

