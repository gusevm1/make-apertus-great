# Boards gate, apertus

2 of 4 acceptable.

- lukas: 0 of 1
- jana: 0 of 1
- daniela: 1 of 1
- marco: 1 of 1

OpenRouter: 8 calls sent, 0 from cache, 30748 tokens in, 101906 out, about $0.1448

## lukas-1: NOT acceptable

- kind: A young professional saving for a specific goal while also building long-term wealth
- question: Will my savings for the Japan trip stay safe and grow until I leave in 2027?
- 8.1 s, apertus-v1-5-70b

**Japan Trip Savings Check**

- Japanreise 2027: CHF 12'000 already saved (savings_goal): 37'566.29
- Total wealth: accounts + securities (net_worth): 131'212.64
- Upcoming credit card bill (card_bill): 3'301.74
- Pillar 3a retirement savings (pillar_3a): 58.00
- Savings accounts breakdown (account_balances): 48'983.35
- Monthly cash flow trend (income_and_spending): -199.61
- Regular partner transfer (expected_income): 2'200.00

- hero_fits: hero savings_goal; strongest headline signals: S1 net_worth, S3 pillar_3a, S5 due_soon
- judge about_customer: Every figure is genuinely Lukas's, but net worth, the Visa bill, pillar 3a, the six-month cash-flow trend and Sara's transfer are strong signals that are not about the Japan-trip request, and the rubric says such signals do not belong on a request board.
- judge coherent: Only the hero really addresses the Japan trip, while net worth, the card bill, pillar 3a, the cash-flow trend and Sara's turn the board into a general wealth-and-spending overview, so a board named «Japan Trip Savings Check» tells no single story.

## jana-1: NOT acceptable

- kind: Young professional starting out with a tight monthly budget
- question: Will my money last until the next salary arrives?
- 7.3 s, apertus-v1-5-70b

**Budget Check Until Next Paycheck**

- What came in and went out each month (income_and_spending): 250.82
- Emergency fund progress (savings_goal): 4'919.20
- Pillar 3a retirement savings (pillar_3a): 3'658.00

- tile_count: tiles per board: [3]
- service tiles_resolved: 4 of 6 resolved; dropped: Loan repayment to Andrea Widmer; Pillar 3a retirement savings; Loan repayment to Andrea Widmer

## daniela-1: acceptable

- kind: single mother living paycheck to paycheck with a child and upcoming bills
- question: Will I have enough money on the day before my next salary to cover all the bills that are due?
- 7.4 s, apertus-v1-5-70b

**Paycheck-to-Paycheck Reality Check**

- Left the day before your salary (payday_balance): 124.96
- Savings pots overview (account_balances): 3'754.75
- Monthly money shortfall (income_and_spending): -370.77
- Late transfer from Patrick Rüegg (expected_income): 1'050.00
- Emergency fund progress (savings_goal): 284.25

- service tiles_resolved: 5 of 6 resolved; dropped: Child's untouchable savings

## marco-1: acceptable

- kind: A family carrying a house with a major decision ahead
- question: Do we have enough left after the next payments to decide whether to renew the mortgage or adjust our budget before the deadline?
- 7.2 s, apertus-v1-5-70b

**Mortgage Decision & Cash Flow**

- The mortgage that must be renewed by 15.12.2026 (mortgage): 862'500.00
- Regular family income (expected_income): 2'600.00
- Monthly cash flow trend (income_and_spending): -246.13
- Savings pots overview (account_balances): 83'484.90
- House maintenance fund progress (savings_goal): 19'350.30

- service tiles_resolved: 5 of 6 resolved; dropped: Family reserve fund

