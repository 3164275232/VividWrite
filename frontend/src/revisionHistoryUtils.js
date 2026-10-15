const NEEDS_WORK = new Set(['developing', 'not_detected']);
const normalise = (value) => String(value || '').replace(/\s+/g, ' ').trim();
const finiteNumber = (value) => typeof value === 'number' && Number.isFinite(value);

function comparisonWarning(previous, current) {
  if (previous.task_id !== current.task_id || previous.reference_id !== current.reference_id
    || previous.feedback_version !== current.feedback_version
    || (previous.analysis_model && current.analysis_model && previous.analysis_model !== current.analysis_model)) {
    return 'The reference data or review framework changed. These reviews cannot reliably measure revision progress.';
  }
  return null;
}

export function sameDraftText(left, right) {
  const newlines = (value) => String(value || '').replace(/\r\n?/g, '\n');
  return newlines(left) === newlines(right);
}

export function comparableRevisions(current, revisions) {
  if (!current) return [];
  return revisions.filter((item) => item.task_id === current.task_id
    && item.id !== current.id && item.sequence < current.sequence);
}

export function compareRevisions(previous, current) {
  if (!previous || !current) return { items: [], warning: null };
  if (!previous.assessments?.length && !current.assessments?.length) {
    return { items: [], warning: 'Neither review contains a writing-criteria assessment to compare.' };
  }
  const warning = comparisonWarning(previous, current);
  if (warning) return { items: [], warning };
  const oldEssay = normalise(previous.essay);
  const newEssay = normalise(current.essay);
  const draftChanged = oldEssay !== newEssay;
  const oldAssessments = new Map((previous.assessments || []).map((item) => [item.code, item]));
  const newAssessments = new Map((current.assessments || []).map((item) => [item.code, item]));
  const codes = new Set([...oldAssessments.keys(), ...newAssessments.keys()]);
  const items = [];
  for (const code of codes) {
    const before = oldAssessments.get(code);
    const after = newAssessments.get(code);
    const wasIssue = NEEDS_WORK.has(before?.status);
    const isIssue = NEEDS_WORK.has(after?.status);
    if (!wasIssue && !isIssue) continue;
    const oldExcerpt = normalise(before?.excerpt);
    const newExcerpt = normalise(after?.excerpt);
    const oldGrounded = Boolean(oldExcerpt && oldEssay.includes(oldExcerpt));
    const newGrounded = Boolean(newExcerpt && newEssay.includes(newExcerpt));
    // A new positive excerpt elsewhere cannot resolve an unchanged flagged passage.
    // Both sides must be grounded, and the old passage must actually have changed.
    const evidenceChanged = draftChanged && oldGrounded && newGrounded
      && !newEssay.includes(oldExcerpt) && !oldEssay.includes(newExcerpt);
    const addedEvidence = draftChanged && before?.status === 'not_detected' && !oldExcerpt
      && newGrounded && !oldEssay.includes(newExcerpt);
    let state;
    let message;
    if (!before || !after) {
      state = 'unverified';
      message = 'One review has no assessment for this criterion; resolution is not verified.';
    } else if (before.analysis_source === 'local_fallback' || after.analysis_source === 'local_fallback') {
      state = 'unverified';
      message = 'A review used a limited local fallback. Compare the passages, but a correction has not been verified.';
    } else if (wasIssue && isIssue) {
      state = 'continuing';
      message = 'This criterion still needs attention. Compare the evidence below; the specific concern may have changed.';
    } else if (after.status === 'not_applicable') {
      state = 'optional';
      message = 'This criterion is now not applicable. Removing an optional passage is not the same as improving it.';
    } else if (wasIssue && after.status === 'effective' && (!newExcerpt || !newEssay.includes(newExcerpt))) {
      state = 'unverified';
      message = 'The new review reports improvement but does not cite a traceable current passage. Resolution is not verified.';
    } else if (!evidenceChanged && !addedEvidence) {
      state = 'reassessed';
      message = draftChanged
        ? 'The assessment changed without a traceable edit to its cited evidence. Check the feedback before treating this as progress.'
        : 'The same draft received a different assessment. This is review variation, not a writing improvement or a newly introduced error.';
    } else if (wasIssue && after.status === 'effective') {
      state = 'addressed';
      message = addedEvidence
        ? 'The draft now includes a cited passage for this previously undetected criterion, and the review rates it effective. Explain how it helps your reader.'
        : 'The previously cited passage changed and this criterion is now rated effective. Compare the two passages and explain what makes the revision clearer or more accurate.';
    } else {
      state = 'new';
      message = 'This review flags a concern alongside changed evidence. Recheck this passage; it was not flagged in the selected review.';
    }
    items.push({ code, before, after, state, message });
  }
  return { items, warning: null, draftChanged };
}

// Compare the same explicit category/series/period value, independently of a
// whole criterion's status. Omissions and system estimates are never corrections.
export function compareRecordValues(previous, current) {
  if (!previous || !current) return { items: [], warning: null };
  const warning = comparisonWarning(previous, current);
  if (warning) return { items: [], warning };
  const keyFor = (record) => JSON.stringify(['category', 'series', 'period', 'region']
    .map((field) => normalise(record[field]).toLowerCase()));
  const indexRecords = (records = []) => {
    const index = new Map();
    for (const record of records) {
      const key = keyFor(record);
      // Ambiguous duplicate keys cannot establish a correction.
      index.set(key, index.has(key) ? null : record);
    }
    return index;
  };
  const oldRecords = indexRecords(previous.records);
  const newRecords = indexRecords(current.records);
  const items = [];
  const explicit = (record) => record?.explicit_student_value === true
    && !record.estimated && !record.missing && finiteNumber(record.value);
  const tolerance = current.value_tolerance;
  if (!finiteNumber(tolerance) || tolerance < 0 || tolerance !== previous.value_tolerance) {
    const hasReferenceValues = [...oldRecords.values(), ...newRecords.values()]
      .some((record) => finiteNumber(record?.official_value));
    return { items, warning: hasReferenceValues
      ? 'A value-by-value comparison is unavailable because these reviews do not retain the same comparison tolerance. New analyses save this information; you can still compare the cited writing feedback.'
      : null };
  }
  const incorrect = (record) => explicit(record) && (
    (record.conflicting_values?.length || 0) > 1
    || Math.abs(record.value - record.official_value) > tolerance + 1e-9
  );
  const draftChanged = normalise(previous.essay) !== normalise(current.essay);
  for (const [key, before] of oldRecords) {
    const after = newRecords.get(key);
    if (!before || !after || !finiteNumber(before.official_value)
      || before.official_value !== after.official_value) continue;
    const wasIncorrect = incorrect(before);
    const isIncorrect = incorrect(after);
    if (!wasIncorrect && !isIncorrect) continue;
    let state;
    let message;
    if (wasIncorrect && isIncorrect) {
      state = 'continuing';
      message = 'This reported value still conflicts with the reference. Recheck the category, time point and unit.';
    } else if (!draftChanged) {
      state = 'reassessed';
      message = 'The same draft produced different extracted values. This is an analysis change, not writing progress.';
    } else if (wasIncorrect && !explicit(after)) {
      state = 'unverified';
      message = 'The earlier value is no longer explicitly extracted. Removing it or replacing it with an estimate does not verify a correction. Keep only details that support your main message.';
    } else if (!explicit(before) && isIncorrect && normalise(after.student_evidence)
      && normalise(current.essay).includes(normalise(after.student_evidence))
      && !normalise(previous.essay).includes(normalise(after.student_evidence))) {
      state = 'new';
      message = 'A newly reported value conflicts with the reference. Check the category, time point and unit before keeping this detail.';
    } else if (!normalise(before.student_evidence) || !normalise(after.student_evidence)
      || !normalise(previous.essay).includes(normalise(before.student_evidence))
      || !normalise(current.essay).includes(normalise(after.student_evidence))) {
      state = 'unverified';
      message = 'The extracted values changed, but both source passages could not be traced. Compare the reports before treating this as a correction or a new error.';
    } else if (normalise(current.essay).includes(normalise(before.student_evidence))
      || normalise(previous.essay).includes(normalise(after.student_evidence))) {
      state = 'reassessed';
      message = 'The extracted values changed without a traceable edit to the cited passages. Recheck the analysis against your report.';
    } else if (wasIncorrect && explicit(after)) {
      state = 'addressed';
      message = 'The revised explicit value now agrees with the reference within the same tolerance. Consider how this detail supports your trend or comparison.';
    } else {
      state = 'new';
      message = 'This review flags an explicit value that was not flagged in the selected review. Check its category, time point and unit against the chart.';
    }
    items.push({ key, before, after, state, message, label: recordLabel(after), tolerance });
  }
  return { items, warning: null };
}

export const REVISION_STATES = {
  addressed: 'Addressed in this review',
  continuing: 'Still needs attention',
  new: 'Newly flagged',
  reassessed: 'Review changed',
  optional: 'Now optional',
  unverified: 'Not verified',
};

export function inferredRecords(chartData) {
  return (chartData?.records || []).filter((record) => record.estimated === true
    && !record.explicit_student_value && !record.missing
    && typeof record.value === 'number' && Number.isFinite(record.value));
}

export function inferenceGroups(chartData) {
  const groups = new Map();
  for (const record of inferredRecords(chartData)) {
    const inference = record.inference;
    const isInterpolation = inference?.method === 'linear_interpolation' && inference.from && inference.to;
    const key = isInterpolation
      ? JSON.stringify([record.series, record.region, inference.from, inference.to, inference.student_evidence])
      : JSON.stringify([recordLabel(record), record.value]);
    if (!groups.has(key)) groups.set(key, {
      key, label: isInterpolation ? record.series || recordLabel(record) : recordLabel(record),
      record, records: [],
    });
    groups.get(key).records.push(record);
  }
  return [...groups.values()];
}

export function recordLabel(record) {
  return [...new Set([record.category, record.series, record.period, record.region]
    .filter((value) => value !== null && value !== undefined && value !== ''))].join(' / ');
}
