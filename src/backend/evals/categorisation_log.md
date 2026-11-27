# Categorisation prompt log

Gold set: `categorisation_gold.jsonl`, 8,623 spending bookings of the four customers, labelled one by one by
Claude (Opus 5.5) against `categorisation_rubric.md`. Held out: one payee in four per customer (2,316
bookings, 120 payees), fixed in commit 7570a89 before the first run and never used for tuning.

Gold quality: a second Opus labeller relabelled 500 rows blind (weighted to the batches written per payee
and to payees whose rows vary) and agreed on 494 (98.8 %). The six disagreements are real borders: club
venues (restaurants or leisure), a night train (transport or leisure), a gift for a child's party
(shopping or children). That is the ceiling a model can reach on this set.

Each run categorises the tune split through the running backend on the real gateway (`LLM_NAME`, the
model the feature uses, temperature 0). Accuracy counts a booking without an answer as wrong. "Wrong but
high" is the worst failure, because the category center sends a booking to review only when it is not
high or not in its payee's usual category. "Review catches" is the share of wrong bookings that rule
sends to review; "review load" the share of all model bookings it sends.

| Version | Hypothesis | Tune accuracy | Wrong but high | Accuracy at high / medium / low | Review catches / load |
|---|---|---|---|---|---|
| v0 | today's prompt (#176) | 84.7 % | 733 | 87.7 / 22.9 / 46.0 % | 70.7 % / 14.0 % |
| v1 | each answer copies its row's payee before the category; 25 rows per call instead of 50 | 89.6 % | 418 | 92.8 / 37.5 / 52.0 % | 67.2 % / 12.0 % |
| v2 | every category described by what was paid for, with the borders spelled out | 91.2 % | 304 | 94.8 / 37.2 / 33.9 % | 67.2 % / 9.6 % |
| v3 | a payment to a private person goes by the purpose in its message | 94.1 % | 334 | 94.6 / 38.7 / 76.1 % | 47.0 % / 6.4 % |

v0 held out: 77.6 %, 383 wrong but high, review catches 66.0 % at 19.3 % load.

## v0 findings

- At 50 rows per call the median call took 50 s against the client's 60 s timeout: 23 of 173 calls timed
  out and Lukas got no category for a third of his bookings on the first pass. The runner calls the
  categorisation again for skipped rows, as the product does on the next open.
- Inside long batches Apertus drops a row and gives each later ref the previous row's category
  (Ostello's leisure on Too Good To Go, a pizzeria's restaurants on Trenitalia and Conad). Identical Coop
  bookings came back as transport, housing or shopping with high certainty.
- Conventions the prompt never states: TWINT to a person by its message, drugstores, fuel stations,
  canteens and food delivery, the Serafe fee, children's activities, marketplaces, gyms, cash
  withdrawals and bank fees.
- Stated but missed: home internet (Swisscom, Sunrise) as housing, Dropbox and iCloud as software.

## v1

The payee copy ties each answer to its row: on six probe batches of 50 it lifted accuracy from 85.0 to
91.0 %, but the longest call took 116 s. At 25 rows the copy gives 89.3 % with calls under 35 s; 25 rows
without the copy gives 85.7 %, a copy of the payee's first word only 81.0 %. First-pass skips fell from
about 1,200 bookings to 11, Lukas's run from 635 s to 130 s.

## v2

Fixed: the university Mensa (groceries and even housing before), children's swimming and ski school,
most drugstores. Left: payments to friends by their message, home internet billed by Swisscom or Sunrise
(still subscriptions, all high), fuel stations (groceries, pulled by "small purchases in petrol-station
shops"), bars that also host events (leisure).

## v3

Payments to friends now follow their message (border bookings 290 → 463 of 620 right, multi-payee 160
→ 325 of 400). But certainty collapsed: 6,157 of 6,259 bookings came back high, so the review rule
catches only 47 % of the wrong ones. Wrong but high, all systematic: home internet from Swisscom and
Sunrise (66), a bar that also hosts concerts (25), fuel stations (24), drugstores (13), children's
swimming and ski courses (18).
