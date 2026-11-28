# Boards gate, apertus

3 of 8 acceptable.

- lukas: 1 of 2
- jana: 1 of 2
- daniela: 1 of 2
- marco: 0 of 2

OpenRouter: 16 calls sent, 0 from cache, 55654 tokens in, 158855 out, about $0.2263

## lukas-1-r1: NOT acceptable

Asked: We want to go to Japan in 2027. Keep an eye on that for me.

- kind: 
- question: We want to go to Japan in 2027. Keep an eye on that for me.
- 4.8 s, apertus-v1-5-70b

**Japan 2027**

- Sparkonto Langfristig (savings_goal): 37'566.29
- Japan 2027 (regular_payments): 600.00

- judge about_customer: The second tile is an upcoming CHF 600 payment to Ferienwohnungen Engadin AG, his Swiss ski-holiday apartment, which is real data but not about the Japan request — exactly the off-topic filler the rubric forbids on a requested board.
- judge titles: The tile titled 'Japan 2027' actually shows an Engadin holiday-apartment payment, so the title does not match what the tile shows.
- judge coherent: The board pairs the Japan savings goal with an unrelated Engadin holiday payment, so it is not about the request and nothing else.
- service tiles_resolved: 3 of 4 resolved; dropped: Sparkonto Langfristig; Bill, due 10.12.
- service titles_checked: default title for: Bill, due 10.12.

## lukas-1-r2: acceptable

Asked: What do my subscriptions cost me?

- kind: 
- question: What do my subscriptions cost me?
- 6.8 s, apertus-v1-5-70b

**Subscriptions**

- Subscriptions (regular_payments): 252.95
- Bill, due 12.01. (bill): 94.00

- service titles_checked: default title for: Bill, due 14.12.; Bill, due 12.01.

## jana-1-r1: NOT acceptable

Asked: How do I get my emergency fund to 10'000?

- kind: 
- question: How do I get my emergency fund to 10'000?
- 5.7 s, apertus-v1-5-70b

**Notgroschen**

- Sparkonto (savings_goal): 4'919.20
- Regular payments (regular_payments): 150.00
- Repaid each month (monthly_spending): 125.00

- judge about_customer: Tiles 2 and 3 are about her loan repayment to her mother, a real part of her life but not about the emergency-fund request, while nothing on the board addresses how to reach the goal beyond the hero.
- judge not_empty_or_repeated: Tiles 2 and 3 show the same CHF 150 payments to Andrea Widmer in two different templates, repeating the same information.
- judge coherent: The board tells two stories — the emergency-fund goal and the parents' loan repayment — instead of staying on the single theme of the request, and the quiet line about the loan is unrelated noise here.
- service tiles_resolved: 3 of 5 resolved; dropped: Sparkonto; Notgroschen

## jana-1-r2: acceptable

Asked: When have I repaid my parents?

- kind: 
- question: When have I repaid my parents?
- 5.4 s, apertus-v1-5-70b

**Parents' loan**

- Regular payments (regular_payments): 150.00
- Repaid each month (monthly_spending): 125.00

- service tiles_resolved: 2 of 3 resolved; dropped: Parents' loan

## daniela-1-r1: NOT acceptable

Asked: What does Lina cost me every month?

- kind: 
- question: What does Lina cost me every month?
- 5.3 s, apertus-v1-5-70b

**What Lina costs**

- What Lina costs (regular_payments): 788.00

- judge hero_question: The headline presents 788 CHF as the answer to what Lina costs "every month", but that sum mixes a one-off dentist bill (440) with a single month of childcare (348), so it does not directly answer the monthly-cost question.
- service tiles_resolved: 3 of 4 resolved; dropped: Bill, due 30.11.; Bill, due 30.11.; Bill, due 10.12.
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 10.12.

## daniela-1-r2: acceptable

Asked: Which bills and reminders are open?

- kind: 
- question: Which bills and reminders are open?
- 6.3 s, apertus-v1-5-70b

**Open bills**

- Open bills (regular_payments): 1'255.20

- service tiles_resolved: 4 of 5 resolved; dropped: Bill, due 30.11.; Bill, due 30.11.; Bill, due 10.12.; Bills until payday
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 10.12.

## marco-1-r1: NOT acceptable

Asked: What does the house cost us?

- kind: 
- question: What does the house cost us?
- 26.2 s, apertus-v1-5-70b

**The house**

- The house (regular_payments): 1'050.00
- Mortgage (mortgage): 862'500.00
- Sparkonto Haus (savings_goal): 19'350.30

- judge hero_question: The hero shows only the single next interest debit of CHF 1'050 rather than the yearly cost of the house (interest, amortisation, maintenance) that the request asks for, even though the board's own second tile holds the more direct annual-interest figure of CHF 8'425.
- judge about_customer: The payment and mortgage tiles are genuinely about what the house costs Marco, but the Sparkonto Haus savings-goal tile reports the repair reserve's status — the answer to his separate question about whether the reserve covers the next repair — rather than anything the house costs.
- judge coherent: The board is not about the request and nothing else: the two cost tiles sit beside a reserve-status tile from a different theme, so the whole does not tell the single story of what the house costs each year.

## marco-1-r2: NOT acceptable

Asked: What should we decide about the mortgage?

- kind: 
- question: What should we decide about the mortgage?
- 9.6 s, apertus-v1-5-70b

**Mortgage decision**

- Mortgage (mortgage): 862'500.00
- Mortgage decision (regular_payments): 1'050.00

- judge titles: The second tile is titled 'Mortgage decision' but shows only the routine CHF 1'050 interest debit due 31 December 2026, a payment that is not the choice itself, so the title does not match what the tile shows.

