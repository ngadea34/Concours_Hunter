/* Concours Hunter - remplissage DOM. Necessite lib/fill-core.js (CHFillCore).
 * Ne soumet jamais un formulaire, ne clique jamais sur un bouton. */
(function () {
  'use strict';
  var Core = (typeof self !== 'undefined' ? self : window).CHFillCore;
  if (!Core) return;
  var GREEN = '2px solid #16a34a', ORANGE = '2px solid #f97316';

  function text(el) { return (el && el.textContent ? el.textContent : '').replace(/\s+/g, ' ').trim(); }

  function labelOf(el) {
    var parts = [];
    try { if (el.labels) for (var i = 0; i < el.labels.length; i++) parts.push(text(el.labels[i])); } catch (e) { /* ignore */ }
    if (!parts.length && el.id) {
      var l = document.querySelector('label[for="' + (window.CSS && CSS.escape ? CSS.escape(el.id) : el.id) + '"]');
      if (l) parts.push(text(l));
    }
    var wrap = el.closest && el.closest('label');
    if (wrap) parts.push(text(wrap));
    var lb = el.getAttribute('aria-labelledby');
    if (lb) lb.split(/\s+/).forEach(function (id) { var n = document.getElementById(id); if (n) parts.push(text(n)); });
    return parts.join(' ').slice(0, 300);
  }

  function nearbyOf(el) {
    var out = [];
    var prev = el.previousElementSibling;
    if (prev && !/^(INPUT|SELECT|TEXTAREA|BUTTON)$/.test(prev.tagName)) out.push(text(prev));
    var fs = el.closest && el.closest('fieldset');
    if (fs) { var lg = fs.querySelector('legend'); if (lg) out.push(text(lg)); }
    var p = el.parentElement;
    for (var depth = 0; p && depth < 3 && !out.join('').trim(); depth++, p = p.parentElement) {
      var t = text(p);
      if (t && t.length < 250 && p.querySelectorAll('input,select,textarea').length <= 1) out.push(t);
    }
    return out.join(' ').slice(0, 250);
  }

  function isHidden(el) {
    if (el.type === 'hidden') return true;
    var st = window.getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden') return true;
    return !(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  }

  function describe(el, index) {
    var d = {
      index: index, tag: el.tagName.toLowerCase(), type: (el.getAttribute('type') || (el.tagName === 'TEXTAREA' ? 'textarea' : 'text')).toLowerCase(),
      autocomplete: el.getAttribute('autocomplete') || '', name: el.getAttribute('name') || '', id: el.id || '',
      className: typeof el.className === 'string' ? el.className : '',
      placeholder: el.getAttribute('placeholder') || '', aria: el.getAttribute('aria-label') || '', title: el.getAttribute('title') || '',
      label: labelOf(el), nearby: nearbyOf(el), required: el.required || el.getAttribute('aria-required') === 'true',
      disabled: !!el.disabled, readonly: !!el.readOnly, hidden: isHidden(el), value: el.value || ''
    };
    if (d.tag === 'select') d.options = Array.prototype.map.call(el.options, function (o) { return { value: o.value, text: o.text }; });
    return d;
  }

  function setValue(el, value) {
    var proto = el.tagName === 'SELECT' ? HTMLSelectElement.prototype : el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    var desc = Object.getOwnPropertyDescriptor(proto, 'value');
    if (desc && desc.set) desc.set.call(el, value); else el.value = value;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function detectCaptcha() {
    var sel = 'iframe, .g-recaptcha, .h-captcha, .cf-turnstile, [class*="captcha" i], [id*="captcha" i], [name*="captcha" i], [class*="turnstile" i]';
    var els = Array.prototype.map.call(document.querySelectorAll(sel), function (e) {
      return { tag: e.tagName.toLowerCase(), src: e.getAttribute('src') || '', id: e.id || '', name: e.getAttribute('name') || '', className: typeof e.className === 'string' ? e.className : '' };
    });
    return Core.detectCaptcha(els);
  }

  function fill(prefill) {
    var nodes = Array.prototype.slice.call(document.querySelectorAll('input, select, textarea'));
    var descs = nodes.map(describe);
    var plan = Core.planFill(descs, prefill || {});
    var res = { filled: 0, unrecognized: 0, skipped_consent: 0, captcha: detectCaptcha(), filled_kinds: [] };
    plan.forEach(function (p) {
      var el = nodes[p.index];
      if (p.action === 'fill') {
        var v = p.value;
        if (el.tagName === 'SELECT') {
          var i = Core.pickOption(descs[p.index].options, v);
          if (i < 0) { if (descs[p.index].required) { el.style.outline = ORANGE; res.unrecognized++; } return; }
          v = el.options[i].value;
        }
        setValue(el, v);
        el.style.outline = GREEN;
        res.filled++; res.filled_kinds.push(p.kind);
      } else if (p.action === 'unrecognized_required') {
        el.style.outline = ORANGE; res.unrecognized++;
      } else if (p.reason === 'consent') res.skipped_consent++;
    });
    return res;
  }

  window.__chFill = fill;
  window.__chDetectCaptcha = detectCaptcha;
})();
