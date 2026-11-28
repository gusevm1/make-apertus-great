# Boards gate, apertus

3 of 8 acceptable.

- lukas: 0 of 2
- jana: 1 of 2
- daniela: 2 of 2
- marco: 0 of 2

OpenRouter: 16 calls sent, 0 from cache, 55670 tokens in, 136783 out, about $0.1954

## lukas-1-r1: NOT acceptable

Asked: We want to go to Japan in 2027. Keep an eye on that for me.

- kind: 
- question: We want to go to Japan in 2027. Keep an eye on that for me.
- 9.5 s, apertus-v1-5-70b

**Japan 2027**

- Sparkonto Langfristig (savings_goal): 37'566.29
- Japan 2027 (regular_payments): 600.00

- judge about_customer: The second tile shows an upcoming payment to Ferienwohnungen Engadin AG, a Swiss ski-holiday rental that has nothing to do with the Japan 2027 request.
- judge titles: The title "Japan 2027" on a tile showing an Engadin holiday-apartment payment does not match what the tile shows.
- judge coherent: The board mixes the Japan savings goal with an unrelated Engadin booking, so it is not about the request and nothing else.
- service tiles_resolved: 3 of 4 resolved; dropped: Sparkonto Langfristig; Bill, due 10.12.
- service titles_checked: default title for: Bill, due 10.12.

## lukas-1-r2: NOT acceptable

Asked: What do my subscriptions cost me?

- kind: 
- question: What do my subscriptions cost me?
- 13.6 s, apertus-v1-5-70b

**Subscriptions**

- Subscriptions (regular_payments): 252.95
- Bill, due 12.01. (bill): 94.00

- judge hero_question: The hero puts CHF 252.95 forward as what his subscriptions cost, but it counts only the gym, mobile and internet payments and omits the streaming and news subscriptions the persona says Lukas pays every month, so it does not answer what his subscriptions cost him.
- judge not_empty_or_repeated: The second tile repeats the Swisscom subscription – the same payee and same CHF 94.00 already shown as a row in the first tile – adding only a due date and carrying no reminder that would justify standing beside the list to show its detail.
- service titles_checked: default title for: Bill, due 14.12.; Bill, due 12.01.

## jana-1-r1: NOT acceptable

Asked: How do I get my emergency fund to 10'000?

- kind: 
- question: How do I get my emergency fund to 10'000?
- 9.5 s, apertus-v1-5-70b

**Notgroschen**

- Sparkonto (savings_goal): 4'919.20
- Regular payments (regular_payments): 150.00
- Repaid each month (monthly_spending): 125.00

- judge about_customer: Tiles 2 and 3 track the CHF 150 monthly repayment to her mother, which is real in her life but belongs to the parents'-loan question, not to the emergency-fund request this board was made for.
- judge not_empty_or_repeated: Tiles 2 and 3 show the same CHF 150-per-month payment to Andrea Widmer, once as the upcoming regular payment and once as its monthly history, so two of three tiles repeat one fact in different words.
- judge coherent: The board opens on the 10'000 savings goal but two of its three tiles and the closing line are about repaying her parents' loan, so it mixes the requested emergency-fund story with a different topic.
- service tiles_resolved: 3 of 5 resolved; dropped: Sparkonto; Notgroschen

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

## daniela-1-r1: acceptable

Asked: What does Lina cost me every month?

- kind: 
- question: What does Lina cost me every month?
- 26.3 s, apertus-v1-5-70b

**What Lina costs**

- What Lina costs (regular_payments): 788.00

- service tiles_resolved: 3 of 4 resolved; dropped: Bill, due 30.11.; Bill, due 30.11.; Bill, due 10.12.
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 10.12.

## daniela-1-r2: acceptable

Asked: Which bills and reminders are open?

- kind: 
- question: Which bills and reminders are open?
- 11.9 s, apertus-v1-5-70b

**Open bills**

- Open bills (regular_payments): 1'255.20

- service tiles_resolved: 4 of 5 resolved; dropped: Bill, due 30.11.; Bill, due 30.11.; Bill, due 10.12.; Bills until payday
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 10.12.

## marco-1-r1: NOT acceptable

Asked: What does the house cost us?

- kind: 
- question: What does the house cost us?
- 28.2 s, server

**Mortgage**

- Mortgage (mortgage): 862'500.00
- Sparkonto Haus (savings_goal): 19'350.30
- Regular payments (regular_payments): 631.40

- judge hero_question: The first tile shows the mortgage balance and tranches (what they owe), and while it carries an annual interest figure, neither it nor any other tile totals what the house costs per year in interest, amortisation and maintenance, so the request is not answered.
- service tiles_resolved: 3 of 4 resolved; dropped: Sparkonto Haus
- service planned_by_model: The model did not answer in time; this board holds what your request names word for word.

## marco-1-r2: NOT acceptable

Asked: What should we decide about the mortgage?

- kind: 
- question: What should we decide about the mortgage?
- 18.3 s, apertus-v1-5-70b

**Mortgage decision**

- Mortgage (mortgage): 862'500.00
- Mortgage decision (regular_payments): 1'050.00

- judge about_customer: The second tile is a lone CHF 1'050 interest debit on the untouched 10-year tranche — real data, but not about the fixed-or-SARON decision the request asks about, while the data holds more decision-relevant material such as the interest actually paid on the fixed and SARON tranches.
- judge titles: The title 'Mortgage decision' sits on a tile that shows a single upcoming payment due 31 December rather than any decision, so the title does not match what the tile shows.
- judge not_empty_or_repeated: The second tile is pointless on this board: one interest debit whose due date the first tile already carries, telling the customer nothing the decision needs.
- judge coherent: After the hero's maturing tranche the board drifts to an upcoming interest debit that plays no part in the fixed-or-SARON decision, so the board is not about the request and nothing else.

