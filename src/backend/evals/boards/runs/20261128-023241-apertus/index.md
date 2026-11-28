# Boards gate, apertus

0 of 1 acceptable.

- daniela: 0 of 1

OpenRouter: 2 calls sent, 0 from cache, 7836 tokens in, 21897 out, about $0.0312

## daniela-1: NOT acceptable

- kind: Alleinerziehende mit knappem Monatsbudget, die jede Woche aufs Geld schauen muss
- question: Wie viel Geld ist am Tag vor dem nächsten Lohn noch auf dem Konto?
- 5.1 s, apertus-v1-5-70b

**Kurz vor dem nächsten Lohn**

- Was bleibt am Tag vor dem Lohn? (payday_balance): 124.96
- Steigende regelmäßige Kosten (regular_payments): 443.00
- Die größten monatlichen Ausgaben (regular_payments): 2'432.40
- Monatlicher Geldfluss (income_and_spending): -370.77
- Income from Patrick Rüegg (expected_income): 1'050.00

- judge titles: "Income from Patrick Rüegg" is an English auto-label that ignores her term "Unterhalt" and the tile's actual point (the payment has not arrived), and "Steigende regelmäßige Kosten" claims a rise that the tile's two plain payments never show.
- judge not_empty_or_repeated: Tile 2's two payments (Betreuung Schule CHF 348 and Steueramt CHF 95) reappear verbatim inside tile 3's six-row list, so the board shows the same payments twice and tile 2 adds nothing.
- service boards_full: Kurz vor dem nächsten Lohn: 1 added

