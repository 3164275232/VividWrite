import { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, LocateFixed, RefreshCw } from 'lucide-react';
import { getRevisionGuidance } from './api.js';
import { sameDraftText } from './revisionHistoryUtils.js';
import { locateMoveRange } from './moveFeedbackUtils.js';
import { trackResearchEvent } from './researchTelemetry.js';

export default function RevisionProgress({ current, text, isAnalyzing, warning, onLocate }) {
  const [guidance, setGuidance] = useState(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let cancelled = false;
    if (!current?.id) return;
    setLoading(true);
    setError(false);
    getRevisionGuidance(current.id, current.submission_id).then(({ guidance: result }) => {
      if (cancelled) return;
      if (!result || result.analysis_revision_id !== current.id) throw new Error('Review mismatch');
      setGuidance(result);
      trackResearchEvent('revision_guidance_viewed', {
        analysis_revision_id: current.id, submission_id: current.submission_id,
        based_on: result.based_on, source: result.source,
      });
    }).catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [current?.id, current?.submission_id, retry]);
  if (!current && !warning) return null;
  const stale = Boolean(current && !sameDraftText(current.essay, text));
  const facts = new Map((guidance?.facts || []).map((fact) => [fact.id, fact]));
  const cards = (items, improved = false) => items.map((item, index) => {
    const evidence = item.fact_ids.map((id) => facts.get(id)).filter(Boolean);
    const excerpt = evidence.map((fact) => fact.excerpt).find((quote) => locateMoveRange({ excerpt: quote }, current.essay));
    return <article className={`revision-coaching-card${improved ? ' revision-coaching-card--improved' : ''}`} key={`${index}-${item.title}`}>
      <h4>{improved ? <CheckCircle2 size={16} /> : <span className="revision-coaching-number">{index + 1}</span>}{item.title}</h4>
      <p>{item.explanation}</p>
      {!improved && <p className="revision-coaching-action"><strong>Try this:</strong> {item.action}</p>}
      {!improved && <p className="revision-coaching-check"><strong>Check your revision:</strong> {item.self_check}</p>}
      {improved && <p className="revision-coaching-check"><strong>Keep using:</strong> {item.action}</p>}
      {excerpt && <details className="revision-coaching-evidence" onToggle={(event) => {
        if (event.currentTarget.open) trackResearchEvent('revision_guidance_evidence_viewed', {
          analysis_revision_id: current.id, fact_ids: item.fact_ids,
        });
      }}>
        <summary>Passage in your report</summary>
        <blockquote>{excerpt}</blockquote>
        <button type="button" disabled={stale || isAnalyzing} onClick={() => onLocate({ excerpt })}>
          <LocateFixed size={14} /> Show in draft
        </button>
      </details>}
    </article>;
  });
  return <section className="revision-progress revision-coaching" aria-label="Revision guidance">
    <header className="revision-progress-heading">
      <div className="revision-progress-overview">
        <div className="revision-progress-title"><h2>Your next revision</h2>{current && <span>Review {current.sequence}</span>}</div>
        {loading && current && <p role="status">Connecting this draft with your recent feedback…</p>}
        {guidance && !loading && <p className="revision-coaching-scope">{guidance.based_on.length
          ? `Automatically informed by ${guidance.based_on.length} recent ${guidance.based_on.length === 1 ? 'draft' : 'drafts'} · Reviews ${guidance.based_on.map((item) => item.sequence).join(', ')}`
          : 'Based on this draft · Future reviews will build on your feedback.'}</p>}
      </div>
    </header>
    {warning && <p className="revision-progress-notice" role="status">{warning}</p>}
    {stale && <p className="revision-progress-notice" role="status"><AlertCircle size={15} />
      Draft changed since Review {current.sequence}. Compare again to update this guidance.
    </p>}
    {error && <p className="revision-progress-notice" role="alert">Your revision guidance could not be loaded.
      <button type="button" disabled={loading || isAnalyzing} onClick={() => setRetry((value) => value + 1)}><RefreshCw size={14} /> Retry</button>
    </p>}
    {guidance && !loading && <>
      {guidance.unchanged_since_latest && <p className="revision-progress-notice">This draft is unchanged from the latest comparable review. Different AI wording does not indicate writing progress.</p>}
      <p className="revision-coaching-summary">{guidance.summary}</p>
      {guidance.improvements.length > 0 && <div className="revision-coaching-improvements"><h3>What improved</h3>{cards(guidance.improvements, true)}</div>}
      {guidance.priorities.length > 0 && <div className="revision-coaching-priorities"><h3>Focus on next</h3>{cards(guidance.priorities)}</div>}
      <p className="revision-comparison-note">{guidance.source === 'ai' ? 'AI guidance grounded in your saved drafts and reviews.' : 'Saved review guidance; AI synthesis was unavailable.'}
        {' '}You do not need to report every data point. These observations concern this task, not lasting mastery.</p>
    </>}
  </section>;
}
