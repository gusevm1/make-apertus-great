# Boards gate, apertus

6 of 8 acceptable.

- lukas: 1 of 2
- jana: 2 of 2
- daniela: 1 of 2
- marco: 2 of 2

OpenRouter: 16 calls sent, 0 from cache, 55040 tokens in, 124870 out, about $0.1787

## lukas-1-r1: NOT acceptable

Asked: We want to go to Japan in 2027. Keep an eye on that for me.

- kind: 
- question: We want to go to Japan in 2027. Keep an eye on that for me.
- 4.0 s, apertus-v1-5-70b

**Japan 2027**

- Sparkonto Langfristig (savings_goal): 37'566.29
- Regular payments (regular_payments): 600.00

- judge about_customer: The second tile is a real payment of his but belongs to his annual Engadin ski-holiday theme, not to the Japan request, so a strong signal that is not about the request has been added.
- judge coherent: The board mixes the Japan savings goal with an unrelated upcoming holiday-apartment payment, and since the data holds more about the Japan goal (the monthly standing order and savings development), this off-topic tile is filler that breaks the single story.
- service tiles_resolved: 3 of 4 resolved; dropped: Sparkonto Langfristig; Bill, due 10.12.
- service titles_checked: default title for: Bill, due 10.12.

## lukas-1-r2: acceptable

Asked: What do my subscriptions cost me?

- kind: 
- question: What do my subscriptions cost me?
- 6.1 s, apertus-v1-5-70b

**Subscriptions**

- Subscriptions (regular_payments): 252.95
- Bill, due 12.01. (bill): 94.00

- service titles_checked: default title for: Bill, due 14.12.; Bill, due 12.01.

## jana-1-r1: acceptable

Asked: How do I get my emergency fund to 10'000?

- kind: 
- question: How do I get my emergency fund to 10'000?
- 4.9 s, apertus-v1-5-70b

**Notgroschen**

- Sparkonto (savings_goal): 4'919.20

- service tiles_resolved: 1 of 2 resolved; dropped: Sparkonto

## jana-1-r2: acceptable

Asked: When have I repaid my parents?

- kind: 
- question: When have I repaid my parents?
- 4.9 s, apertus-v1-5-70b

**Parents' loan**

- Regular payments (regular_payments): 150.00
- Repaid each month (monthly_spending): 125.00

- service tiles_resolved: 2 of 3 resolved; dropped: Regular payments

## daniela-1-r1: NOT acceptable

Asked: What does Lina cost me every month?

- kind: 
- question: What does Lina cost me every month?
- 5.9 s, apertus-v1-5-70b

**What Lina costs**

- What Lina costs (regular_payments): 440.00
- Bill, due 10.12. (bill): 348.00

- judge hero_question: The hero shows a single one-off dentist payment of CHF 440 due 30 November, which does not answer what Lina costs every month — the direct answer would be her recurring monthly costs, above all the CHF 348 childcare that recurs each month.
- judge titles: The hero title 'What Lina costs' sits over a single one-off dentist payment, so the audience would read CHF 440 as Lina's monthly cost, which does not match what the tile shows; the second title 'Bill, due 10.12.' also hides that it is Lina's childcare.
- service tiles_resolved: 3 of 4 resolved; dropped: Bill, due 30.11.; Bill, due 30.11.
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 10.12.

## daniela-1-r2: acceptable

Asked: Which bills and reminders are open?

- kind: 
- question: Which bills and reminders are open?
- 10.4 s, apertus-v1-5-70b

**Open bills**

- Open bills (regular_payments): 440.00
- Bill, due 10.12. (bill): 348.00

- service tiles_resolved: 4 of 5 resolved; dropped: Bill, due 30.11.; Bill, due 30.11.; Bills until payday
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 10.12.

## marco-1-r1: acceptable

Asked: What does the house cost us?

- kind: 
- question: What does the house cost us?
- 25.5 s, apertus-v1-5-70b

**The house**

- The house (regular_payments): 1'681.40
- Mortgage (mortgage): 862'500.00
- Sparkonto Haus (savings_goal): 19'350.30

## marco-1-r2: acceptable

Asked: What should we decide about the mortgage?

- kind: 
- question: What should we decide about the mortgage?
- 11.4 s, apertus-v1-5-70b

**Mortgage decision**

- Mortgage (mortgage): 862'500.00
- Regular payments (regular_payments): 1'050.00

