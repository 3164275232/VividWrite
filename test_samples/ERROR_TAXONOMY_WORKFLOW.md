# Five single-error real-workflow tests

These tests use the normal VividWrite workflow. All five cases use the same chart
and differ only in the report text. No aligned chart records, error labels, or
feedback cards are supplied to the application.

## Inputs

- Image: `charts/01_bar_recycling_rates.png`
- Task type: `Bar Chart`

| Case | Report file | Expected taxonomy result |
| --- | --- | --- |
| 1 | `error_taxonomy/01_value_inaccuracy.txt` | One value inaccuracy |
| 2 | `error_taxonomy/02_entity_misalignment.txt` | One entity or series misalignment |
| 3 | `error_taxonomy/03_trend_direction_error.txt` | One trend direction error |
| 4 | `error_taxonomy/04_comparison_ranking_error.txt` | One comparison or ranking error |
| 5 | `error_taxonomy/05_key_feature_omission.txt` | One key feature omission |

## Run in the interface

1. Open VividWrite normally, without a `demo` query parameter.
2. In Drafting, select `Bar Chart` and upload the image above.
3. Paste one report from the table above into the editor.
4. Continue to Revision and select `Analyze report`.
5. Inspect the generated comparison image and Detected differences panel.
6. Return to Drafting and repeat with the next report while keeping the same image.

This exercises the deployed pipeline:

```text
image -> DePlot -> DeepSeek extraction/alignment -> local validation
      -> five-class taxonomy -> chart rendering -> Revision UI
```

## Injected expert annotations

These are evaluation labels, not inputs sent to the application:

| Type | Deliberately injected evidence |
| --- | --- |
| Value inaccuracy | Manchester 2015 is reported as 50%; the chart shows 31%. |
| Entity or series misalignment | Bristol and Leeds 2015 values are exchanged (35% and 42%). |
| Trend direction error | Manchester is described as decreasing; the chart increases from 31% to 46%. |
| Comparison or ranking error | Leeds is called highest in 2020; Bristol is highest at 55%. |
| Key feature omission | Liverpool is not mentioned. |

Each case should return only its target taxonomy class. A missing target class or
an additional content-fidelity class is a failed case that must be investigated.
The expected labels in this document are for researcher scoring only and must
never be added to the runtime request.

## Last real-workflow verification

All five reports were submitted separately through the local HTTP workflow using
DePlot output extracted from the PNG and fresh DeepSeek alignment for each report.

| Case | Total taxonomy issues | Observed class | Result |
| --- | ---: | --- | --- |
| 1 | 1 | `value_inaccuracy` | Pass |
| 2 | 1 | `entity_misalignment` | Pass |
| 3 | 1 | `trend_direction_error` | Pass |
| 4 | 1 | `comparison_ranking_error` | Pass |
| 5 | 1 | `key_feature_omission` | Pass |
