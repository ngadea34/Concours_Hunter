/* Concours Hunter - logique pure de detection / correspondance (sans DOM).
 * Utilisable dans le content script (global CHFillCore) et dans Node (module.exports).
 * Aucune execution de code dynamique. */
(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.CHFillCore = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  function norm(s) {
    return String(s == null ? '' : s)
      .normalize('NFD').replace(/[̀-ͯ]/g, '')
      .toLowerCase()
      .replace(/ß/g, 'ss')
      .replace(/[^a-z0-9]+/g, ' ')
      .trim();
  }
  // "firstName" -> "first Name" avant normalisation (camelCase des name/id)
  function splitCamel(s) { return String(s == null ? '' : s).replace(/([a-z0-9])([A-Z])/g, '$1 $2'); }
  function normAttr(s) { return norm(splitCamel(s)); }

  function hasPhrase(text, phrase) {
    return (' ' + text + ' ').indexOf(' ' + phrase + ' ') !== -1;
  }
  function hasAny(text, phrases) {
    for (var i = 0; i < phrases.length; i++) if (hasPhrase(text, phrases[i])) return phrases[i];
    return null;
  }

  // Ordre = priorite (le premier gagne).
  var KINDS = [
    ['email', ['email', 'e mail', 'mail', 'courriel', 'correo', 'correo electronico', 'posta elettronica', 'e mail adresse', 'mailadresse', 'emailadres', 'e mailadres', 'endereco de email']],
    ['birthdate', ['date de naissance', 'naissance', 'birth', 'birthday', 'birthdate', 'date of birth', 'dob', 'bday', 'anniversaire', 'fecha de nacimiento', 'nacimiento', 'geburtsdatum', 'geburtstag', 'geburt', 'data di nascita', 'nascita', 'data de nascimento', 'nascimento', 'geboortedatum', 'geboorte', 'jj mm aaaa']],
    ['postal_code', ['code postal', 'postal', 'postal code', 'zip', 'zipcode', 'zip code', 'cp', 'codigo postal', 'plz', 'postleitzahl', 'cap', 'codice postale', 'cep', 'codigo de postal', 'postcode', 'postcode']],
    ['phone', ['telephone', 'phone', 'tel', 'mobile', 'portable', 'telefono', 'telefon', 'handy', 'handynummer', 'telefone', 'celular', 'movil', 'cellulare', 'gsm', 'mobiel', 'telefoonnummer', 'numero de telephone', 'rufnummer']],
    ['country', ['pays', 'country', 'pais', 'land', 'paese', 'nation', 'country name']],
    ['city', ['ville', 'city', 'town', 'localite', 'commune', 'ciudad', 'localidad', 'stadt', 'ort', 'wohnort', 'citta', 'cidade', 'localidade', 'stad', 'woonplaats', 'plaats', 'municipio']],
    ['address', ['adresse', 'address', 'street', 'street address', 'rue', 'direccion', 'domicilio', 'calle', 'strasse', 'anschrift', 'indirizzo', 'endereco', 'morada', 'straat', 'adres', 'address line 1', 'addr']],
    ['first_name', ['prenom', 'first name', 'firstname', 'given name', 'fname', 'forename', 'nombre', 'vorname', 'nome', 'primeiro nome', 'voornaam', 'first', 'given', 'prenoms']],
    ['last_name', ['nom de famille', 'last name', 'lastname', 'surname', 'family name', 'lname', 'apellido', 'apellidos', 'nachname', 'familienname', 'cognome', 'sobrenome', 'apelido', 'achternaam', 'family', 'nom']],
    ['full_name', ['nom complet', 'full name', 'fullname', 'name', 'nom et prenom', 'name and surname', 'nombre completo', 'vollstandiger name', 'nome completo', 'volledige naam', 'naam', 'nom prenom']]
  ];

  var AUTOCOMPLETE = {
    'given-name': 'first_name', 'additional-name': null, 'family-name': 'last_name', 'name': 'full_name',
    'email': 'email', 'tel': 'phone', 'tel-national': 'phone', 'tel-local': 'phone',
    'bday': 'birthdate', 'street-address': 'address', 'address-line1': 'address',
    'postal-code': 'postal_code', 'address-level2': 'city', 'country': 'country', 'country-name': 'country'
  };

  var FIELD_ALIASES = {
    first_name: ['first_name', 'firstname', 'prenom', 'given_name', 'forename'],
    last_name: ['last_name', 'lastname', 'nom', 'family_name', 'surname'],
    full_name: ['full_name', 'fullname', 'name', 'nom_complet'],
    email: ['email', 'mail', 'e_mail'],
    phone: ['phone', 'telephone', 'tel', 'mobile', 'phone_number'],
    birthdate: ['birthdate', 'birth_date', 'date_of_birth', 'dob', 'birthday', 'date_naissance', 'date_de_naissance'],
    address: ['address', 'address_line1', 'street', 'street_address', 'adresse'],
    postal_code: ['postal_code', 'zip', 'zip_code', 'postcode', 'code_postal'],
    city: ['city', 'ville', 'town'],
    country: ['country', 'pays', 'country_name']
  };

  var CONSENT_WORDS = ['newsletter', 'newsletters', 'marketing', 'promotion', 'promotions', 'promotionnel', 'offres', 'partenaires', 'partners', 'cgu', 'cgv', 'conditions', 'terms', 'reglement', 'rules', 'consent', 'consentement', 'accept', 'accepte', 'agree', 'privacy', 'gdpr', 'rgpd', 'optin', 'opt in', 'subscribe', 'abonner', 'datenschutz', 'agb', 'acepto', 'condiciones', 'accetto', 'termini', 'aceito', 'termos', 'voorwaarden', 'akkoord'];

  var SKIP_TYPES = ['hidden', 'password', 'file', 'submit', 'button', 'image', 'reset', 'checkbox', 'radio', 'range', 'color'];

  var STOP = ['the', 'a', 'an', 'of', 'to', 'is', 'are', 'in', 'on', 'and', 'or', 'what', 'which', 'who', 'how', 'you', 'your', 'vous', 'votre', 'vos', 'le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'et', 'ou', 'est', 'quel', 'quelle', 'quels', 'quelles', 'que', 'qui', 'quoi', 'pour', 'dans', 'sur', 'en', 'el', 'los', 'las', 'un', 'una', 'que', 'cual', 'der', 'die', 'das', 'ein', 'eine', 'und', 'welche', 'il', 'lo', 'gli', 'quale', 'o', 'os', 'qual', 'het', 'een', 'wat', 'welke', 'answer', 'reponse', 'question', 'required', 'obligatoire'];

  function fieldTexts(d) {
    return {
      autocomplete: String(d.autocomplete || '').toLowerCase().trim(),
      attrs: normAttr([d.name, d.id].filter(Boolean).join(' ')),
      labels: norm([d.label, d.aria, d.placeholder, d.title].filter(Boolean).join(' ')),
      nearby: norm(d.nearby || '')
    };
  }

  function isCaptchaDescriptor(d) {
    var s = ((d.name || '') + ' ' + (d.id || '') + ' ' + (d.className || '') + ' ' + (d.src || '')).toLowerCase();
    return /captcha|turnstile/.test(s);
  }

  function isSkippableType(d) {
    var t = String(d.type || '').toLowerCase();
    if (d.tag === 'select' || d.tag === 'textarea') return false;
    return SKIP_TYPES.indexOf(t) !== -1;
  }

  /** Classe un champ: {kind, reason}. kind parmi les cles de FIELD_ALIASES, ou null. */
  function classifyField(d) {
    var t = fieldTexts(d);
    if (isCaptchaDescriptor(d)) return { kind: null, skip: 'captcha' };
    var type = String(d.type || '').toLowerCase();
    if (type === 'password') return { kind: null, skip: 'password' };
    if (type === 'file') return { kind: null, skip: 'file' };
    if (isSkippableType(d)) return { kind: null, skip: 'type' };
    if (t.autocomplete) {
      var toks = t.autocomplete.split(/\s+/);
      for (var i = 0; i < toks.length; i++) {
        if (Object.prototype.hasOwnProperty.call(AUTOCOMPLETE, toks[i]) && AUTOCOMPLETE[toks[i]]) {
          return { kind: AUTOCOMPLETE[toks[i]], via: 'autocomplete' };
        }
      }
    }
    if (type === 'email') return { kind: 'email', via: 'type' };
    if (type === 'tel') return { kind: 'phone', via: 'type' };
    if (type === 'date' && !t.labels && !t.attrs) return { kind: 'birthdate', via: 'type' };
    // attributs forts d'abord, puis libelles, puis texte voisin
    var sources = [['attrs', t.attrs], ['labels', t.labels], ['nearby', t.nearby]];
    for (var s = 0; s < sources.length; s++) {
      var text = sources[s][1];
      if (!text) continue;
      // un libelle long ressemble a une question libre : ne pas classer par mot isole
      if (sources[s][0] !== 'attrs' && text.split(' ').length > 8) continue;
      for (var k = 0; k < KINDS.length; k++) {
        if (hasAny(text, KINDS[k][1])) return { kind: KINDS[k][0], via: sources[s][0] };
      }
    }
    return { kind: null };
  }

  /** Champ de consentement / marketing / CGU (jamais coche par l'extension). */
  function isConsentField(d) {
    var t = String(d.type || '').toLowerCase();
    var text = norm([d.name, d.id, d.label, d.aria, d.nearby].filter(Boolean).join(' '));
    if (t === 'checkbox' || t === 'radio') {
      return !!hasAny(text, CONSENT_WORDS) || t === 'checkbox';
    }
    return false;
  }

  function getPrefillValue(fields, kind) {
    if (!fields || !kind) return '';
    var lower = {};
    Object.keys(fields).forEach(function (k) { lower[String(k).toLowerCase()] = fields[k]; });
    var al = FIELD_ALIASES[kind] || [];
    for (var i = 0; i < al.length; i++) {
      var v = lower[al[i]];
      if (v != null && String(v).trim() !== '') return String(v);
    }
    if (kind === 'full_name') {
      var f = getPrefillValue(fields, 'first_name'), l = getPrefillValue(fields, 'last_name');
      return (f + ' ' + l).trim();
    }
    return '';
  }

  /** Date vers AAAA-MM-JJ pour <input type=date>, sinon JJ/MM/AAAA ; chaine inconnue inchangee. */
  function formatDate(value, inputType) {
    var v = String(value || '').trim();
    var y, mo, d, m = /^(\d{1,2})[\/.\-](\d{1,2})[\/.\-](\d{4})$/.exec(v);
    if (m) { d = m[1]; mo = m[2]; y = m[3]; }
    else {
      m = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(v);
      if (!m) return v;
      y = m[1]; mo = m[2]; d = m[3];
    }
    var p = function (n) { return ('0' + n).slice(-2); };
    return String(inputType || '').toLowerCase() === 'date' ? y + '-' + p(mo) + '-' + p(d) : p(d) + '/' + p(mo) + '/' + y;
  }

  function tokens(s) {
    return norm(s).split(' ').filter(function (w) { return w.length > 2 && STOP.indexOf(w) === -1; });
  }

  /** Correspondance approximative libelle de champ <-> question. Renvoie {answer, score} ou null. */
  function matchQuestion(fieldText, answers, threshold) {
    var th = threshold == null ? 0.45 : threshold;
    var ft = tokens(fieldText);
    if (!ft.length || !answers) return null;
    var best = null;
    answers.forEach(function (a, idx) {
      var qt = tokens(a.question);
      if (!qt.length || a.answer == null || String(a.answer) === '') return;
      var shared = 0;
      qt.forEach(function (w) {
        if (ft.indexOf(w) !== -1) shared++;
        else if (w.length > 4 && ft.some(function (x) { return x.length > 4 && (x.indexOf(w) === 0 || w.indexOf(x) === 0); })) shared += 0.8;
      });
      if (!shared) return;
      var score = (2 * shared) / (qt.length + ft.length);
      var cover = shared / Math.min(qt.length, ft.length);
      score = Math.max(score, cover * 0.9);
      if (score >= th && (!best || score > best.score)) best = { answer: String(a.answer), question: a.question, score: score, index: idx };
    });
    return best;
  }

  /** Choisit l'option d'un <select> la plus proche de value. options: [{value,text}]. -1 si aucune. */
  function pickOption(options, value) {
    var v = norm(value);
    if (!v) return -1;
    var i;
    for (i = 0; i < options.length; i++) if (norm(options[i].value) === v || norm(options[i].text) === v) return i;
    for (i = 0; i < options.length; i++) {
      var t = norm(options[i].text);
      if (t && (hasPhrase(t, v) || hasPhrase(v, t)) && t.length > 1) return i;
    }
    var COUNTRY = { fr: 'france', france: 'france', de: 'germany allemagne deutschland', es: 'spain espagne espana', it: 'italy italie italia', be: 'belgium belgique belgie', ch: 'switzerland suisse schweiz', lu: 'luxembourg' };
    if (COUNTRY[v]) {
      var alts = COUNTRY[v].split(' ');
      for (i = 0; i < options.length; i++) {
        var o = norm(options[i].text), ov = norm(options[i].value);
        if (alts.indexOf(o) !== -1 || ov === v) return i;
      }
    }
    return -1;
  }

  function fieldDisplayText(d) {
    return [d.label, d.aria, d.placeholder, d.title, d.nearby].filter(Boolean).join(' ');
  }

  /** Plan de remplissage pur. Renvoie [{index, action, kind?, value?, via?}].
   * action: fill | unrecognized_required | skip */
  function planFill(descriptors, prefill) {
    var fields = (prefill && prefill.fields) || {};
    var answers = (prefill && prefill.answers) || [];
    return descriptors.map(function (d) {
      var base = { index: d.index };
      if (d.hidden || d.disabled || d.readonly) return Object.assign(base, { action: 'skip', reason: 'unavailable' });
      if (isConsentField(d)) return Object.assign(base, { action: 'skip', reason: 'consent' });
      var c = classifyField(d);
      if (c.skip) return Object.assign(base, { action: 'skip', reason: c.skip });
      if (d.value && String(d.value).trim() !== '' && d.tag !== 'select') return Object.assign(base, { action: 'skip', reason: 'already_filled' });
      var value = '', kind = c.kind, via = c.via || null;
      if (kind) {
        value = getPrefillValue(fields, kind);
        if (kind === 'birthdate' && value) value = formatDate(value, d.type);
      } else {
        var m = matchQuestion(fieldDisplayText(d), answers);
        if (m) { value = m.answer; kind = 'answer'; via = 'question'; }
      }
      if (value) return Object.assign(base, { action: 'fill', kind: kind, value: value, via: via });
      if (d.required) return Object.assign(base, { action: 'unrecognized_required', kind: kind });
      return Object.assign(base, { action: 'skip', reason: 'no_value' });
    });
  }

  var CAPTCHA_SRC = [/google\.com\/recaptcha/i, /recaptcha\.net/i, /gstatic\.com\/recaptcha/i, /hcaptcha\.com/i, /challenges\.cloudflare\.com/i, /turnstile/i, /captcha/i];
  var CAPTCHA_CLASS = [
    ['recaptcha', /(^|\s)g-recaptcha(\s|$)|recaptcha/i],
    ['hcaptcha', /(^|\s)h-captcha(\s|$)|hcaptcha/i],
    ['turnstile', /cf-turnstile|turnstile/i],
    ['captcha', /captcha/i]
  ];

  /** elements: [{tag, src, id, name, className}]. Renvoie un nom de fournisseur ou null. */
  function detectCaptcha(elements) {
    for (var i = 0; i < (elements || []).length; i++) {
      var e = elements[i];
      var src = String(e.src || '');
      if (/hcaptcha\.com/i.test(src)) return 'hcaptcha';
      if (/recaptcha|gstatic\.com\/recaptcha/i.test(src)) return 'recaptcha';
      if (/challenges\.cloudflare\.com|turnstile/i.test(src)) return 'turnstile';
      var meta = [e.className, e.id, e.name].filter(Boolean).join(' ');
      for (var j = 0; j < CAPTCHA_CLASS.length; j++) if (CAPTCHA_CLASS[j][1].test(meta)) return CAPTCHA_CLASS[j][0];
      if (/captcha/i.test(src)) return 'captcha';
    }
    return null;
  }

  return {
    norm: norm, classifyField: classifyField, isConsentField: isConsentField, getPrefillValue: getPrefillValue,
    formatDate: formatDate, matchQuestion: matchQuestion, pickOption: pickOption, planFill: planFill,
    detectCaptcha: detectCaptcha, isCaptchaDescriptor: isCaptchaDescriptor, CAPTCHA_SRC: CAPTCHA_SRC
  };
});
