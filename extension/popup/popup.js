import { api, msg, applyI18n } from '../lib/api.js';

const $ = (id) => document.getElementById(id);
applyI18n();
$('settings').addEventListener('click', (e) => { e.preventDefault(); chrome.runtime.openOptionsPage(); });

let tab = null;

function setResult(text, cls) { const r = $('result'); r.textContent = text; r.className = cls || ''; }
function showCaptcha(provider) {
  if (!provider) return;
  const c = $('captcha'); c.hidden = false; c.textContent = msg('captchaWarn') + ' (' + provider + ')';
}

async function inject() {
  await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['lib/fill-core.js', 'content/filler.js'] });
}

async function detectCaptcha() {
  try {
    await inject();
    const [r] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: () => window.__chDetectCaptcha() });
    showCaptcha(r && r.result);
  } catch (e) { /* page non injectable */ }
}

async function prefill(p) {
  setResult(msg('loading'));
  try {
    const data = await api('/participations/' + p.id + '/prefill');
    await inject();
    const [r] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: (d) => window.__chFill(d),
      args: [{ fields: data.fields || {}, answers: data.answers || [] }]
    });
    const res = (r && r.result) || {};
    showCaptcha(res.captcha);
    let t = msg('prefillResult', [String(res.filled || 0), String(res.unrecognized || 0)]);
    if (data.warnings && data.warnings.length) t += ' ' + msg('prefillWarnings', [data.warnings.join(' ; ')]);
    setResult(t, 'ok');
  } catch (e) { setResult(msg('submitFail', [e.message]), 'err'); }
}

async function submitted(p) {
  try {
    const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: 'png' });
    await api('/participations/' + p.id + '/proofs', { method: 'POST', body: { kind: 'screenshot', data_url: dataUrl } });
    await api('/participations/' + p.id + '/submitted', { method: 'POST', body: {} });
    setResult(msg('proofSaved'), 'ok');
  } catch (e) { setResult(msg('submitFail', [e.message]), 'err'); }
}

function render(items) {
  const ul = $('list'); ul.textContent = '';
  items.forEach((p) => {
    const li = document.createElement('li');
    const t = document.createElement('div'); t.className = 'title'; t.textContent = p.contest_title;
    const m = document.createElement('div'); m.className = 'meta'; m.textContent = msg('status_' + p.status);
    const b1 = document.createElement('button'); b1.textContent = msg('prefill'); b1.addEventListener('click', () => prefill(p));
    const b2 = document.createElement('button'); b2.textContent = msg('submittedBtn'); b2.addEventListener('click', () => submitted(p));
    li.append(t, m, b1, b2); ul.append(li);
  });
}

(async () => {
  [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const status = $('status');
  if (!tab || !/^https?:/i.test(tab.url || '')) { status.textContent = msg('unsupportedPage'); return; }
  try {
    const list = await api('/participations?url=' + encodeURIComponent(tab.url));
    const items = (list || []).filter((p) => p.status === 'prepared' || p.status === 'awaiting_human');
    if (!items.length) { status.textContent = msg('noneForPage'); return; }
    status.textContent = '';
    render(items);
    detectCaptcha();
  } catch (e) { status.textContent = msg('serverError', [e.message]); status.className = 'err'; }
})();
