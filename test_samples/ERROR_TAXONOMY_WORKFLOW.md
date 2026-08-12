# Chart-aware taxonomy real-workflow tests

These tests use the normal VividWrite workflow. Each report is submitted independently;
no aligned chart records, expected labels, or feedback cards are supplied to the
application.

## Applicability by chart type

| Taxonomy class | Bar | Line | Single-period pie |
| --- | :---: | :---: | :---: |
| Value inaccuracy | Yes | Yes | Yes |
| Entity or series misalignment | Yes | Yes | Yes |
| Trend direction error | Yes, with at least two periods | Yes | N/A |
| Comparison or ranking error | Yes | Yes | Yes |
| Key feature omission | Yes | Yes | Yes |

A single-period pie chart has no temporal endpoints, so it cannot verify an increase,
decrease, or stable trend. VividWrite displays `N/A` for that check instead of showing a
misleading zero. Comparative pie records with at least two ordered periods make the trend
check applicable at the taxonomy layer.

## Bar-chart cases

- Image: `charts/01_bar_recycling_rates.png`
- Task type: `Bar Chart`

| Case | Report file | Expected result |
| --- | --- | --- |
| 1 | `error_taxonomy/01_value_inaccuracy.txt` | One value inaccuracy |
| 2 | `error_taxonomy/02_entity_misalignment.txt` | One entity or series misalignment |
| 3 | `error_taxonomy/03_trend_direction_error.txt` | One trend direction error |
| 4 | `error_taxonomy/04_comparison_ranking_error.txt` | One comparison or ranking error |
| 5 | `error_taxonomy/05_key_feature_omission.txt` | One key feature omission |

## Line-chart cases

- Image: `charts/02_line_daily_passengers.png`
- Task type: `Line Graph`

| Case | Report file | Deliberately injected evidence | Expected result |
| --- | --- | --- | --- |
| 1 | `error_taxonomy/line/01_value_inaccuracy.txt` | Bus 2010 is stated as 2.0 million instead of 1.8 million. | One value inaccuracy |
| 2 | `error_taxonomy/line/02_entity_misalignment.txt` | Bus and rail values for 2010 are exchanged. | One entity or series misalignment |
| 3 | `error_taxonomy/line/03_trend_direction_error.txt` | Bus is described as increasing although it falls from 1.8 to 1.3 million. | One trend direction error |
| 4 | `error_taxonomy/line/04_comparison_ranking_error.txt` | Metro is called highest in 2020 although rail is highest. | One comparison or ranking error |
| 5 | `error_taxonomy/line/05_key_feature_omission.txt` | Metro is not mentioned. | One key feature omission |

## Pie-chart cases

- Image: `charts/04_pie_household_spending.png`
- Task type: `Pie Chart`

| Case | Report file | Deliberately injected evidence | Expected result |
| --- | --- | --- | --- |
| 1 | `error_taxonomy/pie/01_value_inaccuracy.txt` | Utilities is stated as 14% instead of 10%. | One value inaccuracy |
| 2 | `error_taxonomy/pie/02_entity_misalignment.txt` | Food and transport values are exchanged. | One entity or series misalignment |
| 3 | `error_taxonomy/pie/03_trend_not_applicable.txt` | The report is factually correct and explicitly notes that one year cannot show change. | Zero errors; trend shows `N/A` |
| 4 | `error_taxonomy/pie/04_comparison_ranking_error.txt` | Food is called the largest category although housing is largest. | One comparison or ranking error |
| 5 | `error_taxonomy/pie/05_key_feature_omission.txt` | Other expenditure is not mentioned. | One key feature omission |

## Run in the interface

1. Open VividWrite normally, without a `demo` query parameter.
2. In Drafting, select the task type listed above and upload its image.
3. Paste one corresponding report into the editor.
4. Continue to Revision and select `Analyze report`.
5. Inspect the generated comparison image and `Detected differences` panel.
6. Return to Drafting and repeat with the next report while keeping the same image.

This exercises the real pipeline:

```text
image -> DePlot -> DeepSeek extraction/alignment -> local validation
      -> chart-aware taxonomy -> chart rendering -> Revision UI
```

The expected labels in this document are researcher annotations for scoring. They must
never be added to the runtime request. A missing expected class or an additional
content-fidelity class is a failed case that should be investigated.

## Automated verification

The backend test matrix supplies aligned records in the same schema produced by the real
pipeline. It verifies every line class independently, all four applicable single-pie
classes, pie trend non-applicability, and comparative-pie trend activation.

```powershell
cd backend
venv\Scripts\python.exe -m unittest tests.test_error_taxonomy -v
```

The previously completed bar-chart live-workflow run detected exactly one intended class
for each of the five bar reports. The new line and pie reports are prepared for local live
workflow testing before deployment.
