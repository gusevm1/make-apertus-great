# Boards gate: what changed and what it did

Runs are in `runs/<timestamp>-<model>/`, each with an `index.md`.

## Run 1, GLM, 7 of 12

- Daniela 3 of 3, Marco 3 of 3, Jana 1 of 3, Lukas 0 of 3.
- Lukas: the judge failed the net worth hero against the persona's line
  "where does my money go – and am I on track". The brief and the confirmed
  mockup make net worth his hero, so the rubric now carries the brief's two
  confirmed heroes as ground truth.
- Jana: the model made her tax instalment the question (it was signal S1, at
  strength 55); a bill is no headline, so the service moved another tile first
  and the hero did not match her strongest signals.
- Changes: one-off bills drop to strength 35 (reminders stay at 85), a 3a far
  from the maximum drops to 35; signals that can carry a headline are marked
  "(can be the hero)" in the prompt and the hero is to come from the three
  strongest of them; when the model's hero is no headline, the service now
  prefers the strongest headline signal over any headline tile.
- Earlier, in a single Daniela trial: a merchant tile named a shop with no
  bookings in its period ("Swimming and toys"). The digest now lists the
  largest payees for exactly the periods of merchant_spending, and the service
  narrows a merchant tile to the shops it found.

## Run 2, GLM, 10 of 12

- Daniela 3, Lukas 3, Jana 2, Marco 2. The hero changes worked: Jana's boards
  now open on what is left each month, Lukas's on what he owns.
- Both failures were the judge's "not_empty_or_repeated": a regular_payments
  tile listed payments another list on the board already showed (Jana's KPT
  premium twice, Marco's fixed costs inside "Due in the next 30 days").
- A model typo in a payee ("Elektrizitätswerk" for "...werke") dropped a whole
  tile.

## Run 3, GLM, 9 of 12 (same plans from the cache, new validation)

- Fixed: the service leaves out of a list argument (payees, merchants, account
  ids) the names that do not resolve alone, instead of dropping the tile.
- Fixed: a regular_payments tile that repeats most payments of an earlier
  list on the board is dropped.
- New failures showed the overlap is wider: the board repair added due_soon
  beside bills_until_payday (the same six bills for Jana), a single bill
  repeated a row of a regular_payments tile (Marco's water bill), and a net
  worth without a depot only summed the accounts tile beside it.
- Changes: one overlap rule for every payment list (due_soon,
  bills_until_payday, regular_payments, bill): a tile whose payments an
  earlier tile on the board mostly shows is dropped, and the repair skips
  such tiles; a single bill may stand beside the list it is in (the confirmed
  Daniela board does this with the dentist reminder). net_worth is dropped and
  no longer offered as a signal when only the accounts have value. The prompt
  says both rules.

## Run 4, GLM, 11 of 12

- Daniela 3, Jana 3, Marco 3, Lukas 2.
- Lukas 3 opened on income_and_spending: "months in the red" was one of his
  three strongest headline signals (strength 45), though 49'000 in savings
  stand beside it. Change: months in the red weigh 45 only when the savings
  cover less than three months of spending, else 25.

## Runs 5 and 6, GLM, 11 of 12 each

- Lukas 3, Jana 3, Daniela 3, Marco 2.
- Marco 2 titled a due_soon tile "Due in December" while its rows start on
  27 November. Change: a title may name a month only on a merchant tile whose
  period is that one month, or on a card bill of that month; otherwise the
  default title. Logged as a failed `titles_checked`.
- Then the judge failed the same board for "Left before payday": that
  question belongs to a customer living from salary to salary, not to a
  homeowner with 80'000 in savings (it said the same of Lukas in run 4).
  Change: the payday signal carries a tile only when the payday is tight, the
  catalogue says so, and on first boards the service drops a payday_balance
  tile for a customer without a tight payday.

## Run 7, GLM, 12 of 12 (new cold samples, `--tag r7-`)

## Run 8, GLM, 9 of 12 (new cold samples, `--tag r8-`)

- Lukas 1, Daniela 2, Jana 3, Marco 3. The judge varies: the gate holds 12 of
  12 on one sample and 9 to 11 on others.
- Lukas 2 and 3 put the card bill on a "Travel" board; the judge failed the
  board's theme. Change: the prompt says every tile of the second board is
  about its theme.
- Daniela 1: the after-school care payment sat on both boards (the overlap
  check worked per board only), and the judge, once in six Daniela boards,
  failed the dentist bill beside "Bills until payday", which the confirmed
  mockup shows. Changes: the overlap check covers earlier boards too; the
  rubric names the confirmed bill-beside-list pattern.

## Apertus, first run, 2 of 12 (before the run 8 changes)

See the final report; the run is in `runs/20261128-015722-apertus/`.

## Run 9, GLM, 7 of 12 (`--tag r9-`): the cross-board check backfired

- Daniela 0 of 3: the after-school care left the "Lina" board for repeating a
  row of "Bills until payday", and the repair filled the board with the
  household's fixed costs, which the judge rightly failed as off theme.
- Marco 1: GLM returned an empty answer twice (counted as a failure).
- Changes: the overlap check is per board again; a second board that ends
  with fewer than three tiles is left out instead of being repaired from
  signals off its theme; only the main board (and a requested board) is
  repaired.

## Run 10, GLM, 12 of 12 (new cold samples, `--tag r10-`, final code)

- Lukas 3, Jana 3, Daniela 3, Marco 3. `runs/20261128-021601-glm/`.
- Over the night's cold samples on final or near-final code: 12, 9, 7
  (regression, reverted) and 12 of 12. The judge alone varies by one to three
  boards per run of twelve.
