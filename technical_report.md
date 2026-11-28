# Technical report — `project name`, `team name`

A deeper write-up than the README: what you built, how it works, and what the
numbers say.

- **Challenge partner:** ti&m
- **Challenge:** `challenge name`
- **Event:** On-site Zurich
- **Team:** `team name` — `member`, `member`, `member`
- **Demo:** `link to video`

## 1. Summary

The problem, your approach, and the headline result in one paragraph.

## 2. Architecture

Components, data flow, and where each one runs. Put diagrams in `docs/` and
reference them here.

### Target architecture (mandatory)

State which of the three architectures your project is deployable in, and how
it meets that constraint:

- **a) On-premise** — on the organisation's own infrastructure, under its own administration.
- **b) Air-gapped** — with no external network connection at runtime.
- **c) Sovereign Swiss cloud** — on a cloud platform operated in Switzerland, under Swiss jurisdiction, with Swiss data residency.

List any external dependencies, and separate build time from runtime.

### The boards and their data flow (added 28.11.2026)

The TrustRoom page shows boards of tiles with a chat beside them. Three backend
features carry them, in `src/backend/app/features/`:

- `tiles`: sixteen templates. A tile is a template name plus arguments. The
  server computes its figures from the banking API on every read.
- `boards`: boards, tiles and plans in our Postgres, the endpoints, and the
  tools the chat uses to change the open board.
- `board_plans`: the server reads the customer's data, computes signals, and
  Apertus chooses the question, the tiles and their titles.

What goes where at runtime:

- The customer's token, bookings and documents go from the e-banking to the
  banking API and to our backend. We store boards (template and arguments),
  plans with their provenance, conversations and profile notes. We store no
  balance and no booking.
- Our backend sends prompts with the customer's signals and tool results to
  the Apertus gateway (Keera) and to no other model.
- A tile the customer puts on the e-banking dashboard goes to the banking API
  as a declarative widget.
- Web search, when `SEARXNG_URL` is set, sends the search query to search
  engines outside the bank, and only after the customer has read the query and
  allowed it in the page.
- The page serves its own font. It loads nothing from a third party.

## 3. Use of Apertus

- **Model:** `e.g. swiss-ai/Apertus-v1.5-8B`
- **How it is used:** inference | fine-tuning | evaluation | red-teaming | agents / tool use
- **Where it runs:** `local weights, hosted endpoint, ...`

Prompts, adapters, quantisation, serving stack — whatever a reader needs to
rebuild your setup.

### Development reference model (added 28.11.2026)

Runtime uses Apertus only, `apertus-v1-5-70b` through the Keera gateway.

While building the boards we used one other model as a development reference:
`z-ai/glm-5.3` through OpenRouter. It proved the method before we brought
Apertus to the same gate, and it judges generated boards against the rubric in
`src/backend/evals/boards/rubric.md`. It runs only from `src/backend/evals/`,
only on the four demo customers' data, and never serves a customer. The
backend image does not contain the eval code (`src/backend/.dockerignore`).

## 4. Data

What you used, where it came from, and its licence. Flag anything personal or
non-redistributable, and keep it out of the repository (see `.gitignore`).
If data comes from human subjects or contains personal information, describe
how consent was obtained.

## 5. Limitations

Where it breaks, what you did not test, and known failure modes.

## 6. Reproducibility

What a judge needs to get your numbers back: hardware, runtime, seeds, and the
exact commit.


## License

Creative Commons Attribution 4.0 (CC-BY-4.0). All HackApertus projects are open-sourced.

## References
