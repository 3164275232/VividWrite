const FALLBACK_DEFINITIONS = [
  ['value_inaccuracy', 'Value inaccuracy'],
  ['entity_misalignment', 'Entity or series misalignment'],
  ['trend_direction_error', 'Trend direction error'],
  ['comparison_ranking_error', 'Comparison or ranking error'],
  ['key_feature_omission', 'Key feature omission'],
];

function formatNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  return Number.isInteger(number) ? String(number) : number.toFixed(2).replace(/0+$/, '').replace(/\.$/, '');
}

function humanize(value) {
  return String(value || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatScalar(value, suffix) {
  if (value === null || value === undefined || value === '') return 'Not stated';
  const number = formatNumber(value);
  if (number !== null) return `${number}${suffix}`;
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return humanize(value);
}

function formatFact(fact, suffix) {
  if (!fact || typeof fact !== 'object') return formatScalar(fact, suffix);
  const unitlessKeys = new Set([
    'context', 'direction', 'entity', 'entity_present', 'left', 'rank', 'right', 'traceable_values',
  ]);
  return Object.entries(fact)
    .map(([key, value]) => {
      if (Array.isArray(value)) {
        const rendered = value.length ? value.map((item) => formatScalar(item, suffix)).join(' / ') : 'None';
        return `${humanize(key)}: ${rendered}`;
      }
      return `${humanize(key)}: ${formatScalar(value, unitlessKeys.has(key) ? '' : suffix)}`;
    })
    .join(' / ');
}

function verificationLabel(method) {
  const labels = {
    aligned_numeric_comparison: 'Aligned value check',
    reciprocal_value_swap: 'Reciprocal swap check',
    official_framework_membership: 'Official framework check',
    official_endpoint_direction: 'Endpoint direction check',
    official_context_ranking: 'Context ranking check',
    official_pairwise_comparison: 'Pairwise comparison check',
    complete_entity_coverage_check: 'Entity coverage check',
    temporal_endpoint_coverage_check: 'Endpoint coverage check',
  };
  return labels[method] || humanize(method || 'Local verification');
}

export default function TaxonomyFeedback({ chartData }) {
  const taxonomy = chartData?.error_taxonomy;
  if (!taxonomy || !Array.isArray(taxonomy.issues)) return null;

  const definitions = Array.isArray(taxonomy.definitions) && taxonomy.definitions.length
    ? taxonomy.definitions
    : FALLBACK_DEFINITIONS.map(([code, label]) => ({ code, label }));
  const issues = taxonomy.issues;
  const counts = taxonomy.summary?.counts || {};
  const totalValue = Number(taxonomy.summary?.total_issues);
  const verifiedValue = Number(taxonomy.summary?.verified_issues);
  const total = Number.isFinite(totalValue) ? totalValue : issues.length;
  const verified = Number.isFinite(verifiedValue) ? verifiedValue : issues.length;
  const unitText = String(chartData?.axes?.unit || '').trim();
  const isPercentage = chartData?.chart_type === 'pie'
    || /%|percent/i.test(`${unitText} ${chartData?.axes?.y_label || ''}`);
  const suffix = isPercentage ? '%' : unitText ? ` ${unitText}` : '';

  return (
    <div className="taxonomy-feedback" role="status" aria-live="polite">
      <div className="taxonomy-summary">
        <div>
          <strong>{total}</strong>
          <span>{total === 1 ? 'verified issue' : 'verified issues'}</span>
        </div>
        <small>Five content-fidelity checks / taxonomy v{taxonomy.version || '1.0'}</small>
      </div>

      <div className="taxonomy-check-list" aria-label="Five error checks">
        {definitions.map((definition) => {
          const count = Number(definition.issue_count ?? counts[definition.code]) || 0;
          return (
            <div className={count ? 'has-issues' : ''} key={definition.code}>
              <span>{definition.label}</span>
              <strong>{count}</strong>
            </div>
          );
        })}
      </div>

      {total === 0 ? (
        <div className="taxonomy-clear-result">
          No locally verifiable content-fidelity issues were found.
        </div>
      ) : (
        <div className="taxonomy-groups">
          {definitions.map((definition) => {
            const typeIssues = issues.filter((issue) => issue.error_type === definition.code);
            if (!typeIssues.length) return null;
            return (
              <section className="taxonomy-group" key={definition.code}>
                <header>
                  <strong>{definition.label}</strong>
                  <span>{typeIssues.length}</span>
                </header>
                {typeIssues.map((issue) => (
                  <article className="taxonomy-issue" key={issue.id}>
                    <div className="taxonomy-issue-heading">
                      <strong>{issue.item}</strong>
                      <span>{issue.verification?.status === 'verified' ? 'Verified' : 'Review'}</span>
                    </div>
                    <p>{issue.message}</p>
                    <div className="taxonomy-fact-grid">
                      <div>
                        <span>Your report</span>
                        <strong>{formatFact(issue.student_claim, suffix)}</strong>
                      </div>
                      <div>
                        <span>Official chart</span>
                        <strong>{formatFact(issue.official_fact, suffix)}</strong>
                      </div>
                    </div>
                    <details className="taxonomy-evidence">
                      <summary>Verification evidence</summary>
                      <div>
                        <span>{verificationLabel(issue.verification?.method)}</span>
                        {Array.isArray(issue.evidence?.source_sentences)
                          && issue.evidence.source_sentences.map((sentence, index) => (
                            <blockquote key={`${issue.id}-sentence-${index}`}>{sentence}</blockquote>
                          ))}
                        {!issue.evidence?.source_sentences?.length && (
                          <p>No traceable sentence or value was found for this official feature.</p>
                        )}
                      </div>
                    </details>
                  </article>
                ))}
              </section>
            );
          })}
        </div>
      )}

      {verified !== total && (
        <small className="taxonomy-review-note">{total - verified} issue(s) require human review.</small>
      )}
    </div>
  );
}
