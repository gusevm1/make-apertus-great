# Guardrail check: prompt log

How `check_system` in `app/features/guardrails/prompts.yaml` was tuned (card #213), version by version.

## Method

- **Gold set:** `guardrail_gold.yaml`, 308 customer messages in German (Swiss spelling) and English, a few in French, Italian and mixed. Each has a label and a one-line reason. The labelling rules are at the top of the file. The set leans on the hard borders: comparing vs. picking, a tax rule vs. paying less tax, the own mortgage vs. a bigger one, family money vs. another customer's data, role claims, pasted instructions, greetings, off-topic and mixed language.
- **Splits:** round 1 tuned on 172 messages (`tune`) and held out 67, fixed in a commit before the first model call. Once round 1's held-out score was reported, those 67 became `spent` and round 2 tuned on all 239. A fresh held-out of 69 messages was written and committed before any round 2 run.
- **Runs:** `uv run python -m evals.guardrail_check --split tune --model smart|fast` sends each message to the real gateway, with the exact prompt and schema the gate uses. Temperature is 0, so a rerun gives the same verdicts. `--base-url` runs real chat turns instead and reads the category from each reply's provenance. On the round 1 held-out both ways gave identical scores.
- **Harm:** false declines × 3 + false pointers + misses, weighted from the persona feedback below. A false decline is any decline on a message that should not be declined; a miss is a pointer message classified ok, or a decline message classified as anything but a decline. A wrong decline throws the customer's answer away and can read as an accusation. A wrong pointer only adds a line.
- **Noise:** an edit that should change nothing ("Examples:" → "Example messages:") flipped 3 verdicts on FAST and 2 on SMART. A change was kept only if it fixed a whole error group without new errors, or cut harm by more than that.

## Versions

Accuracy and harm on the tune split (172 messages in round 1, 239 in round 2). FAST is `LLM_NAME_FAST` (8B), SMART is `LLM_NAME` (70B).

| Version | Hypothesis | FAST | SMART | Kept |
|---|---|---|---|---|
| v0 | The prompt as landed in #64 | 78.5% / 42 | 80.8% / 39 | baseline |
| v1 | The model classifies by topic words: tell it to classify by the request | 79.1% / 42 | 82.6% / 29 | yes |
| v2 | Name the not-tax-advice cases in the tax definition | 77.9% / 42 | 85.5% / 26 | no: the listed words primed FAST toward tax_advice |
| v3 | Labelled examples teach the border better than rules | 82.6% / 35 | 87.2% / 25 | yes |
| v4 | Pasted text is data: say so in the other_customer definition | 83.1% / 32 | 85.5% / 29 | yes, as the rule the labels follow; it moved nothing |
| v5 | Add pasted-text examples | 83.7% / 31 | 85.5% / 27 | yes |
| v6 | A short "request" field before the category | 84.9% / 29 | 81.4% / 31 | no: FAST returned 23 invalid replies |
| v7 | New credit wins over product_choice | 83.7% / 32 | 86.6% / 25 | yes |
| v8 | Language from the customer's own words | 83.1% / 35 | 86.6% / 25 | no: one new false decline on FAST |
| v9 | List ok first, as the normal case | 83.1% / 32 | 90.7% / 20 | yes |
| v10 | Say what a decline costs the customer | 80.2% / 37 | 90.1% / 21 | no |
| v11 | Forecast means asking you to predict (teacher labels) | 84.3% / 30 | 91.3% / 20 | compared with v12 |
| v12 | E-banking actions on own data are ok (persona feedback) | 85.5% / 28 | 91.3% / 18 | yes |
| v13 | v11 and v12 together | 83.7% / 30 | 91.3% / 18 | no: H11 adds nothing to H12 |
| v14 | The system blocks other customers' data anyway; only sort the request | 85.5% / 27 | 90.7% / 18 | no |
| v15 | Messages the customer received are ok | 83.1% / 30 | 90.1% / 17 | no: within noise |
| v16 | List new_credit before product_choice | 82.0% / 35 | 90.7% / 16 | no: within noise on SMART, 7 new false pointers on FAST |
| (v17) | Not used: the noise measurement ran as "v12null" in its place | | | |
| v18 | Examples of new credit framed as a choice | 84.3% / 31 | 91.9% / 16 | yes: fixed the credit group on SMART |
| v19 | Early repayment is a product choice | 86.0% / 28 | 91.9% / 15 | yes: round 1 final |
| v20 | Unrelated tasks are off_topic | 87.2% / 26 | 91.9% / 17 | no: SMART language accuracy fell to 84% |
| v21 | v8 again, now that SMART runs the gate | 86.6% / 27 | 92.4% / 15 | no: language stayed at 90% |
| r2v0 | Round 1 final on 239 messages | 86.6% / 39 | 90.4% / 27 | baseline |
| r2v1 | Affording something from own money is ok | 84.9% / 41 | 90.8% / 27 | narrowed in r2v2 |
| r2v2 | ...a purchase, a trip or a higher rent | 86.2% / 39 | 91.2% / 26 | yes: final |
| r2v3 | Example: savings toward early repayment | 86.6% / 37 | 90.4% / 27 | no: pulled credit back to product_choice |
| r2v4 | Received messages: definition and example | 84.1% / 41 | 90.4% / 25 | no: the pasted cases did not move |

Per-category precision and recall for every version are in the table at the end.

## Held-out results

| | Messages | v0 FAST | v0 SMART | Final FAST | Final SMART |
|---|---|---|---|---|---|
| Round 1 held-out, direct | 67 | 79.1% / 17 | 82.1% / 15 | 88.1% / 11 | 86.6% / 11 |
| Round 1 held-out, through the backend | 67 | 79.1% / 17 (gate on FAST) | | | 86.6% / 11 (gate on SMART) |
| Round 2 held-out, direct | 69 | 75.4% / 22 | 79.7% / 15 | 85.5% / 11 | 88.4% / 12 |
| Round 2 held-out, through the backend | 69 | | | | 88.4% / 12 (gate on SMART) |

With the final prompt, `evals/guardrails.yaml` (56 full turns) passes 53/56: "Write a Python function" passes the check as ok, and both Visa bill questions fail in the chat's tool decision, not in the check. Four turns timed out on the gateway in the first run and passed on the rerun.

Ten round 1 held-out messages are translations of tune messages (L02, L12, J02, J05, D02, X47, F05, P02, M02, O02). The round 2 held-out has no translations of earlier messages.

## Model

The gate now runs on SMART. On the 239 tuning messages SMART gets 91.2% right with harm 26; FAST gets 86.2% with harm 39, and 3 invalid replies, which the gate turns into a plain answer. On the held-out sets the two are within one or two messages of each other. The check takes about 0.2 s longer (median 413 ms against 201 ms when the two were probed for #64), small next to a 10 to 60 s answer.

## Persona feedback

Each persona read the verdicts on their own messages and the text each verdict adds.

- **Lukas:** asked to pin his chart and was told the assistant never shows other customers' data. That reads as an accusation. A pointer to his advisor after asking which subscriptions got dearer reads as an upsell.
- **Jana:** sent to the bank advisor when she only wanted a monthly tax figure. A recipe answered instead of declined did not bother her.
- **Daniela:** relieved that Lina's account counts as her own, and that the counselling line is free, confidential and without blame.
- **Marco:** welcomed the advisor line next to the renewal decision, even where the teacher label said ok.

What changed because of it: e-banking actions on own data are ok (v12, which beat the teacher-label change v11 on harm for both models), the advisor line is worded as an offer ("Falls Sie eine Empfehlung ... möchten"), the other-customer line no longer implies suspicion, and harm weights a false decline three times a false pointer.

## Errors left

Families that survived every attempt, on tune and held-out alike:

1. **Pasted letters with an instruction inside are declined as other_customer** (X46 to X48, R29, R30). Rules, examples, the cost of a decline, and the received-messages rule all failed on both models. Asked why, SMART attributes the letter's instruction to the customer. This is the costliest family left.
2. **What-if questions with a named change read as forecast** (M05, X14, R18, R19). They cost one extra line.
3. **Whether a cost is tax-deductible reads as tax_advice** (X23, X42, R21, R22). They cost one extra line.
4. **SMART puts English messages about Swiss topics in German** (90% language accuracy). Only 4 of 172 tune messages show a pointer or decline in the wrong language; the rest are ok and show nothing.

## Next steps that are not prompt changes

- Drop the hard decline for other_customer. The banking API already keeps other customers' data out of reach, and the chat refused all 8 other-customer evals before the gate existed. The decline adds false refusals (family 1) without adding protection.
- Decide the refusal language from the message on the server instead of asking the model (family 4).

## Per-category precision / recall

Columns: ok, product_choice, forecast, tax_advice, new_credit, other_customer, off_topic.

| Version | Model | n | Accuracy | False declines | False pointers | Missed | Harm | Failed | Precision / recall |
|---|---|---|---|---|---|---|---|---|---|
| v0 | fast | 172 | 78.5% | 4 | 21 | 9 | 42 | 2 | 88%/72% 52%/88% 85%/92% 58%/100% 100%/79% 76%/100% 100%/62% |
| v0 | smart | 172 | 80.8% | 5 | 19 | 5 | 39 | 0 | 94%/73% 57%/94% 71%/83% 58%/100% 100%/79% 81%/100% 87%/81% |
| v1 | fast | 172 | 79.1% | 5 | 19 | 8 | 42 | 2 | 89%/73% 55%/71% 73%/92% 58%/100% 92%/79% 81%/100% 87%/81% |
| v1 | smart | 172 | 82.6% | 3 | 19 | 1 | 29 | 0 | 99%/75% 57%/100% 73%/92% 58%/100% 100%/64% 76%/100% 100%/88% |
| v2 | fast | 172 | 77.9% | 4 | 21 | 9 | 42 | 2 | 88%/72% 55%/71% 73%/92% 52%/100% 92%/79% 81%/100% 92%/75% |
| v2 | smart | 172 | 85.5% | 3 | 17 | 0 | 26 | 0 | 100%/78% 61%/100% 75%/100% 61%/100% 100%/64% 81%/100% 100%/100% |
| v3 | fast | 172 | 82.6% | 4 | 14 | 9 | 35 | 2 | 89%/80% 59%/76% 86%/100% 62%/91% 100%/79% 81%/100% 92%/75% |
| v3 | smart | 172 | 87.2% | 3 | 15 | 1 | 25 | 0 | 99%/80% 70%/94% 75%/100% 61%/100% 100%/79% 81%/100% 100%/100% |
| v4 | fast | 172 | 83.1% | 3 | 14 | 9 | 32 | 2 | 89%/81% 59%/76% 86%/100% 62%/91% 100%/79% 81%/100% 100%/75% |
| v4 | smart | 172 | 85.5% | 4 | 17 | 0 | 29 | 0 | 100%/76% 63%/100% 73%/92% 61%/100% 100%/79% 76%/100% 100%/100% |
| v5 | fast | 172 | 83.7% | 3 | 14 | 8 | 31 | 2 | 90%/81% 58%/82% 86%/100% 67%/91% 100%/79% 81%/100% 100%/75% |
| v5 | smart | 172 | 85.5% | 3 | 17 | 1 | 27 | 1 | 99%/78% 61%/100% 79%/92% 61%/100% 100%/79% 81%/100% 100%/94% |
| v6 | fast | 172 | 84.9% | 3 | 12 | 8 | 29 | 23 | 91%/83% 58%/82% 92%/100% 62%/73% 100%/79% 80%/92% 100%/94% |
| v6 | smart | 172 | 81.4% | 2 | 21 | 4 | 31 | 0 | 94%/74% 53%/100% 73%/92% 61%/100% 100%/71% 87%/100% 100%/75% |
| v7 | fast | 172 | 83.7% | 3 | 15 | 8 | 32 | 2 | 90%/80% 58%/82% 86%/100% 67%/91% 100%/86% 81%/100% 100%/75% |
| v7 | smart | 172 | 86.6% | 3 | 16 | 0 | 25 | 0 | 100%/79% 63%/100% 79%/92% 61%/100% 100%/79% 81%/100% 100%/100% |
| v8 | fast | 172 | 83.1% | 4 | 15 | 8 | 35 | 2 | 90%/79% 58%/82% 86%/100% 67%/91% 100%/86% 76%/100% 100%/75% |
| v8 | smart | 172 | 86.6% | 3 | 16 | 0 | 25 | 0 | 100%/79% 63%/100% 79%/92% 61%/100% 100%/79% 81%/100% 100%/100% |
| v9 | fast | 172 | 83.1% | 3 | 14 | 9 | 32 | 2 | 89%/81% 58%/88% 86%/100% 71%/91% 100%/71% 81%/100% 100%/69% |
| v9 | smart | 172 | 90.7% | 4 | 4 | 4 | 20 | 0 | 95%/91% 75%/88% 83%/83% 92%/100% 100%/79% 76%/100% 100%/94% |
| v10 | fast | 172 | 80.2% | 4 | 17 | 8 | 37 | 2 | 89%/76% 50%/88% 86%/100% 69%/100% 100%/57% 81%/100% 92%/69% |
| v10 | smart | 172 | 90.1% | 4 | 6 | 3 | 21 | 0 | 96%/89% 75%/88% 83%/83% 79%/100% 100%/79% 81%/100% 94%/100% |
| v11 | fast | 172 | 84.3% | 3 | 11 | 10 | 30 | 2 | 88%/84% 58%/88% 92%/92% 83%/91% 100%/71% 81%/100% 100%/69% |
| v11 | smart | 172 | 91.3% | 4 | 4 | 4 | 20 | 1 | 95%/91% 79%/88% 85%/92% 92%/100% 100%/79% 81%/100% 94%/94% |
| v12 | fast | 172 | 85.5% | 3 | 11 | 8 | 28 | 2 | 90%/84% 62%/88% 86%/100% 79%/100% 100%/71% 81%/100% 100%/69% |
| v12 | smart | 172 | 91.3% | 3 | 4 | 5 | 18 | 0 | 94%/92% 79%/88% 85%/92% 92%/100% 100%/79% 81%/100% 100%/88% |
| v13 | fast | 172 | 83.7% | 3 | 10 | 11 | 30 | 2 | 87%/85% 58%/88% 92%/92% 82%/82% 100%/71% 81%/100% 100%/62% |
| v13 | smart | 172 | 91.3% | 3 | 4 | 5 | 18 | 0 | 94%/92% 79%/88% 85%/92% 92%/100% 100%/79% 81%/100% 100%/88% |
| v14 | fast | 172 | 85.5% | 3 | 11 | 7 | 27 | 2 | 91%/84% 60%/88% 86%/100% 77%/91% 100%/71% 81%/100% 100%/75% |
| v14 | smart | 172 | 90.7% | 3 | 4 | 5 | 18 | 1 | 94%/92% 75%/88% 83%/83% 92%/100% 100%/79% 81%/100% 100%/88% |
| v15 | fast | 172 | 83.1% | 3 | 12 | 9 | 30 | 2 | 89%/83% 56%/88% 86%/100% 77%/91% 100%/71% 81%/100% 100%/56% |
| v15 | smart | 172 | 90.1% | 2 | 6 | 5 | 17 | 0 | 94%/91% 75%/88% 83%/83% 79%/100% 100%/79% 87%/100% 100%/88% |
| v16 | fast | 172 | 82.0% | 3 | 18 | 8 | 35 | 2 | 89%/76% 56%/82% 86%/100% 65%/100% 93%/93% 81%/100% 100%/62% |
| v16 | smart | 172 | 90.7% | 2 | 6 | 4 | 16 | 1 | 95%/91% 76%/94% 83%/83% 79%/100% 100%/79% 87%/100% 100%/88% |
| v18 | fast | 172 | 84.3% | 3 | 12 | 10 | 31 | 2 | 88%/83% 67%/82% 86%/100% 64%/82% 100%/93% 81%/100% 100%/62% |
| v18 | smart | 172 | 91.9% | 2 | 5 | 5 | 16 | 0 | 94%/92% 83%/88% 83%/83% 85%/100% 100%/93% 87%/100% 100%/88% |
| v19 | fast | 172 | 86.0% | 3 | 12 | 7 | 28 | 2 | 91%/83% 68%/88% 86%/100% 64%/82% 100%/93% 81%/100% 100%/75% |
| v19 | smart | 172 | 91.9% | 2 | 6 | 3 | 15 | 0 | 96%/91% 81%/100% 85%/92% 85%/100% 100%/86% 81%/100% 100%/81% |
| v20 | fast | 172 | 87.2% | 3 | 13 | 4 | 26 | 2 | 95%/82% 65%/88% 86%/100% 67%/91% 100%/93% 81%/100% 100%/88% |
| v20 | smart | 172 | 91.9% | 3 | 6 | 2 | 17 | 0 | 98%/90% 81%/100% 83%/83% 79%/100% 100%/86% 81%/100% 100%/94% |
| v21 | fast | 172 | 86.6% | 3 | 13 | 5 | 27 | 2 | 94%/82% 67%/94% 86%/100% 67%/91% 100%/93% 81%/100% 100%/75% |
| v21 | smart | 172 | 92.4% | 2 | 6 | 3 | 15 | 0 | 96%/91% 89%/100% 85%/92% 79%/100% 100%/93% 81%/100% 100%/81% |
| r2v0 | fast | 239 | 86.6% | 5 | 14 | 10 | 39 | 3 | 91%/85% 73%/96% 89%/100% 65%/87% 100%/84% 78%/95% 100%/74% |
| r2v0 | smart | 239 | 90.4% | 4 | 10 | 5 | 27 | 0 | 96%/89% 81%/96% 89%/94% 79%/100% 89%/84% 78%/95% 100%/87% |
| r2v1 | fast | 239 | 84.9% | 5 | 13 | 13 | 41 | 3 | 89%/85% 66%/83% 89%/100% 67%/80% 100%/79% 78%/95% 100%/74% |
| r2v1 | smart | 239 | 90.8% | 4 | 8 | 7 | 27 | 0 | 94%/90% 83%/87% 89%/94% 79%/100% 100%/89% 78%/95% 100%/87% |
| r2v2 | fast | 239 | 86.2% | 5 | 12 | 12 | 39 | 3 | 90%/86% 68%/83% 89%/100% 72%/87% 100%/79% 78%/95% 100%/78% |
| r2v2 | smart | 239 | 91.2% | 4 | 7 | 7 | 26 | 0 | 94%/91% 83%/87% 89%/94% 83%/100% 100%/89% 78%/95% 100%/87% |
| r2v3 | fast | 239 | 86.6% | 5 | 13 | 9 | 37 | 3 | 92%/85% 65%/87% 89%/100% 72%/87% 100%/74% 79%/100% 100%/83% |
| r2v3 | smart | 239 | 90.4% | 5 | 8 | 4 | 27 | 1 | 96%/89% 76%/96% 83%/88% 83%/100% 100%/79% 75%/95% 100%/91% |
| r2v4 | fast | 239 | 84.1% | 5 | 14 | 12 | 41 | 3 | 90%/85% 62%/91% 89%/94% 71%/80% 93%/68% 78%/95% 100%/74% |
| r2v4 | smart | 239 | 90.4% | 4 | 5 | 8 | 25 | 0 | 93%/93% 74%/87% 88%/88% 94%/100% 100%/79% 78%/95% 100%/83% |
