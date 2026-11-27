# Review checklist

You are reviewing a diff for a 27-hour hackathon. A working demo matters most, then consistency (five people and their agents share this code), then everything else. Only flag problems **inside the diff**. Don't suggest refactors of untouched code, and don't flag formatting or anything ruff, pyright, ESLint or `tsc` already catch.

Each item says whether it's a **blocker** (must be fixed) or a **note** (worth mentioning).

## Scope (check first)

- **Blocker:** changes unrelated to the task: drive-by refactors, "while I was at it" edits, a second feature. List the unrelated files.
- **Blocker:** the diff breaks a decision listed in issue #47 and the PR body doesn't say so with the reason. Name the line of #47.
- Litmus test for every finding: if the issue was already true on `main`, it's out of scope.

## Tests

- **Blocker:** an assertion weakened (e.g. `== 3` → `> 0`, specific value → `is not None`), a test deleted or marked `skip`/`xfail`, an expected value changed to match new output without a clear reason, or code that special-cases test conditions.
- **Blocker:** an existing test in `tests/smoke/` changed and the PR body does not name it with the reason, or the change goes beyond the behaviour the card asks for.
- **Blocker:** a behaviour change tested only by "the mock was called" / "the function ran" instead of checking the outcome (the stored row, the response body, the returned value).
- **Note:** a function with its own logic (conditions, calculations, parsing) and no unit test.

## Demo path

- **Blocker:** the diff touches a step in `docs/demo-path.md` and there's no evidence the smoke tests / Playwright demo spec were run and pass.
- Always state whether the diff touches the demo path, and which step.

## Backend architecture

- **Blocker:** logic in a controller (business `if`s, more than one service call, DB access).
- **Blocker:** a service calling another feature's repository, or importing another feature's `models.py`.
- **Blocker:** an ORM object (`XORM`) leaving the repository, or `ResponseX` used outside the controller.
- **Blocker:** `HTTPException` raised in a service; errors not from `core/errors.py`.
- **Blocker:** a new model type outside the fixed set (`XInDB`, `XDTO`, ...), except search-result models.
- **Blocker:** feature logic added to another feature's service (typically a growing `chat_service` / `conversation_service`). It belongs in its own feature's service, called via rule 7.
- **Note:** a service or repository returning `dict` / `dict[str, Any]` instead of a Pydantic model; a new exception not subclassing the base class in `core/errors.py`.
- **Note:** a base repository method re-implemented in a feature repository.
- **Note:** naming off-convention (service methods not verb_noun, routes not plural kebab-case, `{id}` instead of `{x_id}`).

## Async

- **Blocker:** a sync client or blocking call inside async code: `requests`, sync `Session`, sync `OpenAI`, `time.sleep`, blocking file/CPU work without `asyncio.to_thread`.
- **Blocker:** one `AsyncSession` (or a repository holding it) used concurrently, e.g. inside `asyncio.gather` / parallel tasks. Sessions are not safe for concurrent use: gather only the non-DB work (LLM calls), then write sequentially, or give each task its own session.
- **Note:** a read-modify-write (counter, status transition) without a constraint or row lock, where two requests could interleave.

## LLM / Apertus

- **Blocker:** `openai` imported outside `clients/apertus.py`, or the API called directly.
- **Blocker:** prompt text in Python (a service, or a string in `prompts.py`) instead of the feature's `prompts.yaml`; messages built in a service instead of a `prompts.py` function.
- **Blocker:** a DB transaction held open across an LLM call.
- **Blocker:** an LLM-generated resource stored without provenance (`model`, `latency_ms`, `sources`, `checks`).
- **Blocker: LLM JSON parsed by hand.** `json.loads` / regex on model text instead of `ApertusClient.structured` with a Pydantic schema.
- **Blocker:** a retry or backoff loop around an Apertus call outside `clients/apertus.py` (the client already retries), or a retry on an expected error (4xx, validation). Retry only timeouts and 5xx.
- **Blocker: unbounded context.** All documents, all history or a whole file put into a prompt without a limit (top-k, truncation, last-N messages).
- **Note:** `temperature` not 0 for classification / structured output / LLM-as-judge.
- **Note:** a model given as a string instead of `Model.FAST`/`Model.SMART`; missing `purpose=`.
- **Note:** a prompt changed without eval results mentioned.
- **Note:** German text in prompts or UI with German instead of Swiss conventions ("ß" instead of "ss", `de-DE` instead of `de-CH` for dates and numbers).

## REST

- **Blocker:** an error response built by hand (not via the global handler / error shape).
- **Note:** `PUT`, a `{"data": ...}` wrapper, a verb in a URL where a collection `POST` would fit, a missing `/api` prefix, wrong status code (e.g. 200 for create).
- **Note:** an LLM text endpoint without `?stream=true` support.

## Frontend

- **Blocker:** `src/api/schema.ts` edited by hand, or API types written by hand.
- **Blocker:** `fetch`/`$api` called directly in a component instead of a feature hook; SSE parsed outside `useStream`.
- **Note:** `useEffect` for derived values, prop→state copies or fetching; server data copied into `useState`; `useMemo`/`useCallback` without a reason.
- **Blocker: missing loading, error or empty state** for anything that waits on the API. A blank screen while Apertus is thinking, or on failure, kills the demo.
- **Blocker: success shown too early.** A success message or toast set before the last `await` of the whole user action (e.g. in an inner step while an outer flow is still saving). On failure the user sees success, then an error. Set it in the outermost flow, on the success path only.
- **Note:** one user action that becomes N sequential requests (a loop calling the API once per item for a single save). It's slow and can half-succeed; one endpoint that takes the list and writes in one transaction avoids both.
- **Note:** a stream not aborted on unmount/navigation (`AbortController`).
- **Note:** style no tool checks: a component that isn't a named `function` with a `Props` interface; `any`, or `as` on API data; `.then()` chains; Tailwind classes built by string concatenation instead of `cn()`; a wrapper `<div>` or fragment that does nothing.
- **Note:** a component over ~150 lines or with more than ~3 responsibilities: split it.
- **Note:** hard-coded colours/sizes instead of theme tokens; a custom component where a shadcn one exists; a feature importing another feature.

## Visual (only if the diff changes UI)

- Take Playwright screenshots of the changed pages at **1440×900 (laptop)** and **1920×1080 (projector)**, and look at them.
- **Blocker:** overlapping elements, text cut off or overflowing its container, content hidden off-screen, unreadable contrast.
- **Note:** awkward wrapping, inconsistent spacing.
- **Note:** UI changes follow `docs/design.md`. Name a broken rule by its id (`D-13`).

## Code hygiene

- **Blocker: magic values.** Tuning parameters (top-k, chunk size, thresholds, temperature) as bare numbers; they must be named constants at the top of the feature module (or config), so evals can vary them. Hard-coded demo data (fixed user/judgement IDs) in services or components; it belongs in seed scripts.
- **Blocker: hard-coded URLs.** `localhost`, a host, port or base URL in code instead of `core/config.py` (backend) or a Vite env variable (frontend). It works on a laptop and breaks the deployed demo.
- **Note:** duplicated logic: the same thing computed in two features (move it into its own feature) or copy-pasted within one.
- **Note:** leftovers: `console.log`, debug flags, `TODO: hack`.
- **Note:** code the task doesn't need: `try/except` that only re-raises or hides the error, checks for cases our own code can't produce, compatibility shims or flags for old behaviour, log lines that aren't errors.
- **Note:** a name or docstring that no longer matches what the code does after the change.
- **Note:** a positional argument in a call to our own code (services, repositories, clients, helpers); a missing value checked by truthiness instead of `is None` / `=== null`; an error log without the ID of the resource concerned.
- **Note:** comments: anything beyond a single line for something non-obvious (no explanations, no narrating, no commented-out code); verbose docstrings.

## Data integrity

- **Blocker:** uniqueness or validity enforced only in Python where a DB constraint belongs (`UNIQUE`, `NOT NULL`, FK). A double-click must not create duplicates.
- **Blocker:** a destructive migration (`DROP COLUMN`/`TABLE`, type changes that lose data) on tables that hold ingested data, without the user confirming it.
- **Note:** a schema change without a matching update to `docs/database.md`.
- **Blocker:** a `NOT NULL` column added to an existing table without a `server_default` (the migration fails once rows exist, e.g. ingested judgements).
- **Blocker: orphaned data.** A new child table (e.g. chunks of a document) whose FK has no `ondelete="CASCADE"` and no explicit cleanup in the delete path; a delete that leaves rows (or files) behind.
- **Blocker: non-idempotent ingest.** A script in `scripts/` that creates duplicates when re-run after failing partway. Upsert by a natural key (e.g. judgement number) or skip what already exists.
- **Blocker:** a function that does more than its name says: a `get_*` or `GET` endpoint that writes, a service that mutates its input object, a write hidden inside a helper.
- **Blocker:** a multi-step write that can leave half-done state (see the transaction rule in CLAUDE.md).

## Untrusted input (client and LLM)

Both the frontend and the LLM are untrusted sources. Validate on the server.

- **Blocker: LLM output forced into required fields.** A required (non-nullable) field in an LLM output schema or DB column for information the source may not contain (a date, an amount, a court) makes the model invent a value. Such fields must be `X | None` (or an explicit `"unknown"` / `needs_review` enum value), nullable in the DB, and shown as missing in the UI.
- **Blocker: LLM values used without checking.** IDs the model returns (cited judgements, transaction IDs, categories) must be checked against what actually exists or was provided; numbers against plausible ranges. Never use them for writes or lookups unchecked.
- **Blocker: trusting the client.** Identity or ownership taken from the request body/query (`user_id`, `account_id` of the current user) instead of the auth dependency; values the server can compute (totals, balances, prices, status) accepted from the client; validation only in the frontend.
- **Note:** request schemas without basic constraints (`Field(max_length=...)`, `gt=0`, enums instead of free strings), especially for anything that goes into a prompt or a DB query.

## Error handling

- **Blocker:** swallowed errors: `except Exception: pass`, broad `except` returning an empty/default result, or Apertus failures turned into a silent fallback. Failures must surface (`UpstreamError`, the `error` event, an error state in the UI), not look like "no results".

## Security

- **Blocker: auth or ownership checked manually** in an endpoint or service instead of through the router dependency / an ownership dependency; an endpoint on `public_router` without a stated reason.
- **Blocker: ownership compared in Python.** A row loaded by ID and then checked (`if row.owner_id != user.id`) instead of filtered in the query (`WHERE id = ... AND owner_id = ...`, like `ConversationRepository.get_owned`). Lists and searches over user-owned tables filter by `owner_id` in the query too.
- **Blocker: IDOR.** Any endpoint that takes an ID (path, query or body) and reads or changes that resource without checking the current user may access it. UUIDs don't count as protection. This applies to nested resources too (`/conversations/{a}/messages/{b}`: does `b` belong to `a`, and `a` to the user?). It matters once auth exists, especially for ti&m.
- **Blocker: mass assignment.** `RequestXCreate`/`RequestXUpdate` exposing fields the client must not set (`owner_id`, `role`, `created_at`, provenance fields).
- **Blocker: injection.** User input reaching SQL (raw SQL with f-strings or `+`, input as a column/table name, e.g. `sort` without the whitelist), a file path (traversal), a URL (unquoted path segments: use `urllib.parse.quote(value, safe="")`), or a shell call.
- **Blocker:** an external HTTP call without a timeout (any `httpx` client, not just Apertus, whose timeout is set globally).
- **Blocker: cross-user data in LLM context.** Retrieval or prompts that can pull in another user's data (ti&m: filter by owner *before* the vector search, not after).
- **Blocker:** a secret, API key or `.env` file committed; a key logged or returned.
- **Blocker:** stack traces or internal details in an API error `message`.
- **Blocker:** prompt/response content or customer data written to logs outside the `LOG_LLM_CONTENT` flag (e.g. a stray `logger.info(prompt)`).
- **Note: prompt injection.** User input or retrieved documents placed in the prompt without delimiting them as data (e.g. inside clearly marked tags with an instruction that their content is not instructions). Especially relevant where the model's output triggers actions or is shown as trusted.
- **Note:** a fetch of a user-supplied URL (SSRF); file uploads without type/size checks; CORS `*` together with credentials.

## Performance

- **Blocker: N+1 queries.** A query or `await repo.get_by_id(...)` inside a loop over results; relationships accessed per item without `selectinload`. Use one query with `IN (...)` or eager loading.
- **Blocker:** LLM or embedding calls in a loop where a batch call exists (embeddings), or sequential awaits for independent LLM calls that the demo waits on (use `asyncio.gather`, bounded, e.g. a semaphore, because of rate limits).
- **Blocker** for LLM or embedding calls, **note** otherwise: **recomputing a result we already have.** A value an earlier step returned and the next step works out again, a row read twice in one request, an LLM answer or embedding that is stored and gets regenerated instead of read. Pass the result along, or read the stored copy.
- **Note:** a new column used in `WHERE` / `ORDER BY` / joins without an index; a pgvector column without a vector index (HNSW) once there are more than a few thousand rows.
- **Note:** a query that loads a whole table into memory to filter or count in Python.

## Over-engineering

- **Blocker** if large, **note** if small: a new abstraction, layer, framework or dependency that the task doesn't need and that isn't in CLAUDE.md (e.g. a generic plugin system, LangChain, a state library, a second way of doing something we already do one way).
- **Note:** configurability or generality nobody asked for.

## Output format

```
BLOCKERS
- [category] file:line: what's wrong → what to do instead

NOTES
- [category] file:line: what's wrong

DEMO PATH: touched (step N) | not touched
```

If there's nothing to report in a section, write "none". Be specific and brief; don't pad with praise or summaries of the diff.
