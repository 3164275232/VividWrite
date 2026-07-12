export const SPATIAL_TASK_TYPES = new Set(['map', 'process']);

export function taskTypeLabel(type) {
  if (type === 'map') return 'map task';
  if (type === 'process') return 'process diagram';
  if (type === 'auto') return 'statistical chart';
  return `${type} chart`;
}

export function analysisRequirement(type) {
  return `This is an IELTS Academic Task 1 ${taskTypeLabel(type)}. Summarise the main features and make relevant comparisons.`;
}

export function sampleEssayRequirement(type) {
  return `Write an IELTS Academic Task 1 report for this ${taskTypeLabel(type)}.`;
}
