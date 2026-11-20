import { getSettings, DEFAULTS, api, msg, applyI18n } from '../lib/api.js';

const $ = (id) => document.getElementById(id);
applyI18n();
const show = (t, cls) => { $('msg').textContent = t; $('msg').className = cls || ''; };

getSettings().then((s) => { $('url').value = s.serverUrl; $('token').value = s.token; });

$('save').addEventListener('click', async () => {
  let url;
  try { url = new URL($('url').value.trim() || DEFAULTS.serverUrl); } catch (e) { show(msg('connFail', [e.message])); return; }
  if (!/^https?:$/.test(url.protocol)) { show(msg('connFail', [url.protocol])); return; }
  const origin = url.origin;
  const local = /^(127\.0\.0\.1|localhost)$/.test(url.hostname);
  if (!local) {
    // Serveur LAN : demande d'autorisation ciblee (geste utilisateur requis).
    const ok = await chrome.permissions.request({ origins: [origin + '/*'] });
    if (!ok) { show(msg('permDenied'), 'err'); return; }
  }
  await chrome.storage.local.set({ serverUrl: origin, token: $('token').value.trim() });
  show(msg('saved'), 'ok');
});

$('test').addEventListener('click', async () => {
  try {
    const r = await api('/auth/check');
    show(r && r.ok === false ? msg('needsToken') : msg('connOk'), r && r.ok === false ? 'err' : 'ok');
  } catch (e) { show(msg('connFail', [e.message]), 'err'); }
});
