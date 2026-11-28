# Night run handover, 28.11.2026, 09:00

For Maxim. The run replaced the TrustRoom page with the boards from
`docs/reference/boards/` and made Apertus build them. Everything below is on
`main` and `prod` unless it says otherwise.

## What works

Checked by clicking through the page as Daniela and as Lukas, on Apertus.

- **First visit.** A customer without boards gets one in 10 to 15 seconds.
  The four demo customers get four different boards:
  - Daniela: "Until payday", first tile CHF 124.96 left on 23.12., with
    "If the child support arrives CHF 1'174.96".
  - Lukas: "Overview", first tile CHF 131'212.64.
  - Jana: "Every month", first tile CHF 250.82 left a month on average.
  - Marco: "The house", first tile the mortgage of CHF 862'500.00.
- **The chat changes the open board.** Add, rename, move, remove, change a
  tile's period, add subscriptions, add groceries. Pure edits answer in
  2 to 6 seconds, turns with a model answer in 5 to 12.
- **The first demo turn matches the design.** "Does my money last until
  payday?" answers "Yes, but only just…" in two short paragraphs, lists what
  is on the board, and offers the note about the late child support with
  "Save to my profile" and "Not now".
- **Sources.** The link under every tile opens the bookings or payments
  behind its figure.
- **Profile.** Notes the customer saved, editable and deletable, and every
  uploaded document. "Customer since 2011" comes from the bank.
- **New boards.** The "+" tab, three ideas from the customer's last months,
  and a board from a sentence.
- **Pin to the dashboard.** A tile goes onto the e-banking dashboard as a
  widget in the bank's own format.
- **Both widths.** The e-banking's full page (about 1040 px inside its frame)
  and its 440 px side panel.

### The numbers

All on `apertus-v1-5-70b` through Keera.

| Gate                               | Result          |
| ---------------------------------- | --------------- |
| Tile figures against the mockups   | all reproduced  |
| First boards, 3 runs × 4 customers | 12 of 12    |
| Boards from a request, 8 requests  | 6 and 5 of 8       |
| Idea opens a board, 12 ideas       | 12 of 12           |
| Scripted chat turns, 21 turns      | 21 and 19 of 21 |
| Old plain-chat eval, 23 questions  | 12 to 14 of 23  |

- First boards on GLM (the development reference): 12 of 12 on its best
  sample, 9 to 12 across samples, because the model judge varies.
- At temperature 0 a customer's three Apertus runs are almost identical, so
  12 of 12 is closer to four boards checked three times.
- The two chat failures in the second run: an en dash in a date range (the
  check is too strict there) and the word "tiles" in one answer.
- OpenRouter spend for the whole night: about 10 of the 26 dollars.

### Is it live

Yes. Pull request #309 merged `boards` into `main` (46 commits, rebased, no
review). `prod` is fast-forwarded to `main` at `7d6a9f8`, and the Deploy
workflow went green in 2 min 15 s (run 46117111931).

- E-banking: https://ebanking-apertus.vercel.app, then "TrustRoom" in the
  menu. Logins are in `starter/README.md` (daniela / daniela2026 and so on).
- All four demo customers have a board on production already, built by
  Apertus after the deploy. My first attempt for Daniela and Lukas hit a slow
  gateway (46 and 42 seconds) and got the fallback board with default titles;
  I rebuilt both a few minutes later in 11 seconds each.
- I have not clicked the production page in a browser. I checked it through
  its API: health, the four boards with their tiles and figures, the ideas.

## What is half built

- **Boards from a free request.** On Apertus 6 and 5 of 8 pass the
  gate, where first boards pass 12 of 12. "Japan 2027", the emergency fund,
  the parents' loan and the open bills pass. "What does Lina cost me every
  month?" builds an on-topic board that opens on a list of two upcoming
  payments, where twelve months of bars would answer better. "What do my
  subscriptions cost me?" gives one tile and misses subscriptions paid by
  card. "What does the house cost us?" has no template that answers it.
- **Thin boards.** A board from an idea starts with one tile, the finding
  behind the idea. The page says so beside it. Templates for an instalment
  plan (21 of 24, CHF 311.20 left), the yearly cost of a house and a loan's
  remaining amount do not exist yet.
- **Pinned widgets are snapshots.** The widget says "As of 27.11.". The
  e-banking's refresh hook calls us without a token, so a live widget needs
  a stored customer token or a signed secret per widget. That is a security
  decision for a person.
- **Bookings link on a pinned widget.** It covers the first 40 source rows
  of a tile. A monthly bar chart links 19 of 531 payments.
- **Wording.** About one board answer in ten still says "tile" or runs a
  sentence long. After a note is saved, an unrelated answer sometimes adds
  the child-support case, because the note says "always show both cases".
- **The side panel.** At 440 px the board comes first and the chat sits
  below it, so the customer scrolls to type.
- **Tests.** The night's rule was boot and build only. New tests exist for
  tile meanings, totals, Swiss figures, subscriptions and the widget mapping.
  The full suite did not run, and tests of the old canvas page are deleted
  with it. Expect failures in tests that pin the old chat prompts.

## What is blocked

- **The weekly usage limit.** I could not read it from inside the session,
  so I stopped by the clock, not by the meter.
- **The plain chat's level.** 12 to 14 of 23 on the old eval, the same
  before and after tonight's changes within one question each. Its failures
  are tool and date choices of the 38-tool decision. I tried nothing there
  beyond a total sentence per result. Next I would give the plain chat the
  same treatment as the board chat: a small first decision that routes to a
  handful of tools.
- **A request with no template behind it** ("What does the house cost us a
  year?", "When have I repaid my parents?"). Tried: selection by the model,
  one verdict per entry (slower and no better, reverted). The board now says
  what the bank does not know. Next: two templates, a counterparty's history
  with a running total and a yearly cost by payee group.

## Questions worth a brainstorm at 09:00

1. Do we demo "new board from a sentence" live, or only the ideas and the
   chat? The ideas are deterministic; a free sentence is not yet.
2. One board per customer at first visit, or two? The design's dock shows
   three. A second board is built today only when the customer asks.
3. Should the first tile's question be visible as a line above the board?
   The plan stores it ("Will there be enough money the day before the next
   salary arrives?") and the page does not show it.
4. The pinned widget: accept a snapshot for the jury, or spend the morning
   on a refresh path?
5. The technical report is still the template apart from two sections added
   tonight (data flow of the boards, GLM as development reference). Who
   writes the rest?
6. The gateway under load: plans took 30 to 50 seconds at times in the
   night. The fallback board covers a timeout. Do we pre-build boards for
   the four demo customers before the jury opens the page? I did that on
   production after the deploy.

## Where to look

- Reference screens: `docs/reference/boards/`.
- The case for the jury: `docs/night-run-report.md`.
- Generated boards, one folder per run: `src/backend/evals/boards/runs/`.
  Each has an `index.md` readable in a terminal.
- What was tried for Apertus and what each step scored:
  `src/backend/evals/boards/log.md`.
- The rubric: `src/backend/evals/boards/rubric.md`.
- Chat turns with answers, tool calls and seconds:
  `src/backend/evals/boards/chat_runs/`.
- Commands, from `src/backend`:

```sh
uv run python -m evals.boards.tile_figures
uv run python -m evals.boards.run --model apertus --runs 3
uv run python -m evals.boards.run --model apertus --requests
uv run python -m evals.boards.fallback
uv run python -m evals.boards.chat_turns --base-url http://localhost:8010
```

## Assumptions I made alone

- A tile is drawn by the page from typed data, not from the old widget
  catalogue. The catalogue and its endpoints are still in the backend,
  unused by the page. `build_widget` is no longer a chat tool.
- The model never writes a figure and never chooses a figure's meaning. The
  server writes the verdict and the total, the model words them.
- Less freedom for Apertus where it bought reliability: the first tile comes
  from the customer's strongest signals, subscriptions and grocery shops are
  narrowed by the server, an idea opens on its own finding.
- The page serves its own font, so the browser contacts nobody outside.
- Board names and tile titles are English, as the e-banking is.
