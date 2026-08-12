# VividWrite Statistical-Chart Error Taxonomy

## Purpose and scope

VividWrite uses a five-class operational taxonomy for content-fidelity errors in
IELTS Academic Writing Task 1 statistical-chart reports. The taxonomy covers bar,
line, and pie charts, while reporting whether each class is applicable to the
available chart structure. It does not grade grammar, vocabulary, style, or an
overall IELTS band.

The scope follows the official IELTS Task Achievement criterion: a response should
cover the task accurately and identify relevant key features, trends, and
differences. See the official [IELTS Writing Band Descriptors](https://ielts.org/cdn/Guides/ielts-writing-band-descriptors.pdf)
and [Academic test format](https://ielts.org/organisations/ielts-for-organisations/test-types/ielts-academic-test/academic-test-format-in-detail).

These five classes are VividWrite's operationalisation of that criterion. They are
not presented as an official IELTS-published error taxonomy. Before a participant
study, the labels and annotation guide should be reviewed by IELTS instructors.

## Stable error types

| Code | Display label | Inclusion rule | Local verification |
| --- | --- | --- | --- |
| `value_inaccuracy` | Value inaccuracy | An explicit value differs from the aligned official value outside the chart tolerance, or the report gives conflicting values for one cell. | Recompute the difference for the same category-series-period key. |
| `entity_misalignment` | Entity or series misalignment | Two explicit values form a reciprocal swap, or a named entity is absent from the official framework. | Compare the student-to-official assignment for both affected keys. |
| `trend_direction_error` | Trend direction error | A sentence explicitly describes an entity as increasing, decreasing, or stable, and that direction contradicts its official first-to-last direction. | Recompute direction from the entity's official endpoints. |
| `comparison_ranking_error` | Comparison or ranking error | An explicit highest, lowest, higher, or lower claim contradicts the official ordering in the same period or comparison context. | Recompute the ranking or pairwise ordering from official values. |
| `key_feature_omission` | Key feature omission | No traceable student value exists for an entire chart entity, or a required line-chart endpoint is absent. | Check aligned record coverage for the entity or endpoint. |

### Chart-specific applicability

All five classes are applicable to a line chart with at least two periods. A
single-period pie chart supports value, entity, comparison/ranking, and omission
checks, but not trend direction because it contains no temporal endpoints. The
API and interface report that distinction as `applicable: false` and `N/A` rather
than treating it as a successful zero-error trend check. Comparative pie records
with at least two ordered periods can activate the trend check.

## Output contract

Every statistical chart response contains an `error_taxonomy` object, uses chart
schema version `1.1`, and currently returns taxonomy version `1.1`:

```json
{
  "version": "1.1",
  "scope": "statistical-chart-content-fidelity",
  "definitions": [
    {
      "code": "value_inaccuracy",
      "applicable": true,
      "reason": "Official values are available for aligned numeric comparison.",
      "issue_count": 1
    }
  ],
  "applicability": {},
  "issues": [
    {
      "id": "value_inaccuracy:1",
      "error_type": "value_inaccuracy",
      "item": "Bristol - 2015",
      "message": "The report gives 47 for Bristol - 2015; the official value is 42.",
      "student_claim": {"value": 47},
      "official_fact": {"value": 42},
      "evidence": {
        "record_keys": [{"category": "Bristol", "series": "2015"}],
        "source_sentences": ["Bristol recorded 47% in 2015."]
      },
      "verification": {
        "status": "verified",
        "method": "aligned_numeric_comparison",
        "tolerance": 2
      },
      "confidence": 1
    }
  ],
  "summary": {
    "total_issues": 1,
    "verified_issues": 1,
    "affected_error_types": 1,
    "applicable_checks": 5,
    "not_applicable_checks": 0,
    "counts": {"value_inaccuracy": 1}
  }
}
```

The legacy `records`, `feedback_status`, and `comparison` fields remain available
for renderer and API compatibility. A record also receives `taxonomy_issue_ids`
when it supports one or more taxonomy issues.

The stable catalogue is available from `GET /api/error-taxonomy`. This endpoint is
useful for study materials and annotation tools because it does not require a model
call.

## Verification and demonstration

Use the normal Drafting and Revision workflow for demonstrations. The controlled
bar, line, and pie images, intentionally flawed reports, expected expert
annotations, applicability matrix, and exact steps are documented in
`test_samples/ERROR_TAXONOMY_WORKFLOW.md`. The image must go through DePlot and the
report must go through DeepSeek extraction/alignment; the expected labels are
never included in the runtime request.

Run the focused automated tests:

```powershell
cd backend
venv\Scripts\python.exe -m unittest tests.test_error_taxonomy -v
```

## Annotation rules for a benchmark

1. Annotate only content claims that can be linked to an official chart fact.
2. Use the most specific primary class. A reciprocal swap is
   `entity_misalignment`, not two independent `value_inaccuracy` labels.
3. Record the exact source sentence and official category-series-period key.
4. Treat a trend or ranking as an error only when the relation is explicit.
5. Use `key_feature_omission` only under the operational coverage rule above; do
   not assume every unreported chart cell is a required IELTS key feature.
6. Keep grammar and vocabulary annotations in a separate textual-feedback dataset.

## Known limitations

- A leading `it`, `its`, or `this category` can be resolved from the immediately
  preceding sentence only when that sentence names exactly one chart entity.
  Ambiguous pronouns such as "the former" still require human review.
- Trend checks currently cover explicit increase, decrease, and stable claims.
- Ranking checks are conservative and avoid ambiguous "largest change" wording.
- A single-period pie chart cannot support a trend-direction claim; this is
  reported as not applicable rather than inferred from slice order.
- Map and process tasks are outside this statistical taxonomy.
- Detection reliability still needs to be measured on an expert-labelled corpus;
  deterministic verification does not by itself establish recall on natural essays.
