# Widget benchmark

Run on 2026-11-27. `smart` is `apertus-v1-5-70b`, `fast` is `apertus-v1-5-8b`. A run is clean when the page loads without a JavaScript error at 360 px and 1000 px, draws something, and shows only numbers from `DATA` or the request.

Clean says nothing about how the widget looks: a clean page can still overlap its labels or show a list instead of a chart. Judge that in `results/index.html`.

| Variant | Model | Task | Clean | Seconds | Tokens out | Chars | 360 px | 1000 px |
|---|---|---|---|---|---|---|---|---|
| html_svg | smart | monthly_spending | no | 28.7 | 552 | 1562 | 1 JS errors: Uncaught ReferenceError: d3 is not defined (line 73); scrolls sideways | 1 JS errors: Uncaught ReferenceError: d3 is not defined (line 73); scrolls sideways |
| html_svg | smart | upcoming_payments | yes | 68.0 | 1421 | 3504 | scrolls sideways | ok |
| html_svg | smart | pricier_subscriptions | yes | 29.5 | 582 | 1939 | ok | ok |
| html_svg | smart | year_vs_year | no | 110.4 | 2184 | 5118 | 1 JS errors: Uncaught TypeError: document.querySelectorAll(...).find is not a function (line 209) | 1 JS errors: Uncaught TypeError: document.querySelectorAll(...).find is not a function (line 209) |
| html_svg | smart | liquidity | no | 35.6 | 773 | 2376 | 4 JS errors: error; not in DATA: 2, 2; scrolls sideways | 4 JS errors: error; not in DATA: 2, 2 |
| html_svg | smart | where_money_goes | no | 34.4 | 740 | 2314 | not in DATA: 2, 2, 3, 1, 33 | not in DATA: 2, 2, 3, 1, 33 |
| html_svg | smart | monthly_spending + red (rewrite) | no | 24.5 | 598 | 1697 | 1 JS errors: Uncaught ReferenceError: d3 is not defined (line 73); scrolls sideways | 1 JS errors: Uncaught ReferenceError: d3 is not defined (line 73); scrolls sideways |
| html_svg | smart | monthly_spending + red (edits) | no | 4.7 | 75 | 1603 | 1 JS errors: Uncaught ReferenceError: d3 is not defined (line 73); scrolls sideways | 1 JS errors: Uncaught ReferenceError: d3 is not defined (line 73); scrolls sideways |
| html_svg | smart | monthly_spending + last_3 (rewrite) | no | 23.2 | 570 | 1611 | 1 JS errors: Uncaught ReferenceError: d3 is not defined (line 73); scrolls sideways | 1 JS errors: Uncaught ReferenceError: d3 is not defined (line 73); scrolls sideways |
| html_svg | smart | monthly_spending + last_3 (edits) | no | 4.6 | 93 | 1592 | 1 JS errors: Uncaught ReferenceError: d3 is not defined (line 73); scrolls sideways | 1 JS errors: Uncaught ReferenceError: d3 is not defined (line 73); scrolls sideways |
| html_d3 | smart | monthly_spending | no | 31.6 | 574 | 1712 | 1 JS errors: Uncaught TypeError: Cannot read properties of undefined (reading 'attr') (line 118) | 1 JS errors: Uncaught TypeError: Cannot read properties of undefined (reading 'attr') (line 118) |
| html_d3 | smart | upcoming_payments | no | 32.0 | 590 | 1708 | 1 JS errors: Uncaught InvalidCharacterError: Failed to execute 'createElement' on 'Document': The tag name provided ('td.classed("amount", true)') is not a vali | 1 JS errors: Uncaught InvalidCharacterError: Failed to execute 'createElement' on 'Document': The tag name provided ('td.classed("amount", true)') is not a vali |
| html_d3 | smart | pricier_subscriptions | yes | 48.4 | 898 | 2837 | ok | ok |
| html_d3 | smart | year_vs_year | no | 63.4 | 1072 | 3151 | not in DATA: 0, 0 | not in DATA: 0, 0 |
| html_d3 | smart | liquidity | yes | 15.5 | 305 | 959 | ok | ok |
| html_d3 | smart | where_money_goes | yes | 50.6 | 833 | 2674 | ok | ok |
| html_d3 | smart | monthly_spending + red (rewrite) | no | 21.4 | 598 | 1753 | 1 JS errors: Uncaught TypeError: Cannot read properties of undefined (reading 'attr') (line 118) | 1 JS errors: Uncaught TypeError: Cannot read properties of undefined (reading 'attr') (line 118) |
| html_d3 | smart | monthly_spending + red (edits) | no | 4.9 | 82 | 1753 | 1 JS errors: Uncaught TypeError: Cannot read properties of undefined (reading 'attr') (line 118) | 1 JS errors: Uncaught TypeError: Cannot read properties of undefined (reading 'attr') (line 118) |
| html_d3 | smart | monthly_spending + last_3 (rewrite) | no | 17.9 | 584 | 1740 | 1 JS errors: Uncaught TypeError: Cannot read properties of undefined (reading 'attr') (line 118) | 1 JS errors: Uncaught TypeError: Cannot read properties of undefined (reading 'attr') (line 118) |
| html_d3 | smart | monthly_spending + last_3 (edits) | no | 4.6 | – | – | edit matches 0 times: 'months.map(m => ({\n        "label": m.label,\n        "value"' |  |
| shapes | smart | monthly_spending | yes | 167.9 | 1533 | 2232 | ok | ok |
| shapes | smart | upcoming_payments | yes | 317.2 | 2416 | 3810 | ok | ok |
| shapes | smart | pricier_subscriptions | yes | 55.1 | 874 | 1369 | ok | ok |
| shapes | smart | year_vs_year | yes | 113.6 | 1074 | 1679 | ok | ok |
| shapes | smart | liquidity | yes | 52.0 | 1139 | 1722 | ok | ok |
| shapes | smart | where_money_goes | yes | 176.5 | 2183 | 3108 | ok | ok |
| shapes | smart | monthly_spending + red (rewrite) | yes | 101.4 | 1651 | 2232 | ok | ok |
| shapes | smart | monthly_spending + red (edits) | yes | 7.4 | 127 | 2232 | ok | ok |
| shapes | smart | monthly_spending + last_3 (rewrite) | no | 34.6 | 1222 | 1653 | not in DATA: 12'345.67, 14'567.89 | not in DATA: 12'345.67, 14'567.89 |
| shapes | smart | monthly_spending + last_3 (edits) | no | 45.6 | 828 | 1083 | invalid shapes: 1 errors |  |
| html_svg | fast | monthly_spending | yes | 6.2 | 1033 | 2160 | ok | ok |
| html_svg | fast | upcoming_payments | no | 8.3 | 1347 | 3891 | 1 JS errors: Uncaught TypeError: chart.getContext is not a function (line 159); scrolls sideways | 1 JS errors: Uncaught TypeError: chart.getContext is not a function (line 159); scrolls sideways |
| html_svg | fast | pricier_subscriptions | no | 6.0 | 958 | 2539 | not in DATA: 136.80 | not in DATA: 136.80 |
| html_svg | fast | year_vs_year | no | 9.3 | 1541 | 4199 | 1 JS errors: Uncaught SyntaxError: Unexpected string (line 129); not in DATA: 1'174.20, 8'454.40, 10'901.40, 10'598.80 | 1 JS errors: Uncaught SyntaxError: Unexpected string (line 129); not in DATA: 1'174.20, 8'454.40, 10'901.40, 10'598.80 |
| html_svg | fast | liquidity | no | 5.2 | 854 | 2636 | 1 JS errors: Uncaught TypeError: Cannot set properties of null (setting 'textContent') (line 152) | 1 JS errors: Uncaught TypeError: Cannot set properties of null (setting 'textContent') (line 152) |
| html_svg | fast | where_money_goes | no | 9.3 | 1561 | 4227 | 1 JS errors: Uncaught TypeError: Cannot read properties of null (reading 'querySelector') (line 194); not in DATA: 0, 0, 600, 300; scrolls sideways | 1 JS errors: Uncaught TypeError: Cannot read properties of null (reading 'querySelector') (line 194); not in DATA: 0, 0, 600, 300 |
| html_svg | fast | monthly_spending + red (rewrite) | yes | 7.7 | 1280 | 2544 | ok | ok |
| html_svg | fast | monthly_spending + red (edits) | yes | 1.3 | 34 | 2174 | ok | ok |
| html_svg | fast | monthly_spending + last_3 (rewrite) | yes | 5.4 | 903 | 1899 | ok | ok |
| html_svg | fast | monthly_spending + last_3 (edits) | yes | 1.3 | 30 | 2161 | ok | ok |
| html_d3 | fast | monthly_spending | no | 6.7 | 1133 | 2643 | not in DATA: 0, 1, 564.56, 9, 191.31 | not in DATA: 0, 1, 564.56, 9, 191.31 |
| html_d3 | fast | upcoming_payments | no | 4.2 | 653 | 1919 | not in DATA: 6, 66, 0, 1 | not in DATA: 6, 66, 0, 1 |
| html_d3 | fast | pricier_subscriptions | no | 10.9 | 1755 | 4794 | not in DATA: 80.0, 08.3%, 25.8, 5.9%, 230.0; scrolls sideways | not in DATA: 80.0, 08.3%, 25.8, 5.9%, 230.0; scrolls sideways |
| html_d3 | fast | year_vs_year | yes | 4.1 | 657 | 1815 | scrolls sideways | ok |
| html_d3 | fast | liquidity | yes | 3.5 | 565 | 1808 | ok | ok |
| html_d3 | fast | where_money_goes | no | 4.3 | 709 | 2033 | 1 JS errors: Uncaught TypeError: Cannot read properties of undefined (reading 'selection') (line 53); not in DATA: 0, 0, 1000, 200; scrolls sideways | 1 JS errors: Uncaught TypeError: Cannot read properties of undefined (reading 'selection') (line 53); not in DATA: 0, 0, 1000, 200; scrolls sideways |
| html_d3 | fast | monthly_spending + red (rewrite) | no | 7.4 | 1218 | 2808 | not in DATA: 0, 1, 564.56, 9, 191.31 | not in DATA: 0, 1, 564.56, 9, 191.31 |
| html_d3 | fast | monthly_spending + red (edits) | no | 1.3 | 31 | 2639 | not in DATA: 0, 1, 564.56, 9, 191.31 | not in DATA: 0, 1, 564.56, 9, 191.31 |
| html_d3 | fast | monthly_spending + last_3 (rewrite) | no | 6.2 | 1034 | 2446 | not in DATA: 0, 9, 191.31, 9, 630.03 | not in DATA: 0, 9, 191.31, 9, 630.03 |
| html_d3 | fast | monthly_spending + last_3 (edits) | no | 1.3 | – | – | edit matches 0 times: 'Show my monthly spending over the last 6 months as a bar cha' |  |
| shapes | fast | monthly_spending | no | 8.5 | – | – | Model returned invalid Scene twice |  |
| shapes | fast | upcoming_payments | no | 8.9 | – | – | Model returned invalid Scene twice |  |
| shapes | fast | pricier_subscriptions | no | 9.0 | – | – | Model returned invalid Scene twice |  |
| shapes | fast | year_vs_year | no | 8.8 | – | – | Model returned invalid Scene twice |  |
| shapes | fast | liquidity | no | 15.1 | – | – | Model returned invalid Scene twice |  |
| shapes | fast | where_money_goes | no | 8.6 | – | – | Model returned invalid Scene twice |  |

## Summary

| Variant | Model | Clean | Median seconds | Edits applied |
|---|---|---|---|---|
| html_svg | smart | 2 of 10 (20%) | 29.1 | 2 of 2 |
| html_d3 | smart | 3 of 10 (30%) | 31.6 | 1 of 2 |
| shapes | smart | 8 of 10 (80%) | 101.4 | 1 of 2 |
| html_svg | fast | 5 of 10 (50%) | 6.1 | 2 of 2 |
| html_d3 | fast | 2 of 10 (20%) | 4.3 | 1 of 2 |
| shapes | fast | 0 of 6 (0%) | – | 0 of 0 |
