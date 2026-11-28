# The TrustRoom boards: the case for the jury

Written 28.11.2026 after the night run. Each section names what we built and
what it proves. All numbers come from runs stored in the repository, under
`src/backend/evals/boards/`.

## What the customer sees

The TrustRoom opens on a board that the model built from the customer's own
bookings. The first tile is large and dark and answers the one question that
matters most to this customer. A chat sits beside the board and changes it.
Boards are tabs along the bottom. A second view shows the chat alone, with the
customer's profile notes and documents.

Daniela, a single parent on a tight budget, gets "Until payday". Its first tile
says CHF 124.96 are left on 23.12., the day before her salary, and CHF 1'174.96
if the child support arrives. Lukas, who is building wealth, gets "Overview"
with CHF 131'212.64 in accounts and securities. Nobody typed either board.

## Customer value and freedom (30 %)

What we built:

- **A board per customer, inferred from evidence.** The server reads accounts,
  bookings, upcoming payments, depot, pillar 3a, loans and cards, and computes
  signals such as "a regular income has not arrived", "the emergency fund is
  at 9.5 % of its goal" or "a mortgage tranche runs out in March". Apertus
  says what kind of customer this is, picks the question and chooses and
  titles the tiles. No rule looks at a name.
- **The chat edits the open board.** "Remove the groceries tile", "Rename the
  emergency fund", "Move the dentist bill to the top", "Make the spending
  chart show 12 months", "Add my subscriptions" each change the board in
  5 to 12 seconds.
- **New boards from a sentence.** The "+" tab asks "What should this board be
  about?" and offers three ideas taken from the customer's last months.
- **A profile the customer owns.** The chat proposes a note ("The child
  support often comes late. Always show both cases."), and saves it only
  after "Save to my profile". The customer can edit and delete every note
  and every document.
- **Sixteen tile templates**, from the balance on the day before payday to
  mortgage tranches, each drawn as a first tile or as a small one.

What it proves: four customers with different lives get four different
boards without configuration, and each customer reshapes theirs in plain
language.

## Reliable output and traceability (30 %)

What we built:

- **The model never writes a figure.** A tile stores a template and its
  arguments. The server computes the figures from the banking API every time
  the board is read, so a board is current when it opens.
- **Every tile names its source.** The link under a tile ("Privatkonto and
  8 upcoming payments") opens the bookings or payments behind the figure,
  with date, text, amount and id.
- **The verdict is the server's.** Each tile has a server-written sentence
  with its meaning, including "Yes, but only just" for a payday balance of
  CHF 4.63 a day. The model words the answer and may not form its own
  judgement. Before this, Apertus answered "you lack sufficient funds" with
  CHF 124.96 left.
- **Totals come from a server sentence.** Every tool result with a sum
  carries one sentence with the total. Before this, the model multiplied
  rows itself and got CHF 2'714.00 where the bookings say CHF 2'985.40.
- **Checks on every answer.** The existing figure check runs on board
  answers too: each number in an answer has to appear in the data behind it.
- **Arguments are validated before a tile is stored.** An account, payee or
  merchant that does not exist returns an error that says what exists. A
  tile that cannot be filled is dropped with its reason, never shown empty.

The numbers, all on Apertus v1.5 70B through the Keera gateway:

| Gate                                  | Result                           |
| ------------------------------------- | -------------------------------- |
| Tile figures against the design       | all reference figures reproduced |
| First boards, 3 runs × 4 customers    | 12 of 12                         |
| Boards built from a request, two runs | 6 and 5 of 8                     |
| An idea opens a board, 12 ideas       | 12 of 12                         |
| Scripted chat turns, two runs         | 21 and 19 of 21                  |

A board counts as acceptable when deterministic checks pass and a model
judge, given the rubric and the persona's file, passes it. The rubric is in
`evals/boards/rubric.md`, every generated board in `evals/boards/runs/`.

## Technical rigour and sovereign architecture (20 %)

What we built:

- **Apertus only at runtime.** Every model call goes through one client to
  the Keera gateway. Nothing in `src/backend/app/` can reach another model.
- **Why 70B.** Everything runs on `apertus-v1-5-70b`. Once the decision was
  small and schema-bound, a plan was two calls of 2 and 5 seconds on a quiet
  gateway, so speed gave no reason to switch. We did not measure the 8B
  model on the boards.
- **What made Apertus reliable**, in the order we found it:
  - A small decision. A board turn sees 6 board tools and about 4'900
    tokens, where every turn used to see 38 tools and 14'000 tokens. A turn
    fell from 30 to 95 seconds to 5 to 12.
  - Schema-constrained output. The gateway enforces a JSON schema with
    enums, so the model cannot return a signal id the customer does not have.
  - One verdict per signal, keyed by its label, so a title cannot land on
    the wrong tile.
  - No few-shot examples in the plan. Apertus copied the Daniela example
    onto every customer; a short rule list per signal kind replaced it.
  - Errors that say what to do next.
- **A fallback for a slow gateway.** Each planning call has a 28 second
  limit. Past it the server builds the board from its own ranking of the
  signals and marks it "planned by the server" in the provenance.
- **A development reference, kept out of runtime.** We proved the method
  first with `z-ai/glm-5.3` through OpenRouter (12 of 12 boards on its best
  sample). That model runs in evals only, on the four demo customers, and
  judges the boards. Every reply is cached on disk.
- **Layers.** Three new features, each with controller, service and
  repository where it stores something: `tiles` (templates and resolvers),
  `boards` (storage, endpoints, chat tools) and `board_plans` (signals and
  the plan).

What it proves: the board works with an open-weights model inside the bank,
and the techniques are specific and repeatable.

## Feasibility and integration (20 %)

What we built:

- **It runs inside the e-banking today.** The page loads in the e-banking's
  full page and in its 440 px side panel, takes identity from the e-banking's
  token and builds no login of its own.
- **A tile goes onto the e-banking dashboard.** "Put on my e-banking
  dashboard" writes the tile as a widget in the bank's own declarative
  format, with the bank's link to the underlying bookings. Publishing again
  replaces the widget.
- **Bank data stays in the banking API.** We store boards, tiles (template
  and arguments), plans with their provenance, conversations and notes. No
  balance and no booking is copied into our database.
- **One deployment path.** A push to `prod` builds the backend image, swaps
  it in on the box without downtime, runs the migration and rebuilds both
  pages.
- **Nothing from outside.** The page serves its own font and loads no
  script, style or image from a third party.

What it proves: a bank can add this beside an existing e-banking with one
iframe, one token and read access to its own API.

## What is not finished

The handover in `docs/night-run-handover.md` lists it plainly. In short:
boards built from a free request pass 5 to 6 of 8 where first boards pass
12 of 12, the plain chat without a board answers 12 to 14 of 23 reference
questions in our older eval, and a pinned dashboard widget is a snapshot.
Under a loaded gateway a plan can take 30 to 50 seconds, and then the
fallback builds the board.
