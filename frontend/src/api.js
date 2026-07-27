const configuredApiBase = import.meta.env?.VITE_API_BASE;
export const API_BASE = (
  configuredApiBase === undefined ? 'http://127.0.0.1:8000' : configuredApiBase
).replace(/\/$/, '');

const TRANSIENT_GATEWAY_STATUSES = new Set([502, 503, 504]);
const TRANSIENT_RETRY_DELAY_MS = 800;

function backendUnavailableMessage(action) {
  const target = API_BASE || 'the current server';
  return `${action}: cannot reach backend at ${target}. Make sure the FastAPI backend is running and VITE_API_BASE points to it.`;
}

function transientFailureMessage(action, status) {
  const suffix = status ? ` (HTTP ${status})` : '';
  return `${action}: the connection was interrupted after one automatic retry${suffix}. Please try again.`;
}

function wait(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function requestJson(path, options, action, { retryTransient = false } = {}) {
  const maxAttempts = retryTransient ? 2 : 1;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    let response;
    try {
      response = await fetch(`${API_BASE}${path}`, {
        ...options,
        credentials: 'include',
      });
    } catch (error) {
      const canRetry = retryTransient && attempt < maxAttempts && error?.name !== 'AbortError';
      if (canRetry) {
        await wait(TRANSIENT_RETRY_DELAY_MS);
        continue;
      }
      if (retryTransient && error?.name !== 'AbortError') {
        throw new Error(transientFailureMessage(action));
      }
      throw new Error(backendUnavailableMessage(action));
    }

    let data = {};
    try {
      data = await response.json();
    } catch {
      // Preserve the HTTP status when the backend returns a non-JSON response.
    }
    if (response.ok) {
      return data;
    }

    const transientGatewayFailure = TRANSIENT_GATEWAY_STATUSES.has(response.status);
    if (retryTransient && transientGatewayFailure && attempt < maxAttempts) {
      await wait(TRANSIENT_RETRY_DELAY_MS);
      continue;
    }
    if (response.status === 401 && !path.startsWith('/api/auth/')) {
      window.dispatchEvent(new Event('vividwrite:unauthorized'));
    }
    if (retryTransient && transientGatewayFailure) {
      throw new Error(transientFailureMessage(action, response.status));
    }
    throw new Error(data.detail || data.error || data.message || `HTTP ${response.status}`);
  }

  throw new Error(transientFailureMessage(action));
}

function postJson(path, payload, action, requestPolicy) {
  return requestJson(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }, action, requestPolicy);
}

export function resolveBackendUrl(url) {
  if (!url || /^https?:\/\//i.test(url)) return url || null;
  return `${API_BASE}${url.startsWith('/') ? '' : '/'}${url}`;
}

export function getAuthConfig() {
  return requestJson('/api/auth/config', {}, 'Loading login settings failed');
}

export function getCurrentUser() {
  return requestJson('/api/auth/me', {}, 'Checking your login failed');
}

export function login(username, password) {
  return postJson('/api/auth/login', { username, password }, 'Login failed');
}

export function logout() {
  return postJson('/api/auth/logout', {}, 'Logout failed');
}

export function analyzeChartWithImage(formData) {
  return requestJson('/api/analyze-chart-with-image', {
    method: 'POST',
    body: formData,
  }, 'Chart analysis failed');
}

export function prepareTaskImage(formData) {
  return requestJson('/api/prepare-task-image', {
    method: 'POST',
    body: formData,
  }, 'Task type detection failed', { retryTransient: true });
}

export function requestNextSentence(payload) {
  return postJson('/api/next-sentence', payload, 'Next sentence generation failed');
}

export function mapSentences(payload) {
  return postJson('/api/map-sentences', payload, 'Sentence mapping failed');
}

export function analyzeStructure(payload) {
  return postJson('/api/analyze-structure', payload, 'Structure analysis failed');
}

export function extractDeplot(formData) {
  return requestJson('/api/deplot-extract', {
    method: 'POST',
    body: formData,
  }, 'DePlot extraction failed', { retryTransient: true });
}

export function saveFinalImage(username, file) {
  const formData = new FormData();
  formData.append('username', username);
  formData.append('image', file);
  return requestJson('/api/save-final-image', {
    method: 'POST',
    body: formData,
  }, 'Saving the final image failed');
}

export function saveRevisionText(username, text) {
  return postJson('/api/save-revision-text', { username, text }, 'Saving revision text failed');
}

export function generateSampleEssay(payload) {
  return postJson(
    '/api/generate-sample-essay',
    payload,
    'Sample essay generation failed',
    { retryTransient: true },
  );
}

export function generateSpatialSampleEssay(payload) {
  const formData = new FormData();
  formData.append('image', payload.image);
  formData.append('chart_type', payload.chart_type);
  formData.append('requirement', payload.requirement || '');
  formData.append('flowchart', JSON.stringify(payload.flowchart || {}));
  formData.append('min_words', String(payload.min_words || 150));
  if (payload.use_standard_structure !== undefined && payload.use_standard_structure !== null) {
    formData.append('use_standard_structure', String(payload.use_standard_structure));
  }
  return requestJson('/api/generate-spatial-sample-essay', {
    method: 'POST',
    body: formData,
  }, 'Spatial sample essay generation failed', { retryTransient: true });
}

export function reviewRevision(payload) {
  return postJson('/api/revision-review', payload, 'Revision review failed');
}
