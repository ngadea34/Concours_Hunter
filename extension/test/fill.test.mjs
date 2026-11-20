import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const require = createRequire(import.meta.url);
const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const C = require('../lib/fill-core.js');
const kind = (d) => C.classifyField({ tag: 'input', type: 'text', ...d }).kind;

test('manifest JSON valide, permissions minimales', () => {
  const m = JSON.parse(readFileSync(join(root, 'manifest.json'), 'utf8'));
  assert.equal(m.manifest_version, 3);
  assert.deepEqual([...m.permissions].sort(), ['activeTab', 'scripting', 'storage']);
  assert.deepEqual(m.host_permissions, ['http://127.0.0.1/*', 'http://localhost/*']);
  assert.ok(!m.content_scripts, 'pas de content script permanent');
  assert.equal(m.default_locale, 'fr');
  for (const l of ['fr', 'en']) JSON.parse(readFileSync(join(root, '_locales', l, 'messages.json'), 'utf8'));
});

test('classification multilingue', () => {
  const cases = [
    [{ autocomplete: 'given-name' }, 'first_name'], [{ autocomplete: 'family-name' }, 'last_name'],
    [{ label: 'Prénom *' }, 'first_name'], [{ label: 'Nom' }, 'last_name'], [{ name: 'firstName' }, 'first_name'],
    [{ placeholder: 'Vorname' }, 'first_name'], [{ placeholder: 'Nachname' }, 'last_name'],
    [{ label: 'Apellido' }, 'last_name'], [{ label: 'Cognome' }, 'last_name'], [{ label: 'Achternaam' }, 'last_name'],
    [{ label: 'Voornaam' }, 'first_name'], [{ label: 'Sobrenome' }, 'last_name'],
    [{ type: 'email' }, 'email'], [{ label: 'Correo electrónico' }, 'email'], [{ label: 'E-Mail-Adresse' }, 'email'],
    [{ type: 'tel' }, 'phone'], [{ label: 'Telefono' }, 'phone'], [{ label: 'Handynummer' }, 'phone'],
    [{ label: 'Date de naissance' }, 'birthdate'], [{ label: 'Geburtsdatum' }, 'birthdate'], [{ label: 'Data di nascita' }, 'birthdate'],
    [{ label: 'Geboortedatum' }, 'birthdate'], [{ label: 'Data de nascimento' }, 'birthdate'], [{ autocomplete: 'bday' }, 'birthdate'],
    [{ label: 'Code postal' }, 'postal_code'], [{ label: 'PLZ' }, 'postal_code'], [{ name: 'zip' }, 'postal_code'], [{ label: 'Codigo postal' }, 'postal_code'],
    [{ label: 'Ville' }, 'city'], [{ label: 'Ciudad' }, 'city'], [{ label: 'Stadt' }, 'city'], [{ label: 'Woonplaats' }, 'city'], [{ label: 'Cidade' }, 'city'],
    [{ label: 'Pays' }, 'country'], [{ label: 'País' }, 'country'], [{ label: 'Land' }, 'country'], [{ label: 'Paese' }, 'country'],
    [{ label: 'Adresse' }, 'address'], [{ label: 'Straße' }, 'address'], [{ label: 'Dirección' }, 'address'], [{ label: 'Indirizzo' }, 'address'], [{ label: 'Straat' }, 'address'],
    [{ label: 'Votre adresse e-mail' }, 'email'], [{ label: 'Full name' }, 'full_name']
  ];
  for (const [d, k] of cases) assert.equal(kind(d), k, JSON.stringify(d));
  assert.equal(kind({ label: 'Quelle est la capitale de la France ?' }), null);
});

test('password, file, captcha et consentements jamais remplis', () => {
  assert.equal(C.classifyField({ tag: 'input', type: 'password', name: 'email' }).skip, 'password');
  assert.equal(C.classifyField({ tag: 'input', type: 'file' }).skip, 'file');
  assert.equal(C.classifyField({ tag: 'input', type: 'text', name: 'captcha_response' }).skip, 'captcha');
  assert.ok(C.isConsentField({ tag: 'input', type: 'checkbox', name: 'newsletter', label: 'newsletter' }));
  const plan = C.planFill([
    { index: 0, tag: 'input', type: 'checkbox', name: 'cgu', required: true, label: "J'accepte le règlement" },
    { index: 1, tag: 'input', type: 'password', name: 'pwd', required: true },
    { index: 2, tag: 'input', type: 'file', required: true }
  ], { fields: { email: 'a@b.fr' } });
  assert.ok(plan.every((p) => p.action === 'skip'));
});

test('planFill : valeurs, date, requis non reconnus, champ deja rempli', () => {
  const prefill = {
    fields: { first_name: 'Ada', last_name: 'Lovelace', email: 'ada@example.org', birthdate: '10/12/1990', postal_code: '75001' },
    answers: [{ question: 'Quelle est la capitale de la France ?', answer: 'Paris' }]
  };
  const plan = C.planFill([
    { index: 0, tag: 'input', type: 'text', label: 'Prénom', required: true },
    { index: 1, tag: 'input', type: 'date', label: 'Date de naissance' },
    { index: 2, tag: 'input', type: 'text', label: 'Quelle est la capitale de la France ?', required: true },
    { index: 3, tag: 'input', type: 'text', label: 'Champ bizarre', required: true },
    { index: 4, tag: 'input', type: 'email', value: 'deja@x.fr' },
    { index: 5, tag: 'input', type: 'text', label: 'Ville', required: true },
    { index: 6, tag: 'input', type: 'text', label: 'Prénom', hidden: true }
  ], prefill);
  assert.deepEqual([plan[0].action, plan[0].value], ['fill', 'Ada']);
  assert.equal(plan[1].value, '1990-12-10');
  assert.deepEqual([plan[2].action, plan[2].value], ['fill', 'Paris']);
  assert.equal(plan[3].action, 'unrecognized_required');
  assert.equal(plan[4].reason, 'already_filled');
  assert.equal(plan[5].action, 'unrecognized_required'); // ville connue mais sans valeur
  assert.equal(plan[6].action, 'skip');
});

test('matchQuestion : correspondance approximative', () => {
  const answers = [
    { question: 'Combien de ministres compte le gouvernement ?', answer: '35' },
    { question: 'Quel est le nom du fondateur de la marque ?', answer: 'Coco' }
  ];
  assert.equal(C.matchQuestion('Nom du fondateur de la marque', answers).answer, 'Coco');
  assert.equal(C.matchQuestion('Combien de ministres ?', answers).answer, '35');
  assert.equal(C.matchQuestion('Votre animal préféré', answers), null);
});

test('pickOption : pays', () => {
  const o = [{ value: '', text: '--' }, { value: 'DE', text: 'Allemagne' }, { value: 'FR', text: 'France' }];
  assert.equal(C.pickOption(o, 'France'), 2);
  assert.equal(C.pickOption(o, 'fr'), 2);
  assert.equal(C.pickOption(o, 'Japon'), -1);
});

test('detectCaptcha', () => {
  assert.equal(C.detectCaptcha([{ tag: 'iframe', src: 'https://www.google.com/recaptcha/api2/anchor?k=1' }]), 'recaptcha');
  assert.equal(C.detectCaptcha([{ tag: 'iframe', src: 'https://newassets.hcaptcha.com/captcha/v1/x' }]), 'hcaptcha');
  assert.equal(C.detectCaptcha([{ tag: 'iframe', src: 'https://challenges.cloudflare.com/cdn-cgi/x' }]), 'turnstile');
  assert.equal(C.detectCaptcha([{ tag: 'div', className: 'cf-turnstile' }]), 'turnstile');
  assert.equal(C.detectCaptcha([{ tag: 'div', className: 'my-captcha-box' }]), 'captcha');
  assert.equal(C.detectCaptcha([{ tag: 'input', name: 'captcha_code' }]), 'captcha');
  assert.equal(C.detectCaptcha([{ tag: 'iframe', src: 'https://www.youtube.com/embed/x' }]), null);
});
