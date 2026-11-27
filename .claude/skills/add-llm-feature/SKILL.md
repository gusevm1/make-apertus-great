---
name: add-llm-feature
description: Procedure for building or changing a backend feature that calls Apertus (the LLM): chat replies, summaries, classification, extraction, RAG answers, LLM-as-judge. Use this whenever a task involves generating, summarising, classifying or answering with the model, or touching a prompt, even if the request doesn't say "LLM" or "Apertus", e.g. "summarise the judgements", "let the user ask about their transactions", "categorise the product", "make the answer cite its sources".
---

# Building an LLM-powered feature

The rules for using Apertus (client only, `Model` enum, prompts in `prompts.yaml` + `prompts.py`, provenance) are in CLAUDE.md. This is the procedure. For the endpoint and the layer plumbing, follow the `add-endpoint` skill as well; this skill covers only the LLM-specific parts.

Read the reference first: `app/features/conversations/` has a working `prompts.yaml` + `prompts.py` and a streamed endpoint. The client calls (`chat`, `stream_chat`, `structured`) are in `app/features/tool_calls/service.py`, which answers its messages.

## 1. Decide the output shape

- **Free text** (chat answer, summary): use `chat()` / `stream_chat()`.
- **Structured** (category, extracted fields, verdict): define a Pydantic model and use `structured(schema=...)`. Keep it small and flat, and give every field a `Field(description=...)`. The model reads those descriptions as instructions, so write them like instructions.
- **Make a field optional (`X | None`) whenever the source might not contain it,** and say so in the description ("null if the judgement doesn't state it"). A required field makes the model invent a value, which is a hallucination you created through the schema. Matching DB columns are nullable.

Either way, the stored resource gets the provenance fields `model`, `latency_ms`, `sources`, `checks`. Store enough of the input that the prompt can be rebuilt from the resource alone; that's how we debug without logging content. They are shown in the UI. For our challenges, transparency is part of the product, not a debug feature.

## 2. Write the prompt function

The text goes in `app/features/<feature>/prompts.yaml`, with `{placeholders}` for the inputs:

```yaml
summary_system: |
  ...
summary_user: |
  Frage: {query}

  Urteile:
  {judgements}
```

The function goes in `app/features/<feature>/prompts.py`:

```python
PROMPTS = load_prompts(__file__)

def summary_prompt(query: str, judgements: list[Judgement]) -> list[Message]:
    user = PROMPTS["summary_user"].format(query=query, judgements=_format(judgements))
    return [
        {"role": "system", "content": PROMPTS["summary_system"]},
        {"role": "user", "content": user},
    ]
```

- No prompt text in Python. A literal `{` or `}` in the YAML (e.g. a JSON example) is written `{{` / `}}`, because the text goes through `.format()`.
- Typed inputs, returns a message list, no I/O beyond loading the YAML once at import. Evals import this same function.
- When the answer must be grounded in sources, number them in the prompt (`[1]`, `[2]`, ...) and tell the model to cite only those numbers. The service can then check every citation against what was actually provided.

## 3. Call the client from the service

```python
result = await self.apertus.chat(
    summary_prompt(query, judgements),
    model=Model.SMART,
    purpose="suva_summary",
)
# result.content, result.model, result.latency_ms
```

- `purpose` is a short snake_case label. It's how the JSON-lines log is filtered.
- Default to `Model.SMART` until an eval shows `Model.FAST` is good enough for this task.
- Follow the transaction rule in CLAUDE.md: commit the input before the call and store the result after it.

## 4. Validate, then store with provenance

- Treat the model's output as untrusted input. Run deterministic checks before storing: every cited `[n]` exists among the sources, every returned ID exists, numbers are in plausible ranges. Put the outcome in `checks`, including failures. Show a failed check instead of hiding it.
- Store `content` + `model` + `latency_ms` + `sources` + `checks` on the resource through the repository.

## 5. Endpoint

For text output, support both representations (CLAUDE.md, REST): plain JSON by default, SSE with `?stream=true`. The service exposes `create_x()` and `stream_x()`, sharing the prompt and storage logic. When streaming, checks run after the stream ends and go in the `done` event.

## 6. Evals

Add questions for the feature to `src/backend/evals/questions.yaml` and run them against your running backend, on the real gateway:

```
uv run python -m evals.run --base-url http://localhost:<your backend port>
```

If you're fixing a bad answer, add that case to the dataset first. Report the scores and latencies to the user. Model choice per task is decided from these numbers. Prompt changes should be re-evaluated before they're merged.

## Done checklist

- [ ] Prompt text in `prompts.yaml`, messages built in `prompts.py`, nothing inlined in the service
- [ ] Structured output uses a Pydantic schema with field descriptions
- [ ] Client called with `model=` and `purpose=`
- [ ] Provenance (`model`, `latency_ms`, `sources`, `checks`) stored and returned
- [ ] Text endpoints support `?stream=true`
- [ ] Eval cases added and run on both models
- [ ] `add-endpoint` checklist done too
