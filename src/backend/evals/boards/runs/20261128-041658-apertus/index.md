# Boards gate, apertus

3 of 8 acceptable.

- lukas: 0 of 2
- jana: 1 of 2
- daniela: 1 of 2
- marco: 1 of 2

OpenRouter: 16 calls sent, 0 from cache, 56922 tokens in, 127163 out, about $0.1820

## lukas-1-r1: NOT acceptable

Asked: We want to go to Japan in 2027. Keep an eye on that for me.

- kind: 
- question: We want to go to Japan in 2027. Keep an eye on that for me.
- 4.8 s, apertus-v1-5-70b

**Japan 2027**

- Sparkonto Langfristig (savings_goal): 37'566.29
- Japan 2027 (regular_payments): 1'100.00

- judge about_customer: While the savings figures are genuinely Lukas's, the second tile includes a CHF 600 payment to Ferienwohnungen Engadin AG, his Swiss ski-flat booking, which is real but has nothing to do with the Japan 2027 request.
- judge titles: The tile titled 'Japan 2027' lists an unrelated Engadin holiday-flat payment next to the savings transfer, so the title does not match what the tile actually shows.
- judge coherent: A board requested purely to watch the Japan trip should contain nothing else, and the off-topic Engadin ski-flat payment breaks the single-story focus on the request.
- service tiles_resolved: 3 of 4 resolved; dropped: Sparkonto Langfristig; Bill, due 10.12.
- service titles_checked: default title for: Bill, due 10.12.

## lukas-1-r2: NOT acceptable

Asked: What do my subscriptions cost me?

- kind: 
- question: What do my subscriptions cost me?
- 6.3 s, apertus-v1-5-70b

**Subscriptions**

- Where the money goes (monthly_spending): 124.27
- Subscriptions (regular_payments): 252.95
- Bill, due 12.01. (bill): 94.00

- judge hero_question: The hero shows twelve months of SBB spending titled 'Where the money goes', which does not answer what his subscriptions cost; the tile that actually answers the request (CHF 252.95 in regular payments) sits second.
- judge about_customer: The SBB monthly-spending tile is real data from Lukas's life but is not about the subscription request, so an off-topic signal takes up a third of a requested board.
- judge titles: 'Where the money goes' promises a spending overview while the tile shows only SBB payments and never uses the customer's own word 'subscriptions', though the other two titles fit their tiles.
- judge coherent: The board mixes Lukas's general 'where does my money go' story (SBB spending) with the subscription request instead of being about the request and nothing else.
- service titles_checked: default title for: Subscriptions per month (estimated from last 12 months): CHF 1'368.00 (Fitnesspark Zürich Stadelhofen), CHF 94.00 (Swisscom inOne home), CHF 94.00 (Swisscom inOne home January) → total CHF 1'556.00 per month; Bill, due 14.12.; Bill, due 12.01.

## jana-1-r1: NOT acceptable

Asked: How do I get my emergency fund to 10'000?

- kind: 
- question: How do I get my emergency fund to 10'000?
- 6.1 s, apertus-v1-5-70b

**Notgroschen**

- Regular payments (regular_payments): 150.00
- Sparkonto (savings_goal): 4'919.20
- Repaid each month (monthly_spending): 125.00

- judge hero_question: The hero shows a regular 150-franc payment to her mother, which says nothing about getting her emergency fund to 10'000, while the savings-goal tile that directly answers the request sits in second place.
- judge about_customer: Only the Sparkonto goal tile is about the emergency-fund request; the two Andrea Widmer tiles are about repaying her parents' loan, a strong signal that on a requested board does not belong, and the loan disclaimer line equally answers a different question.
- judge not_empty_or_repeated: Tiles 1 and 3 show the same thing in different words — her monthly 150-franc payment to Andrea Widmer — once as an upcoming regular payment and once as monthly history.
- judge coherent: The board tells no single story about reaching 10'000: two of the three tiles and the quiet loan line belong to the separate theme of repaying her parents, leaving only one tile about the request.
- service tiles_resolved: 4 of 5 resolved; dropped: Sparkonto; Notgroschen

## jana-1-r2: acceptable

Asked: When have I repaid my parents?

- kind: 
- question: When have I repaid my parents?
- 20.6 s, apertus-v1-5-70b

**Parents' loan**

- Regular payments (regular_payments): 150.00
- Repaid each month (monthly_spending): 125.00

- service tiles_resolved: 2 of 3 resolved; dropped: Parents' loan

## daniela-1-r1: NOT acceptable

Asked: What does Lina cost me every month?

- kind: 
- question: What does Lina cost me every month?
- 8.0 s, apertus-v1-5-70b

**What Lina costs**

- Where the money goes (monthly_spending): 41.84
- What Lina costs (regular_payments): 1'077.60

- judge hero_question: The hero answers only a sliver of the request — an average of CHF 41.84 a month at the swimming school and pediatrician — so the large headline wildly understates what Lina costs, while the more direct answer, her recurring dentist, childcare and insurance payments totalling CHF 1'077.60, sits in the second tile.
- judge titles: The hero title 'Where the money goes' is generic template wording that names neither Lina nor the two merchants the tile actually shows, so it neither matches its tile nor uses the customer's terms.
- service tiles_resolved: 4 of 5 resolved; dropped: Bill, due 30.11.; Bill, due 30.11.; Bill, due 10.12.
- service titles_checked: default title for: Lina's monthly costs per month (December/January 2026/27): dentist + school care (hort & lunch) bills and upcoming payments for Lina's dentist and school care fees, including any late fees or reminders for her bills this month and next month's due amounts for her school care and dentist bill with reminder status shown for the overdue dentist bill due 30.11.2026 of CHF 440.00 including CHF 20.00 late fee for the second reminder for Lina's dental bill and CHF 348.00 due for school care in December and January 2027 each month for a total of CHF 696.00 for school care over the two months plus the dentist bill of CHF 440.00 for this month's outstanding bill with reminder status shown for the overdue amount due by 30.11.2026; Bill, due 30.11.; Bill, due 10.12.

## daniela-1-r2: acceptable

Asked: Which bills and reminders are open?

- kind: 
- question: Which bills and reminders are open?
- 4.3 s, apertus-v1-5-70b

**Open bills**

- Open bills (regular_payments): 1'255.20

- service tiles_resolved: 4 of 5 resolved; dropped: Bill, due 30.11.; Bill, due 30.11.; Bill, due 10.12.; Bills until payday
- service titles_checked: default title for: Bill, due 30.11.; Bill, due 10.12.

## marco-1-r1: NOT acceptable

Asked: What does the house cost us?

- kind: 
- question: What does the house cost us?
- 19.9 s, apertus-v1-5-70b

**The house**

- The house (regular_payments): 2'581.40
- Mortgage (mortgage): 862'500.00
- Sparkonto Haus (savings_goal): 19'350.30

- judge hero_question: The hero lists the next three house payments — one of them a CHF 900 transfer into the Baumanns' own savings account — instead of the yearly cost of the house (interest, amortisation, maintenance) that Marco is really asking about and that the data holds.
- service titles_checked: default title for: Bill, due 15.01.

## marco-1-r2: acceptable

Asked: What should we decide about the mortgage?

- kind: 
- question: What should we decide about the mortgage?
- 28.2 s, server

**Mortgage**

- Mortgage (mortgage): 862'500.00
- Regular payments (regular_payments): 1'050.00

- service planned_by_model: The model did not answer in time; this board holds what your request names word for word.

