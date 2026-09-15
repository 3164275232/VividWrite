import { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, History, LocateFixed, RefreshCw, AlertCircle } from 'lucide-react';
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

  if (!current && !warning) return null;
  return (
    <section className="revision-progress" aria-label="Revision progress">
      <header className="revision-progress-heading">
        <h2><History size={17} /> Revision progress</h2>
        {current && <span>Review {current.sequence} · {new Date(current.created_at).toLocaleString()}</span>}
        {previous && (
          <label>
            Compare with
            <select aria-label="Compare with earlier review" value={previous.id}
              disabled={isAnalyzing || loading}
              onChange={(event) => {
                setSelectedId(event.target.value);
                trackResearchEvent('revision_baseline_selected', {
                  analysis_id: current.id, baseline_id: event.target.value,
                });
              }}>
              {candidates.map((item) => <option value={item.id} key={item.id}>
                Review {item.sequence} · {new Date(item.created_at).toLocaleString()}
              </option>)}
            </select>
          </label>
        )}
      </header>
      {warning && <p className="revision-progress-notice" role="status">{warning}</p>}
      {error && <p className="revision-progress-notice" role="alert">History could not be loaded.
        <button type="button" onClick={() => setReload((value) => value + 1)}><RefreshCw size={14} /> Retry</button>
      </p>}
      {loading && <p role="status">Loading earlier reviews...</p>}
      {current && stale && <p className="revision-progress-notice" role="status">
        <AlertCircle size={15} /> Draft changed since Review {current.sequence}. Compare again to check your latest edits.
      </p>}
      {current && !previous && !loading && !error && <p>
        Your first saved review for this task. After revising, compare again to see what changed.
      </p>}
      {comparison.warning && <p className="revision-progress-notice">{comparison.warning}</p>}
      {previous && !comparison.warning && <>
        <p>Comparing Review {current.sequence} with Review {previous.sequence}. These are review outcomes for this task, not a measure of lasting mastery.</p>
        {valueComparison.warning && <p>{valueComparison.warning}</p>}
        {valueComparison.items.length > 0 && <section className="revision-value-changes" aria-label="Changes to reported values">
          <h3>What changed in your reported values</h3>
          <p>Only previously or currently flagged values are compared. Unreported details are not automatically writing errors.</p>
          {valueComparison.items.map((item) => (
            <details className={`revision-change revision-change--${item.state}`} key={item.key}
              onToggle={(event) => {
                if (event.currentTarget.open) trackResearchEvent('revision_value_evidence_viewed', {
                  analysis_id: current.id, baseline_id: previous.id, record_key: item.key, state: item.state,
                });
              }}>
              <summary><span>{item.label}</span><strong>{REVISION_STATES[item.state]}</strong></summary>
              <p>{item.message}</p>
              <p>Reference value: <strong>{item.after.official_value} {current.unit || ''}</strong>
                {' · '}Accepted tolerance: ±{item.tolerance} {current.unit || ''}</p>
              <div className="revision-evidence-grid">
                <ReportedValue record={item.before} label={`Review ${previous.sequence}`} />
                <ReportedValue record={item.after} label={`Review ${current.sequence}`} />
              </div>
              {locateMoveRange({ excerpt: item.after.student_evidence }, current.essay) &&
                <button type="button" disabled={stale || isAnalyzing}
                  onClick={() => onLocate({ excerpt: item.after.student_evidence })}>
                  <LocateFixed size={14} /> Locate revised value
                </button>}
            </details>
          ))}
        </section>}
        <h3>Changes in writing criteria</h3>
        <div className="revision-progress-counts" aria-live="polite">
          {['addressed', 'continuing', 'new', 'reassessed'].map((state) => (
            <span className={`revision-change--${state}`} key={state}>
              {state === 'addressed' ? <CheckCircle2 size={15} /> : state === 'reassessed' ? <RefreshCw size={15} /> : <AlertCircle size={15} />}
              <strong>{comparison.items.filter((item) => item.state === state).length}</strong> {REVISION_STATES[state]}
            </span>
          ))}
        </div>
        {!comparison.items.length && <p>No flagged criteria in either review. This is not a guarantee that the report is error-free.</p>}
        {comparison.items.map((item) => (
          <details className={`revision-change revision-change--${item.state}`} key={item.code}
            onToggle={(event) => {
              if (event.currentTarget.open) trackResearchEvent('revision_criterion_evidence_viewed', {
                analysis_id: current.id, baseline_id: previous.id, criterion_code: item.code, state: item.state,
              });
            }}>
            <summary>
              <span>Criterion {item.after?.number || item.before?.number}: {item.after?.label || item.before?.label}</span>
              <strong>{REVISION_STATES[item.state]}</strong>
            </summary>
            <p>{item.message}</p>
            <div className="revision-evidence-grid">
              <ReviewEvidence assessment={item.before} label={`Review ${previous.sequence}`} />
              <ReviewEvidence assessment={item.after} label={`Review ${current.sequence}`} />
            </div>
            {locateMoveRange(item.after, current.essay) && <button type="button" disabled={stale || isAnalyzing}
              onClick={() => onLocate(item.after)}><LocateFixed size={14} /> Locate current passage</button>}
          </details>
        ))}
        {[...comparison.items, ...valueComparison.items].some((item) => item.state === 'addressed') &&
          <p className="revision-learning-prompt">Before your next task, explain which change helped your reader and how you could use that approach with a new chart.</p>}
      </>}
      {previous && <details className="revision-history-archive">
        <summary>Earlier report and images · Review {previous.sequence}</summary>
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
      </details>}
      {nextBefore && <button type="button" disabled={loadingMore} onClick={loadMore}>
        <History size={14} /> {loadingMore ? 'Loading...' : 'Load earlier reviews'}
      </button>}
    </section>
  );
}
