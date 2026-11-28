# Boards gate, apertus

2 of 8 acceptable.

- lukas: 0 of 2
- jana: 0 of 2
- daniela: 1 of 2
- marco: 1 of 2

OpenRouter: 16 calls sent, 0 from cache, 54894 tokens in, 63061 out, about $0.0921

## lukas-1-r1: NOT acceptable

Asked: We want to go to Japan in 2027. Keep an eye on that for me.

- kind: A young professional building wealth with a large investment portfolio and multiple savings pots.
- question: We want to go to Japan in 2027. Keep an eye on that for me.
- 9.0 s, apertus-v1-5-70b

**Japan 2027**

- Japan savings pot (account_balances): 37'566.29
- Bills due soon (due_soon): 8'302.59
- Japan savings goal (savings_goal): 37'566.29

- judge about_customer: The 'Bills due soon' tile is a strong generic signal that is not about the Japan request and does not belong on a board made for this request.
- judge not_empty_or_repeated: The 'Japan savings pot' and 'Japan savings goal' tiles both headline the same CHF 37'566.29 balance of the same account, so one largely repeats the other.
- judge coherent: The off-topic bills-due tile breaks the board's single theme, so the board is not about the Japan request and nothing else.
- service tiles_resolved: 3 of 4 resolved; dropped: Bills due before payday

## lukas-1-r2: NOT acceptable

Asked: What do my subscriptions cost me?

- kind: A young professional building wealth with a large investment portfolio and multiple savings pots.
- question: What do my subscriptions cost me?
- 8.7 s, apertus-v1-5-70b

**Biggest monthly bills**

- Biggest monthly bills (regular_payments): 3'542.85
- Bills due soon (due_soon): 8'302.59

- judge hero_question: The customer asked what his subscriptions cost, but the hero lists his biggest monthly bills including rent and health insurance, which are not subscriptions, and gives no subscription total.
- judge about_customer: The tiles are about Lukas's real payments but not about the request: rent, ETF savings plan, a holiday deposit and the credit card bill are bills, not subscriptions.
- judge coherent: The board tells a story about upcoming bills in general rather than being about the requested topic, subscriptions, and nothing else.
- service titles_checked: default title for: Monthly subscriptions and bills

## jana-1-r1: NOT acceptable

Asked: How do I get my emergency fund to 10'000?

- kind: Young professional starting out with negative cash flow
- question: How do I get my emergency fund to 10'000?
- 6.3 s, apertus-v1-5-70b

**Emergency fund progress**

- Emergency fund (savings_goal): 4'919.20
- Savings pot balance (account_balances): 4'919.20

- judge not_empty_or_repeated: The second tile merely restates the same CHF 4'919.20 Sparkonto balance the hero already shows, adding only the account name and purpose label.
- service tiles_resolved: 2 of 3 resolved; dropped: Big bills due soon

## jana-1-r2: NOT acceptable

Asked: When have I repaid my parents?

- kind: Young professional starting out with negative cash flow
- question: When have I repaid my parents?
- 5.5 s, apertus-v1-5-70b

**Repaying Parents**

- Loan to Andrea Widmer (regular_payments): 150.00
- Monthly Balance (income_and_spending): 250.82

- judge hero_question: The hero shows only the next CHF 150 instalment to her mother with a due date, but the request asks when the loan is fully repaid, and the tile gives no remaining amount, repayment history or payoff date.
- judge about_customer: The second tile is a generic six-month income-and-spending overview that has nothing to do with repaying her parents, so an off-topic tile was added to fill the board.
- judge titles: Both titles are short and free of filler, but "Loan to Andrea Widmer" states the wrong direction (she borrowed from her parents, she did not lend to them) and "Monthly Balance" is a generic label rather than the customer's terms.
- judge coherent: A board answering when she has repaid her parents should be about that and nothing else, yet half of it is a general monthly budget overview, so the board tells no single story about the request.
- service tiles_resolved: 2 of 3 resolved; dropped: Loan to Andrea Widmer

## daniela-1-r1: NOT acceptable

Asked: What does Lina cost me every month?

- kind: single mother with tight month-to-month cash flow
- question: What does Lina cost me every month?
- 7.0 s, apertus-v1-5-70b

**Lina's monthly costs**

- Bills due before next salary (bills_until_payday): 2'950.20
- Dentist bill due soon (bill): 440.00

- judge hero_question: The hero tile lists all bills due before her next salary (rent, internet, washing machine included), which answers Daniela's payday-survival question, not "what does Lina cost me every month".
- judge about_customer: The tiles show Daniela's real data, but the hero is a strong signal about her total bill load rather than the requested Lina-specific monthly costs, and such an off-request signal does not belong on a request board.
- judge coherent: The board as a whole tells the story of bills due before payday with the dentist reminder highlighted, not a coherent board about Lina's recurring monthly costs.
- service titles_checked: default title for: Fixed monthly bills for Lina and home

## daniela-1-r2: acceptable

Asked: Which bills and reminders are open?

- kind: single mother with tight month-to-month cash flow
- question: Which bills and reminders are open?
- 5.6 s, apertus-v1-5-70b

**bill**

- bill (bill): 440.00
- Bills due before payday (bills_until_payday): 2'950.20

- service tiles_resolved: 2 of 3 resolved; dropped: Dentist bill due soon

## marco-1-r1: NOT acceptable

Asked: What does the house cost us?

- kind: Family with a house and a decision ahead on their mortgage tranche
- question: What does the house cost us?
- 7.0 s, apertus-v1-5-70b

**The house**

- Your accounts (account_balances): 83'484.90
- House reserve nearly met (savings_goal): 19'350.30

- judge hero_question: The request asks what the house costs, but the hero tile shows savings account balances, which says nothing about interest, amortisation or maintenance costs.
- judge about_customer: Both tiles are about Marco's real accounts, but neither is about the request: they show savings reserves rather than the annual cost of the house, so they do not belong on a board made for this question.
- judge coherent: The two tiles form a story about savings reserves, not about the requested theme of what the house costs each year, so the board is not about the request.
- service tiles_resolved: 2 of 4 resolved; dropped: Savings pots for house and family; House reserve fund
- service titles_checked: default title for: Savings pots for house and family

## marco-1-r2: acceptable

Asked: What should we decide about the mortgage?

- kind: Family carrying a house with a decision ahead
- question: What should we decide about the mortgage?
- 6.9 s, apertus-v1-5-70b

**Mortgage decision**

- Mortgage tranche expiry (mortgage): 862'500.00
- Your accounts (account_balances): 83'484.90

- service tiles_resolved: 2 of 3 resolved; dropped: House and family savings
- service titles_checked: default title for: Savings pots for house and family

