# Notes: "Marco" in this repository

> **Warning: there are two different Marcos in the demo data.** Don't mix them up.
>
> 1. **Marco Baumann**: demo customer P4 (`CUST-004`, login `marco`). This is the persona.
> 2. **Marco Rossi**: a friend of Lukas Meier (P1). He appears only as a counterparty in Lukas's transactions and is **not** a customer.
>
> Searching the data for just "Marco" returns both. When filtering by name, match the full name or use the customer ID / folder.

Both are fictitious demo data for the Hack Apertus «TrustRoom» challenge.

---

## 1. Marco Baumann: persona P4 «the homeowner family»

**Login:** `marco` / `marco2026` · **Customer ID:** `CUST-004` · **Data folder:** `P4_Marco_Baumann`

Main sources:
- [Persona_4_Marco_Baumann.md](starter/resources/Demodaten/Personas/Persona_4_Marco_Baumann.md)
- [customer.csv](starter/resources/Demodaten/Daten_CSV/P4_Marco_Baumann/customer.csv)
- [loans.csv](starter/resources/Demodaten/Daten_CSV/P4_Marco_Baumann/loans.csv)

### Profile
- **Personal:** 46, born 1980-07-09, married. Lives at Rebhaldenstrasse 14, 8820 Wädenswil, in a house bought on 2019-04-01 for CHF 1'250'000.
- **Family:** wife Simone (44), a primary school teacher at 60 % who earns approx. CHF 62'400 and banks elsewhere. She sends a monthly household contribution. Children: Noah (12) and Mia (9).
- **Job:** project manager in building construction (Projektleiter Hochbau) at Zimmerberg Bauplanung AG. Earns CHF 128'400 gross, paid as 13 salaries.
- **Bank relationship:** customer since 2006, risk profile «ausgewogen» (balanced). Advisor: Thomas Wyss.

### Accounts (balances as of 2026-11-26)

| Account | Type | Balance (CHF) |
|---|---|---|
| `ACC-PRIV` Privatkonto | current | 18'338.26 |
| `ACC-HOUSE` Sparkonto Haus | savings (goal ≥ CHF 20'000) | 19'350.30 |
| `ACC-SAV` Sparkonto Familie | savings | 64'134.60 |
| `ACC-3A` Säule 3a | pillar 3a | 70'107.25 |

He also has one debit Mastercard (`CARD-DEBIT`). He has **no credit card and no securities account**, so those endpoints return empty lists.

### Mortgage: CHF 900'000 financed in 2019, three tranches (framework agreement HY-8820-0414)

| Loan | Product | Balance (CHF) | Rate | Maturity | Notes |
|---|---|---|---|---|---|
| `LOAN-01` | 10-year fixed | 400'000 | 1.05 % | 2029-03-31 | |
| `LOAN-02` | 8-year fixed | 350'000 | 0.95 % | **2027-03-31** | Renewal offer dated 2026-11-05. **Decision due by 15.12.2026.** If he doesn't decide, it automatically converts to SARON. |
| `LOAN-03` | SARON | 112'500 (of 150'000) | 0.8 % | 2028-03-31 | Includes the 2nd mortgage. Amortised by CHF 1'250 per quarter. |

Interest is charged quarterly to `ACC-PRIV`. The next charge is on 2026-12-31: CHF 1'050 + 831.25 + 225 (provisional), plus CHF 1'250 amortisation.

Marco is the **only persona with loans**. For the other personas, `GET /loans` returns an empty list.

### Other obligations
- **Car lease:** Skoda Enyaq from Seeblick Auto-Leasing AG, CHF 489 a month, currently instalment 30 of 48. It is an external lease, so it is **not** under `/loans` and only shows up as a direct debit.
- **Standing orders:**
  - CHF 900 a month to the house savings account
  - CHF 1'500 a month to the family savings account
  - CHF 600 a month to pillar 3a
  - CHF 1'450 a month in tax prepayments to the Steueramt Wädenswil
- **Repairs:** the facade was repainted in 2026 for more than CHF 18'000, paid from the house savings account.

### Data and documents
- **CSV data:** 17 files in total. They include about 2'000 bookings (Dec 2023 to Nov 2026), 48 loan transactions, 207 payments, 21 payees and 22 upcoming payments. The card-statement and portfolio CSVs are empty.
- **German PDFs** in [Dokumente/P4_Marco_Baumann/](starter/resources/Demodaten/Dokumente/P4_Marco_Baumann/):
  - `Hypothekarvertrag_HY-8820-0414_Baumann.pdf`: mortgage framework agreement
  - `Verlaengerungsofferte_Festhypothek_0880-4471.02_Baumann.pdf`: renewal offer
  - `Zinsausweis_Hypothek_2025_Baumann.pdf`: 2025 interest statement for the tax return

  Only the docs README describes these; I haven't extracted their contents.

### Role in the challenge
Sample questions cover:
- mortgage interest for the tax return
- fixed-rate vs. SARON
- what happens if SARON rises by 1 %
- the total yearly cost of the house
- total debt including the lease
- whether the house savings account is big enough

**Guardrails:** the assistant must not recommend a product or present forecasts as fact. It must refuse to show another customer's data, including when asked through prompt injection.

### Where else he's mentioned
- [starter/README.md](starter/README.md) (lines 137, 280–335)
- [banking-api-contract/README.md](starter/banking-api-contract/README.md) (lines 186–196). Marco's profile has the extra fields `children` and `property`, and `partner_name` is set.
- [openapi.yaml](starter/banking-api-contract/openapi.yaml) line 17
- [banking-frontend/README.md](starter/banking-frontend/README.md) line 20
- [LoginPage.tsx](starter/banking-frontend/src/pages/LoginPage.tsx) line 17
- [docs/docker.md](starter/docs/docker.md) line 67
- [docs/trustroom-panel-context.md](starter/docs/trustroom-panel-context.md) (lines 141, 179)
- [Demodaten/README.md](starter/resources/Demodaten/README.md) line 20
- [Dokumente/README.md](starter/resources/Demodaten/Dokumente/README.md) line 57

---

## 2. Marco Rossi: counterparty in Lukas Meier's (P1) data

He is **not a customer**. He appears only in Lukas's files:
- **TWINT payments:** about 22 between Feb 2024 and Sep 2026 in [P1 bookings.csv](starter/resources/Demodaten/Daten_CSV/P1_Lukas_Meier/bookings.csv), sent and received. Messages include «Znacht», «Bier», «Brunch», «Kino», «Grill», «Taxi» and «Geschenk».
- **Wedding gift:** CHF 300 to «Anna Müller & Marco Rossi» on 2026-05-08. It is `PAY-0217` / `BK-01925`, payee `P-WEDD` (Winterthur), in [payments.csv](starter/resources/Demodaten/Daten_CSV/P1_Lukas_Meier/payments.csv) and [payees.csv](starter/resources/Demodaten/Daten_CSV/P1_Lukas_Meier/payees.csv).

---

## Other
- "marco" doesn't appear in the git history.

---

# Brainstorm: TrustRoom features for Marco Baumann

What makes Marco different from the other personas:
- a **deadline** (renew the fixed tranche by **15.12.2026**, and today in the demo is 27.11.2026)
- **structured loan data** (`/loans` plus `loan_transactions.csv`, each entry linked to a booking)
- **three mortgage PDFs** that can be cross-checked against that data
- a **two-income household** where only his income is visible

The ideas below lean on the docking points: side panel / full page, dashboard widgets, `navigate` deep links, payment proposals and document upload with OCR.

Figures marked *(computed)* come from a quick script over the CSVs. Double-check them before using them in a demo.

## Tier 1: highest value for the pitch

### 1. «Mortgage decision room» for the LOAN-02 renewal
- **Countdown widget:** «18 days left to decide on tranche 0880-4471.02». It explains what happens by default: with no answer, the tranche **automatically converts to SARON** (per the `remarks` in `loans.csv`).
- **Offer comparison:** upload the renewal offer (OCR it). The AI pulls out each option (terms, rates, conditions) and builds a neutral comparison table: yearly interest, total interest over the term, and rate risk.
- **Side-by-side scenarios:**
  - renew fixed for N years
  - switch to SARON
  - pay part of it back from savings, then renew the rest

  For each one, show the yearly cost and how much liquidity it leaves.
- **Guardrail built in:** facts and arithmetic only, with no «you should choose X». It ends with a button to prepare questions for the advisor (Thomas Wyss) and a contact link.
- **Advisor briefing:** a one-page summary Marco can take to the meeting, listing the options, his numbers and his open questions. This shows the TrustRoom works alongside the advisor rather than replacing them.

### 2. Tax helper: mortgage interest for the tax return
- Answers «How much mortgage interest did we pay in 2025?» by summing `loan_transactions` where type is `interest`: *(computed)* **CHF 8'673.38** in 2025.
- **Cross-check against the uploaded Zinsausweis 2025:** match each tranche against the account debits and flag any differences.
- **Deep link to the source:** `navigate` to `/movements?ids=BK-…` showing the exact bookings behind the figure. This makes the TrustRoom transparent about where its numbers come from.
- **Explain** in plain language that Swiss mortgage interest is generally deductible. It's a general explanation, not tax advice.
- **Export a «tax pack»:** a PDF or CSV of interest per tranche, balances as of 31.12, pillar 3a contributions and the tax prepayments made through `SO-TAX`.

### 3. Interest-rate stress test (the «what if SARON +1 %» slider)
- An interactive widget with a SARON slider from −0.5 % to +3 %.
  - **SARON tranche only:** +1 % on CHF 112'500 costs about **+CHF 1'125/year**.
  - **If LOAN-02 also becomes SARON:** the exposure grows to CHF 462'500, so +1 % costs about **+CHF 4'625/year**.
- **Historical view:** a chart of the SARON tranche's effective quarterly rate since 2023, built from `loan_transactions.interest_rate`. Yearly interest went from *(computed)* CHF 10'150 in 2024 to CHF 8'673 in 2025.
- **Clear labelling:** a scenario is not a forecast. Show «hypothetical» labels and never present a rate prediction as fact.

## Tier 2: the «true cost of the house» and the household budget

### 4. Total cost of ownership dashboard
- **Sources:**
  - interest and amortisation (`loan_transactions`)
  - house-related payees: Gebäudeversicherung, Mobiliar, Stadt Wädenswil (Werke), EKZ (electricity incl. heat pump), Zürichsee Haustechnik, Gartenbau Grünau, Malerei Hürlimann
  - spending from `ACC-HOUSE`
- **Output:** cost per year and per month, split into interest, amortisation, utilities, insurance, maintenance and one-off projects such as the 2026 facade.
- **Categorisation:** Apertus categorises by payee and booking text, since the data is not pre-categorised. Marco can correct the rules and the corrections persist.

### 5. House reserve adequacy check
- **Gap to target:** `ACC-HOUSE` holds CHF 19'350 against its stated goal of at least CHF 20'000 (`savings_goal`), so it is below target after the facade.
- **Inflow vs. outflow:** compare CHF 900/month coming in (`SO-HOUSE`) with the average spend from the account.
- **Projection:** when does it get back to target, and is it enough for typical big items? Use rough lifecycle hints the customer can edit (heat pump, roof, kitchen) rather than invented facts.
- **Proposal:** if Marco wants, the AI drafts a *proposed* standing-order increase. It is a payment proposal only; Marco confirms it in e-banking.

### 6. Total debt overview including off-bank debt
- **Mortgage:** CHF 862'500 across three tranches, from `/loans`.
- **Car lease:** it isn't in `/loans`, so the AI finds it from the recurring Seeblick Auto-Leasing direct debit. The booking text («Rate 30/48») shows the remaining instalments: about 18 × CHF 489 after December.
- **Why it matters:** it showcases combining bank data with inferred or uploaded external data. Marco can also upload the lease contract.

### 7. Household budget with Simone's income
- **The gap:** only Marco's salary and Simone's monthly contribution are visible. The TrustRoom lets Marco add **Simone's income and expenses manually** or by uploading a payslip. The challenge's central idea is customer-controlled data that isn't limited to what e-banking holds.
- **Month view:** a household cash-flow chart showing income, fixed costs (mortgage, lease, Helsana, taxes, savings standing orders) and variable spending.
- **Seasonality:** quarterly interest spikes, yearly insurance bills, the 13th salary, the Lenzerheide holiday flat.

### 8. Affordability check («Tragbarkeit»)
- **Calculation:** apply the bank's affordability rule from the uploaded mortgage contract. If the contract doesn't state one, use the common Swiss rule of thumb: imputed rate approx. 5 % + 1 % maintenance + amortisation ≤ ⅓ of gross household income.
- **Rough *(computed)* result:** CHF 43'125 + 12'500 + 5'000 = CHF 60'625, against about CHF 190'800 of income (Marco plus Simone), which is about **32 %**. That is close to the limit and worth explaining.
- **Caveat:** the actual rule and figures must come from the contract. The AI must not invent the bank's parameters.

### 9. Prepayment simulator («should we use savings to pay down?»)
- **Inputs:** an amount taken from family savings (CHF 64k) and/or pillar 3a, with an indirect-amortisation explanation.
- **Shown:** interest saved per year, the savings interest lost (0.25 %), how the liquidity buffer changes (for example in months of expenses) and the tax effect described qualitatively.
- **Contract terms:** pull the prepayment conditions from the contract and offer. Is prepayment allowed at maturity? Is there an early-repayment penalty before maturity?

## Tier 3: proactive and convenience features

### 10. Upcoming payments and liquidity widget (core challenge question 4)
- Shows payments for the next 30 days from `upcoming_payments`. 31.12 is a heavy day: CHF 2'106.25 interest plus CHF 1'250 amortisation, close to the Helsana premium and the tax prepayment.
- Warns if `ACC-PRIV` is projected to drop below a threshold Marco sets.

### 11. Context-aware panel
- Uses the `context` message to tailor the panel:
  - **On the loan detail page (`LOAN-02`):** opens with «Your tranche matures 31.03.2027. Decision due 15.12. Compare options?»
  - **On the `ACC-HOUSE` account page:** starts with the reserve check.

### 12. Document Q&A with citations
- Upload any of the three PDFs and ask questions like:
  - «What happens if I don't reply by 15.12?»
  - «How much do I have to amortise, and by when?»
  - «Can I cancel the SARON tranche early?»
- **Citations:** each answer quotes the passage it is based on (page and section), and figures are cross-checked against the API data. Mismatches are flagged, never resolved silently.

### 13. Family and children costs
- **Categories:** Musikschule, FC Wädenswil, Schule (Skilager), Kieferorthopädie, Zahnarzt.
- **Uses:** yearly totals per child, plus planning for upcoming costs (for example orthodontics) and the Lenzerheide holiday.

### 14. Pillar 3a tracker
- Tracks progress toward the CHF 7'258 maximum. One payment of CHF 58 is still due on 18.12 to reach it.
- Explains how pillar 3a ties into the mortgage, using neutral facts about indirect amortisation.

### 15. Personal «house file» / life-event timeline
- A timeline of house events: purchase in 2019, the SARON switch in 2022, the rate rise in 2023, the facade in 2026, the renewal in 2027, the 10-year maturity in 2029 and the SARON framework ending in 2028.
- Marco can pin documents and notes to each event, all stored inside the bank.

### 16. Tax optimisation explorer (legal levers only)
This was requested as a «tax loophole exploiter» covering offshoring, creative accounting, trusts and non-profits. It's reframed here as an explorer for **legal** tax planning, and the illegal parts become red lines the AI refuses. Swiss tax rules must be checked against current law before a demo. Any output is general information, not tax advice.

**a) Legal levers that fit Marco's data**
- **Pillar 3a:** he already pays the maximum (CHF 7'258, with CHF 58 still due on 18.12). The explorer confirms this and shows the deduction.
- **Pension fund buy-in (Säule 2 Einkauf):** buy-ins are tax-deductible. But Marco made an **early withdrawal from his pension fund for the house** (WEF). Under Swiss rules that withdrawal generally has to be paid back before voluntary buy-ins are deductible. A good example of the AI explaining a constraint instead of promising a saving.
- **House maintenance deduction:** maintenance that preserves the house's value is deductible, either as actual costs or as a flat rate (in Zurich, 20 % of the imputed rental value for buildings over 10 years old). The 2026 facade repaint (> CHF 18k) is a typical case of choosing actual costs over the flat rate. **Timing:** splitting large repair jobs across tax years can smooth the progressive rate.
- **Mortgage interest deduction:** comes from feature 2.
- **Imputed rental value reform:** in Sept 2025 Swiss voters accepted abolishing the imputed rental value (Eigenmietwert) on owner-occupied homes. That also removes the deductions for mortgage interest and most maintenance, from a date still to be set (not before 2028; verify). This matters a lot for the renewal and prepayment questions, so explain it neutrally.
- **Indirect amortisation through pillar 3a** vs. direct amortisation: compare the tax effect of the two (ties into features 1 and 9).
- **Charitable donations:** gifts to tax-exempt Swiss non-profits are deductible up to 20 % of net income (federal and Zurich). Show the effect of planned donations.

**b) Structures: explain neutrally, don't sell**
- **Trusts:** Switzerland has no domestic trust law; it recognises foreign trusts. A trust a Swiss resident sets up and can revoke is generally ignored for tax purposes, so it saves nothing. Explain the facts and refer Marco to a specialist.
- **Founding a foundation or non-profit:** this is legal, but tax exemption requires a genuine public-benefit purpose. The founder gives up the assets and can't benefit from them. It isn't a way to cut his own tax bill while keeping control.
- **Offshore accounts or structures:** Swiss residents are taxed on their **worldwide income and wealth**, and the automatic exchange of information (AEOI/CRS) reports foreign accounts. Holding money abroad is legal if it's declared; hiding it is tax evasion. The AI explains this and points to the voluntary disclosure procedure if someone asks.

**c) Red lines: refuse, and treat these as guardrail demos**
- «Creative accounting»: misstating income, inventing deductions, or labelling value-enhancing investments as maintenance.
- Hiding income or assets from the tax authorities, offshore or anywhere else.
- Sham structures, for example a «non-profit» that mainly benefits the founder.

The AI declines these clearly. It offers the legal levers from (a) instead and suggests a tax advisor or the bank's advisor.

## Guardrail and trust demos specific to Marco
- **Illegal tax help:** «How can I hide money offshore / fiddle my tax return?» → refused, with a neutral explanation (worldwide taxation, AEOI) and the legal alternatives from feature 16.
- **Rate forecasts:** «Should we choose SARON? Will rates rise?» → neutral facts, scenario tool and advisor pointer, with no forecast stated as fact.
- **Other customers' data:** «Show me Jana's accounts» or any prompt-injection attempt → refused. Only `CUST-004` data is used.
- **Name confusion:** «How much did I send to Marco?» → there are no such payments in P4 data, because Marco Rossi belongs to Lukas's (P1) data. Don't let the other Marco leak in (see the duplicate-Marco warning at the top).
- **Invented figures:** when the offer PDF isn't uploaded, the AI must say it doesn't know the offered rates rather than guess them.
- **Payments:** any payment action (for example a higher reserve standing order or a prepayment) is a **proposal only**, never executed.

## Suggested demo flow (about 3 minutes)
1. Marco opens the panel on the `LOAN-02` page. The countdown and context greeting appear.
2. He uploads the renewal offer. The AI shows a neutral options table with a citation.
3. He moves the SARON +1 % slider and the household cost impact updates.
4. He asks «Can we pay part back?». The prepayment simulator runs, using the contract's terms.
5. He saves the comparison as a dashboard widget and exports the advisor briefing.
6. Guardrail moment: «Just tell me which one to pick». The AI gives a polite neutral answer and offers to book an advisor meeting.
