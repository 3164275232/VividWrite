const BASE = import.meta.env.VITE_API_BASE;

export async function hello() {
  const res = await fetch(`${BASE}/api/hello`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function analyzeChart(chartData) {
  const res = await fetch(`${BASE}/api/analyze-chart`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(chartData),
  });
  
  if (!res.ok) {
    const errorData = await res.json();
    throw new Error(errorData.error || `HTTP ${res.status}`);
  }
  
  return res.json();
}

export async function analyzeChartWithImage(formData) {
  const res = await fetch(`${BASE}/api/analyze-chart-with-image`, {
    method: 'POST',
    body: formData, // 不设置Content-Type，让浏览器自动设置multipart/form-data
  });
  
  if (!res.ok) {
    const errorData = await res.json();
    throw new Error(errorData.error || `HTTP ${res.status}`);
  }
  
  return res.json();
}

export async function requestNextSentence(payload) {
  const res = await fetch(`${BASE}/api/next-sentence`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    let errText = `HTTP ${res.status}`;
    try { const data = await res.json(); errText = data.error || errText; } catch {}
    throw new Error(errText);
  }
  return res.json();
}

export async function mapSentences(payload) {
  const res = await fetch(`${BASE}/api/map-sentences`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    let errText = `HTTP ${res.status}`;
    try { const data = await res.json(); errText = data.error || errText; } catch {}
    throw new Error(errText);
  }
  return res.json();
}

// DePlot extraction (image -> structured text string)
export async function extractDeplot(formData) {
  // formData should contain { image: File }
  const res = await fetch(`${BASE}/api/deplot-extract`, {
    method: 'POST',
    body: formData
  });
  if (!res.ok) {
    let errText = `HTTP ${res.status}`;
    try { const data = await res.json(); errText = data.detail || data.error || errText; } catch {}
    throw new Error(errText);
  }
  return res.json();
}

export async function saveFinalImage(username, file) {
  const fd = new FormData();
  fd.append('username', username);
  fd.append('image', file);
  const res = await fetch(`${BASE}/api/save-final-image`, { method: 'POST', body: fd });
  if (!res.ok) {
    let t = `HTTP ${res.status}`; try { const d = await res.json(); t = d.detail || d.error || t; } catch {}
    throw new Error(t);
  }
  return res.json();
}

export async function saveRevisionText(username, text) {
  const res = await fetch(`${BASE}/api/save-revision-text`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, text })
  });
  if (!res.ok) {
    let t = `HTTP ${res.status}`; try { const d = await res.json(); t = d.detail || d.error || t; } catch {}
    throw new Error(t);
  }
  return res.json();
}

export async function generateSampleEssay(payload) {
  // payload: { deplot_text, flowchart, requirement? }
  const res = await fetch(`${BASE}/api/generate-sample-essay`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    let t = `HTTP ${res.status}`; try { const d = await res.json(); t = d.detail || d.error || t; } catch {}
    throw new Error(t);
  }
  return res.json();
}

// Revision stage comprehensive review (vocabulary / grammar / coherence / overall)
export async function reviewRevision(payload) {
  // payload: { text, flowchart, deplot_text }
  const res = await fetch(`${BASE}/api/revision-review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    let t = `HTTP ${res.status}`; try { const d = await res.json(); t = d.detail || d.error || t; } catch {}
    throw new Error(t);
  }
  return res.json();
}
