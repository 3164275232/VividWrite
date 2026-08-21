import { useEffect, useState } from 'react';
import {
  CircleX,
  CheckCircle2,
  Eye,
  Lightbulb,
  LoaderCircle,
  MinusCircle,
} from 'lucide-react';

const WRITING_CRITERIA = Object.freeze([
  ['Introducing the topic', 'Identify what the visual presents, including its subject and scope.'],
  ['Stating the overview', 'Give a broad synthesis of the most notable patterns without listing details.'],
  ['Highlighting key trends', 'Prioritise the trends or features that carry the main message of the visual.'],
  ['Elaborating on the key trends', 'Support an identified trend with relevant and accurate detail.'],
  ['Including key trends and their elaboration', 'Combine a meaningful trend and its supporting evidence coherently.'],
  ['Making comparative or contrastive statements', 'Make relevant relationships across categories, groups, or time periods explicit.'],
  ['Stating the conclusion', 'If a closing statement is used, synthesise rather than repeat individual details.'],
]);

const RESULT_REVEAL_INTERVAL_MS = 160;
const EMPTY_ASSESSMENTS = Object.freeze([]);

const STATUS_META = {
  effective: { label: 'Criterion met', tone: 'effective', Icon: CheckCircle2 },
  developing: { label: 'Needs revision', tone: 'developing', Icon: CircleX },
  not_detected: { label: 'Not yet demonstrated', tone: 'opportunity', Icon: CircleX },
  not_applicable: { label: 'Optional criterion', tone: 'optional', Icon: MinusCircle },
};

function statusMeta(status) {
  return STATUS_META[status] || STATUS_META.not_detected;
}

function FocusLabels({ visual }) {
  if (!visual) return null;
  const current = Array.isArray(visual.current_focus_labels)
    ? visual.current_focus_labels
    : [];
  const recommended = Array.isArray(visual.recommended_focus_labels)
    ? visual.recommended_focus_labels
    : [];
  if (!current.length && !recommended.length) return null;

  return (
    <div className="move-visual-key">
      {current.length > 0 && (
        <span className="move-visual-key__current">
          Current: {current.join(', ')}
        </span>
      )}
      {recommended.length > 0 && (
        <span className="move-visual-key__recommended">
          Suggested: {recommended.join(', ')}
        </span>
      )}
    </div>
  );
}

export function CriteriaAnalysisProgress() {
  return (
    <div className="move-feedback move-feedback--loading" role="status" aria-live="polite">
      <div className="move-feedback-summary">
        <div>
          <strong>Reviewing writing criteria</strong>
          <span>All seven criteria are being evaluated together</span>
        </div>
        <small>Analysis in progress</small>
      </div>

      <div className="move-feedback-list" aria-label="Writing criteria analysis" aria-busy="true">
        {WRITING_CRITERIA.map(([label, purpose], index) => (
          <article className="move-feedback-item" key={label}>
            <div className="move-feedback-row">
              <div className="move-feedback-trigger move-feedback-trigger--static">
                <span className="move-number">{index + 1}</span>
                <span className="move-trigger-copy">
                  <strong>{label}</strong>
                  <small>{purpose}</small>
                </span>
                <span
                  className="move-status move-status--pending"
                  role="img"
                  aria-label="Analysis pending"
                  title="Analysis pending"
                >
                  <LoaderCircle className="is-spinning" size={17} aria-hidden="true" />
                </span>
              </div>
              <span className="move-visual-placeholder" aria-hidden="true" />
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

export default function MoveFeedback({ chartData, activeMoveId, onSelectMove }) {
  const feedback = chartData?.move_feedback;
  const assessments = Array.isArray(feedback?.assessments)
    ? feedback.assessments
    : EMPTY_ASSESSMENTS;
  const [revealedCount, setRevealedCount] = useState(0);
  const revealComplete = revealedCount >= assessments.length;

  useEffect(() => {
    setRevealedCount(0);
    const timers = assessments.map((_, index) => setTimeout(
      () => setRevealedCount(index + 1),
      RESULT_REVEAL_INTERVAL_MS * (index + 1),
    ));
    return () => timers.forEach((timer) => clearTimeout(timer));
  }, [assessments]);

  if (!assessments.length) return null;

  const attentionCount = Number(feedback?.summary?.attention_count) || 0;

  return (
    <div className="move-feedback" aria-live="polite">
      <div className="move-feedback-summary">
        <div>
          <strong>{revealComplete ? 'Seven writing criteria reviewed' : 'Preparing criteria results'}</strong>
          <span>
            {!revealComplete
              ? `${revealedCount} of ${assessments.length} results ready`
              : attentionCount
              ? `${attentionCount} ${attentionCount === 1 ? 'criterion' : 'criteria'} to refine`
              : 'All criteria are currently clear'}
          </span>
        </div>
        <small>Criteria review · v{feedback.version || '1.0'}</small>
      </div>

      <div className="move-feedback-list" aria-label="Seven writing criteria">
        {assessments.map((assessment, assessmentIndex) => {
          const isRevealed = assessmentIndex < revealedCount;
          const meta = statusMeta(assessment.status);
          const StatusIcon = meta.Icon;
          const isActive = assessment.id === activeMoveId;
          const hasRange = Number.isInteger(assessment?.range?.start)
            && Number.isInteger(assessment?.range?.end)
            && assessment.range.end > assessment.range.start;
          const hasVisual = Boolean(assessment?.visual?.image_url);
          return (
            <article
              className={`move-feedback-item move-feedback-item--${meta.tone}${isActive ? ' is-active' : ''}`}
              key={assessment.id}
            >
              <div className="move-feedback-row">
                <button
                  className="move-feedback-trigger"
                  type="button"
                  onClick={() => onSelectMove(assessment)}
                  aria-expanded={isActive}
                  disabled={!isRevealed}
                  title={hasRange ? 'Review this criterion and locate the related text' : 'Review this criterion'}
                >
                  <span className="move-number">{assessment.number}</span>
                  <span className="move-trigger-copy">
                    <strong>{assessment.label}</strong>
                    <small>{assessment.purpose}</small>
                  </span>
                  {isRevealed ? (
                    <span
                      className={`move-status move-status--${meta.tone} move-status--revealed`}
                      role="img"
                      aria-label={meta.label}
                      title={meta.label}
                    >
                      <StatusIcon size={17} aria-hidden="true" />
                    </span>
                  ) : (
                    <span
                      className="move-status move-status--pending"
                      role="img"
                      aria-label="Result pending"
                      title="Result pending"
                    >
                      <LoaderCircle className="is-spinning" size={17} aria-hidden="true" />
                    </span>
                  )}
                </button>
                {hasVisual && isRevealed ? (
                  <button
                    className="move-visual-button"
                    type="button"
                    onClick={() => onSelectMove(assessment)}
                    aria-label={`View visual feedback for criterion ${assessment.number}`}
                    aria-expanded={isActive}
                    title="View visual feedback"
                  >
                    <Eye size={17} aria-hidden="true" />
                  </button>
                ) : (
                  <span className="move-visual-placeholder" aria-hidden="true" />
                )}
              </div>

              {isActive && (
                <div className="move-feedback-detail">
                  <p>{assessment.rationale}</p>
                  {assessment.status !== 'effective' && assessment.hint && (
                    <div className="move-hint">
                      <Lightbulb size={15} />
                      <span>{assessment.hint}</span>
                    </div>
                  )}
                  {assessment.excerpt && (
                    <blockquote>
                      <span>{hasRange ? 'Highlighted in your report' : 'Related text'}</span>
                      {assessment.excerpt}
                    </blockquote>
                  )}
                  {hasVisual && (
                    <div className="move-visual-note">
                      <Eye size={15} />
                      <span>The original image above now shows a complementary visual cue.</span>
                    </div>
                  )}
                  <FocusLabels visual={assessment.visual} />
                </div>
              )}
            </article>
          );
        })}
      </div>

      <p className="move-feedback-footnote">
        These criteria describe rhetorical choices. Feedback highlights revision opportunities rather than supplying replacement text.
      </p>
    </div>
  );
}
