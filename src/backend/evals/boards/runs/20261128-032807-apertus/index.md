# Boards gate, apertus

0 of 8 acceptable.

- lukas: 0 of 2
- jana: 0 of 2
- daniela: 0 of 2
- marco: 0 of 2

OpenRouter: 16 calls sent, 0 from cache, 52332 tokens in, 48761 out, about $0.0719

## lukas-1-r1: NOT acceptable

Asked: We want to go to Japan in 2027. Keep an eye on that for me.

- kind: A young professional building wealth with a large investment portfolio and multiple savings pots.
- question: We want to go to Japan in 2027. Keep an eye on that for me.
- 7.4 s, apertus-v1-5-70b

**Japan 2027**

- Japan fund (savings_goal): 37'566.29

- tile_count: tiles per board: [1]

## lukas-1-r2: NOT acceptable

Asked: What do my subscriptions cost me?

- kind: A young professional building wealth with a large investment portfolio and multiple savings pots.
- question: What do my subscriptions cost me?
- 7.4 s, apertus-v1-5-70b

**Bills due soon**

- Bills due soon (due_soon): 8'302.59

- tile_count: tiles per board: [1]
- judge hero_question: Lukas asked what his subscriptions cost him, but the hero lists payments due in the next 30 days (rent, ETF savings plan, holiday deposit, credit card bill), which does not answer that question at all.
- judge about_customer: The data is genuinely Lukas's, but for a request board every tile must be about the request, and a bills-due list is a strong signal about something other than his subscriptions.
- judge coherent: The board tells one story, but it is the story of upcoming bills rather than the subscription costs the request was about, so it is not coherent with the request.

## jana-1-r1: NOT acceptable

Asked: How do I get my emergency fund to 10'000?

- kind: Young professional starting out with negative cash flow
- question: How do I get my emergency fund to 10'000?
- 5.5 s, apertus-v1-5-70b

**Emergency fund progress**

- Emergency fund (savings_goal): 4'919.20

- tile_count: tiles per board: [1]

## jana-1-r2: NOT acceptable

Asked: When have I repaid my parents?

- kind: Young professional starting out with negative cash flow
- question: When have I repaid my parents?
- 5.4 s, apertus-v1-5-70b

**Until payday**

- Tax bill (bill): 1'180.00

- tile_count: tiles per board: [1]
- judge hero_question: The hero is a provisional tax bill, which answers nothing about when Jana will have finished repaying her parents, the very question she asked.
- judge about_customer: The tax bill is a real signal in Jana's life but is not about the requested parents' loan repayment, and a strong off-request signal does not belong on a request board.
- judge coherent: A board named 'Until payday' showing one tax bill is about neither the parents' repayment request nor any coherent theme around it, and the data clearly holds more about the request (her monthly repayments to her parents).

## daniela-1-r1: NOT acceptable

Asked: What does Lina cost me every month?

- kind: single mother with tight month-to-month cash flow
- question: What does Lina cost me every month?
- 5.1 s, apertus-v1-5-70b

**Lina's monthly bills**

- Bills until payday (bills_until_payday): 2'950.20
- Dentist bill due (bill): 440.00

- judge hero_question: The request is what Lina costs per month, but the hero shows all household bills until payday (rent, washing-machine instalment, mobile, internet included) totalling CHF 2'950.20, which answers the 'will my money last' question, not Lina's monthly cost.
- judge about_customer: The dentist bill for Lina fits the request, but the hero list is mostly household spending unrelated to Lina, and a strong signal that is not about the request does not belong on a request board.
- judge coherent: The board tells one story about bills due before payday rather than about what Lina costs each month, so it is not about the request.

## daniela-1-r2: NOT acceptable

Asked: Which bills and reminders are open?

- kind: single mother with tight month-to-month cash flow
- question: Which bills and reminders are open?
- 4.8 s, apertus-v1-5-70b

**Until payday**

- Emergency fund (savings_goal): 284.25
- Dentist bill due (bill): 440.00
- Bills until payday (bills_until_payday): 2'950.20

- judge hero_question: The hero is the emergency fund tile, which does not answer 'Which bills and reminders are open?' — the bills list or the dentist reminder would answer it directly.
- judge about_customer: The dentist bill and bills list are about the request, but the emergency fund tile is a strong signal about her savings buffer, not about open bills and reminders, so it does not belong on a request board.
- judge coherent: The board should be about the open bills and reminders and nothing else, but the emergency fund tile pulls in a second theme, breaking the request's focus.

## marco-1-r1: NOT acceptable

Asked: What does the house cost us?

- kind: Family with a house and a decision ahead on their mortgage tranche
- question: What does the house cost us?
- 5.8 s, apertus-v1-5-70b

**The house savings**

- House reserve (savings_goal): 19'350.30

- tile_count: tiles per board: [1]
- judge hero_question: The hero shows the house savings reserve against a CHF 20'000 goal, which answers whether the reserve is big enough, not the request of what the house costs in interest, amortisation and maintenance.
- judge about_customer: The tile uses the customer's real house savings account, but it is a strong signal about the savings reserve rather than about the request, and the rubric says such a signal does not belong on a request board.
- judge coherent: The board is about the savings reserve rather than the request, and nothing on it shows what the house costs even though the data holds mortgage interest, amortisation and maintenance transactions.

## marco-1-r2: NOT acceptable

Asked: What should we decide about the mortgage?

- kind: Family with a house and a decision ahead
- question: What should we decide about the mortgage?
- 5.3 s, apertus-v1-5-70b

**The house**

- Mortgage decision (mortgage): 862'500.00

- tile_count: tiles per board: [1]

