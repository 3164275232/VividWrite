import { useMemo, useState } from 'react';
import {
  AlertCircle,
  BarChart3,
  CheckCircle2,
  FileText,
  Minus,
  Plus,
  RefreshCw,
} from 'lucide-react';
import CmEditor from './CmEditor.jsx';
import { CriteriaAnalysisProgress } from './MoveFeedback.jsx';

function FeedbackStatus({ chartUrl, chartData }) {
  if (!chartUrl) {
    return <span className="revision-status revision-status--idle">Not analyzed</span>;
  }

  if (!Array.isArray(chartData?.move_feedback?.assessments)) {
    return <span className="revision-status revision-status--idle">Visual ready</span>;
  }

  const attentionCount = Number(chartData?.move_feedback?.summary?.attention_count) || 0;
  if (attentionCount === 0) {
    return (
      <span className="revision-status revision-status--success">
        <CheckCircle2 size={13} />
        Seven criteria reviewed
      </span>
    );
  }

  return (
    <span className="revision-status revision-status--warning">
      <AlertCircle size={13} />
      {attentionCount} {attentionCount === 1 ? 'criterion' : 'criteria'} to refine
    </span>
  );
}

function ComparisonImage({ src, alt, zoom, emptyIcon, emptyTitle, emptyBody, isLoading = false }) {
  return (
    <div className="revision-image-stage">
      {src ? (
        <div className="revision-image-scroll">
          <div
            className="revision-image-zoom"
            style={{ width: `${zoom}%`, height: `${zoom}%` }}
          >
            <img src={src} alt={alt} />
          </div>
        </div>
      ) : (
        <div className="revision-image-empty" role="status" aria-live="polite">
          {emptyIcon}
          <strong>{isLoading ? 'Creating comparison image...' : emptyTitle}</strong>
          <span>{isLoading ? 'This can take a moment.' : emptyBody}</span>
        </div>
      )}
    </div>
  );
}

function LanguageSuggestions({
  suggestions,
  revisionReview,
  activeSuggestionId,
  setActiveSuggestionId,
  editorRef,
  applySuggestion,
  onSuggestionFocus,
}) {
  const groupedSuggestions = useMemo(() => {
    const groups = suggestions.reduce((result, suggestion) => {
      const category = suggestion.category || 'other';
      if (category !== 'overall') {
        (result[category] ||= []).push(suggestion);
      }
      return result;
    }, {});
    const preferredOrder = ['vocabulary', 'grammar', 'coherence'];
    return [
      ...preferredOrder.filter((category) => groups[category]),
      ...Object.keys(groups).filter((category) => !preferredOrder.includes(category)),
    ].map((category) => [category, groups[category]]);
  }, [suggestions]);

  const focusSuggestion = (suggestion) => {
    const range = suggestion.range || (Array.isArray(suggestion.ranges) && suggestion.ranges[0]);
    if (!range || !editorRef.current) return;
    const nextId = suggestion.id === activeSuggestionId ? null : suggestion.id;
    onSuggestionFocus?.();
    setActiveSuggestionId(nextId);
    editorRef.current.clearHighlights();
    if (nextId) {
      editorRef.current.highlightRange(range.start, range.end, false);
    }
  };

  if (!groupedSuggestions.length && !revisionReview) {
    return <p className="revision-empty-copy">Language notes will appear after analysis.</p>;
  }

  return (
    <div className="revision-language-content">
      {groupedSuggestions.map(([category, items]) => (
        <section className="revision-suggestion-group" key={category}>
          <h4>
            {category}
            <span>{items.length}</span>
          </h4>
          {items.map((suggestion) => {
            const range = suggestion.range
              || (Array.isArray(suggestion.ranges) && suggestion.ranges[0]);
            const isActive = suggestion.id === activeSuggestionId;
            return (
              <article
                className={`revision-suggestion${isActive ? ' is-active' : ''}`}
                key={suggestion.id}
                onClick={() => focusSuggestion(suggestion)}
              >
                <div className="revision-suggestion-heading">
                  <span>{suggestion.severity || 'note'}</span>
                  <button
                    type="button"
                    disabled={suggestion.applied || !suggestion.replacement}
                    onClick={(event) => {
                      event.stopPropagation();
                      applySuggestion(suggestion);
                    }}
                  >
                    {suggestion.applied ? 'Applied' : 'Apply'}
                  </button>
                </div>
                <p>{suggestion.message}</p>
                {range && <small>Click to locate this text in your report.</small>}
              </article>
            );
          })}
        </section>
      ))}
      {revisionReview && (
        <section className="revision-overall-review">
          <h4>Overall review</h4>
          <div className="revision-score-row">
            {['vocabulary', 'grammar', 'coherence'].map((category) => (
              <span key={category}>
                {category} <strong>{revisionReview[category]?.score ?? '-'}</strong>
              </span>
            ))}
          </div>
          {revisionReview.summary && <p>{revisionReview.summary}</p>}
        </section>
      )}
    </div>
  );
}

export default function RevisionWorkspace({
  imagePreview,
  chartUrl,
  chartData,
  chartFeedbackDetails,
  activeMoveAssessment,
  text,
  onTextChange,
  editorRef,
  isAnalyzing,
  onAnalyze,
  analysisError,
  reviewSuggestions,
  revisionReview,
  activeSuggestionId,
  setActiveSuggestionId,
  onLanguageSuggestionFocus,
  applySuggestion,
}) {
  const [zoom, setZoom] = useState(100);
  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
  const suggestionCount = reviewSuggestions.length;
  const activeMoveVisual = activeMoveAssessment?.visual?.image_url || null;

  const changeZoom = (delta) => {
    setZoom((current) => Math.min(180, Math.max(70, current + delta)));
  };

  return (
    <div className="revision-workspace">
      <section className="revision-comparison">
        <header className="revision-comparison-header">
          <div>
            <span className="panel-eyebrow">Revision workspace</span>
            <h1>Compare what the task shows with what your report communicates</h1>
          </div>
          <div className="revision-comparison-actions">
            <div className="revision-zoom-controls" aria-label="Comparison zoom">
              <button
                className="icon-button"
                type="button"
                onClick={() => changeZoom(-10)}
                aria-label="Zoom out"
                title="Zoom out"
                disabled={zoom <= 70}
              >
                <Minus size={15} />
              </button>
              <button
                className="revision-zoom-value"
                type="button"
                onClick={() => setZoom(100)}
                title="Reset zoom"
              >
                {zoom}%
              </button>
              <button
                className="icon-button"
                type="button"
                onClick={() => changeZoom(10)}
                aria-label="Zoom in"
                title="Zoom in"
                disabled={zoom >= 180}
              >
                <Plus size={15} />
              </button>
            </div>
            <button
              className="revision-primary-action"
              type="button"
              onClick={onAnalyze}
              disabled={isAnalyzing}
            >
              <RefreshCw className={isAnalyzing ? 'is-spinning' : ''} size={15} />
              {isAnalyzing ? 'Analyzing...' : chartUrl ? 'Compare again' : 'Analyze report'}
            </button>
          </div>
        </header>

        <div className="revision-comparison-grid">
          <figure className="revision-comparison-view">
            <figcaption>
              <span>
                <small>Target</small>
                {activeMoveVisual ? `Original image · Criterion ${activeMoveAssessment.number} cue` : 'Original task image'}
              </span>
              <span className={`revision-view-label${activeMoveVisual ? ' revision-view-label--visual' : ''}`}>
                {activeMoveVisual ? 'Annotated cue' : 'Reference'}
              </span>
            </figcaption>
            <ComparisonImage
              src={activeMoveVisual || imagePreview}
              alt={activeMoveVisual ? 'Original IELTS task with writing-criteria feedback cues' : 'Original IELTS task'}
              zoom={zoom}
              emptyIcon={<FileText size={24} />}
              emptyTitle="No task image"
              emptyBody="Return to the earlier stage and upload the IELTS task image."
            />
          </figure>

          <figure className="revision-comparison-view">
            <figcaption>
              <span>
                <small>Your report</small>
                Image generated from your text
              </span>
              <FeedbackStatus chartUrl={chartUrl} chartData={chartData} />
            </figcaption>
            <ComparisonImage
              src={chartUrl}
              alt="Visual interpretation generated from the report"
              zoom={zoom}
              isLoading={isAnalyzing}
              emptyIcon={<BarChart3 size={24} />}
              emptyTitle="No comparison image yet"
              emptyBody="Analyze your report to see what your writing communicates."
            />
          </figure>
        </div>
      </section>

      <section className="revision-editing-grid">
        <div className="revision-editor-panel">
          <header className="revision-section-heading">
            <div>
              <span className="panel-eyebrow">Revise directly</span>
              <h2>Your report</h2>
            </div>
            <span className="word-count">{wordCount} words</span>
          </header>
          <div className="revision-editor-surface">
            <CmEditor
              ref={editorRef}
              value={text}
              onChange={onTextChange}
              placeholder="Revise your report while comparing the two images above."
              style={{ height: '100%' }}
            />
          </div>
        </div>

        <aside className="revision-review-panel" aria-label="Revision feedback">
          <header className="revision-section-heading">
            <div>
              <span className="panel-eyebrow">What to review</span>
              <h2>Writing criteria</h2>
            </div>
          </header>

          {analysisError && (
            <div className="revision-error" role="alert">
              <AlertCircle size={16} />
              <span>{analysisError}</span>
            </div>
          )}

          <div className="revision-difference-content">
            {!chartUrl && !isAnalyzing && (
              <div className="revision-review-empty">
                <BarChart3 size={22} />
                <strong>Review your writing criteria</strong>
                <p>Analyze your report to receive evidence-linked hints across seven writing criteria.</p>
              </div>
            )}
            {isAnalyzing && (
              <CriteriaAnalysisProgress />
            )}
            {chartUrl && chartFeedbackDetails}
          </div>

          <details className="revision-secondary-feedback">
            <summary>
              <span>
                <FileText size={15} />
                Language notes
              </span>
              <small>{suggestionCount ? `${suggestionCount} notes` : 'Optional'}</small>
            </summary>
            <LanguageSuggestions
              suggestions={reviewSuggestions}
              revisionReview={revisionReview}
              activeSuggestionId={activeSuggestionId}
              setActiveSuggestionId={setActiveSuggestionId}
              editorRef={editorRef}
              applySuggestion={applySuggestion}
              onSuggestionFocus={onLanguageSuggestionFocus}
            />
          </details>
        </aside>
      </section>
    </div>
  );
}
