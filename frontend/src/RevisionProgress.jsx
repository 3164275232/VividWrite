import { useEffect, useId, useMemo, useState } from 'react';
import { CheckCircle2, ChevronDown, History, LocateFixed, RefreshCw, AlertCircle } from 'lucide-react';
import { getRevisionHistory, resolveBackendUrl } from './api.js';
import { comparableRevisions, compareRevisions, compareRecordValues, REVISION_STATES, sameDraftText } from './revisionHistoryUtils.js';
import { locateMoveRange } from './moveFeedbackUtils.js';
import { trackResearchEvent } from './researchTelemetry.js';

function ReviewEvidence({ assessment, label }) {
  return (
    <div className="revision-evidence">
      <strong>{label}</strong>
      {assessment?.excerpt && <blockquote>{assessment.excerpt}</blockquote>}
      <p>{assessment?.rationale || 'No passage was cited in this review.'}</p>
      {assessment?.hint && assessment.status !== 'effective' && <p>{assessment.hint}</p>}
    </div>
  );
}

function ReportedValue({ record, label }) {
  const value = record?.missing || record?.value == null ? 'No explicit value extracted'
    : record.estimated ? 'System estimate (no explicit value)'
      : record.conflicting_values?.length > 1 ? record.conflicting_values.join(' / ') : record.value;
  return <div className="revision-evidence">
    <strong>{label}</strong>
    <p>Reported value: <strong>{value}</strong></p>
    {record?.student_evidence && <blockquote>{record.student_evidence}</blockquote>}
  </div>;
}

export default function RevisionProgress({ current, text, isAnalyzing, warning, onLocate }) {
  const [expanded, setExpanded] = useState(false);
  const [activeGroup, setActiveGroup] = useState('improved');
  const panelId = useId();
  const [revisions, setRevisions] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [nextBefore, setNextBefore] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  useEffect(() => {
    let cancelled = false;
    setRevisions([]);
    setSelectedId('');
    setNextBefore(null);
    setError('');
    setLoading(false);
    if (!current?.task_id) return;
    setLoading(true);
    getRevisionHistory(current.task_id, current.sequence).then((response) => {
      if (cancelled) return;
      setRevisions(response.revisions || []);
      setNextBefore(response.next_before);
    }).catch((failure) => {
      if (!cancelled) setError(failure.message);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [current?.task_id, current?.id, current?.sequence, reload]);
  const candidates = comparableRevisions(current, revisions);
  const previous = candidates.find((item) => item.id === selectedId) || candidates[0];
  const comparison = useMemo(() => compareRevisions(previous, current), [previous, current]);
  const valueComparison = useMemo(() => compareRecordValues(previous, current), [previous, current]);
  useEffect(() => {
    if (!previous || !current || loading) return;
    trackResearchEvent('revision_comparison_ready', {
      submission_id: current.submission_id || null, analysis_id: current.id,
      baseline_id: previous.id, essay: current.essay,
      criteria: comparison, reported_values: valueComparison,
    });
  }, [current, previous, loading, comparison, valueComparison]);
  const stale = Boolean(current && !sameDraftText(current.essay, text));

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const response = await getRevisionHistory(current.task_id, nextBefore);
      setRevisions((items) => [...items, ...(response.revisions || [])]);
      setNextBefore(response.next_before);
      setError('');
    } catch (failure) { setError(failure.message); }
    finally { setLoadingMore(false); }
  };

  const changes = [
    ...valueComparison.items.map((item) => ({ ...item, kind: 'value', title: item.label })),
    ...comparison.items.map((item) => ({ ...item, kind: 'criterion',
      key: item.code, title: item.after?.label || item.before?.label })),
  ];
  const groups = [
    { id: 'improved', label: 'Improved', items: changes.filter((item) => item.state === 'addressed') },
    { id: 'attention', label: 'Needs attention', items: changes.filter((item) => ['new', 'continuing'].includes(item.state)) },
    { id: 'other', label: 'Other changes', items: changes.filter((item) => !['addressed', 'new', 'continuing'].includes(item.state)) },
  ].filter((group) => group.items.length);
  const selectedGroup = groups.find((group) => group.id === activeGroup) || groups[0];
  const improved = changes.filter((item) => item.state === 'addressed');
  const attention = changes.filter((item) => ['new', 'continuing'].includes(item.state));
  const shortState = { addressed: 'Improved', continuing: 'Still needs attention', new: 'New concern',
    reassessed: 'Review changed', optional: 'Now optional', unverified: 'Not verified' };

  if (!current && !warning) return null;
  return (
    <section className="revision-progress" aria-label="Revision progress">
      <header className="revision-progress-heading">
        <div className="revision-progress-overview">
          <div className="revision-progress-title">
            <h2>This revision</h2>
            {current && <span>Review {current.sequence}</span>}
            {previous && <span className="revision-baseline-caption">since Review {previous.sequence}</span>}
          </div>
          {previous && !comparison.warning && <p className="revision-progress-preview" aria-live="polite">
            {improved.length ? <><CheckCircle2 size={16} /><span><strong>Improved:</strong>{' '}
              {improved.slice(0, 2).map((item) => item.kind === 'value'
                ? `${item.title} (${item.before.value} → ${item.after.value})` : item.title).join(' · ')}
              {improved.length > 2 && ` +${improved.length - 2} more`}</span></>
              : <span>{attention.length ? 'Keep revising the areas below.' : 'No verified improvements in this comparison.'}</span>}
            {attention.length > 0 && <span className="revision-attention-count">{attention.length} to revisit</span>}
          </p>}
          {current && !previous && !loading && !error && <p>Your first review. Revise your report, then compare again.</p>}
          {loading && <p role="status">Loading earlier reviews…</p>}
        </div>
        {previous && <button type="button" className="revision-disclosure" aria-expanded={expanded}
          aria-controls={panelId} onClick={() => setExpanded((value) => !value)}>
          {expanded ? 'Hide changes' : 'Review changes'}<ChevronDown size={15} />
        </button>}
      </header>
      {warning && <p className="revision-progress-notice" role="status">{warning}</p>}
      {error && <p className="revision-progress-notice" role="alert">History could not be loaded.
        <button type="button" onClick={() => setReload((value) => value + 1)}><RefreshCw size={14} /> Retry</button>
      </p>}
      {current && stale && <p className="revision-progress-notice" role="status">
        <AlertCircle size={15} /> Draft changed since Review {current.sequence}. Compare again to check your edits.
      </p>}
      {comparison.warning && <p className="revision-progress-notice">{comparison.warning}</p>}
      {previous && <div className="revision-progress-body" id={panelId} hidden={!expanded}>
        <div className="revision-progress-toolbar">
          <div className="revision-change-filters" role="group" aria-label="Filter revision changes">
            {groups.map((group) => <button key={group.id} type="button"
              aria-pressed={selectedGroup?.id === group.id} onClick={() => setActiveGroup(group.id)}>
              {group.label}<span>{group.items.length}</span>
            </button>)}
          </div>
          <label className="revision-baseline-select">Compare with
            <select aria-label="Compare with earlier review" value={previous.id} disabled={isAnalyzing || loading}
              onChange={(event) => {
                setSelectedId(event.target.value);
                trackResearchEvent('revision_baseline_selected', { analysis_id: current.id, baseline_id: event.target.value });
              }}>
              {candidates.map((item) => <option value={item.id} key={item.id}>
                Review {item.sequence} · {new Date(item.created_at).toLocaleDateString(undefined, { timeZone: 'Asia/Shanghai' })}
              </option>)}
            </select>
          </label>
        </div>
        {valueComparison.warning && <p className="revision-comparison-note">{valueComparison.warning}</p>}
        {selectedGroup?.items.map((item) => {
          const excerpt = item.kind === 'value' ? item.after.student_evidence : item.after?.excerpt;
          return <details name={panelId + '-evidence'} className={`revision-change revision-change--${item.state}`}
            key={item.kind + item.key} data-change-kind={item.kind}
            onToggle={(event) => {
              if (event.currentTarget.open) trackResearchEvent(`revision_${item.kind}_evidence_viewed`, {
                analysis_id: current.id, baseline_id: previous.id, item_key: item.key, state: item.state,
              });
            }}>
            <summary><span><small>{item.kind === 'value' ? 'Reported value' : 'Writing'}</small>{item.title}</span>
              <strong>{shortState[item.state] || REVISION_STATES[item.state]}</strong><ChevronDown size={15} /></summary>
            <div className="revision-change-detail">
              <p>{item.message}</p>
              <div className="revision-evidence-grid">
                {item.kind === 'value' ? <>
                  <ReportedValue record={item.before} label={`Before · Review ${previous.sequence}`} />
                  <ReportedValue record={item.after} label={`Now · Review ${current.sequence}`} />
                </> : <>
                  <ReviewEvidence assessment={item.before} label={`Before · Review ${previous.sequence}`} />
                  <ReviewEvidence assessment={item.after} label={`Now · Review ${current.sequence}`} />
                </>}
              </div>
              <div className="revision-evidence-actions">
                {item.kind === 'value' && <span>Reference: {item.after.official_value} {current.unit || ''}
                  {' · '}Tolerance: ±{item.tolerance}</span>}
                {locateMoveRange({ excerpt }, current.essay) && <button type="button" disabled={stale || isAnalyzing}
                  onClick={() => onLocate({ excerpt })}><LocateFixed size={14} /> Show in draft</button>}
              </div>
            </div>
          </details>;
        })}
        {!changes.length && !comparison.warning && <p>No flagged changes between these reviews.</p>}
        {selectedGroup?.id === 'improved' && <p className="revision-learning-prompt">
          What made this revision clearer? Try the same approach with your next chart.
        </p>}
        <details className="revision-history-archive">
          <summary><History size={14} /> Earlier draft & images · Review {previous.sequence}</summary>
          <div className="revision-history-images">
            {[['Original task', previous.original_url], ['Generated from the earlier report', previous.chart_url]].map(([label, url]) => (
              url && <figure key={label}><img src={resolveBackendUrl(url)} alt={label} loading="lazy" /><figcaption>{label}</figcaption></figure>
            ))}
            {(previous.assessments || []).filter((item) => item.visual?.image_url).map((item) => (
              <figure key={item.code}><img src={resolveBackendUrl(item.visual.image_url)} alt={`Earlier criterion ${item.number} annotation`} loading="lazy" />
                <figcaption>Criterion {item.number} · Earlier annotation</figcaption></figure>
            ))}
          </div>
          <div className="revision-history-essay">{previous.essay}</div>
        </details>
        {nextBefore && <button type="button" disabled={loadingMore} onClick={loadMore}>
          {loadingMore ? 'Loading…' : 'Load earlier reviews'}
        </button>}
        <p className="revision-comparison-note">Changes refer to these two drafts. They do not measure lasting mastery or require you to report every data point.</p>
      </div>}
      {!previous && nextBefore && <button type="button" disabled={loadingMore} onClick={loadMore}>Load earlier reviews</button>}
    </section>
  );
}
