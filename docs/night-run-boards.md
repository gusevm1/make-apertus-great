# Night run: the TrustRoom boards

Written 28.11.2026, 02:00. You are a Fable 5.2 orchestrator running alone on Maxim's laptop
until 09:00 today. Nobody will answer you. Read this whole file, then start.

This run replaces the TrustRoom's page with the one in `docs/reference/boards/`, and makes the
model build those boards by itself. Phase 1 proves it with a stronger model through OpenRouter.
Phase 2 brings Apertus to the same standard.

## The goal

The dashboard is the product. The chat is how you build and change it.

A customer opens the TrustRoom and already has one or two boards about what matters to them,
inferred from their own bookings and documents. The board fills the page, the chat sits on the
right, and the customer switches between "Board and chat" and "Chat". Talking to the chat adds,
renames, moves and removes tiles on the open board. Boards sit as tabs along the bottom, and a new
tab opens empty and asks what it should be about. Every figure on a tile names the bookings or the
document it comes from. The chat proposes notes for the customer's profile, which they save or
decline, and the profile holds every document they ever uploaded.

Two customers must never get the same board. Daniela needs to know whether her money lasts until
payday. Lukas needs an overview of what he owns and where it goes.

## Reference material, read before you plan

- `docs/reference/boards/*.html`, four screens, confirmed by Maxim. Open them in a browser. The
  `.png` beside each one is how it renders at 1440 px. This is the design, not an inspiration.
  Treat the layout, the spacing, the tile shapes and the wording as the specification.
- `CLAUDE.md` in the repo root, the rules for the code. They hold, with the exceptions below.
- `challenge_description.md`, the brief and the four judging criteria.
- `starter/README.md`, the personas and the demo logins.
- `starter/docs/custom-widgets.md`, what the e-banking dashboard accepts from us.
- `starter/resources/Demodaten/Personas/*.md`, the four lives behind the data.

The mockups are static HTML with no build step. They were drawn from the real banking API of the
demo customers, so their figures are real.

## The method the model has to exhibit

This is the most valuable part of this document. The mockups were produced by following these
steps, and the system prompt, the tools and the few-shot examples all exist to make a model walk
the same path.

1. **Read the raw material.** Accounts and their balances, the bookings of the last months, the
   payments that fall due, the documents, and what we already know about the customer.
2. **Find the signals.** What is late, tight, large, recurring, unusual or about to happen. For
   Daniela: the child support has not arrived, the emergency fund is at 9 % of its goal, a second
   reminder is due in three days. For Lukas: a depot worth more than his accounts, a 3a account
   58 francs short of the maximum, a provisional card bill of 3'301.74.
3. **Say what kind of customer this is,** from the evidence alone, never from a name. Someone
   whose month is decided by timing needs a different board from someone who is building wealth.
4. **Choose the one question that matters most** and make it the first tile, large and dark.
   Daniela's is "what is left on the day before my salary", and it is worth more than any chart.
5. **Add four to six tiles that answer what the customer asks next,** each one small, each one
   about a single thing.
6. **Name the source under every tile,** so the customer can open the bookings behind a figure.

Write this into the prompt as the model's job, and build a few-shot example from Daniela and one
from Lukas, using the real signals and the real tiles of the mockups.

## Rules of the run

- **Branch.** `git pull` on `main` first, then work on `boards`. One commit per change that stands
  on its own, in Maxim's name, with no mention of Claude or an AI.
- **No board, no tickets, no cards.** Ignore the `scrum-board`, `build-card`, `land-card`,
  `night-run` and `refine-issue` skills. They need GitHub issues and a human. You have neither.
- **Models.** You orchestrate. Opus 5.5 does the work that needs judgement: prompts, the board
  model, the inference of a first board, the harder frontend. Sonnet 5.5 does the work that is
  typing against a clear plan: components, endpoints, tests, migrations, moving code. Run agents
  in parallel whenever two pieces of work do not touch the same files.
- **Spend.** Stop when about 10 % of the weekly usage is left. Check often enough that the stop is
  not a surprise. Then finish only the piece in your hands, to a state that runs, and write the
  brief.
- **Nothing in this repo is untouchable.** A tool, an endpoint, a prompt or a component that makes
  the output worse gets rewritten or deleted. The template files named in `CLAUDE.md` stay where
  they are, and so do the challenge's own rules: Apertus at runtime, no closed model serving a
  customer, no customer data leaving the stack, figures never invented.
- **The UI is replaced outright.** `src/frontend/src/App.tsx` and `Canvas.tsx` give way to the
  board page. Keep what still earns its place: `api.ts`, `useStream`, `host.ts`, the markdown
  renderer, the voice input, the tokens. Deleting more than you add is usually right.
- **A solution exists.** Perfect parity on this task is reachable with Apertus behind a schema it
  can follow. If an approach fails, that approach was wrong, not the goal. Try another one, keep
  whatever scored best so far, and iterate. Never write "this is not possible with Apertus".
- **Ship fast, check thin.** Do not run `.claude/skills/land-card/gates.sh`, and do not run the
  formatter, the linter or the full test suite on the way. Tonight only two failures matter,
  because each one means nothing reaches the live boxes in the morning:

  ```sh
  cd src/backend && uv run alembic upgrade head && uv run alembic heads   # one head
  cd src/frontend && npm run build
  ```

  Run that pair after each agent hands back a piece, and again before the merge. Several agents
  writing migrations in parallel is the way to get two heads, and a backend that will not boot.
  Fix a second head by pointing your migration's `down_revision` at the other one.

- **Tests.** Write a test only where it would catch a wrong figure. When you delete a feature,
  delete its tests with it; that is not weakening a test. Never change a passing test to make new
  code fit.

## Phase 0: ground work

Do this before any model work, and keep it small.

- **Cache every OpenRouter reply.** Key on the model, the messages and the parameters, store the
  response as JSON on disk under `src/backend/evals/cache/`, git ignored. Every rerun of a prompt
  you have already sent must be free. Without this the 26 dollars will not last the night.
- **The board model.** A board is a named list of tiles that belongs to a customer. A tile is a
  template name plus arguments, never free HTML and never figures. The server resolves the
  arguments against the banking API every time the board is read, so a board is current when the
  customer opens it. Store the question a tile answers, not its answer.
- **Keep the model's job small.** The model writes intentions: which template, which arguments,
  what title, which board. Our code draws. If a template cannot express something, add a template
  rather than letting the model write markup.
- **Start from the catalogue** in `src/backend/app/features/widgets/catalogue/`. It already has 19
  components, two Jinja templates and the e-banking's look. Judge it honestly against the mockups:
  the hero tile, the running balance, the month strip, the shop bars and the document tile may be
  new components, and some of the 19 may deserve deletion.

## Phase 1: prove it with GLM

Model: `z-ai/glm-5.3` through `openrouter_client()` in `src/backend/app/clients/openrouter.py`.
The key is `OPENROUTER_API_KEY` in the repo root `.env`. Input costs 0.07 dollars per million
tokens, output 1.40. Only demo customers' data may go there, and the technical report has to list
the model as a development reference.

Build, in this order:

1. The board model, the templates and the endpoints.
2. The page from the mockups, replacing the current one.
3. The chat that edits the open board, with its operations as tools.
4. The first boards, inferred from the customer's own data.
5. The profile: notes the chat proposes, the customer saves, and the documents.

**The gate.** Three cold runs for each of the four customers, twelve boards in all, every one
acceptable. Acceptable means a board Maxim would show in the demo: the first tile is the question
that customer actually has, the tiles are about that customer's real situation, every figure is
right, and nothing is empty or repeated. Write the rubric down before you judge, judge with a
model and with the figure checks, and keep every board you generated so the morning can see them.

## Phase 2: Apertus to the same standard

Same gate, same rubric, on `apertus-v1-5-70b` through the Keera gateway. The boards need not match
GLM's tile for tile. They have to be good, useful and correct.

Work through the techniques from the cheapest to the most involved, and keep what scores best:

1. **Shrink the decision.** Apertus sees 38 tools and about 14'000 tokens on every turn. A board
   is built from a handful of them. Give the board work its own small tool set.
2. **Turn on the schema.** `apertus_json_schema_supported` is false in the settings, and the
   widget benchmark found that the gateway accepts `json_schema`. Constrained output removes a
   whole class of failure.
3. **Few-shot examples** in the prompt, taken from Daniela and Lukas, showing the method of this
   document end to end.
4. **Split the work** into separate Apertus calls with their own prompts: classify the customer,
   pick the board plan, fill one tile. A small prompt with one job beats one large prompt.
5. **Fix the errors the model reads.** An error has to say what to do next. See below.
6. **Narrow the choice.** Fewer templates, enumerated arguments, a blueprint per customer type.
   Less freedom is allowed. A board that is always good beats a board that is sometimes clever.

## What we already know about Apertus

Found tonight, while making "Show my monthly spending over the last 6 months as a chart" work.

- It picks a tool whose description sounds close, so two tools with overlapping descriptions mean
  the wrong one gets called. Descriptions have to say what a tool does **not** do.
- It repeats an argument the tool does not have when the error only says
  "Extra inputs are not permitted". With "This tool has no such argument. Send the call again
  without it" it corrects itself in the next round. Three commits landed on `main` for this.
- It writes the whole decision as JSON text that our server parses. The gateway never sees a
  `tools` parameter, and the per-tool schemas reach it only as text inside the prompt.
- A single chart turn took 30 to 95 seconds on the 70B model. Any design that needs several
  sequential calls before the customer sees something will feel broken. Precompute the first
  boards.
- The widget catalogue already works well with it: most specs came back clean on the first try,
  at about 3 seconds each (`src/backend/evals/widgets/results.md`).

## Verification

The traceability criterion is worth 30 %, so verification is a feature, not a test.

- The server computes every figure from the banking API. The model picks what to compute and
  writes the words.
- Keep `figure_checks`: every number in a title or a sentence has to appear in the data behind it.
- Check an argument the model returns against what exists before a tile is stored.
- A tile that cannot be filled is dropped with a reason, never shown with a blank or a zero.
- The customer can open the bookings behind any figure. Make the click in the mockups real.

## Stopping, the merge, and the morning

At 09:00, or when about 10 % of the weekly usage is left, stop building.

1. Finish the piece in your hands so the app runs.
2. Start the stack and click the demo through yourself: log in as Daniela, open the TrustRoom,
   see her board, ask the chat for a change, watch it happen. Then as Lukas. This matters more
   than any test tonight. Fix what is broken in that path and nothing else.
3. Run the thin check: one Alembic head, and `npm run build` passes.
4. Merge `boards` into `main` in one go, no review and no waiting. Open the pull request, write
   one line of body, merge it. Push `main`.
5. Promote to production: fast-forward `prod` to `main` and push it. The push triggers the deploy
   workflow, which builds the backend image, swaps it on the EC2 box and rebuilds both pages on
   Vercel. Maxim has authorised this. Say in the brief what you deployed and whether the workflow
   went green.
6. Write two files.

**`docs/night-run-report.md`,** the case for the jury. One short section per criterion, each
naming what we built and what it proves.

- Customer value and freedom, 30 %
- Reliable output and traceability, 30 %
- Technical rigour and sovereign architecture, 20 %
- Feasibility and integration, 20 %

**`docs/night-run-handover.md`,** the brief for Maxim at 09:00, written plainly.

- What works, with the numbers from the gate, and whether it is live.
- What is half built, and what is left on it.
- What is blocked, each with what you tried, what happened, and what you would try next.
- The questions worth a brainstorm at 09:00, in the order they matter.
- Where the generated boards and the eval output are, so they can be looked at.

Say what is true. A blocker named clearly at 09:00 is worth more than a sentence that hides it.
