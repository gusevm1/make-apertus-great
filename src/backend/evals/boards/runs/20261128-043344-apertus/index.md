# Boards gate, apertus

2 of 8 acceptable.

- lukas: 0 of 2
- jana: 1 of 2
- daniela: 0 of 2
- marco: 1 of 2

OpenRouter: 16 calls sent, 0 from cache, 57400 tokens in, 115311 out, about $0.1655

## lukas-1-r1: NOT acceptable

Asked: We want to go to Japan in 2027. Keep an eye on that for me.

- kind: 
- question: We want to go to Japan in 2027. Keep an eye on that for me.
- 4.9 s, apertus-v1-5-70b

**Japan 2027**

- Sparkonto Langfristig (savings_goal): 37'566.29
- Japan 2027 (regular_payments): 600.00

- judge about_customer: The second tile is a CHF 600 payment to Ferienwohnungen Engadin AG, a Swiss ski-holiday booking from Lukas's winter weekends, which has nothing to do with the Japan 2027 request and looks like filler.
- judge titles: The second tile is titled 'Japan 2027' but its payload shows an Engadin holiday-apartment payment, so the title does not match what the tile shows.
- judge coherent: The board mixes the Japan savings goal with an unrelated Engadin holiday payment, so it does not tell the one story of the Japan 2027 request.
- service tiles_resolved: 3 of 4 resolved; dropped: Sparkonto Langfristig; Bill, due 10.12.
- service titles_checked: default title for: Bill, due 10.12.

## lukas-1-r2: NOT acceptable

Asked: What do my subscriptions cost me?

- kind: 
- question: What do my subscriptions cost me?
- 7.5 s, apertus-v1-5-70b

**Subscriptions**

- What Subscriptions costs (monthly_spending): 204.67
- Subscriptions (regular_payments): 39.95
- Bill, due 14.12. (bill): 94.00
- Bill, due 12.01. (bill): 94.00

- judge hero_question: The hero shows monthly spending for only two merchants (Fitnesspark gym and Swisscom internet, ~CHF 205), leaving out his Salt mobile subscription shown on the very next tile plus any streaming or news subscriptions, so it does not answer what his subscriptions cost him.
- judge titles: "What Subscriptions costs" is broken grammar and overclaims a tile holding only two merchants, and "Subscriptions" heads a tile listing a single Salt Mobile payment, so titles do not read like a person wrote them or match their tiles.
- judge not_empty_or_repeated: The two Swisscom inOne home bills (CHF 94.00 due 14.12 and CHF 94.00 due 12.01) repeat the same subscription cost twice, a cost already folded into the hero's monthly total.
- judge coherent: The board never tells one story answering the request: a partial two-merchant average, a lone Salt payment, and two duplicate internet bills, with streaming and news subscriptions absent, leaves Lukas without a coherent picture of his subscription costs.
- service titles_checked: default title for: Bill, due 14.12.; Bill, due 12.01.

## jana-1-r1: NOT acceptable

Asked: How do I get my emergency fund to 10'000?

- kind: 
- question: How do I get my emergency fund to 10'000?
- 7.5 s, apertus-v1-5-70b

**Notgroschen**

- Sparkonto (savings_goal): 4'919.20
- Regular payments (regular_payments): 150.00
- Repaid each month (monthly_spending): 125.00

- judge about_customer: Tiles 2 and 3 show the 150 monthly repayment to her mother, a strong but off-request signal that belongs to a different question, and nothing on the board connects it to reaching the 10'000 emergency fund.
- judge titles: 'Regular payments' reads like a system category label that hides who she pays instead of using her terms (e.g. repayment to her parents), and the English titles sit oddly beside the German board name 'Notgroschen' and account name 'Sparkonto'.
- judge coherent: The board mixes two stories — emergency-fund progress in the hero and the parents'-loan repayment in two tiles plus the under-board line about the unknown loan remainder — so it is not about the request and nothing else.
- service tiles_resolved: 3 of 5 resolved; dropped: Sparkonto; Notgroschen

## jana-1-r2: acceptable

Asked: When have I repaid my parents?

- kind: 
- question: When have I repaid my parents?
- 8.1 s, apertus-v1-5-70b

**Parents' loan**

- Regular payments (regular_payments): 150.00
- Repaid each month (monthly_spending): 125.00

- service tiles_resolved: 2 of 3 resolved; dropped: Parents' loan

## daniela-1-r1: NOT acceptable

Asked: What does Lina cost me every month?

- kind: 
- question: What does Lina cost me every month?
- 4.4 s, apertus-v1-5-70b

**What Lina costs**

- What What Lina costs costs (monthly_spending): 321.00
- What Lina costs (regular_payments): 440.00
- Bill, due 10.12. (bill): 348.00

- judge titles: The hero title 'What What Lina costs costs' is a garbled doubled string no person would write, and 'What Lina costs' on the dentist tile does not match the single CHF 440 bill that tile shows.
- service tiles_resolved: 4 of 5 resolved; dropped: Bill, due 30.11.; Bill, due 30.11.
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 10.12.

## daniela-1-r2: NOT acceptable

Asked: Which bills and reminders are open?

- kind: 
- question: Which bills and reminders are open?
- 6.5 s, apertus-v1-5-70b

**Open bills**

- What Open bills costs (monthly_spending): 669.23
- Open bills (regular_payments): 440.00
- Bill, due 10.12. (bill): 348.00

- judge hero_question: The request asks which bills and reminders are open, but the hero shows a 12-month monthly spending trend at her recurring payees instead of the open items (dentist reminder, upcoming bills) that tiles 2 and 3 actually contain.
- judge about_customer: The dentist reminder and the Hort bill are her real open items, but the hero's historical cost trend is a strong signal about her fixed costs that is not about the request and does not belong on this board.
- judge titles: "What Open bills costs" reads machine-generated (the board name slotted into a sentence, wrongly cased) and mislabels a spending trend, and "Open bills" for a single dentist row is generic rather than her term (Zahnarzt, reminder).
- judge coherent: A requested board must be about the request and nothing else, but this board mixes the open-bills question with an off-topic 12-month cost trend as its largest tile.
- service tiles_resolved: 5 of 6 resolved; dropped: Bill, due 30.11.; Bill, due 30.11.; Bills until payday
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 10.12.

## marco-1-r1: acceptable

Asked: What does the house cost us?

- kind: 
- question: What does the house cost us?
- 5.1 s, apertus-v1-5-70b

**The house**

- What the house costs (monthly_spending): 1'120.83
- Mortgage (mortgage): 862'500.00
- Sparkonto Haus (savings_goal): 19'350.30

## marco-1-r2: NOT acceptable

Asked: What should we decide about the mortgage?

- kind: 
- question: What should we decide about the mortgage?
- 6.2 s, apertus-v1-5-70b

**Mortgage decision**

- Mortgage (mortgage): 862'500.00
- Mortgage decision (regular_payments): 1'050.00

- judge titles: The second tile is titled 'Mortgage decision' but shows a single upcoming payment of CHF 1'050, so the title does not match what the tile shows.

