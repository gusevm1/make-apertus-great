# Boards gate, apertus

4 of 8 acceptable.

- lukas: 0 of 2
- jana: 2 of 2
- daniela: 0 of 2
- marco: 2 of 2

OpenRouter: 16 calls sent, 0 from cache, 54882 tokens in, 126495 out, about $0.1809

## lukas-1-r1: NOT acceptable

Asked: We want to go to Japan in 2027. Keep an eye on that for me.

- kind: 
- question: We want to go to Japan in 2027. Keep an eye on that for me.
- 5.3 s, apertus-v1-5-70b

**Japan 2027**

- Sparkonto Langfristig (savings_goal): 37'566.29
- Bill, due 10.12. (bill): 600.00

- judge about_customer: The second tile is a real upcoming bill, but the Engadin holiday-flat deposit (January 2027 ski trip) has nothing to do with the Japan request, and a strong signal not about the request does not belong on this board.
- judge coherent: A board named 'Japan 2027' that mixes the Japan savings goal with an unrelated Engadin ski-holiday deposit is not about the request and nothing else.
- service tiles_resolved: 2 of 3 resolved; dropped: Sparkonto Langfristig
- service titles_checked: default title for: Bill, due 10.12.

## lukas-1-r2: NOT acceptable

Asked: What do my subscriptions cost me?

- kind: 
- question: What do my subscriptions cost me?
- 6.6 s, apertus-v1-5-70b

**Subscriptions**

- Subscriptions (regular_payments): 252.95

- judge hero_question: The hero presents the three account-drafted payments (gym, mobile, internet) totalling 252.95 as the answer to "what do my subscriptions cost me", but the persona says Lukas also pays streaming and news subscriptions monthly on his Visa Gold, so the board undercounts his real subscription costs instead of answering the request.
- service titles_checked: default title for: Bill, due 14.12.; Bill, due 12.01.

## jana-1-r1: acceptable

Asked: How do I get my emergency fund to 10'000?

- kind: 
- question: How do I get my emergency fund to 10'000?
- 5.7 s, apertus-v1-5-70b

**Notgroschen**

- Sparkonto (savings_goal): 4'919.20

- service tiles_resolved: 1 of 2 resolved; dropped: Sparkonto

## jana-1-r2: acceptable

Asked: When have I repaid my parents?

- kind: 
- question: When have I repaid my parents?
- 5.8 s, apertus-v1-5-70b

**Parents' loan**

- Regular payments (regular_payments): 150.00
- Repaid each month (monthly_spending): 125.00

- service tiles_resolved: 2 of 3 resolved; dropped: Regular payments

## daniela-1-r1: NOT acceptable

Asked: What does Lina cost me every month?

- kind: 
- question: What does Lina cost me every month?
- 3.4 s, apertus-v1-5-70b

**What Lina costs**

- What Lina costs (regular_payments): 440.00
- Bill, due 10.12. (bill): 348.00

- judge hero_question: The hero shows a single one-off dentist bill of CHF 440 rather than the recurring monthly cost of Lina the request asks for, even though the data holds her monthly Hort und Mittagstisch payments that would answer it far more directly.
- judge titles: The hero title 'What Lina costs' claims the monthly answer while its tile shows only one dentist payment, and 'Bill, due 10.12.' is a generic label that does not name the childcare it carries, so the titles do not match what the tiles show.
- judge coherent: The board answers a question about every month with two individual upcoming bills and never shows the recurring monthly picture, and since the data plainly holds more about the request the two-tile board does not meet the small-board condition.
- service tiles_resolved: 3 of 4 resolved; dropped: Bill, due 30.11.; Bill, due 30.11.
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 10.12.

## daniela-1-r2: NOT acceptable

Asked: Which bills and reminders are open?

- kind: 
- question: Which bills and reminders are open?
- 5.0 s, apertus-v1-5-70b

**Open bills**

- Open bills (regular_payments): 440.00
- Bill, due 10.12. (bill): 348.00

- judge titles: The hero title 'Open bills' promises a list of open bills but its payload holds only the dentist's, with the second open bill sitting in the next tile, and no title ever mentions the reminder or its fee that her question named.
- judge coherent: A two-tile board passes only when the data holds nothing more about the request, but the dentist's second reminder with its fee — the reminder she asked about and one the brief confirms as its own detail tile — is never surfaced, so the thin board answers only the bills half of 'bills and reminders'.
- service tiles_resolved: 4 of 5 resolved; dropped: Bill, due 30.11.; Bill, due 30.11.; Bills until payday
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 10.12.

## marco-1-r1: acceptable

Asked: What does the house cost us?

- kind: 
- question: What does the house cost us?
- 7.0 s, apertus-v1-5-70b

**The house**

- The house (regular_payments): 1'681.40
- Mortgage (mortgage): 862'500.00
- Sparkonto Haus (savings_goal): 19'350.30

## marco-1-r2: acceptable

Asked: What should we decide about the mortgage?

- kind: 
- question: What should we decide about the mortgage?
- 25.5 s, apertus-v1-5-70b

**Mortgage decision**

- Mortgage (mortgage): 862'500.00
- Regular payments (regular_payments): 1'050.00

