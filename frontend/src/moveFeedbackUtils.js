export function withResolvedMoveVisualUrls(chartData, resolveUrl) {
  const feedback = chartData?.move_feedback;
  if (!feedback || !Array.isArray(feedback.assessments)) return chartData;
  return {
    ...chartData,
    move_feedback: {
      ...feedback,
      assessments: feedback.assessments.map((assessment) => {
        const visual = assessment?.visual;
        if (!visual?.image_url) return assessment;
        return {
          ...assessment,
          visual: {
            ...visual,
            image_url: resolveUrl(visual.image_url),
          },
        };
      }),
    },
  };
}

export function findMoveAssessment(chartData, moveId) {
  if (!moveId || !Array.isArray(chartData?.move_feedback?.assessments)) return null;
  return chartData.move_feedback.assessments.find((item) => item.id === moveId) || null;
}

export function locateMoveRange(assessment, text) {
  if (!assessment || typeof text !== 'string') return null;
  const range = assessment.range;
  const excerpt = String(assessment.excerpt || '');
  if (
    Number.isInteger(range?.start)
    && Number.isInteger(range?.end)
    && range.start >= 0
    && range.end > range.start
    && range.end <= text.length
    && (!excerpt || text.slice(range.start, range.end) === excerpt)
  ) {
    return { start: range.start, end: range.end };
  }
  if (!excerpt) return null;
  const index = text.indexOf(excerpt);
  return index >= 0 ? { start: index, end: index + excerpt.length } : null;
}
