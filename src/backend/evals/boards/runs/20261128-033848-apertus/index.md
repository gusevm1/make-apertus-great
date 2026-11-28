# Boards gate, apertus

0 of 8 acceptable.

- lukas: 0 of 2
- jana: 0 of 2
- daniela: 0 of 2
- marco: 0 of 2

OpenRouter: 6 calls sent, 0 from cache, 19200 tokens in, 48055 out, about $0.0686

## lukas-1-r1: NOT acceptable

Asked: We want to go to Japan in 2027. Keep an eye on that for me.

Error: Apertus timed out

## lukas-1-r2: NOT acceptable

Asked: What do my subscriptions cost me?

Error: Apertus timed out

## jana-1-r1: NOT acceptable

Asked: How do I get my emergency fund to 10'000?

- kind: Young professional starting out with negative cash flow
- question: How do I get my emergency fund to 10'000?
- 49.6 s, apertus-v1-5-70b

**Emergency fund progress**

- Emergency fund (savings_goal): 4'919.20

- tile_count: tiles per board: [1]
- service tiles_resolved: 2 of 3 resolved; dropped: Big bills due soon; Savings pot balance

## jana-1-r2: NOT acceptable

Asked: When have I repaid my parents?

- kind: Young professional starting out with negative cash flow
- question: When have I repaid my parents?
- 46.0 s, apertus-v1-5-70b

**Repaying Parents**

- Loan to Andrea Widmer (regular_payments): 150.00

- tile_count: tiles per board: [1]
- judge hero_question: The hero shows only one upcoming CHF 150 payment due 2026-12-28, which does not answer when the loan from her parents is fully repaid — no remaining balance, payoff date or payment history is shown.
- judge titles: 'Loan to Andrea Widmer' inverts the relationship (Jana borrowed from her parents and is repaying them), uses neither her words ('repay my parents') nor matches the single scheduled payment the tile shows.
- service tiles_resolved: 1 of 2 resolved; dropped: Loan to Andrea Widmer

## daniela-1-r1: NOT acceptable

Asked: What does Lina cost me every month?

Error: Apertus timed out

## daniela-1-r2: NOT acceptable

Asked: Which bills and reminders are open?

Error: Apertus timed out

## marco-1-r1: NOT acceptable

Asked: What does the house cost us?

Error: Apertus timed out

## marco-1-r2: NOT acceptable

Asked: What should we decide about the mortgage?

- kind: Family carrying a house with a decision ahead
- question: What should we decide about the mortgage?
- 165.4 s, apertus-v1-5-70b

**Hypothek Entscheidung**

- Hypothek läuft aus (mortgage): 862'500.00
- Your accounts (account_balances): 83'484.90
- Monatliche Fixkosten (regular_payments): 2'876.30

- judge about_customer: The monthly fixed-costs tile of insurance, tax office and Swisscom bills is real data but has nothing to do with the mortgage decision, so an off-topic signal sits on a board made for the request.
- judge titles: "Your accounts" is a generic English template label among otherwise German titles and does not say what the savings mean for the decision (the possible paydown of the maturing tranche).
- judge coherent: The first two tiles tell one story — which tranche expires and what savings could be used against it — but the third tile wanders off into unrelated household bills, breaking the single thread about the mortgage decision.
- service titles_checked: default title for: Sparkonten für Haus und Familie

