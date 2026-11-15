const { _electron: electron, expect } = require('@playwright/test');
const path = require('node:path');
const fs = require('node:fs');
const { execFileSync } = require('node:child_process');

(async () => {
  const root = path.resolve(__dirname, '..');
  fs.mkdirSync(path.join(root, 'tmp'), { recursive: true });
  const temp = fs.mkdtempSync(path.join(root, 'tmp', 'desktop-smoke-'));
  const sample = path.join(temp, 'sample.pdf');
  execFileSync(path.join(root, 'backend', '.venv', 'Scripts', 'python.exe'), ['-c',
    'import pymupdf,sys; d=pymupdf.open(); d.set_metadata({"title":"Leaf classification: evidence study","author":"LitLens test fixture"}); p=d.new_page(); p.insert_text((50,60),"Abstract\\nThis study evaluates leaf classification.\\nMethods\\nWe used logistic regression on 120 leaf photographs.\\nResults\\nAccuracy was 81 percent.\\nLimitations\\nOnly one crop variety was evaluated.\\nFuture Work\\nEvaluate field photographs from additional crop varieties."); d.save(sys.argv[1]); d.close()', sample]);
  const executablePath = process.env.LITLENS_PACKAGED_EXE || undefined;
  const instance = await electron.launch({ ...(executablePath ? { executablePath } : { args: [root] }),
    env: { ...process.env, LITLENS_DATA_DIR: path.join(temp, 'data'), LITLENS_SMOKE_TEST: '1' }, timeout: 90000 });
  try {
    const page = await instance.firstWindow({ timeout: 90000 });
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.getByRole('button', { name: 'New to LitLens? Create an account' }).click();
    await page.getByLabel('Your name').fill('Researcher');
    await page.getByLabel('Username', { exact: true }).fill('smoke-user');
    await page.getByLabel('Password', { exact: true }).fill('test-password-123');
    await page.getByRole('button', { name: 'Create account' }).click();
    await expect(page.getByRole('heading', { name: 'My library' })).toBeVisible();
    await page.getByRole('button', { name: /Models & preferences/ }).click();
    await page.getByRole('button', { name: /Evidence only/ }).click();
    await page.getByLabel('Combine local embeddings').uncheck();
    await page.getByRole('button', { name: 'Save preferences' }).click();
    await expect(page.getByText('Preferences saved for your account.')).toBeVisible();
    await page.getByRole('button', { name: 'My library' }).click();
    await page.locator('input[type=file]').setInputFiles(sample);
    await expect(page.getByRole('heading', { name: 'Executive summary' })).toBeVisible({ timeout: 30000 });
    await page.screenshot({ path: path.join(root, 'tmp', 'desktop-report.png') });
    await page.locator('.report-section .refs button').first().click();
    await expect(page.getByRole('dialog', { name: 'Source evidence' })).toBeVisible();
    await page.getByRole('button', { name: 'Close evidence' }).click();
    await page.getByRole('tab', { name: 'Ask this paper' }).click();
    await page.getByRole('textbox', { name: 'Question about this paper' }).fill('What classification method was used?');
    await page.getByRole('button', { name: 'Ask →', exact: true }).click();
    await expect(page.locator('.chat-message.assistant')).toBeVisible({ timeout: 30000 });
    await expect(page.locator('.chat-message.assistant')).toContainText('logistic regression');
    await page.screenshot({ path: path.join(root, 'tmp', 'desktop-chat.png') });
    await page.getByRole('button', { name: 'Sign out' }).click();
    await page.getByLabel('Username', { exact: true }).fill('smoke-user');
    await page.getByLabel('Password', { exact: true }).fill('test-password-123');
    await page.getByRole('button', { name: 'Enter LitLens' }).click();
    await page.locator('.paper-open').first().click();
    await page.getByRole('tab', { name: 'Ask this paper' }).click();
    await expect(page.locator('.chat-message.assistant')).toContainText('logistic regression');
    await page.getByRole('button', { name: 'Remove paper', exact: true }).click();
    await page.getByRole('dialog', { name: 'Remove paper' }).getByRole('button', { name: 'Remove paper' }).click();
    await expect(page.locator('.paper-card')).toHaveCount(0);
    if (errors.length) throw new Error(errors.join('\n'));
    console.log('PASS: Desktop account, preferences, upload, automatic analysis, source evidence, chat, persistence, and deletion.');
    console.log('Screenshots: tmp/desktop-report.png and tmp/desktop-chat.png');
  } finally { await instance.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
