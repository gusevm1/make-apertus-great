# Make Apertus Great: project guide

Our entry for the ti&m challenge at Hack Apertus: the TrustRoom, an AI space inside e-banking.
`challenge_description.md` is the brief, `starter/README.md` explains the mock e-banking we plug into.
Five people and their agents work in parallel, so the conventions below matter more than any clever solution.

## Rules of the challenge

- Our code lives in `src/`. Never rename or move the template files (`README.md`, `technical_report.md`,
  `challenge_description.md`, `LICENSE`, `starter/`).
- The model is Apertus v1.5 through the Keera gateway, configured by `LLM_NAME`, `LLM_BASE_URL` and
  `LLM_API_KEY`. An optional `LLM_NAME_FAST` names the smaller Apertus model for small tasks such as
  transcription; without it everything runs on `LLM_NAME`. No closed model and no proprietary AI API
  at runtime.
- Customer data stays inside: nothing the customer types, uploads or owns goes to a service outside
  the stack in `starter/docker-compose.yml`, except the model gateway.
- Web search is the one exception. It runs through our own SearXNG, exists only when `SEARXNG_URL`
  is set, and sends the search query to search engines outside the bank. So every search waits
  until the customer has read the query and allowed it in the page. The technical report has to
  list it in the data flow.
- Figures are never invented. The server computes every sum, date and comparison from the banking API;
  the model only chooses what to compute and words the result. Every figure can name its bookings.
- Identity comes from the token the e-banking hands us. We build no login of our own.

## Branches

- `main` is development. Every card lands here.
- `prod` holds stable versions. It only moves by promoting a commit of `main` that a human picked.
  Agents never push to `prod`.

## Board

The [board](https://github.com/users/gusevm1/projects/4) is the single source of truth for what gets
built, who is on it and how far it is. Every change belongs to a card.

- **Before any work, use the `scrum-board` skill:** take the next Ready card, claim it, build it, open
  a PR with `Closes #<n>`.
- **Humans decide what gets built** (Backlog to Ready, priority, owner) at the sprint boundary. Agents
  add cards to Backlog and never promote them.
- **Stuck or need a decision:** block the card with the exact question and take the next one. Never
  wait, never guess a product decision.
- **Building a card:** `build-card` takes it from claim to merged in its own worktree with its own
  banking API and ports, and `land-card` lands it on `main` after checking what others landed.
- **One card at a time changes prompts or tool descriptions.** Such an edit changes answers to
  unrelated questions, so those cards run in sequence and small prompt wishes go into one card.
- **Unattended runs:** one orchestrator follows the `night-run` skill. It hands cards to implementers
  and keeps the run log; it never builds or merges.
- Humans run `sprint-boundary` every few hours and `refine-issue` on new ideas.

First use on a laptop, once per person:

- `gh auth status` shows the GitHub account that has access to this repo and to the board.
- `gh auth refresh -s project` adds the scope the board commands need. A board command that fails with
  a permission error means this step is missing.
- No board access at all: ask Maxim to add your account to the board.

GitHub moves cards by itself (issue opened, PR opened, PR merged) through the Board workflow, which
reads the repository secret `PROJECT_TOKEN`. Nobody needs that token locally. When the `sync` check
turns red on every PR, the token has expired and a repo admin stores a new one.

## Writing

Before prose goes to a person (a card, a PR body, a commit message, docs, the report), apply the
`unslop` skill to it.

## Backend rules (`src/backend`, always apply, also when fixing code)

**Layers:** controller → service → repository, one set per feature in `app/features/<name>/`.

- **Controllers only translate HTTP:** call one service method and map to `ResponseX`. No business logic.
- **Services hold the logic.** They may call their own repository, `app/clients/`, and other features' *services*, never another feature's repository. If two features need each other, move the shared logic into its own feature.
- **Repositories are the only layer that touches the DB.** They inherit `BaseRepository`, commit on write, and return Pydantic domain models, never ORM objects.

**ORM style:** SQLAlchemy 2.0 typed mappings only (`title: Mapped[str | None]`, `mapped_column(...)`), never legacy `Column(...)`. Nullability comes from the type. Don't add `relationship()`; query by foreign key in the repository.

**Models per feature** (`models.py` + `schemas.py`): `XORM` (repository only), `X` (domain), `RequestXCreate`/`RequestXUpdate` (request bodies), `ResponseX` (controller only). No other model types.

**Async everywhere.** A blocking call in async code silently freezes the whole server for every user. Use `AsyncSession`, `httpx.AsyncClient` and the async Apertus client. Never use `requests`, a sync `Session` or `time.sleep`. CPU-heavy work goes through `await asyncio.to_thread(...)`. Never use one session concurrently (e.g. in `asyncio.gather`): parallelise LLM calls, then write sequentially. Every external call has a timeout.

**Feature logic stays in its feature.** Don't grow `chat_service` into a god service; new behaviour gets its own feature, called via its service.

**Data lifecycle:** child tables use `ondelete="CASCADE"` (or explicit cleanup). New `NOT NULL` columns on existing tables need a `server_default`. Ingest scripts are idempotent (upsert by natural key), so re-running after a partial failure is safe. **Migrations:** `uv run alembic revision --autogenerate -m "..."`, then read the file. If `alembic heads` shows more than one head after a merge, point your migration's `down_revision` at the other head (don't edit merged migrations).

**Apertus calls:**
- Always go through `ApertusClient` in `app/clients/apertus.py` (`chat`, `stream_chat`, `structured`), injected as `ApertusClientDep`. Never import `openai` elsewhere.
- Pass `model=Model.SMART | Model.FAST` (never model strings) and a `purpose="..."` label. The default is `SMART` until evals say otherwise.
- The client returns `LLMResult` (`content`, `model`, `latency_ms`, tokens). LLM-generated resources store **provenance**: `model`, `latency_ms`, `sources`, `checks`, shown in the UI.
- Prompt text lives in `features/<name>/prompts.yaml`, never in Python. `prompts.py` loads it (`load_prompts(__file__)`) and has typed functions that fill in the placeholders and return messages.
- Structured answers always go through `structured` with a Pydantic schema. Never parse model text yourself (`json.loads`, regex).
- The client already retries timeouts and 5xx. Don't add your own retry or backoff loop, and never retry expected errors (4xx, validation).
- Don't regenerate what is already stored or was returned by an earlier step (LLM answers, embeddings): pass it along or read the stored copy.
- German text in prompts and the UI uses Swiss conventions: "ss" not "ß", `de-CH` for dates and numbers.
- Never keep a DB transaction open across an LLM call (write → call → write).
- Never log prompts, responses or customer data yourself. The client logs metadata always and content only when `LOG_LLM_CONTENT=true`.
- For the procedure, use the `add-llm-feature` skill.

**Bank data comes from the banking API, through `BankingClient` in `app/clients/banking.py`,** called with the customer's token (`user.token`). Its address comes from our config, never from the browser. We store only what the API has no place for: conversations, messages, tool calls and the text of uploaded documents. The uploaded file itself goes to the API's `/documents`, and `OcrClient` in `app/clients/ocr.py` turns it into Markdown once.

**Bank tools are thin reads.** `features/bank_data/tools.py` lists one tool per read endpoint of the banking API; a new read is one line there, one args model and one description in `prompts.yaml`. They return the API's own sums. A tool that changes the bank (a payment, a standing order, a widget) is not a read: it needs the customer's confirmation in the page and its own card.

**Auth and ownership are dependencies, secure by default.** The user is the customer the e-banking token belongs to, resolved by `get_current_user` through the banking API. Routers carry `dependencies=[Depends(require_user)]`, and only an explicit `public_router` is unprotected. Endpoints that take a resource ID receive it through an ownership dependency (`get_owned_x`, which raises `NotFoundError`), never by loading and checking it manually. The owner filter is part of the query (`WHERE id = ... AND owner_id = ...`), not a comparison in Python after loading.

**Client input and LLM output are untrusted.** Identity comes only from the auth dependency, never from the request. The server recomputes anything it can compute (totals, balances, status). Validate LLM output like user input: fields the source may not contain are optional (`X | None`), never required (required fields make the model invent values), and returned IDs are checked against what exists.

**No hard-coded URLs.** Hosts, ports and base URLs come from `core/config.py` (backend) or a Vite env variable (frontend), never from a literal like `http://localhost:8000`.

**Errors:** services raise exceptions from `app/core/errors.py` (`NotFoundError`, ...), never `HTTPException`. One global handler maps them to HTTP.

## REST API

- All routes under `/api`, no versioning. Plural, kebab-case nouns: `/api/conversations/{conversation_id}/messages`.
- Methods: `GET` / `POST` / `PATCH` / `DELETE`. No `PUT`.
- Actions that produce something storable are a `POST` to a collection (`POST /api/searches`, `POST /api/product-images/{id}/classifications`). Use an "action endpoint" (`POST /api/documents/reindex`) only when no resource results.
- Responses: plain resources and plain arrays, `snake_case` fields, UUID ids, ISO timestamps. No `{"data": ...}` wrapper.
- Errors: always `{"error": "<code>", "message": "..."}` (plus `fields` on 422), produced by the global handler from `core/errors.py` exceptions: 400 `BadRequestError`, 404 `NotFoundError`, 409 `ConflictError`, 502 `UpstreamError` (Apertus failed).
- Lists: filter via query params, `?sort=-created_at` with whitelisted fields, no pagination.
- LLM text endpoints support `?stream=true` (SSE: `tool_call` and `tool_result` while tools run, then `token`… → `done`; `error` can come at any point and ends the stream, and the turn is then not stored); the default is plain JSON.

**Naming:** feature folders plural snake_case; routes plural kebab-case with descriptive path params (`/conversations/{conversation_id}/messages`); service methods verb_noun (`create_message`); repository methods come from `BaseRepository` (`get_by_id` returns `None`, and the service decides whether that's an error). No LangChain or LlamaIndex.

## Code style

Formatting, import order, naming case, type hints on signatures and leftover `print`s are enforced by `ruff` (backend) and Prettier + ESLint (frontend). Run them; don't spend words or review time on what they catch. The rules below are the ones no tool checks. Write the least code that does the task cleanly.

- **Copy the reference.** A new feature has the same files and names as `features/conversations/`. Consistency beats taste.
- **Names** are full words (`page_number`, not `page_nbr`) and say what comes back.
- **Early return** instead of nesting. No nested ternaries. One function does one job.
- **Named arguments** for every call to our own code (services, repositories, clients, helpers), also with one argument: `get_owned(conversation_id=conversation_id, owner_id=user.id)`. Library calls and exception messages are exempt.
- **Check for missing values explicitly:** `is None` / `=== null`, never truthiness (`0` and `""` are values).
- **Docstrings:** one line, only on controller endpoints, public service methods and client methods. Never repeat what the name and types already say.
- **Comments:** one line, only for things that aren't obvious. No explanations, no multi-line comments, no commented-out code.
- **Validate at the boundary only** (request schemas, LLM output). No `try/except` unless you handle the error, and no checks for cases our own code can't produce.
- **Nothing speculative:** no parameter with one caller, no wrapper around a single call, no base class with one subclass.
- **No compatibility code:** change things in place and delete the old code. No shims, flags or `_v2`.
- **No extra logging.** The Apertus client logs LLM calls; otherwise log errors only, with the ID of the resource concerned.
- **Commits and PR titles:** one line. PR body: one line, `Closes #<n>` and your assumptions.

## Frontend rules (`src/frontend`)

The page is deliberately small: React, TypeScript and plain CSS, no component library and no global store.

- **Look:** colours, radii and the font come from `src/tokens.css`, a copy of the e-banking's tokens. No literal colours in `styles.css`.
- **The e-banking is the host.** Context, token and navigation go through `src/host.ts` and nowhere else. The protocol is in `starter/docs/trustroom-panel-context.md`.
- **API access** goes through `api()` in `src/api.ts`, which sends the customer's token. Streaming goes through `useStream`. Never parse SSE elsewhere.
- **It has to work at 440 px,** the width of the side panel, and in the full page.
- **Every API wait has three states:** loading, error and empty. Never a blank screen.
- **Model output is untrusted text.** Render it as text, never as HTML.
- Components are named `function` declarations with destructured props. `async`/`await`, never `.then()` chains. No `any`.

## Scope

One concern per PR: one capability or one fix, end to end. If you notice something else worth fixing,
add a card for it.

## Tests

- Never weaken, skip or delete a failing test to make it pass. If you think the test is wrong, stop
  and explain why. When your card changes the behaviour a test pins, update that test in the same
  PR and name it in the PR body with the reason.
- Tests check outcomes (stored rows, response bodies, return values), not just that a mock was called.
- Tests use a fake Apertus and a fake banking API, both faked at the HTTP level (`tests/conftest.py`).
- Tests run against real Postgres. Don't replace the DB with mocks.
- Model quality is measured by evals (`src/backend/evals`), against a running backend on the real
  gateway. They are not part of the gates.

## Commands

- Whole stack (from `starter/`): `docker compose up -d`. E-banking on 8090, banking API on 8000,
  MCP server on 8001, OCR on 8002. Demo logins are in `starter/README.md`.
- Their example TrustRoom: `TRUSTROOM_URL=http://localhost:3000 docker compose --profile example up -d`.
- Model settings for local work: `.env` in the repo root with the three `LLM_*` variables.
- Our Postgres (from `src/`): `docker compose up -d db`, on port 5433.
- Web search (from `src/`): `docker compose up -d searxng`, on port 8089, and
  `SEARXNG_URL=http://localhost:8089` in `src/backend/.env`. Without it the chat has no web search.
- Backend (from `src/backend`): `uv run alembic upgrade head`, then
  `uv run uvicorn app.main:app --reload --port 8010`.
- Frontend (from `src/frontend`, after `npm install`): `npm run dev`, on port 3000, which is where
  `TRUSTROOM_URL=http://localhost:3000` points the e-banking.
- Everything of ours in Docker (from `src/`): `docker compose --profile app up --build`, page and
  API on port 3000.
- Logged-in call with `curl`: get a token from the banking API, then send it as a bearer header.
  ```
  TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login -H 'Content-Type: application/json' \
    -d '{"username": "lukas", "password": "lukas2026"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')
  curl -H "Authorization: Bearer $TOKEN" http://localhost:8010/api/conversations
  ```
- Evals (from `src/backend`, with the backend running): `uv run python -m evals.run --base-url http://localhost:8010`.
- Board: `python3 .claude/skills/scrum-board/board.py list`.
- Checks before landing: `.claude/skills/land-card/gates.sh`.
