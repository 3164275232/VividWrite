/* Browser integration checks with synthetic API responses, not a model accuracy test. */
const { chromium } = require(process.argv[2] || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'backend/user_data/revision_feature_checks');
const fixtures = JSON.parse(fs.readFileSync(path.join(output, 'fixtures.json'), 'utf8'));
const firstEssay = 'The figure shows some numbers.\n\nOverall, rail and metro use rose, while bus use fell. Rail rose steadily from 1.1 million in 2010 to 2.2 million in 2020. Metro use grew steadily from 0.8 million to 1.9 million. Bus use declined from 1.8 million to 1.3 million.';
const secondEssay = firstEssay.replace('The figure shows some numbers.',
  'The line graph compares daily bus, rail and metro passengers from 2010 to 2020, in millions.');
const thirdEssay = secondEssay.replace('Rail rose steadily', 'Rail increased steadily');

function responseFor(sequence, essay) {
  const assessments = fixtures.definitions.map((definition) => ({
    ...definition, id: definition.code,
    status: (definition.number === 1 && sequence === 1) || (definition.number === 4 && sequence >= 4) ? 'developing' : 'effective',
    excerpt: definition.number === 1 ? essay.split(/\r?\n/)[0] : 'Overall, rail and metro use rose, while bus use fell.',
    rationale: definition.number === 1 && sequence === 1 ? 'The opening does not identify the subject or time span.' : 'The passage identifies its subject and supports the comparison.',
    hint: 'Identify the transport modes, years and measurement unit.',
  }));
  const records = structuredClone(fixtures.records);
  const busSentence = essay.match(/Bus use declined from [^.]+(?:\.\d+[^.]*)*\./)?.[0]
    || essay.slice(essay.indexOf('Bus use declined'));
  const busValue = Number(essay.match(/Bus use declined from ([\d.]+) million/)?.[1]);
  records[0] = { ...records[0], value: busValue, official_value: 1.8, student_evidence: busSentence,
    feedback_status: busValue === 1.8 ? 'correct' : 'incorrect' };
  const chartUrl = busValue === 1.8 ? '/charts/line_estimates.png' : '/charts/line_wrong_value.png';
  const revision = { id: `review-${sequence}`, task_id: 'line-test', reference_id: 'ref-test', feedback_version: '1.0', sequence,
    created_at: `2026-09-04T10:0${sequence}:00Z`, essay, assessments, chart_type: 'line', records,
    value_tolerance: 0.1, unit: 'millions', analysis_model: 'ui-fixture',
    original_url: '/practice-samples/02_line_daily_passengers.png', chart_url: chartUrl };
  return { success: true, chart_url: revision.chart_url, analysis_revision: revision,
    chart_data: { chart_type: 'line', title: fixtures.title, records, axes: { unit: 'millions' }, vega_lite_spec: fixtures.spec,
      move_feedback: { version: '1.0', assessments, summary: { attention_count: sequence === 1 ? 1 : 0 } } } };
}

(async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'chrome' });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1080 } });
    const failures = [];
    const saved = [];
    let failNextAnalysis = false;
    let failHistorySave = false;
    page.on('pageerror', (error) => failures.push(error.message));
    await page.route('**/practice-samples/**', (route) => route.fulfill({
      path: path.join(root, 'frontend/public/practice-samples', path.basename(new URL(route.request().url()).pathname)),
      contentType: 'image/png',
    }));
    await page.route('**/charts/line_estimates.png', (route) => route.fulfill({ path: path.join(output, 'line_estimates.png'), contentType: 'image/png' }));
    await page.route('**/charts/line_wrong_value.png', (route) => route.fulfill({ path: path.join(output, 'line_wrong_value.png'), contentType: 'image/png' }));
    await page.route('**/api/**', async (route) => {
      const url = new URL(route.request().url());
      let payload = { success: true };
      if (url.pathname === '/api/auth/config') payload = { password_required: false, research_enabled: false };
      if (url.pathname === '/api/auth/me') payload = { authenticated: true, username: 'ui-fixture' };
      if (url.pathname === '/api/analyze-chart-with-image') {
        const sequence = saved.length + 1;
        const form = await new Request(route.request().url(), { method: 'POST',
          headers: route.request().headers(), body: route.request().postDataBuffer() }).formData();
        payload = responseFor(sequence, form.get('student_answer'));
        if (failNextAnalysis) {
          payload = { success: false, error: 'Synthetic analysis failure' };
          failNextAnalysis = false;
        } else if (failHistorySave) {
          payload.analysis_revision = null;
          payload.history_warning = 'This review could not be saved to your revision history.';
        } else saved.unshift(payload.analysis_revision);
      }
      if (url.pathname.startsWith('/api/revision-history/')) payload = {
        revisions: saved.filter((item) => item.sequence < Number(url.searchParams.get('before'))), next_before: null,
      };
      if (url.pathname === '/api/revision-review') payload = { success: true, overall: null, suggestions: [] };
      await route.fulfill({ json: payload });
    });
    await page.goto('http://127.0.0.1:5173/');
    await page.getByLabel('Practice sample').selectOption('line-passengers');
    const editor = page.locator('.cm-content[contenteditable="true"]');
    await editor.fill(firstEssay);
    await page.getByRole('button', { name: 'Next Stage', exact: true }).click();
    await page.getByRole('button', { name: 'Confirm', exact: true }).click();
    await page.getByRole('button', { name: 'Analyze report', exact: true }).click();
    await page.getByText('Your first saved review for this task.', { exact: false }).waitFor();
    await page.getByText('8 system-estimated values in the generated chart').click();
    await page.getByText('Interpolated between 2010 (1.1) and 2020 (2.2)', { exact: false }).first().waitFor();
    await page.getByRole('button', { name: 'Locate trend description', exact: true }).first().click();
    await page.locator('.cm-hl-yellow').first().waitFor();
    await editor.fill(secondEssay);
    await page.getByText('Draft changed since Review 1.', { exact: false }).waitFor();
    await page.getByRole('button', { name: 'Compare again', exact: true }).click();
    await page.locator('details.revision-change--addressed').waitFor();
    await page.locator('.revision-change--addressed summary').click();
    await page.getByRole('button', { name: 'Locate current passage', exact: true }).click();
    await page.locator('.cm-hl-yellow').first().waitFor();
    await page.getByText('Seven writing criteria reviewed', { exact: true }).waitFor();
    assert.equal(await page.locator('.revision-change--addressed').count(), 2); // one count and one detail
    await page.locator('.revision-workspace').evaluate((node) => { node.scrollTop = 0; });
    await page.screenshot({ path: path.join(output, 'revision-desktop.png'), fullPage: true });
    await editor.fill(thirdEssay);
    await page.getByRole('button', { name: 'Compare again', exact: true }).click();
    await page.getByText('No flagged criteria in either review.', { exact: false }).waitFor();
    const draftBeforeSelection = await editor.innerText();
    await page.getByLabel('Compare with earlier review').selectOption('review-1');
    await page.locator('details.revision-change--addressed').waitFor();
    assert.equal(await editor.innerText(), draftBeforeSelection);
    await page.locator('.revision-history-archive summary').click();
    await page.locator('.revision-history-essay').getByText('The figure shows some numbers.', { exact: false }).waitFor();
    // Request a historical asset from the dev server, not the API origin used in production.
    await page.route('**/practice-samples/02_line_daily_passengers.png', (route) => route.fulfill({
      path: path.join(root, 'frontend/public/practice-samples/02_line_daily_passengers.png'), contentType: 'image/png',
    }));
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('.revision-workspace').evaluate((node) => { node.scrollTop = 0; });
    await page.screenshot({ path: path.join(output, 'revision-mobile.png'), fullPage: true });
    await page.locator('.revision-progress').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, 'revision-mobile-progress.png'), fullPage: true });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    assert.equal(overflow, false, 'No viewport-level horizontal overflow');
    assert.equal(await page.locator('.revision-progress').evaluate((node) => node.scrollWidth > node.clientWidth + 1), false);
    const brokenImages = await page.locator('.revision-history-images img').evaluateAll((images) => images.filter((image) => !image.complete || image.naturalWidth === 0).length);
    assert.equal(brokenImages, 0, 'All historical images render');
    await page.setViewportSize({ width: 1440, height: 1080 });
    await editor.fill(thirdEssay.replace('Bus use declined from 1.8', 'Bus use declined from 1.4'));
    await page.getByRole('button', { name: 'Compare again', exact: true }).click();
    await page.locator('.revision-value-changes details.revision-change--new').waitFor();
    await editor.fill(thirdEssay);
    await page.getByRole('button', { name: 'Compare again', exact: true }).click();
    const correctedValue = page.locator('.revision-value-changes details.revision-change--addressed');
    await correctedValue.waitFor();
    await correctedValue.locator('summary').click();
    await correctedValue.getByText('Reported value: 1.4', { exact: true }).waitFor();
    await correctedValue.getByText('Reported value: 1.8', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Locate revised value', exact: true }).click();
    assert.match(await page.locator('.cm-hl-yellow').first().innerText(), /Bus use declined from 1\.8/);
    assert.equal(await page.locator('details.revision-change--continuing').count(), 1,
      'The remaining criterion concern does not hide a corrected value');
    await page.locator('.revision-progress').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, 'revision-value-progress.png'), fullPage: true });
    failNextAnalysis = true;
    await page.getByRole('button', { name: 'Compare again', exact: true }).click();
    await page.getByText('Synthetic analysis failure', { exact: true }).waitFor();
    assert.equal(saved.length, 5, 'Failure does not create a review');
    assert.equal(await page.getByAltText('Visual interpretation generated from the report').count(), 1,
      'The last successful image survives a failed reanalysis');
    failHistorySave = true;
    await page.getByRole('button', { name: 'Compare again', exact: true }).click();
    await page.getByText('This review could not be saved to your revision history.', { exact: true }).waitFor();
    await editor.fill(`${thirdEssay} A new sentence.`);
    await page.getByText('Draft changed since this analysis.', { exact: false }).waitFor();
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1), false);
    assert.deepEqual(failures, []);
    console.log(JSON.stringify({ result: 'PASS', checks: ['first review', 'stale draft', 'addressed evidence', 'sentence highlight', 'earlier baseline', 'draft preservation', 'estimated details and source quote', 'specific value correction with continuing criterion', 'failed reanalysis', 'stale notice without saved history', 'desktop/mobile layout'], output }, null, 2));
  } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
