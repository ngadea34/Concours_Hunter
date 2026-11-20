// Client API Concours Hunter (module ES, pages de l'extension uniquement).
export const DEFAULTS = { serverUrl: 'http://127.0.0.1:8765', token: '' };

export async function getSettings() {
  const s = await chrome.storage.local.get(DEFAULTS);
  return { serverUrl: String(s.serverUrl || DEFAULTS.serverUrl).replace(/\/+$/, ''), token: s.token || '' };
}

export function msg(key, subs) { return chrome.i18n.getMessage(key, subs) || key; }

export async function api(path, { method = 'GET', body } = {}) {
  const { serverUrl, token } = await getSettings();
  const headers = {};
  if (token) headers['X-CH-Token'] = token;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const res = await fetch(serverUrl + '/api' + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  let data = null;
  try { data = await res.json(); } catch (e) { /* corps vide */ }
  if (!res.ok) throw new Error((data && data.detail) || ('HTTP ' + res.status));
  return data;
}

export function applyI18n(root = document) {
  root.querySelectorAll('[data-i18n]').forEach((el) => { el.textContent = msg(el.dataset.i18n); });
  document.documentElement.lang = chrome.i18n.getUILanguage().slice(0, 2);
}
