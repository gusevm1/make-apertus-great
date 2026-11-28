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

For the categorisation, Claude (Opus 5.5) labelled the gold set described in
the next section. It saw only the bookings of the four demo customers, at
development time, and never runs in the product.

### Categorisation compared with Claude (added 28.11.2026)

Apertus gives every spending booking one of 13 categories and a certainty of
high, medium or low. We measured it against a gold set that Claude labelled
booking by booking, following `src/backend/evals/categorisation_rubric.md`.
The gold set is `src/backend/evals/categorisation_gold.jsonl`: 8,623 spending
bookings of the four demo customers, of which the eval scores the 8,575 that
are not loan instalments.

A second Opus labeller relabelled 500 rows blind and agreed on 494 (98.8 %).
So the figures below measure agreement with Claude's labels, not accuracy
against a human, and 98.8 % is about the best the set allows. The six
disagreements sit on real borders, such as a club venue (restaurants or
leisure) or a night train (transport or leisure).

Before the first run we held out one payee in four per customer, 2,316
bookings of 120 payees. We tuned the prompt in ten versions on the other 6,259
bookings and ran the held-out part once, at the end. "Wrong but high" counts
bookings that Apertus got wrong while rating itself high. "Review catches" is
the share of wrong bookings that the category center asks the customer to
check.

| Held out, 2,316 bookings | First prompt (v0) | Final prompt (v9) | v9 with the customer's corrections as examples |
|---|---|---|---|
| Agreement with Claude | 77.6 % | 88.6 % | 89.9 % |
| Wrong but high | 383 | 163 | 182 |
| Agreement at high / medium / low | 82.2 / 14.3 / 29.3 % | 92.1 / 54.6 / 75.0 % | 91.6 / 61.8 / 89.3 % |
| Review catches / share of bookings sent to review | 66.0 / 19.3 % | 58.7 / 17.5 % | 41.7 / 13.6 % |
| Lukas / Jana / Daniela / Marco | 76 / 65 / 65 / 92 % | 82 / 96 / 83 / 97 % | 85 / 95 / 83 / 98 % |

On the tune bookings the same two prompts score 84.7 % and 95.5 %. Both parts
gained about 11 points, so the tuning did not fit itself to the tune payees.
The held-out payees are harder, above all Lukas's travel bookings abroad.

The product runs the third column once a customer has corrected a category,
because it sends those corrections to Apertus as examples. They make Apertus
surer on payees nobody corrected without making it more right, and the review
then catches 41.7 % of the errors instead of 58.7 %. Card #296 drops the
examples and keeps only the payee memory, which on the tune bookings put all
927 bookings of the 38 corrected payees right without calling Apertus.

We measured at commit `cf0c0e1`. Since then the prompt also asks for a second
choice and offers the customer's own categories (`cb6fa88`, `dfcaabd`), and
we have not measured that version. Every prompt version and what it changed
is in `src/backend/evals/categorisation_log.md`.

## 4. Data

What you used, where it came from, and its licence. Flag anything personal or
non-redistributable, and keep it out of the repository (see `.gitignore`).
If data comes from human subjects or contains personal information, describe
how consent was obtained.

## 5. Limitations

Where it breaks, what you did not test, and known failure modes.

### Categorisation (added 28.11.2026)

Apertus agrees with Claude on 88.6 % of the held-out bookings, against a
ceiling of about 98.8 %. The category center sends 59 % of the wrong bookings
to review. The other 41 % carry high certainty and the payee's usual category,
so nothing asks the customer to check them. Most of them are payees whose name
says nothing about what they sell, such as a vegetarian buffet or a bar Apertus
reads as a bookshop. Further tuning needs a fresh held-out part, because the
current one has been seen.

## 6. Reproducibility

What a judge needs to get your numbers back: hardware, runtime, seeds, and the
exact commit.

### Categorisation (added 28.11.2026)

From `src/backend`, with the backend running on its own database and the real
gateway:
`uv run python -m evals.categorisation --base-url http://localhost:8010 --split heldout --out heldout.json`.
The run deletes the stored categories and corrections of the four customers in
that database, so never point it at the shared demo one. Apertus runs at
temperature 0, and two runs of the same prompt still differed by 0.1 points
(95.2 and 95.1 % on the tune bookings).


## License

Creative Commons Attribution 4.0 (CC-BY-4.0). All HackApertus projects are open-sourced.

## References
