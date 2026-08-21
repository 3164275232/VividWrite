# VividWrite Practice Sample Showcase

This folder contains 18 pre-validated IELTS Academic Writing Task 1 reports:
six for each of the bar, line, and pie practice samples. Each report should be
tested separately through the normal Drafting to Revision workflow.

## Bar chart: UK recycling rates

| File | Intended result | Deliberate flaw |
| --- | --- | --- |
| `01_value_inaccuracy.txt` | Value inaccuracy | Manchester is reported as 50% in 2015 instead of 31%. |
| `02_entity_misalignment.txt` | Entity or series misalignment | Bristol's and Leeds's 2015 values are exchanged. |
| `03_trend_direction_error.txt` | Trend direction error | Manchester is described as decreasing although it rises from 31% to 46%. |
| `04_comparison_ranking_error.txt` | Comparison or ranking error | Leeds is described as the highest city in 2020 instead of Bristol. |
| `05_key_feature_omission.txt` | Key feature omission | Liverpool is omitted from the report. |
| `06_perfect_no_error.txt` | No content-fidelity error | All five cities, values, trends, and rankings agree with the chart. |

## Line graph: public transport use

| File | Intended result | Deliberate flaw |
| --- | --- | --- |
| `line/01_value_inaccuracy.txt` | Value inaccuracy | Bus use is reported as 2.0 million in 2010 instead of 1.8 million. |
| `line/02_entity_misalignment.txt` | Entity or series misalignment | The 2010 bus and rail values are exchanged. |
| `line/03_trend_direction_error.txt` | Trend direction error | Bus use is described as increasing although it falls from 1.8 to 1.3 million. |
| `line/04_comparison_ranking_error.txt` | Comparison or ranking error | Metro is described as the highest mode in 2020 instead of rail. |
| `line/05_key_feature_omission.txt` | Key feature omission | Metro is omitted from the report. |
| `line/06_perfect_no_error.txt` | No content-fidelity error | All three modes have correct endpoints, directions, and final ranking. |

## Pie chart: Canadian household spending

| File | Intended result | Deliberate flaw |
| --- | --- | --- |
| `pie/01_value_inaccuracy.txt` | Value inaccuracy | Utilities are reported as 14% instead of 10%. |
| `pie/02_entity_misalignment.txt` | Entity or series misalignment | Food's and transport's values are exchanged. |
| `pie/03_trend_not_applicable.txt` | No trend classification; trend check is Not applicable | The report explicitly explains that a one-year pie chart cannot show change over time. |
| `pie/04_comparison_ranking_error.txt` | Comparison or ranking error | Food is described as the largest category instead of housing. |
| `pie/05_key_feature_omission.txt` | Key feature omission | Other expenditure is omitted from the report. |
| `pie/06_perfect_no_error.txt` | No content-fidelity error | All six shares and comparisons agree with the chart. |

## Validation result

The 18 reports were run through the current `ChartFeedbackService`, including
DeepSeek extraction/alignment, deterministic taxonomy checks, and chart image
rendering. Seventeen passed on the first run. The line-graph perfect report was
simplified after its detailed description caused model alignment ambiguity; it
then passed a targeted rerun. All final reports produced their intended taxonomy
result and a valid rendered image.

The pie chart contains only one period (2024). Therefore, trend direction is not
verifiable for that sample. VividWrite correctly reports the trend check as
`Not applicable`; no wording-only edit can make a temporal trend error verifiable
without changing the source chart or the program's taxonomy rules.
