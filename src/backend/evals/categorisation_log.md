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
| v4 | five worked examples of the hardest borders, with made-up names | 95.4 % | 248 | 96.0 / 27.6 / 78.1 % | 61.1 % / 5.8 % |
| v5 | high only when the payee sells one kind of thing or the text names it; medium for shops, stations, telecoms and venues where it depends | 95.2 % | 204 | 96.5 / 73.4 / 76.0 % | 65.0 % / 9.7 % |
| v6 | low for a payee Apertus does not know whose name says nothing (rejected, reverted) | 95.2 % | 217 | 96.3 / 77.3 / 78.4 % | 59.5 % / 9.4 % |
| v7 | a phone company's home package stays housing; the Mensa is restaurants, "not children" | 93.9 % | 286 | 95.2 / 71.2 / 79.3 % | 76.6 % / 10.7 % |
| v8 | v7 with the Mensa named among canteens, "also at a university" | 94.8 % | 224 | 96.2 / 72.7 / 82.9 % | 73.8 % / 10.5 % |
| **v9** | v5 with only the home-package example of v7 | **95.5 %** | **182** | 96.9 / 72.8 / 82.0 % | 70.8 % / 9.8 % |

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

## v4

The examples use names that appear nowhere in the gold set (Quickline, Agrola, an invented drugstore and
swimming club, a concert bar). Fixed: fuel stations, drugstores, most home internet. During this run
the gateway timed out 148 calls between 20:50 and 21:30, so Jana's last 401 bookings were categorised
by a further call after the run; the prompt was the same.
Left at high: a bar with concerts (Rössli Reitschule, 20, a border the blind labeller also split on),
Swisscom home internet (19), food delivery and toy shops, «Grill» shares as restaurants.

## v5

Accuracy stays (95.4 → 95.2 %, within a run's noise), certainty starts to mean something: medium is now
right 73 % of the time instead of 28 %, wrong but high drops to 204. Left at high: payees Apertus cannot
know from the name (a vegetarian buffet, a food delivery service, a bar it reads as a bookshop), Swisscom
"inOne home", and the university Mensa read as school (children).

## v6 (rejected)

Apertus kept rating unknown payees high (Tibits, Smood, Glacier du Port), and the review rule caught
fewer wrong bookings (65.0 → 59.5 %). Reverted to v5. The first draft named two tune payees as examples;
they were replaced by made-up names before the run.

## Noise

v5 ran twice unchanged: 95.2 and 95.1 %, 204 and 212 wrong but high, review catches 65.0 and 69.3 %;
298 wrong bookings are the same in both runs, 13 differ. So differences under about half a point of
accuracy, 15 wrong-but-high bookings or 5 points of review catches are noise: v4 and v5 are equal on
accuracy, v5's calibration gain and v6's loss are real.

## v7

The home-package example worked: Swisscom and Sunrise home bills 35 → 15 wrong. The Mensa sentence
backfired: with "not children" in it, 71 Mensa lunches went to children and 26 to housing (10 before).
v8 keeps the telecom line and names the Mensa among canteens without a negation.

## v8

Mensa still 52 wrong (35 children, 17 housing). Counting Mensa and telecom errors per version shows the
v2 wording "canteens and university Mensa" had 0 Mensa errors (7 to 10 once v4 added the examples), and
every rewrite since made it worse; the telecom example is what helped (28 to 30 → 15 to 16). v9 is v5
with only the telecom example changed.

| | v1 | v2 | v3 | v4 | v5 | v5b | v7 | v8 |
|---|---|---|---|---|---|---|---|---|
| Mensa wrong | 91 | 0 | 1 | 7 | 10 | 10 | 97 | 52 |
| Swisscom/Sunrise wrong | 67 | 77 | 68 | 23 | 30 | 28 | 15 | 16 |

## v9 (kept)

Mensa 5 wrong, telecom 16. What is left are payees Apertus cannot know from their name (a bar in a
cultural centre read as leisure, a vegetarian buffet, a bar read as a bookshop, a food delivery
service, a toy shop read as general shopping) and the borders («Grill», «Geschenk», a children's ski
school). Fixing those in the prompt would mean naming the payees, which is a payee rule; the customer's
correction is the remedy, so step 4 measures it.

## The customers review in the category center

`categorisation_review.py` plays each customer once through the center's review list on top of v9,
for half of their tune payees ("reviewed"); the other half ("untouched") is never corrected, so
carry-over is measured on payees nobody touched, on the same bookings with and without the
corrections. A payee with one true category gets one "All are X"; a payee whose bookings rightly differ
gets "Right" or a booking-only change per flagged row.

| Customer | Flagged | Clicks | Payee corrections | Booking corrections | Bookings changed |
|---|---|---|---|---|---|
| Lukas | 176 | 60 | 12 | 48 | 424 |
| Jana | 164 | 24 | 12 | 12 | 437 |
| Daniela | 111 | 26 | 5 | 21 | 56 |
| Marco | 165 | 47 | 9 | 38 | 129 |

Then the tune split was categorised again with the corrections kept:
- One correction fixes a payee for good: all 927 bookings of the 38 corrected payees came back right,
  from the payee memory, without Apertus. Scored apart, never as model accuracy.
- A payee whose bookings rightly differ cannot be fixed per payee; its booking corrections hold for those
  bookings, and new ones need review again. No payee correction was put on such a payee, so none broke
  a booking that rightly belongs elsewhere.
- No carry-over: untouched payees 95.3 → 95.2 %, wrong but high 104 → 121, both within noise. The
  correction examples in the prompt neither help nor clearly hurt similar payees.
- Review effort falls by 41 % after one pass (616 → 362 flagged bookings): Lukas 176 → 86, Jana
  164 → 97, Daniela 111 → 96, Marco 165 → 83.

So the teacher-tuned prompt does the work on payees nobody has seen, and the payee memory removes what
the customer has corrected; both stay. The examples in the prompt stay as they are, since they cost
nothing measurable.

## Held out, measured once at the end

2,316 bookings of 120 payees, never used for a decision. Run through the backend with v0 at the start
(before any change) and with v9 at the end, once with the payee memory and examples from the tune
review kept, once without.

| | v0 | v9 | v9 with the tune corrections |
|---|---|---|---|
| Accuracy | 77.6 % | 88.6 % | 89.9 % |
| Wrong but high | 383 | 163 | 182 |
| Accuracy at high / medium / low | 82.2 / 14.3 / 29.3 % | 92.1 / 54.6 / 75.0 % | 91.6 / 61.8 / 89.3 % |
| Review catches / load | 66.0 % / 19.3 % | 58.7 % / 17.5 % | 41.7 % / 13.6 % |
| Lukas / Jana / Daniela / Marco | 76 / 65 / 65 / 92 % | 82 / 96 / 83 / 97 % | 85 / 95 / 83 / 98 % |

- No sign of overfitting: tune and held out are 7 points apart before (84.7 / 77.6 %) and after
  (95.5 / 88.6 %); the gain is the same on both (+10.8 / +11.0 points). The held-out payees are harder,
  above all Lukas's travel bookings abroad.
- The correction examples make Apertus surer on payees nobody corrected without making it much more
  right (+1.3 points), so the review rule catches far fewer of its errors (58.7 → 41.7 %). The payee
  memory is worth keeping; the examples in the prompt are not.
- Not yet where it should be: 88.6 % against a ceiling of about 98.8 %, and the review rule catches
  59 % of the errors. Tuning on after this run would be tuning with the held-out result in mind, so a
  next round needs a fresh held-out part.
