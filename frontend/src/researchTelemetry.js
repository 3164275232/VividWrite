const SESSION_STORAGE_KEY = 'vividwrite_research_session_v1';
const FLUSH_INTERVAL_MS = 2500;
const HEARTBEAT_INTERVAL_MS = 30000;
const IDLE_THRESHOLD_MS = 60000;
const MAX_QUEUE_SIZE = 1000;
const MAX_STRING_LENGTH = 250000;
const SENSITIVE_KEY_PATTERN = /password|passwd|secret|token|api[_-]?key|authorization|cookie/i;

const telemetry = {
  enabled: false,
  username: '',
  sessionId: '',
  apiBase: '',
  consentVersion: '',
  getContext: () => ({}),
  queue: [],
  started: false,
  startPromise: null,
  flushTimer: null,
  heartbeatTimer: null,
  lastTickAt: 0,
  lastActivityAt: 0,
  activeMs: 0,
  idleMs: 0,
  listenersInstalled: false,
  scrollTimer: null,
};

function nowIso() {
  return new Date().toISOString();
}

function createId(prefix) {
  const id = globalThis.crypto?.randomUUID?.()
    || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  return `${prefix}-${id}`;
}

export function serializeResearchValue(value, key = '', depth = 0) {
  if (SENSITIVE_KEY_PATTERN.test(key)) return '[redacted]';
  if (depth > 12) return '[maximum depth reached]';
  if (value == null || ['boolean', 'number'].includes(typeof value)) return value;
  if (typeof value === 'string') {
    return value.length <= MAX_STRING_LENGTH
      ? value
      : `${value.slice(0, MAX_STRING_LENGTH)}...[truncated ${value.length - MAX_STRING_LENGTH} chars]`;
  }
  if (value instanceof File) {
    return {
      file_name: value.name,
      mime_type: value.type,
      byte_size: value.size,
      last_modified: value.lastModified,
    };
  }
  if (value instanceof FormData) {
    const result = {};
    for (const [entryKey, entryValue] of value.entries()) {
      const serialized = serializeResearchValue(entryValue, entryKey, depth + 1);
      if (Object.hasOwn(result, entryKey)) {
        result[entryKey] = Array.isArray(result[entryKey])
          ? [...result[entryKey], serialized]
          : [result[entryKey], serialized];
      } else {
        result[entryKey] = serialized;
      }
    }
    return result;
  }
  if (Array.isArray(value)) {
    return value.slice(0, 1000).map((item) => serializeResearchValue(item, '', depth + 1));
  }
  if (typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value)
        .slice(0, 1000)
        .map(([entryKey, entryValue]) => [
          entryKey.slice(0, 200),
          serializeResearchValue(entryValue, entryKey, depth + 1),
        ]),
    );
  }
  return String(value);
}

export function calculateTextDelta(previousText, nextText) {
  const previous = String(previousText ?? '');
  const next = String(nextText ?? '');
  let start = 0;
  const sharedLength = Math.min(previous.length, next.length);
  while (start < sharedLength && previous[start] === next[start]) start += 1;

  let previousEnd = previous.length;
  let nextEnd = next.length;
  while (
    previousEnd > start
    && nextEnd > start
    && previous[previousEnd - 1] === next[nextEnd - 1]
  ) {
    previousEnd -= 1;
    nextEnd -= 1;
  }
  return {
    change_start: start,
    deleted_text: previous.slice(start, previousEnd),
    inserted_text: next.slice(start, nextEnd),
    previous_character_count: previous.length,
    character_count: next.length,
  };
}

export function calculateLastActivityTimestamp(
  wallClockMs,
  currentMonotonicMs,
  lastActivityMonotonicMs,
) {
  const elapsedSinceActivity = Math.max(
    0,
    Number(currentMonotonicMs) - Number(lastActivityMonotonicMs),
  );
  return new Date(Number(wallClockMs) - elapsedSinceActivity).toISOString();
}

function lastActivityIso() {
  return calculateLastActivityTimestamp(
    Date.now(),
    performance.now(),
    telemetry.lastActivityAt,
  );
}

function wordCount(text) {
  const trimmed = String(text || '').trim();
  return trimmed ? trimmed.split(/\s+/).length : 0;
}

function researchUrl(path) {
  return `${telemetry.apiBase}${path}`;
}

function sessionStorageValue() {
  try {
    return JSON.parse(sessionStorage.getItem(SESSION_STORAGE_KEY) || 'null');
  } catch {
    return null;
  }
}

function saveSessionStorage() {
  try {
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({
      username: telemetry.username,
      session_id: telemetry.sessionId,
    }));
  } catch {
    // Telemetry still works when sessionStorage is unavailable.
  }
}

function clearSessionStorage() {
  try {
    sessionStorage.removeItem(SESSION_STORAGE_KEY);
  } catch {
    // Ignore storage restrictions.
  }
}

function clientMetadata() {
  return serializeResearchValue({
    page_url: location.href,
    page_path: location.pathname,
    referrer: document.referrer,
    user_agent: navigator.userAgent,
    language: navigator.language,
    languages: navigator.languages,
    platform: navigator.platform,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    viewport: { width: window.innerWidth, height: window.innerHeight },
    screen: {
      width: window.screen?.width,
      height: window.screen?.height,
      color_depth: window.screen?.colorDepth,
      pixel_ratio: window.devicePixelRatio,
    },
    consent_version: telemetry.consentVersion,
  });
}

async function ensureSessionStarted() {
  if (!telemetry.enabled || !telemetry.username || !telemetry.sessionId) return false;
  if (telemetry.started) return true;
  if (telemetry.startPromise) return telemetry.startPromise;
  telemetry.startPromise = fetch(researchUrl('/api/research/sessions/start'), {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-VividWrite-Session': telemetry.sessionId,
    },
    body: JSON.stringify({
      session_id: telemetry.sessionId,
      client_started_at: nowIso(),
      metadata: clientMetadata(),
    }),
  })
    .then(async (response) => {
      if (!response.ok) throw new Error(`Research session start failed (${response.status})`);
      const data = await response.json();
      if (data.session_id && data.session_id !== telemetry.sessionId) {
        telemetry.sessionId = data.session_id;
        saveSessionStorage();
      }
      telemetry.started = true;
      return true;
    })
    .catch((error) => {
      console.warn(error.message);
      return false;
    })
    .finally(() => {
      telemetry.startPromise = null;
    });
  return telemetry.startPromise;
}

function currentStage() {
  try {
    return String(telemetry.getContext?.()?.stage || '') || null;
  } catch {
    return null;
  }
}

export function trackResearchEvent(eventType, payload = {}, options = {}) {
  if (!telemetry.enabled || !telemetry.username) return;
  const context = (() => {
    try {
      return telemetry.getContext?.() || {};
    } catch {
      return {};
    }
  })();
  telemetry.queue.push({
    event_id: createId('event'),
    event_type: String(eventType || 'unknown').slice(0, 120),
    source: options.source || 'frontend',
    occurred_at: nowIso(),
    stage: options.stage || context.stage || null,
    payload: serializeResearchValue({
      ...payload,
      context: options.includeContext === false ? undefined : context,
    }),
  });
  if (telemetry.queue.length > MAX_QUEUE_SIZE) {
    telemetry.queue.splice(0, telemetry.queue.length - MAX_QUEUE_SIZE);
  }
  if (telemetry.queue.length >= 20) void flushResearchEvents();
}

export async function flushResearchEvents({ useBeacon = false } = {}) {
  if (!telemetry.enabled || !telemetry.queue.length) return false;
  const started = await ensureSessionStarted();
  if (!started) return false;
  const events = telemetry.queue.slice(0, 200);
  const body = JSON.stringify({ session_id: telemetry.sessionId, events });
  const removeSentEvents = () => {
    const sentIds = new Set(events.map((event) => event.event_id));
    telemetry.queue = telemetry.queue.filter((event) => !sentIds.has(event.event_id));
  };
  if (useBeacon && navigator.sendBeacon) {
    const sent = navigator.sendBeacon(
      researchUrl('/api/research/events'),
      new Blob([body], { type: 'application/json' }),
    );
    if (sent) removeSentEvents();
    return sent;
  }
  try {
    const response = await fetch(researchUrl('/api/research/events'), {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-VividWrite-Session': telemetry.sessionId,
      },
      body,
    });
    if (!response.ok) return false;
    removeSentEvents();
    return true;
  } catch {
    return false;
  }
}

function updateTimeCounters() {
  const current = performance.now();
  if (!telemetry.lastTickAt) telemetry.lastTickAt = current;
  const elapsed = Math.max(0, current - telemetry.lastTickAt);
  const idle = document.hidden || current - telemetry.lastActivityAt >= IDLE_THRESHOLD_MS;
  if (idle) telemetry.idleMs += elapsed;
  else telemetry.activeMs += elapsed;
  telemetry.lastTickAt = current;
}

function markActivity() {
  updateTimeCounters();
  telemetry.lastActivityAt = performance.now();
}

async function sendHeartbeat() {
  if (!telemetry.enabled) return;
  updateTimeCounters();
  await ensureSessionStarted();
  try {
    await fetch(researchUrl('/api/research/heartbeat'), {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-VividWrite-Session': telemetry.sessionId,
      },
      body: JSON.stringify({
        session_id: telemetry.sessionId,
        active_ms: Math.round(telemetry.activeMs),
        idle_ms: Math.round(telemetry.idleMs),
        visible: !document.hidden,
        stage: currentStage(),
        last_activity_at: lastActivityIso(),
      }),
    });
  } catch {
    // A later heartbeat will retry while the session remains open.
  }
  void flushResearchEvents();
}

function elementDescriptor(element) {
  if (!(element instanceof Element)) return {};
  const label = (
    element.getAttribute('aria-label')
    || element.getAttribute('title')
    || element.labels?.[0]?.textContent
    || element.textContent
    || element.getAttribute('name')
    || element.id
    || ''
  ).replace(/\s+/g, ' ').trim().slice(0, 240);
  return {
    tag: element.tagName.toLowerCase(),
    type: element.getAttribute('type'),
    role: element.getAttribute('role'),
    id: element.id || null,
    name: element.getAttribute('name'),
    label,
    class_name: String(element.className || '').slice(0, 300),
  };
}

function handleDocumentClick(event) {
  markActivity();
  const control = event.target?.closest?.('button, a, summary, [role="button"], label');
  if (!control) return;
  trackResearchEvent('ui_control_activated', {
    control: elementDescriptor(control),
    pointer: {
      x: Number.isFinite(event.clientX) ? event.clientX : null,
      y: Number.isFinite(event.clientY) ? event.clientY : null,
    },
  });
}

function handleDocumentChange(event) {
  markActivity();
  const control = event.target;
  if (!(control instanceof HTMLInputElement || control instanceof HTMLSelectElement)) return;
  let selection = null;
  if (control instanceof HTMLSelectElement) selection = control.value;
  if (control instanceof HTMLInputElement && ['checkbox', 'radio'].includes(control.type)) {
    selection = control.checked;
  }
  if (control instanceof HTMLInputElement && control.type === 'file') {
    selection = Array.from(control.files || []).map((file) => serializeResearchValue(file));
  }
  trackResearchEvent('ui_control_changed', {
    control: elementDescriptor(control),
    selection,
  });
}

function handleVisibilityChange() {
  updateTimeCounters();
  trackResearchEvent('page_visibility_changed', { visible: !document.hidden });
  if (document.hidden) void flushResearchEvents({ useBeacon: true });
}

function handleScroll(event) {
  markActivity();
  clearTimeout(telemetry.scrollTimer);
  telemetry.scrollTimer = setTimeout(() => {
    const target = event.target === document ? document.scrollingElement : event.target;
    trackResearchEvent('scroll_position', {
      target: elementDescriptor(target),
      scroll_top: Number(target?.scrollTop || window.scrollY || 0),
      scroll_left: Number(target?.scrollLeft || window.scrollX || 0),
    });
  }, 2000);
}

function installListeners() {
  if (telemetry.listenersInstalled) return;
  telemetry.listenersInstalled = true;
  document.addEventListener('click', handleDocumentClick, true);
  document.addEventListener('change', handleDocumentChange, true);
  document.addEventListener('keydown', markActivity, true);
  document.addEventListener('pointerdown', markActivity, true);
  document.addEventListener('scroll', handleScroll, true);
  document.addEventListener('visibilitychange', handleVisibilityChange);
  window.addEventListener('beforeunload', handleBeforeUnload);
}

function removeListeners() {
  if (!telemetry.listenersInstalled) return;
  telemetry.listenersInstalled = false;
  document.removeEventListener('click', handleDocumentClick, true);
  document.removeEventListener('change', handleDocumentChange, true);
  document.removeEventListener('keydown', markActivity, true);
  document.removeEventListener('pointerdown', markActivity, true);
  document.removeEventListener('scroll', handleScroll, true);
  document.removeEventListener('visibilitychange', handleVisibilityChange);
  window.removeEventListener('beforeunload', handleBeforeUnload);
}

function handleBeforeUnload() {
  updateTimeCounters();
  trackResearchEvent('page_unloaded', {
    active_ms: Math.round(telemetry.activeMs),
    idle_ms: Math.round(telemetry.idleMs),
  });
  void flushResearchEvents({ useBeacon: true });
  if (navigator.sendBeacon && telemetry.started) {
    navigator.sendBeacon(
      researchUrl('/api/research/sessions/end'),
      new Blob([JSON.stringify({
        session_id: telemetry.sessionId,
        active_ms: Math.round(telemetry.activeMs),
        idle_ms: Math.round(telemetry.idleMs),
        visible: !document.hidden,
        stage: currentStage(),
        last_activity_at: lastActivityIso(),
        reason: 'page_unload',
      })], { type: 'application/json' }),
    );
  }
}

export function configureResearchTelemetry({
  enabled,
  username,
  apiBase = '',
  consentVersion = '',
  getContext = () => ({}),
}) {
  if (!enabled || !username) return;
  if (telemetry.enabled && telemetry.username === username) {
    telemetry.getContext = getContext;
    telemetry.apiBase = apiBase;
    return;
  }
  const stored = sessionStorageValue();
  telemetry.enabled = true;
  telemetry.username = username;
  telemetry.apiBase = apiBase.replace(/\/$/, '');
  telemetry.consentVersion = consentVersion;
  telemetry.getContext = getContext;
  telemetry.sessionId = stored?.username === username && stored?.session_id
    ? stored.session_id
    : createId('session');
  telemetry.queue = [];
  telemetry.started = false;
  telemetry.activeMs = 0;
  telemetry.idleMs = 0;
  telemetry.lastTickAt = performance.now();
  telemetry.lastActivityAt = performance.now();
  saveSessionStorage();
  installListeners();
  clearInterval(telemetry.flushTimer);
  clearInterval(telemetry.heartbeatTimer);
  telemetry.flushTimer = setInterval(() => void flushResearchEvents(), FLUSH_INTERVAL_MS);
  telemetry.heartbeatTimer = setInterval(() => void sendHeartbeat(), HEARTBEAT_INTERVAL_MS);
  trackResearchEvent('page_loaded', clientMetadata(), { includeContext: false });
  void ensureSessionStarted().then(() => flushResearchEvents());
}

export async function endResearchSession(reason = 'logout') {
  if (!telemetry.enabled) return;
  updateTimeCounters();
  trackResearchEvent('session_closing', {
    reason,
    active_ms: Math.round(telemetry.activeMs),
    idle_ms: Math.round(telemetry.idleMs),
  });
  await flushResearchEvents();
  try {
    await fetch(researchUrl('/api/research/sessions/end'), {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-VividWrite-Session': telemetry.sessionId,
      },
      body: JSON.stringify({
        session_id: telemetry.sessionId,
        active_ms: Math.round(telemetry.activeMs),
        idle_ms: Math.round(telemetry.idleMs),
        visible: !document.hidden,
        stage: currentStage(),
        last_activity_at: lastActivityIso(),
        reason,
      }),
    });
  } catch {
    // Logout must continue even if the final telemetry request is interrupted.
  }
  clearInterval(telemetry.flushTimer);
  clearInterval(telemetry.heartbeatTimer);
  removeListeners();
  clearSessionStorage();
  telemetry.enabled = false;
  telemetry.started = false;
  telemetry.username = '';
  telemetry.sessionId = '';
  telemetry.queue = [];
}

export function abandonResearchSession() {
  clearInterval(telemetry.flushTimer);
  clearInterval(telemetry.heartbeatTimer);
  removeListeners();
  clearSessionStorage();
  telemetry.enabled = false;
  telemetry.started = false;
  telemetry.username = '';
  telemetry.sessionId = '';
  telemetry.queue = [];
}

export function getResearchRequestHeaders() {
  return telemetry.enabled && telemetry.sessionId
    ? { 'X-VividWrite-Session': telemetry.sessionId }
    : {};
}

export function captureApiCall({
  path,
  method,
  durationMs,
  status,
  requestPayload,
  responsePayload,
  attempt,
  error,
}) {
  if (path.startsWith('/api/auth/') || path.startsWith('/api/research/')) return;
  trackResearchEvent(error ? 'api_call_failed' : 'api_call_completed', {
    path,
    method,
    duration_ms: Math.round(durationMs * 1000) / 1000,
    status,
    attempt,
    request: serializeResearchValue(requestPayload),
    response: serializeResearchValue(responsePayload),
    error: error ? String(error) : null,
  });
}

export function trackEssayEdit(previousText, nextText, editSource = 'editor') {
  if (previousText === nextText) return;
  const delta = calculateTextDelta(previousText, nextText);
  trackResearchEvent('essay_edit', {
    edit_source: editSource,
    ...delta,
    word_count: wordCount(nextText),
  });
}

export function snapshotEssay(text, reason, metadata = {}) {
  trackResearchEvent('essay_snapshot', {
    reason,
    text: String(text || ''),
    word_count: wordCount(text),
    character_count: String(text || '').length,
    ...metadata,
  });
}

export async function archiveResearchArtifact(file, category, metadata = {}) {
  if (!telemetry.enabled || !(file instanceof File)) return null;
  const started = await ensureSessionStarted();
  if (!started) return null;
  const body = new FormData();
  body.append('image', file);
  body.append('category', category);
  body.append('metadata_json', JSON.stringify(serializeResearchValue(metadata)));
  try {
    const response = await fetch(researchUrl('/api/research/artifacts'), {
      method: 'POST',
      credentials: 'include',
      headers: getResearchRequestHeaders(),
      body,
    });
    if (!response.ok) return null;
    const result = await response.json();
    trackResearchEvent('artifact_archived', {
      category,
      file: serializeResearchValue(file),
      artifact: result.artifact,
    });
    return result.artifact;
  } catch {
    return null;
  }
}
