# Revision Progress and Estimated Chart Values

## Local workflow

1. Sign in, select or upload a task image, and analyse a report.
2. Edit the report and choose **Compare again**. **This revision** shows a compact
   summary of verified improvements and remaining concerns, compared with the
   previous successful review for that user and image.
3. Open **Review changes** to filter **Improved**, **Needs attention** or **Other
   changes**. Expand one finding to compare its old and new evidence, then choose
   **Show in draft** to locate the current passage. **Compare with** selects an
   earlier baseline without changing the editable draft.
4. **Earlier draft & images** retains the earlier essay, generated chart and
   original-image annotations when those annotations exist.

History starts with analyses performed after this feature is installed. Older
research logs are not silently imported as learner revision histories. Selecting
the same task on a later visit and analysing again retrieves its earlier reviews.
Changing image content or chart type creates a separate task history. Changed
reference data or framework versions prevent potentially misleading comparisons.

## Interpreting changes

- **Addressed in this review**: previously flagged, now effective, with changed
  cited evidence in the draft. This is an assessment outcome, not proof of mastery.
- **Still needs attention**: flagged in both reviews. The specific concern may
  have changed; both explanations and excerpts are retained.
- **Newly flagged**: the new review flags a criterion alongside changed evidence.
- **Review changed**: the assessment changed without a traceable evidence edit,
  including repeated analysis of identical text. This is not reported as progress.
- **Now optional / Not verified**: not applicable in the new review, or an
  assessment is missing. Neither is counted as a successful correction.

Comparisons use existing assessment results, not another paid model call. They
track criteria and their cited evidence; they are not a universal semantic
issue-matching engine. A criterion may contain multiple concerns. The system
does not claim that every concern disappeared because one status became green.

### Evidence and specific value changes

The comparison now checks both sides of the cited evidence. A new positive
excerpt elsewhere in the essay cannot resolve an unchanged flagged passage.
An ungrounded earlier quote or a local fallback assessment cannot establish a
verified improvement. Newly added, traceable evidence can demonstrate a
previously undetected move. This remains a criterion-level review: arbitrary
semantic rewrites and multiple concerns within a criterion require learner or
teacher judgement.

**Reported value** findings compare the same category/series/period/region
record, alongside writing-criterion findings in the same filters. For example, a student value changing from
47 to 42 against a reference of 42 can be shown as addressed even while Criterion
4 still needs work. The card retains the old and new values, verbatim source
sentences when locally traceable, the reference value and the accepted tolerance.
The learner can locate the current sentence and consider how it supports a trend
or comparison. This adds no model call and does not generate replacement prose.

Only explicit values are eligible. Removing an incorrect value or replacing it
with an estimate is not counted as a correction. Adding an omitted correct value
is not automatically counted as progress: a good report selects useful details
instead of listing every cell. Identical drafts with changed extraction results
are treated as analysis variation. Changes without grounded, edited evidence are
not reported as verified corrections. Tolerances and reference values must agree;
duplicate record keys are excluded. Model changes, when recorded in both reviews,
also prevent progress comparisons. Older snapshots without this metadata remain
readable, with a notice when numerical comparison is unavailable.

Edits after analysis trigger a stale-review notice. Historical feedback and
images never overwrite the current editable draft. Failed analyses do not create
new reviews. Failed history storage does not discard a successful chart analysis.
The notice also works when history storage fails. A failed reanalysis preserves
the last successful image; while another analysis runs, its earlier provenance
is stated. Selecting historical evidence never replaces the editable essay.

## Estimated values

The PNG renderer adds **diagonal stripes** to drawable records where
`estimated=true`, `missing=false`, and `explicit_student_value` is not true.
Bars and pie sectors retain their original category colours, with a stripe pattern
covering the exact inferred shape. Line and area estimates use striped circular
points. Explicit values keep their existing style; missing values stay missing.
The exported PNG itself includes an explanatory subtitle, so provenance remains
visible outside the application. Numerical-error outlines, fills and labels remain
separate; pie-error hatching was removed so stripes have only one meaning.

Vega-Lite's [description channel](https://vega.github.io/vega-lite/docs/encoding.html#description)
identifies each inferred SVG mark. The renderer copies its actual geometry into
a transparent SVG pattern overlay before PNG conversion. This preserves grouped,
horizontal, stacked, normalized and centered bar geometry and pie angles. Area
points retain the original stack order and offset; all values participate in
positioning while only inferred points are shown.

Explicit-value enforcement still removes unsupported model values before
reconstruction. A conservative local pass then supports exact-label comparisons
(half, twice, triple and compatible-unit differences) against an explicitly stated
student value. Pie remainders are derived only when the student explicitly names
the remaining category and states every other share. These calculations never
read official values. Multiple series require an unambiguous series reference;
conflicting, negated or hypothetical claims remain unfilled. Estimates cannot
become anchors for more estimates, and an explicit value always takes precedence.

Continuous temporal trends with stated endpoints can support straight-line
interpolation for line, area and year-based bar charts. Bars with unordered
categories are never interpolated across categories. Every inferred record stores
its method, student source sentence and anchor values. This is a possible rendering
of the description: words such as "steadily" do not specify exact intermediate
figures. Unbounded qualitative descriptions alone do not establish numeric heights.
An estimate is not automatically an essay error, and not every chart value needs
to be included in a Task 1 report. A report explicitly stating every plotted value
correctly has zero inferred marks.

The exported line chart also uses **dashed connections** where a segment touches
an estimated point or crosses an unreported period. Explicit adjacent points retain
solid connections. A dashed connector never fills a missing record with a number.
Its subtitle explains that the exact intermediate path was not stated in the essay.
Thus a gap bridged for display cannot silently appear to be a fully specified trend.

The interface shows a small provenance legend with stated and inferred counts.
**How were these values inferred?** is collapsed for each new review and groups
repeated interpolation explanations by series and endpoints, retaining every
estimated period and value.
Each group explains the straight-line assumption and, where available, quotes the
student's trend wording with a button to locate it. An estimate is a possible
rendering of the description, not the official value to copy into the report.
Without a stored derivation, the interface explicitly says that it is unavailable.
This remains narrower than the teacher's full qualitative-proposition proposal:
it does not yet reconstruct every value-free trend, comparison or degree expression.

The learning emphasis is on noticing, checking evidence and explaining one's own
revision. A short prompt invites the learner to carry a useful strategy to a new
chart. Successful correction on this task is not evidence of transfer; an independent
new task would be needed to evaluate that educational outcome.

## Storage and verification

- Private snapshots: `backend/user_data/revision_history.sqlite3`, within the
  existing user-data volume. Requests derive identity from the authenticated session.
- Historical media use the existing uploads/charts directories and volumes.
- New snapshots also retain numeric tolerance, analysis model and available
  record-level source sentences. Existing JSON snapshots require no schema migration.
- Research events record opening criterion/value comparisons, opening estimate
  explanations and locating their evidence; they do not infer understanding from a click.
- `GET /api/revision-history/{task_id}?before={sequence}` returns at most 30
  earlier reviews belonging to the caller; the UI can fetch earlier pages.
- Backend unit/integration tests: `test_revision_history.py`,
  `test_estimated_chart_marks.py`, `test_chart_inference.py` and
  `test_chart_feedback.py` (including the complete extraction-to-PNG pipeline).
- Frontend comparisons: `frontend/tests/revisionHistory.test.js`.
- Deterministic rendering fixtures: run
  `backend\venv\Scripts\python.exe deploy\verify_revision_features.py`.
- Browser checks: with the local frontend running, execute
  `node deploy/verify_revision_progress_ui.cjs [path-to-playwright]`.
  Chrome is used by default; `BROWSER_CHANNEL` can select another installed channel.

The browser checks mock analysis responses and use real locally rendered PNGs.
They verify interaction and rendering, not live model classification accuracy.
Outputs are saved under `backend/user_data/revision_feature_checks/`.
