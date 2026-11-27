# Widget benchmark

Run on 2026-11-27. `smart` is `apertus-v1-5-70b`, `fast` is `apertus-v1-5-8b`. A run is clean when the page loads without a JavaScript error at 360 px and 1000 px, draws something, shows no NaN or undefined, and passes the chat's own figure check (`app/features/figure_checks`) against `DATA` and the request.

Clean says nothing about how the widget looks: a clean page can still overlap its labels or show a list instead of a chart. Judge that in `results/index.html`.

| Variant | Model | Task | Clean | Seconds | Tokens out | Chars | 360 px | 1000 px |
|---|---|---|---|---|---|---|---|---|
| html_svg | smart | monthly_spending | no | 28.7 | 552 | 1562 | 1 JS errors: Uncaught ReferenceError: d3 is not defined (line 73); scrolls sideways | 1 JS errors: Uncaught ReferenceError: d3 is not defined (line 73); scrolls sideways |
| html_svg | smart | upcoming_payments | yes | 68.0 | 1421 | 3504 | scrolls sideways | ok |
| html_svg | smart | pricier_subscriptions | yes | 29.5 | 582 | 1939 | ok | ok |
| html_svg | smart | year_vs_year | no | 110.4 | 2184 | 5118 | 1 JS errors: Uncaught TypeError: document.querySelectorAll(...).find is not a function (line 209) | 1 JS errors: Uncaught TypeError: document.querySelectorAll(...).find is not a function (line 209) |
| html_svg | smart | liquidity | no | 35.6 | 773 | 2376 | 4 JS errors: error; scrolls sideways | 4 JS errors: error |
| html_svg | smart | where_money_goes | no | 34.4 | 740 | 2314 | figures: 280 of 283 found; not found: 33, 15, 209 | figures: 280 of 283 found; not found: 33, 15, 209 |
| html_svg | smart | monthly_spending + red (rewrite) | no (first version broken) | 24.5 | 598 | 1697 | 1 JS errors: Uncaught ReferenceError: d3 is not defined (line 73); scrolls sideways | 1 JS errors: Uncaught ReferenceError: d3 is not defined (line 73); scrolls sideways |
| html_svg | smart | monthly_spending + red (edits) | no (first version broken) | 4.7 | 75 | 1603 | 1 JS errors: Uncaught ReferenceError: d3 is not defined (line 73); scrolls sideways | 1 JS errors: Uncaught ReferenceError: d3 is not defined (line 73); scrolls sideways |
| html_svg | smart | monthly_spending + last_3 (rewrite) | no (first version broken) | 23.2 | 570 | 1611 | 1 JS errors: Uncaught ReferenceError: d3 is not defined (line 73); scrolls sideways | 1 JS errors: Uncaught ReferenceError: d3 is not defined (line 73); scrolls sideways |
| html_svg | smart | monthly_spending + last_3 (edits) | no (first version broken) | 4.6 | 93 | 1592 | 1 JS errors: Uncaught ReferenceError: d3 is not defined (line 73); scrolls sideways | 1 JS errors: Uncaught ReferenceError: d3 is not defined (line 73); scrolls sideways |
| html_d3 | smart | monthly_spending | no | 31.6 | 574 | 1712 | 1 JS errors: Uncaught TypeError: Cannot read properties of undefined (reading 'attr') (line 118) | 1 JS errors: Uncaught TypeError: Cannot read properties of undefined (reading 'attr') (line 118) |
| html_d3 | smart | upcoming_payments | no | 32.0 | 590 | 1708 | 1 JS errors: Uncaught InvalidCharacterError: Failed to execute 'createElement' on 'Document': The tag name provided ('td.classed("amount", true)') is not a vali | 1 JS errors: Uncaught InvalidCharacterError: Failed to execute 'createElement' on 'Document': The tag name provided ('td.classed("amount", true)') is not a vali |
| html_d3 | smart | pricier_subscriptions | yes | 48.4 | 898 | 2837 | ok | ok |
| html_d3 | smart | year_vs_year | yes | 63.4 | 1072 | 3151 | ok | ok |
| html_d3 | smart | liquidity | yes | 15.5 | 305 | 959 | ok | ok |
| html_d3 | smart | where_money_goes | yes | 50.6 | 833 | 2674 | ok | ok |
| html_d3 | smart | monthly_spending + red (rewrite) | no (first version broken) | 21.4 | 598 | 1753 | 1 JS errors: Uncaught TypeError: Cannot read properties of undefined (reading 'attr') (line 118) | 1 JS errors: Uncaught TypeError: Cannot read properties of undefined (reading 'attr') (line 118) |
| html_d3 | smart | monthly_spending + red (edits) | no (first version broken) | 4.9 | 82 | 1753 | 1 JS errors: Uncaught TypeError: Cannot read properties of undefined (reading 'attr') (line 118) | 1 JS errors: Uncaught TypeError: Cannot read properties of undefined (reading 'attr') (line 118) |
| html_d3 | smart | monthly_spending + last_3 (rewrite) | no (first version broken) | 17.9 | 584 | 1740 | 1 JS errors: Uncaught TypeError: Cannot read properties of undefined (reading 'attr') (line 118) | 1 JS errors: Uncaught TypeError: Cannot read properties of undefined (reading 'attr') (line 118) |
| html_d3 | smart | monthly_spending + last_3 (edits) | no (first version broken) | 4.6 | – | – | edit matches 0 times: 'months.map(m => ({\n        "label": m.label,\n        "value"' |  |
| shapes | smart | monthly_spending | no | 167.9 | 1533 | 2232 | figures: 3 of 6 found; not found: 15'645, 7'030, 17'273 | figures: 3 of 6 found; not found: 15'645, 7'030, 17'273 |
| shapes | smart | upcoming_payments | yes | 317.2 | 2416 | 3810 | ok | ok |
| shapes | smart | pricier_subscriptions | yes | 55.1 | 874 | 1369 | ok | ok |
| shapes | smart | year_vs_year | yes | 113.6 | 1074 | 1679 | ok | ok |
| shapes | smart | liquidity | yes | 52.0 | 1139 | 1722 | ok | ok |
| shapes | smart | where_money_goes | yes | 176.5 | 2183 | 3108 | ok | ok |
| shapes | smart | monthly_spending + red (rewrite) | no (first version broken) | 101.4 | 1651 | 2232 | figures: 3 of 6 found; not found: 15'645, 7'030, 17'273 | figures: 3 of 6 found; not found: 15'645, 7'030, 17'273 |
| shapes | smart | monthly_spending + red (edits) | no (first version broken) | 7.4 | 127 | 2232 | figures: 3 of 6 found; not found: 15'645, 7'030, 17'273 | figures: 3 of 6 found; not found: 15'645, 7'030, 17'273 |
| shapes | smart | monthly_spending + last_3 (rewrite) | no (first version broken) | 34.6 | 1222 | 1653 | figures: 0 of 4 found; not found: 17'273, 10'598, 12'345, 14'567.89 | figures: 0 of 4 found; not found: 17'273, 10'598, 12'345, 14'567.89 |
| shapes | smart | monthly_spending + last_3 (edits) | no (first version broken) | 45.6 | 828 | 1083 | invalid shapes: 1 errors |  |
| html_svg | fast | monthly_spending | yes | 6.2 | 1033 | 2160 | ok | ok |
| html_svg | fast | upcoming_payments | no | 8.3 | 1347 | 3891 | 1 JS errors: Uncaught TypeError: chart.getContext is not a function (line 159); scrolls sideways | 1 JS errors: Uncaught TypeError: chart.getContext is not a function (line 159); scrolls sideways |
| html_svg | fast | pricier_subscriptions | no | 6.0 | 958 | 2539 | figures: 4 of 5 found; not found: 136.80 | figures: 4 of 5 found; not found: 136.80 |
| html_svg | fast | year_vs_year | no | 9.3 | 1541 | 4199 | 1 JS errors: Uncaught SyntaxError: Unexpected string (line 129); figures: 2 of 6 found; not found: 1'174.20, 8'454.40, 10'901.40, 10'598.80 | 1 JS errors: Uncaught SyntaxError: Unexpected string (line 129); figures: 2 of 6 found; not found: 1'174.20, 8'454.40, 10'901.40, 10'598.80 |
| html_svg | fast | liquidity | no | 5.2 | 854 | 2636 | 1 JS errors: Uncaught TypeError: Cannot set properties of null (setting 'textContent') (line 152) | 1 JS errors: Uncaught TypeError: Cannot set properties of null (setting 'textContent') (line 152) |
| html_svg | fast | where_money_goes | no | 9.3 | 1561 | 4227 | 1 JS errors: Uncaught TypeError: Cannot read properties of null (reading 'querySelector') (line 194); figures: 1 of 3 found; not found: 600, 300; scrolls sidewa | 1 JS errors: Uncaught TypeError: Cannot read properties of null (reading 'querySelector') (line 194); figures: 1 of 3 found; not found: 600, 300 |
| html_svg | fast | monthly_spending + red (rewrite) | yes | 7.7 | 1280 | 2544 | ok | ok |
| html_svg | fast | monthly_spending + red (edits) | yes | 1.3 | 34 | 2174 | ok | ok |
| html_svg | fast | monthly_spending + last_3 (rewrite) | yes | 5.4 | 903 | 1899 | ok | ok |
| html_svg | fast | monthly_spending + last_3 (edits) | yes | 1.3 | 30 | 2161 | ok | ok |
| html_d3 | fast | monthly_spending | no | 6.7 | 1133 | 2643 | figures: 2 of 10 found; not found: 0, 564.56, 191.31, 630.03, 030.63, 17, 273.6, 598.77 | figures: 2 of 10 found; not found: 0, 564.56, 191.31, 630.03, 030.63, 17, 273.6, 598.77 |
| html_d3 | fast | upcoming_payments | yes | 4.2 | 653 | 1919 | ok | ok |
| html_d3 | fast | pricier_subscriptions | no | 10.9 | 1755 | 4794 | figures: 11 of 28 found; not found: 80.0, 08.3%, 25.8, 5.9%, 230.0, 6.1%, 20.0, 18.6%, 26.4, 2.2%; scrolls sideways | figures: 11 of 28 found; not found: 80.0, 08.3%, 25.8, 5.9%, 230.0, 6.1%, 20.0, 18.6%, 26.4, 2.2%; scrolls sideways |
| html_d3 | fast | year_vs_year | yes | 4.1 | 657 | 1815 | scrolls sideways | ok |
| html_d3 | fast | liquidity | yes | 3.5 | 565 | 1808 | ok | ok |
| html_d3 | fast | where_money_goes | no | 4.3 | 709 | 2033 | 1 JS errors: Uncaught TypeError: Cannot read properties of undefined (reading 'selection') (line 53); figures: 0 of 2 found; not found: 1000, 200; scrolls sidew | 1 JS errors: Uncaught TypeError: Cannot read properties of undefined (reading 'selection') (line 53); figures: 0 of 2 found; not found: 1000, 200; scrolls sidew |
| html_d3 | fast | monthly_spending + red (rewrite) | no (first version broken) | 7.4 | 1218 | 2808 | figures: 3 of 14 found; not found: 0, 564.56, 191.31, 630.03, 030.63, 17, 273.6, 598.77 | figures: 3 of 14 found; not found: 0, 564.56, 191.31, 630.03, 030.63, 17, 273.6, 598.77 |
| html_d3 | fast | monthly_spending + red (edits) | no (first version broken) | 1.3 | 31 | 2639 | figures: 2 of 10 found; not found: 0, 564.56, 191.31, 630.03, 030.63, 17, 273.6, 598.77 | figures: 2 of 10 found; not found: 0, 564.56, 191.31, 630.03, 030.63, 17, 273.6, 598.77 |
| html_d3 | fast | monthly_spending + last_3 (rewrite) | no (first version broken) | 6.2 | 1034 | 2446 | figures: 1 of 6 found; not found: 0, 191.31, 630.03, 17, 273.6 | figures: 1 of 6 found; not found: 0, 191.31, 630.03, 17, 273.6 |
| html_d3 | fast | monthly_spending + last_3 (edits) | no (first version broken) | 1.3 | – | – | edit matches 0 times: 'Show my monthly spending over the last 6 months as a bar cha' |  |
| shapes | fast | monthly_spending | no | 8.5 | – | – | Model returned invalid Scene twice |  |
| shapes | fast | upcoming_payments | no | 8.9 | – | – | Model returned invalid Scene twice |  |
| shapes | fast | pricier_subscriptions | no | 9.0 | – | – | Model returned invalid Scene twice |  |
| shapes | fast | year_vs_year | no | 8.8 | – | – | Model returned invalid Scene twice |  |
| shapes | fast | liquidity | no | 15.1 | – | – | Model returned invalid Scene twice |  |
| shapes | fast | where_money_goes | no | 8.6 | – | – | Model returned invalid Scene twice |  |
| jinja | smart | monthly_spending | no | 20.6 | 538 | 1425 | template error: too many values to unpack (expected 2) |  |
| jinja | smart | upcoming_payments | no | 15.8 | 450 | 1214 | template error: 'm' is undefined |  |
| jinja | smart | pricier_subscriptions | no | 15.6 | 438 | 1313 | template error: Encountered unknown tag 'end'. Jinja was looking for the following tags: 'endfor' or 'else'. The innermost block that needs to be closed is 'for |  |
| jinja | smart | year_vs_year | no | 30.1 | 927 | 2693 | template error: expected token ',', got ':' |  |
| jinja | smart | liquidity | no | 16.6 | 605 | 1688 | template error: 'm' is undefined |  |
| jinja | smart | where_money_goes | no | 20.2 | 803 | 2307 | template error: 'max_total' is undefined |  |
| jinja | smart | monthly_spending + red (rewrite) | no (first version broken) | 19.1 | 557 | 1482 | template error: too many values to unpack (expected 2) |  |
| jinja | smart | monthly_spending + red (edits) | no (first version broken) | 1.7 | 42 | 1426 | template error: too many values to unpack (expected 2) |  |
| jinja | smart | monthly_spending + last_3 (rewrite) | no (first version broken) | 17.5 | 495 | 1349 | template error: 'max' is undefined |  |
| jinja | smart | monthly_spending + last_3 (edits) | no (first version broken) | 2.1 | – | – | edit matches 0 times: '{% for m in DATA.months %}' |  |
| jinja | fast | monthly_spending | no | 10.0 | 656 | 1505 | numbers of its own: 0 of 5 found; not found: 10'000, 2'000, 4'000, 6'000, 8'000 |  |
| jinja | fast | upcoming_payments | no | 6.7 | 439 | 1220 | template error: 'max_chf' is undefined |  |
| jinja | fast | pricier_subscriptions | no | 9.9 | 621 | 1695 | template error: Invalid isoformat string: '1' |  |
| jinja | fast | year_vs_year | no | 12.9 | 823 | 2298 | template error: 'loop' is undefined |  |
| jinja | fast | liquidity | no | 7.6 | 499 | 1147 | template error: unsupported format string passed to StrictUndefined.__format__ |  |
| jinja | fast | where_money_goes | no | 9.4 | 615 | 1440 | template error: 'enumerate' is undefined |  |
| jinja | fast | monthly_spending + red (rewrite) | no (first version broken) | 11.2 | 774 | 1792 | numbers of its own: 0 of 5 found; not found: 10'000, 2'000, 4'000, 6'000, 8'000 |  |
| jinja | fast | monthly_spending + red (edits) | no (first version broken) | 5.1 | – | – | Model returned invalid Edits twice |  |
| jinja | fast | monthly_spending + last_3 (rewrite) | no (first version broken) | 10.1 | 659 | 1526 | numbers of its own: 0 of 5 found; not found: 10'000, 2'000, 4'000, 6'000, 8'000 |  |
| jinja | fast | monthly_spending + last_3 (edits) | no (first version broken) | 1.2 | 55 | 1506 | numbers of its own: 0 of 5 found; not found: 10'000, 2'000, 4'000, 6'000, 8'000 |  |

On 8B, 4 of the 10 jinja failures (the rows with "not found: 10'000, 2'000, …") are axis tick labels typed into the template. The prompt asks for tick labels in `.tick` elements, but the template check refuses every typed number, so the two contradict each other. The 0 of 6 still stands, because the card refuses typed numbers.

## Summary

Revisions count only where the first version was clean, so a broken first version doesn't count five times.

| Variant | Model | Tasks clean | Median seconds | Revisions clean | Edits applied |
|---|---|---|---|---|---|
| html_svg | smart | 2 of 6 (33%) | 35.0 | – | 2 of 2 |
| html_d3 | smart | 4 of 6 (67%) | 40.2 | – | 1 of 2 |
| shapes | smart | 5 of 6 (83%) | 140.8 | – | 1 of 2 |
| html_svg | fast | 1 of 6 (17%) | 7.2 | 4 of 4 (100%) | 2 of 2 |
| html_d3 | fast | 3 of 6 (50%) | 4.2 | – | 1 of 2 |
| shapes | fast | 0 of 6 (0%) | – | – | 0 of 0 |
| jinja | smart | 0 of 6 (0%) | – | – | 0 of 2 |
| jinja | fast | 0 of 6 (0%) | – | – | 0 of 2 |

## Catalogue

Run on 2026-11-27. The Keera gateway accepts `json_schema` with the WidgetSpec schema.

Apertus returns a `WidgetSpec` through `structured`, which already gives it one round with a validation error. A spec whose path doesn't resolve goes back once with the error (`repaired`); after that the widget is `fallback(data)`, which counts as not clean. Edits change the spec's JSON and get no repair round.

| Variant | Model | Task | Outcome | Clean | Seconds | 360 px | 1000 px | Last error |
|---|---|---|---|---|---|---|---|---|
| catalogue | smart | monthly_spending | first | yes | 9.4 | ok | ok | – |
| catalogue | smart | upcoming_payments | first | yes | 11.3 | ok | ok | – |
| catalogue | smart | pricier_subscriptions | fallback | no | 14.1 | ok | ok | subscriptions[0] has no field old_price; fields: payee, cadence, payments, last_date, last_paid_chf, paid_last_12_months_chf, next_expected, active, price_chang |
| catalogue | smart | year_vs_year | first | yes | 12.7 | ok | ok | – |
| catalogue | smart | liquidity | first | yes | 4.5 | ok | ok | – |
| catalogue | smart | where_money_goes | first | yes | 4.7 | ok | ok | – |
| catalogue | smart | monthly_spending + red (rewrite) | first | yes | 7.4 | ok | ok | – |
| catalogue | smart | monthly_spending + red (edits) | – | no | 12.7 | edit matches 0 times: '{"type": "bar_chart", "data": "months", "x": "label", "y": "' |  | – |
| catalogue | smart | monthly_spending + last_3 (rewrite) | first | yes | 4.0 | ok | ok | – |
| catalogue | smart | monthly_spending + last_3 (edits) | – | no | 2.2 | invalid spec: 1 errors |  | – |
| catalogue_schema | smart | monthly_spending | first | yes | 5.0 | ok | ok | – |
| catalogue_schema | smart | upcoming_payments | first | yes | 7.5 | ok | ok | – |
| catalogue_schema | smart | pricier_subscriptions | fallback | no | 14.9 | ok | ok | subscriptions[0].payee is a str, not a number |
| catalogue_schema | smart | year_vs_year | fallback | no | 363.1 | ok | ok | Apertus returned 502 |
| catalogue_schema | smart | liquidity | repaired | yes | 17.8 | ok | ok | total_liquidity_chf is not a list of rows |
| catalogue_schema | smart | where_money_goes | repaired | yes | 7.4 | ok | ok | payees[0] has no field kpi; fields: label, total_chf, booking_ids |
| catalogue_schema | smart | monthly_spending + red (rewrite) | first | yes | 30.6 | ok | ok | – |
| catalogue_schema | smart | monthly_spending + red (edits) | – | no | 132.1 | edit matches 0 times: '{"type": "bar_chart", "data": "months", "x": "label", "y": "' |  | – |
| catalogue_schema | smart | monthly_spending + last_3 (rewrite) | first | yes | 48.7 | ok | ok | – |
| catalogue_schema | smart | monthly_spending + last_3 (edits) | – | no | 27.5 | invalid spec: 1 errors |  | – |
| catalogue | fast | monthly_spending | first | yes | 1.6 | ok | ok | – |
| catalogue | fast | upcoming_payments | first | yes | 2.7 | ok | ok | – |
| catalogue | fast | pricier_subscriptions | fallback | no | 48.0 | ok | ok | Model returned invalid WidgetSpec twice |
| catalogue | fast | year_vs_year | first | yes | 3.7 | ok | ok | – |
| catalogue | fast | liquidity | fallback | no | 2.9 | ok | ok | none: DATA has no field none; fields: total_liquidity_chf, as_of, accounts |
| catalogue | fast | where_money_goes | first | yes | 4.5 | ok | ok | – |
| catalogue | fast | monthly_spending + red (rewrite) | first | yes | 0.7 | ok | ok | – |
| catalogue | fast | monthly_spending + red (edits) | – | yes | 1.0 | ok | ok | – |
| catalogue | fast | monthly_spending + last_3 (rewrite) | first | yes | 0.6 | ok | ok | – |
| catalogue | fast | monthly_spending + last_3 (edits) | – | no | 1.0 | Model returned invalid Edits twice |  | – |
| catalogue_schema | fast | monthly_spending | first | yes | 0.8 | ok | ok | – |
| catalogue_schema | fast | upcoming_payments | fallback | no | 361.5 | ok | ok | Apertus returned 502 |
| catalogue_schema | fast | pricier_subscriptions | fallback | no | 361.5 | ok | ok | Apertus returned 502 |
| catalogue_schema | fast | year_vs_year | first | yes | 1.0 | ok | ok | – |
| catalogue_schema | fast | liquidity | first | yes | 0.6 | ok | ok | – |
| catalogue_schema | fast | where_money_goes | first | yes | 1.5 | ok | ok | – |
| catalogue_schema | fast | monthly_spending + red (rewrite) | first | yes | 3.8 | ok | ok | – |
| catalogue_schema | fast | monthly_spending + red (edits) | – | yes | 8.2 | ok | ok | – |
| catalogue_schema | fast | monthly_spending + last_3 (rewrite) | repaired | yes | 6.7 | ok | ok | months[3] is not a list of rows |
| catalogue_schema | fast | monthly_spending + last_3 (edits) | – | no | 7.3 | Model returned invalid Edits twice |  | – |

| Variant | Model | First try | After one repair | Fallback | No page | Median seconds | Tasks clean |
|---|---|---|---|---|---|---|---|
| catalogue | smart | 7 of 8 | 0 | 1 | 2 | 8.4 | 5 of 6 (83%) |
| catalogue_schema | smart | 4 of 8 | 2 | 2 | 2 | 16.4 | 4 of 6 (67%) |
| catalogue | fast | 6 of 8 | 0 | 2 | 1 | 2.8 | 4 of 6 (67%) |
| catalogue_schema | fast | 5 of 8 | 1 | 2 | 1 | 2.6 | 4 of 6 (67%) |
