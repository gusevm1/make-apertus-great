# Boards gate, apertus

1 of 8 acceptable.

- lukas: 0 of 2
- jana: 1 of 2
- daniela: 0 of 2
- marco: 0 of 2

OpenRouter: 16 calls sent, 0 from cache, 62752 tokens in, 90735 out, about $0.1314

## lukas-1-r1: NOT acceptable

Asked: We want to go to Japan in 2027. Keep an eye on that for me.

- kind: 
- question: We want to go to Japan in 2027. Keep an eye on that for me.
- 6.2 s, apertus-v1-5-70b

**Japan 2027**

- Japan 2027 (savings_goal): 37'566.29
- 3 dedicated savings pots (account_balances): 48'983.35
- Monthly fixed costs (regular_payments): 3'542.85

- judge about_customer: The third tile's rent, health insurance, gym and telecom bills (and largely the taxes and reserves pots beside it) are strong signals that are not about the Japan-trip request at all.
- judge coherent: The board does not stay on the request: the Japan savings hero sits next to a generic monthly fixed-costs list, so the whole is not one story about watching the trip.
- service tiles_resolved: 3 of 4 resolved; dropped: Japan 2027 savings goal reached

## lukas-1-r2: NOT acceptable

Asked: What do my subscriptions cost me?

- kind: 
- question: What do my subscriptions cost me?
- 6.8 s, apertus-v1-5-70b

**Subscriptions**

- Regular monthly payments (regular_payments): 3'542.85
- Monthly income (expected_income): 2'200.00
- Monthly cash flow (income_and_spending): -199.61
- Japan 2027 (savings_goal): 37'566.29

- judge hero_question: The request was what his subscriptions cost him, but the hero totals all regular monthly payments (CHF 3'542.85, dominated by CHF 2'800 rent plus health insurance), so the figure a demo audience would read as his subscription cost is wrong and the actual subscriptions (streaming, news, gym) are not isolated.
- judge about_customer: Tiles 2 to 4 (Sara's monthly transfer, the six-month cash flow and the Japan savings goal) are true facts about Lukas's life but have nothing to do with the cost of his subscriptions, and a strong signal off the request does not belong on a requested board.
- judge coherent: A board named Subscriptions that mixes upcoming payment dates with partner income, overall monthly cash flow and a long-term savings goal does not tell one story about the request.

## jana-1-r1: acceptable

Asked: How do I get my emergency fund to 10'000?

- kind: 
- question: How do I get my emergency fund to 10'000?
- 6.1 s, apertus-v1-5-70b

**Emergency fund**

- Emergency fund (savings_goal): 4'919.20
- bills (due_soon): 3'155.45
- Monthly cash shortfall (income_and_spending): 250.82

- service tiles_resolved: 3 of 4 resolved; dropped: Emergency fund at 49%

## jana-1-r2: NOT acceptable

Asked: When have I repaid my parents?

- kind: 
- question: When have I repaid my parents?
- 9.2 s, apertus-v1-5-70b

**Open bills**

- Sparkonto (savings_goal): 4'919.20
- Your accounts (account_balances): 11'819.38
- Regular payments (regular_payments): 150.00
- Due in 30 days (due_soon): 3'155.45
- Bill, due 30.11. (bill): 1'180.00

- judge hero_question: The hero is a savings-goal tile for her emergency fund, which says nothing about when she will have repaid her parents; the closest signal the data holds (the CHF 150 standing payment to Andrea Widmer) sits third, and no quiet line explains that the bank cannot know the loan's remaining amount.
- judge about_customer: Only the Andrea Widmer payment tile is about the request; the savings goal, account balances, due-in-30-days list and the tax bill are real facts about Jana but off-request filler that the rubric says does not belong on a requested board.
- judge coherent: The board tells a generic open-bills and savings story rather than being about the one theme the customer asked for, repaying her parents, which appears only in a single buried tile.
- service titles_checked: default title for: Repaid private loan to Andrea Widmer; 6 upcoming payments totaling CHF 3'155.45; Tax bill due 30.11.2026: CHF 1'180.00

## daniela-1-r1: NOT acceptable

Asked: What does Lina cost me every month?

- kind: 
- question: What does Lina cost me every month?
- 5.1 s, apertus-v1-5-70b

**Lina's savings**

- Lina's savings (account_balances): 3'470.50
- Two savings accounts exist (account_balances): 3'754.75
- Dentist bill for Lina due (bill): 440.00
- Income and spending (income_and_spending): -370.77

- judge hero_question: The hero shows the balance of Lina's youth savings account — money given to Lina that Daniela does not touch — which is not a cost and does not answer what Lina costs her every month.
- judge about_customer: Only the dentist bill is a real cost for Lina; the two savings-account tiles and the whole-household income-and-spending tile are not about the request and do not belong on this board.
- judge titles: 'Two savings accounts exist' reads like a database observation rather than a title a person would write, and none of the titles speak to the question of Lina's monthly costs.
- judge not_empty_or_repeated: The second tile repeats the Lina savings balance of CHF 3'470.50 already shown alone in the first tile, merely adding the emergency fund in a pointless existence listing.
- judge coherent: The board jumps from savings balances to one due bill to total household cashflow without ever addressing Lina's monthly costs, so it tells no single story about the request.
- service titles_checked: default title for: Monthly spending exceeds income

## daniela-1-r2: NOT acceptable

Asked: Which bills and reminders are open?

- kind: 
- question: Which bills and reminders are open?
- 10.4 s, apertus-v1-5-70b

**Regular payments**

- Regular payments (regular_payments): 2'950.20
- Privatkonto (account_balances): 3'075.16
- Left before payday (payday_balance): 124.96

- judge about_customer: The Privatkonto balance tile and the payday-runway tile with the child-support alternative are strong signals about Daniela's general situation but are not about the open bills and reminders she asked for, so they do not belong on this request board.
- judge coherent: The board starts on the requested list of open bills but then drifts into Daniela's signature payday-survival story, so it is not about the request and nothing else.
- service titles_checked: default title for: Upcoming bills and reminders due before next payday; Zahnarztpraxis Neuwiesen due 30.11.2026; 8 upcoming payments totalling CHF 2'950.20 before salary on 24.12.2026; Only CHF 124.96 left on Privatkonto before next salary

## marco-1-r1: NOT acceptable

Asked: What does the house cost us?

- kind: 
- question: What does the house cost us?
- 6.7 s, apertus-v1-5-70b

**The house**

- The house (savings_goal): 19'350.30
- Mortgage (mortgage): 862'500.00
- Income and spending (income_and_spending): -246.13
- Regular payments (regular_payments): 3'502.30

- judge hero_question: The hero shows the house savings account's balance against its CHF 20'000 reserve goal, which answers whether the repair reserve is enough, not what the house costs — the mortgage tile with its interest, or a summed annual cost of interest, amortisation and maintenance, is what the request asks for and the data holds.
- judge about_customer: The six-month income-and-spending tile shows the family's entire budget including groceries and everyday spending rather than the cost of the house, so a strong signal that is not about the request sits on the board.
- judge coherent: The board mixes the house story (reserve, mortgage, house-related payments) with the family's overall budget, so it is not about the request and nothing else.
- service tiles_resolved: 4 of 5 resolved; dropped: House reserve nearly met
- service titles_checked: default title for: Mortgage tranche matures in March 2027; Monthly cash flow slightly negative; House-related bills and reserves

## marco-1-r2: NOT acceptable

Asked: What should we decide about the mortgage?

- kind: 
- question: What should we decide about the mortgage?
- 5.5 s, apertus-v1-5-70b

**The house**

- The house (savings_goal): 19'350.30
- Mortgage (mortgage): 862'500.00
- Mortgage and house reserve (regular_payments): 1'950.00

- judge hero_question: The hero shows the Sparkonto Haus reserve at 96.8% of its CHF 20'000 goal, while the request — what to decide about the mortgage — is answered most directly by the second tile, the CHF 350'000 8-year fixed tranche maturing 31 March 2027.
- judge about_customer: The savings-goal hero (and the Sparkonto-Haus row in the payments tile) is a strong signal about the house-maintenance reserve, which is a real part of Marco's life but not about the mortgage decision he asked about, so it does not belong on this requested board.
- judge coherent: The board drifts between the maintenance-reserve story and the mortgage instead of staying on the request alone, and nothing on it surfaces the actual decision the customer asked about — the 15 December deadline or the fixed-versus-SARON choice.
- service tiles_resolved: 3 of 4 resolved; dropped: House reserve nearly met at CHF 19'350
- service titles_checked: default title for: Mortgage tranche matures 31.03.2027

