export const SPATIAL_TASK_TYPES = new Set(['map', 'process']);
export const STATISTICAL_TASK_TYPES = new Set(['bar', 'line', 'area', 'pie']);
export const KNOWN_TASK_TYPES = new Set([
  ...SPATIAL_TASK_TYPES,
  ...STATISTICAL_TASK_TYPES,
]);

export function taskTypeLabel(type) {
  if (type === 'map') return 'map task';
  if (type === 'process') return 'process diagram';
  if (type === 'auto') return 'IELTS Task 1 visual';
  if (type === 'unknown') return 'IELTS Task 1 visual';
  return `${type} chart`;
}

export function analysisRequirement(type) {
  return `This is an IELTS Academic Task 1 ${taskTypeLabel(type)}. Summarise the main features and make relevant comparisons.`;
}

export function sampleEssayRequirement(type) {
  return `Write an IELTS Academic Task 1 report for this ${taskTypeLabel(type)}.`;
}
