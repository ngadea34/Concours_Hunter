// Test e2e Chromium (Playwright). Ignore si Playwright est absent.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, join } from 'node:path';

const require = createRequire(import.meta.url);
const here = dirname(fileURLToPath(import.meta.url));
let chromium = null;
try { ({ chromium } = require('playwright')); } catch (e) { /* absent */ }

test('e2e : remplissage de form.html sans soumission', { skip: !chromium && 'playwright indisponible' }, async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    let navigations = 0, posts = 0;
    page.on('framenavigated', () => navigations++);
    await page.route('**/*', (r) => { if (r.request().method() === 'POST') posts++; return r.request().url().startsWith('file:') ? r.continue() : r.abort(); });
    await page.goto(pathToFileURL(join(here, 'form.html')).href);
    const navBefore = navigations;
    await page.addScriptTag({ path: join(here, '..', 'lib', 'fill-core.js') });
    await page.addScriptTag({ path: join(here, '..', 'content', 'filler.js') });
    const prefill = {
      fields: { first_name: 'Ada', last_name: 'Lovelace', email: 'ada@example.org', phone: '0601020304', birthdate: '10/12/1990', address: '1 rue X', postal_code: '75001', city: 'Paris', country: 'France' },
      answers: [{ question: 'Quelle est la capitale de la France ?', answer: 'Paris' }]
    };
    const res = await page.evaluate((p) => window.__chFill(p), prefill);
    const val = (sel) => page.inputValue(sel);
    assert.equal(await val('#a1'), 'Ada');
    assert.equal(await val('input[name=x2]'), 'Lovelace');
    assert.equal(await val('input[name=mail]'), 'ada@example.org');
    assert.equal(await val('input[name=phone]'), '0601020304');
    assert.equal(await val('#dob'), '1990-12-10');
    assert.equal(await val('input[name=strasse]'), '1 rue X');
    assert.equal(await val('input[name=cap]'), '75001');
    assert.equal(await val('#stad'), 'Paris');
    assert.equal(await val('#c'), 'FR');
    assert.equal(await val('#q'), 'Paris');
    // non touches
    assert.equal(await val('input[name=pwd]'), '');
    assert.equal(await page.isChecked('input[name=newsletter]'), false);
    assert.equal(await page.isChecked('input[name=cgu]'), false);
    // surlignage
    assert.match(await page.$eval('#a1', (e) => e.style.outline), /rgb\(22, 163, 74\)/);
    assert.match(await page.$eval('#z', (e) => e.style.outline), /rgb\(249, 115, 22\)/);
    assert.equal(res.captcha, 'recaptcha');
    assert.equal(res.unrecognized, 1);
    // aucune soumission
    assert.equal(await page.evaluate(() => window.__submitCount), 0);
    assert.equal(navigations, navBefore);
    assert.equal(posts, 0);
  } finally { await browser.close(); }
});
