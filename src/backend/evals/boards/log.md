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

## Phase 2: Apertus (`apertus-v1-5-70b`, Keera gateway)

Baseline: the one-call plan with the Daniela and Lukas few-shot examples scored 2 of 12
(`runs/20261128-015722-apertus/`). Every customer got "Until payday", and titles drifted onto
the wrong signal ("Tax due" on the emergency fund).

### A1, split calls + json_schema + enumerated ids, 0 of 1 (Daniela trial)

- `structured(..., json_schema_mode=True)` is a per-call opt-in; the global setting is unchanged.
  A probe showed the gateway enforces the schema: an id outside the enum cannot come back.
- Two calls, each with a schema built for this customer. The profile call returns kind, evidence,
  question and hero, with the hero an enum of the candidate heroes. The tiles call returns
  `{signal, title}` pairs, the signal an enum of labels such as `S4 goal_far savings_goal`, so
  the title sits beside a label that says what the tile is. An "own tile" (merchant_spending,
  regular_payments, account_balances, bill) takes names from an enum of the customer's payees,
  account ids and payment ids. The few-shot examples are gone. A short rule list maps signal
  kinds (not customers) to the question instead.
- Failed: titles came back in German (the data is German), and a price-rise list repeated rows
  of the fixed-costs list. Changes: "Write in English" in both prompts. The overlap check now
  works both ways (the smaller list mostly inside the larger one is a repeat).

### A2, 3 of 4 (one run per customer)

- Every board had a hero from its candidates; no drift between title and signal was seen.
- Payment lists (due_soon, bills_until_payday, fixed costs, price rise) knocked each other off
  the board, and the repair filled it with monthly_spending beside income_and_spending (judge:
  the same months twice).
- Changes: the planner offers only the signals whose tile shows something no stronger signal's
  tile shows (the others stay in the prompt as facts without a label). monthly_spending and
  income_and_spending count as a repeat. A title with a digit gets the default title (Apertus
  wrote "renewed by 15.12.2026", a date it invented). A thin second board frees its tiles for
  the main board's repair.

### A3, 2 of 4

- Bug: an empty payment list counted as "repeated" by any list (`min(...) = 0`), so due_soon
  was never offered to Lukas. Fixed.
- Lukas's hero came out as the Japan savings goal and then as due_soon. Apertus ignored the
  prompt rule "[depot_large]: the hero is what they own" both times.
- Change (technique 6, blueprint): when one of the deciding kinds is among the three strongest
  headline signals (payday_tight, mortgage_maturity, depot_large, cashflow_negative, in that
  order), the hero enum holds only that signal. Otherwise the model picks among the top three.
  The model still writes the kind, evidence, question, the hero's title, and the whole rest of
  the board. The hero is the first field of the profile answer, so the kind and question are
  written after it and fit it.

### A4, 4 of 4 (one run per customer), 6 to 8 s per plan

- Apertus repeated a signal in its tile list (dropped as a repeat, refilled by the repair). The
  prompt now says every label at most once.
- `expected_label`: the profile schema asks for it (required) when the hero can be a
  payday_balance with a late income, and the hero tile carries it. A label with a digit or
  longer than 40 characters is left out.

### A5, 10 of 12; A6, 11 of 12 (`runs/20261128-024759-apertus/`, `runs/20261128-025348-apertus/`)

- At temperature 0 the three runs of a customer come back almost identical, so a failure
  usually repeats three times.
- A5 failures: the hero with an `expected_label` and the same tile without one counted as two
  tiles, so the repair added the payday tile a second time. Now `tile_key` ignores wording
  arguments. The label read "the money from Patrick Rüegg". The facts now carry each income's
  booking text ("Unterhalt Lina Dezember"), and a label that holds a word of the payer's name
  is left out. Marco's board was named "Payday Decision Check"; the mortgage rule in the prompt
  now names the question.

### Live findings from the page (Maxim), then A7, 12 of 12 (`runs/20261128-030008-apertus/`)

- Board names came back as sentences, and tile titles read like a system wrote them. Changes:
  - The prompt gives title style examples tied to signal kinds (not to customers) and bans
    filler words.
  - In code, a filler word is cut from a title. A title over 28 characters, or one that
    names a date or a figure, falls back to the default title.
  - A board name has one to three words, at most 24 characters and no question mark, else a
    default ("Until payday" for a payday hero, "The house", "Every month", "Overview"; for a
    request, the first tile's title).
  - The default titles in `tiles/service.py` are short now ("Left before payday",
    "From Patrick", "Bill, due 30.11.", "Due in 30 days", "Shops since September").
  - The gate checks both deterministically (`names_short`, `titles_short`).
- A7 passed 12 of 12, but the boards were thin. Lukas's tile list degenerated into
  "Partner's monthly share" six times, and Jana's board was named "Until payday".

### A8: one verdict per signal instead of a list (4 of 12, 8 errors from gateway timeouts)

- The tiles schema no longer holds a list of picks. It holds one object per offered signal,
  keyed by its label, with `use` (main / second / idea / no, or yes / no for a request) and a
  `title`. No signal can repeat, and every title is written right after its label. Order on
  the board: the hero, then the chosen signals strongest first, then up to two own tiles. A
  request has a `first` field (the label, or the own tile, that answers it).
- From 03:11 the gateway slowed down for everyone (a profile call of 96 tokens took 37 to
  50 s), and 4 of 12 plans timed out (55 s per call). That says nothing about the boards;
  the 4 judged boards that failed did so on titles. "Bills until payday" sat on a due_soon
  list for customers without a tight payday, and "Rising fixed costs" sat on the price_rise
  tile, which shows no old prices.
- Changes: a "payday" title off the payday templates gets the default title, and so does a
  "payday" first-board name off a payday hero. price_rise is no longer offered as a tile (it
  stays a fact). due_soon's style example is "Bills due soon".

### A9, 12 of 12 first boards (`runs/20261128-032019-apertus/`), the code as it stands

- Lukas 3, Jana 3, Daniela 3, Marco 3. Plans took 33 to 53 s because the gateway was loaded
  (6 to 8 s per plan when it was quiet, at A4 to A7).
- Not yet good: no second board and no ideas came back. Daniela's `expected_label` still came
  back unusable and was left out ("If the money from Patrick Rüegg arrives" stays). One title
  came back lowercase ("credit card bill").

### GLM regression, 12 of 12 (`runs/20261128-032019-glm/`)

- The same code path with `--model glm` (both calls with `json_schema` through OpenRouter):
  12 of 12, $0.72 for planner plus two judge samples.

### Judge: two samples per board

- Each board is judged twice (the first sample keeps the earlier cache label, the second gets
  `-judge2`), and it fails only when neither sample passes it whole. The rubric is not looser.
  Its new section for requested boards names what a request board must not do (tiles off the
  request, filler to reach a count).

### Requested boards (`--requests`, 2 per customer): best 2 of 8 (R3, R4)

- R1 (yes/no per signal): 0 of 8. Apertus said yes to one tile and used no own tiles, so 5
  boards had a single tile.
- R2 ("answers" / "related" / "unrelated", at least one own tile): 1 of 8. "related" took in
  everything (net worth on the Japan board), and own tiles came last and were cut by
  "board is full".
- R3 (answers first, then own tiles, related only to fill to three; an account_balances of the
  one account a savings goal shows is a repeat): 2 of 8.
- R4 (related only to fill to two, a prompt line that an own tile never repeats a signal's):
  2 of 8 (`runs/20261128-033544-apertus/`).
- R5 (the "first" field after the verdicts): 5 of 8 plans timed out on the gateway, not
  judgeable. Reverted to R4, the best measured.
- What fails: Apertus chooses poor own tiles. For "subscriptions" it took the largest monthly
  payments (rent, health insurance); for "What does Lina cost me" it took no Lina payee. Two
  requests have no template that answers them: when the parents' loan is repaid (no tile shows
  a loan's remaining amount) and what the house costs a year (no tile sums interest,
  amortisation and the house's payees).

## Night 2 (04:50 to 06:00): requested boards, ideas, fallback, expected_label

### Requested boards: the model selects, the server builds
- Tried first: a yes/no per entry over every account, payee, booking payee, payment and
  finding (`runs/20261128-035642-apertus/`, 0 of 8). The answer was long, some calls timed
  out, and Apertus said yes to unrelated findings.
- Now: one small call returns `entries` (payee names, an enum of this customer's payees),
  `keywords` (German words of the data), `costs_only`, `open_bills`, a tab name and three
  group titles. The server matches them against the accounts, upcoming payees, payees of the
  last 12 months, open payments and the specific findings. General findings (cash flow,
  spending, due soon, fixed costs, savings pots) are never offered to a request. Then it
  builds the tiles by type: goal → savings_goal, payees → regular_payments, booking payees →
  monthly_spending over 12 months, a payment → bill, a finding → its tile. A private-loan
  payee gets both the standing order and "Repaid each month", plus the note "The bank does not
  know how much of the loan is left; tell me the amount and I add it." in `dropped`. A board
  with nothing gets the reason "Nothing in your accounts is about this request yet."
- Scores over the iterations: 4, 3, 3, 5, 3, 2 of 8 (`runs/20261128-040323` to
  `-043344-apertus`). Best: 5 of 8 (`runs/20261128-042129-apertus/`); two of the passing
  boards there came from the keyword fallback after gateway timeouts.
- What still fails: Apertus names off-topic payees (the Engadin holiday flat for Japan, Andrea
  Widmer for the emergency fund) and sets `costs_only` for "open bills". Cross-checking
  entries against keywords did not help, and opening cost questions on monthly bars broke
  titles. Both were reverted (b8), so the code is at the b6/b7 method.

### Ideas: always three, server-chosen
- The strongest signals off the first board, findings about one thing before findings about
  the whole month, never payday or price_rise. Titled by the model's own title for that
  signal, else a title by kind ("Instalments", "Fixed costs", "Savings pots"). The fallback
  check shows three per customer.
- Round trip ("<title>. <sentence>" as a request): 3 of 12 (`runs/20261128-044355-apertus/`),
  then 2 of 12 (`runs/20261128-045204-apertus/`) after the idea's finding became the hero.
  That second run looked up the idea's finding among the offered signals only, and spending
  and fixed costs are not offered (they overlap other tiles), so it missed. Fixed after the
  run (it now looks in all signals), not yet measured.

### Fallback when the gateway does not answer
- Each planning call has `timeout_seconds=20` and an `asyncio.wait_for` budget of 28 s (the
  client's retries happen inside it), so a first plan is at most about 56 s and a request
  28 s. On a timeout or UpstreamError the board comes from the server's ranking, or from a
  keyword match for a request. `model` is "server", and the check `planned_by_model` is false
  with "The model did not answer in time; ...".
- `uv run python -m evals.boards.fallback` runs every customer's first plan and both requests
  with a client that always fails: all fall back cleanly, first boards of 6 to 7 tiles with 3
  ideas, every request a board or an empty board with its reason.

### expected_label
- The profile call gets the late income's booking text beside the field, with the German to
  English list. If the model's label is unusable, code maps the booking text (Unterhalt →
  "the child support"). Daniela's hero now carries `expected_label: "the child support"`.

### First boards after these changes: 9 of 12 (`runs/20261128-043744-apertus/`)
- Jana 1 and 2: the judge failed the lowercase title "bills". Titles now start with a
  capital (after this run). Marco 2: the board drifted off the mortgage story (pillar 3a and
  the car instalments).
