# Boards gate, apertus

5 of 8 acceptable.

- lukas: 1 of 2
- jana: 2 of 2
- daniela: 2 of 2
- marco: 0 of 2

OpenRouter: 16 calls sent, 0 from cache, 54987 tokens in, 137494 out, about $0.1963

## lukas-1-r1: NOT acceptable

Asked: We want to go to Japan in 2027. Keep an eye on that for me.

- kind: 
- question: We want to go to Japan in 2027. Keep an eye on that for me.
- 12.9 s, apertus-v1-5-70b

**Japan 2027**

- Sparkonto Langfristig (savings_goal): 37'566.29
- Japan 2027 (regular_payments): 600.00

- judge about_customer: The second tile shows a payment to Ferienwohnungen Engadin AG, his Swiss ski-weekend lodging, which is real but not about the Japan 2027 request this board is meant to keep an eye on.
- judge titles: The second tile is titled 'Japan 2027' while showing a payment for an Engadin holiday apartment, so the title does not match what the tile shows.
- judge coherent: The board mixes the Japan savings goal with an unrelated domestic ski-holiday payment, so it does not tell one story about the request alone.
- service tiles_resolved: 3 of 4 resolved; dropped: Sparkonto Langfristig; Bill, due 10.12.
- service titles_checked: default title for: Bill, due 10.12.

## lukas-1-r2: acceptable

Asked: What do my subscriptions cost me?

- kind: 
- question: What do my subscriptions cost me?
- 17.6 s, apertus-v1-5-70b

**Subscriptions**

- Subscriptions (regular_payments): 252.95
- Bill, due 12.01. (bill): 94.00

- service titles_checked: default title for: Bill, due 14.12.; Bill, due 12.01.

## jana-1-r1: acceptable

Asked: How do I get my emergency fund to 10'000?

- kind: 
- question: How do I get my emergency fund to 10'000?
- 17.4 s, apertus-v1-5-70b

**Emergency fund**

- Sparkonto (savings_goal): 4'919.20

- service tiles_resolved: 1 of 2 resolved; dropped: Sparkonto

## jana-1-r2: acceptable

Asked: When have I repaid my parents?

- kind: 
- question: When have I repaid my parents?
- 18.5 s, apertus-v1-5-70b

**Parents' loan**

- Regular payments (regular_payments): 150.00
- Repaid each month (monthly_spending): 125.00

- service tiles_resolved: 2 of 3 resolved; dropped: Parents' loan

## daniela-1-r1: acceptable

Asked: What does Lina cost me every month?

- kind: 
- question: What does Lina cost me every month?
- 15.9 s, apertus-v1-5-70b

**What Lina costs**

- What Lina costs (regular_payments): 788.00

- service tiles_resolved: 3 of 4 resolved; dropped: Bill, due 30.11.; Bill, due 30.11.; Bill, due 10.12.
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 10.12.

## daniela-1-r2: acceptable

Asked: Which bills and reminders are open?

- kind: 
- question: Which bills and reminders are open?
- 10.2 s, apertus-v1-5-70b

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

- judge hero_question: The hero's headline is the CHF 862'500 mortgage balance — what Marco owes — and although the tile carries the CHF 8'425 annual interest as a detail, it never shows what the house costs per year (interest, amortisation, maintenance), so it answers 'how much do we owe' rather than the request 'what does the house cost us'.
- service tiles_resolved: 3 of 4 resolved; dropped: Sparkonto Haus
- service planned_by_model: The model did not answer in time; this board holds what your request names word for word.

## marco-1-r2: NOT acceptable

Asked: What should we decide about the mortgage?

- kind: 
- question: What should we decide about the mortgage?
- 11.6 s, apertus-v1-5-70b

**Mortgage decision**

- Mortgage (mortgage): 862'500.00
- Mortgage decision (regular_payments): 1'050.00

- judge about_customer: The second tile is a routine CHF 1'050 interest payment due 31 December, which is about Marco's mortgage but not about the decision he asked about (fixed or SARON, paying down, the 15 December deadline), while decision-relevant data like the SARON rate history or his savings went unused.
- judge titles: Tile 2 is titled 'Mortgage decision' but shows a single upcoming payment, so the title promises decision content the tile does not hold (tile 1's plain 'Mortgage' is fine).
- judge coherent: Beyond the hero's maturing tranche the board never touches the decision itself, and the routine interest payment tile does not belong in that story, so the board reads as a mortgage overview plus a debit rather than an answer to 'what should we decide'.

