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
