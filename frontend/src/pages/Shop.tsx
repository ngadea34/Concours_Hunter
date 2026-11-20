import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api, getToken } from '../api';
import { Async } from '../components/Async';
import { Badge, type Tone } from '../components/Badge';
import { Modal } from '../components/Modal';
import { PageHeader } from '../components/PageHeader';
import { useToast } from '../components/Toast';
import { useAsync } from '../hooks';
import { useI18n } from '../i18n';
import type { ShopCheck, ShopClaim, ShopDashboard, ShopDoc, ShopOffer, ShopPreview, ShopPrefs } from '../types';
import { fmtDate, safeHref } from '../util';

const TABS = ['offers', 'claims', 'documents', 'expenses', 'analyze', 'settings'] as const;
type Tab = typeof TABS[number];
const OFFER_SECTIONS = ['available', 'to_buy', 'full_refund', 'purchase_games', 'partial_refund', 'ending_soon'] as const;
const CLAIM_SECTIONS = ['claims_to_complete', 'claims_sent', 'refunds_awaiting', 'refunds_late', 'refunds_received', 'refused', 'history'] as const;
const SUBCOMMANDS = ['discover', 'available', 'cashback', 'contests', 'analyze', 'submit', 'track', 'report'] as const;
const CMD_TAB: Record<string, Tab> = { available: 'offers', analyze: 'analyze', claims: 'claims', expenses: 'expenses' };
const DOC_KINDS = ['receipt', 'invoice', 'packaging', 'barcode', 'qr', 'promo_label', 'payment_proof', 'rules_capture', 'other'];
const LEVELS = ['store_confirmed', 'catalog_listed', 'third_party', 'unknown'];
const catTone: Record<string, Tone> = { A: 'ok', B: 'info', C: 'warn' };
const checkTone: Record<string, Tone> = { ok: 'ok', warn: 'warn', fail: 'bad', pending: 'neutral', na: 'neutral' };
const levelTone: Record<string, Tone> = { store_confirmed: 'ok', catalog_listed: 'info', third_party: 'warn', unknown: 'neutral' };
const statusTone: Record<string, Tone> = { refunded: 'ok', refused: 'bad', cancelled: 'neutral', sent: 'info', confirmed: 'info', refund_pending: 'info' };

type Run = (fn: () => Promise<unknown>, msg?: string) => Promise<void>;

function eur(v: number | null | undefined, lang: string): string {
  if (v === null || v === undefined) return '—';
  return v.toLocaleString(lang === 'en' ? 'en-GB' : 'fr-FR', { style: 'currency', currency: 'EUR' });
}
function num(s: string): number | undefined {
  const v = parseFloat(s.replace(',', '.'));
  return Number.isFinite(v) ? v : undefined;
}
function readFile(f: File): Promise<string> {
  return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(String(r.result)); r.onerror = rej; r.readAsDataURL(f); });
}
const today = () => new Date().toISOString().slice(0, 10);

export function Shop() {
  const { t } = useI18n();
  const toast = useToast();
  const [tab, setTab] = useState<Tab>('offers');
  const [cmd, setCmd] = useState('/hunter-shop ');
  const [cmdOut, setCmdOut] = useState<string | null>(null);
  const [claimId, setClaimId] = useState<number | null>(null);
  const d = useAsync(() => api.shopDashboard(), []);

  const run: Run = async (fn, msg) => {
    try { await fn(); d.reload(); if (msg) toast.ok(msg); } catch (e) { toast.err(e); }
  };
  const exec = async (text: string) => {
    try {
      const r = await api.shopCommand(text);
      const target = CMD_TAB[r.tab];
      if (target) setTab(target);
      setCmdOut(r.text);
      d.reload();
    } catch (e) { toast.err(e); }
  };
  const onCmd = (e: FormEvent) => { e.preventDefault(); void exec(cmd); };
  const openClaim = (id: number) => { setClaimId(id); setTab('claims'); };

  return (
    <>
      <PageHeader title={t('sh.title')}>
        <button className="btn" onClick={() => d.reload()}>{t('common.refresh')}</button>
      </PageHeader>
      <p className="alert alert-warn small" role="note">{t('sh.safety')}</p>

      <section className="card no-print" aria-label={t('sh.command')}>
        <form className="row gap wrap" onSubmit={onCmd}>
          <label htmlFor="sh-cmd" className="sr-only">{t('sh.command')}</label>
          <input id="sh-cmd" value={cmd} onChange={(e) => setCmd(e.target.value)} style={{ flex: 1, minWidth: '12rem' }}
            placeholder="/hunter-shop discover | available | cashback | contests | analyze … | submit 12 | track | report" />
          <button className="btn">{t('sh.run')}</button>
        </form>
        <div className="row gap wrap" style={{ marginTop: '.6rem' }}>
          {SUBCOMMANDS.map((s) => (
            <button key={s} className="btn btn-sm" title={t(`sh.cmd.${s}.help`)}
              onClick={() => (s === 'analyze' ? setTab('analyze') : s === 'submit' ? setCmd('/hunter-shop submit ') : void exec(`/hunter-shop ${s}`))}>
              {t(`sh.cmd.${s}`)}
            </button>
          ))}
        </div>
      </section>

      <div className="tabs no-print" role="tablist">
        {TABS.map((k) => (
          <button key={k} role="tab" aria-selected={tab === k} className={`btn btn-sm${tab === k ? ' btn-primary' : ''}`} onClick={() => setTab(k)}>
            {t(`sh.tab.${k}`)}
          </button>
        ))}
      </div>

      {tab === 'offers' && <Async state={d}>{(x) => <Offers d={x} run={run} openClaim={openClaim} />}</Async>}
      {tab === 'claims' && <Async state={d}>{(x) => <Claims d={x} claimId={claimId} setClaimId={setClaimId} reloadAll={d.reload} />}</Async>}
      {tab === 'documents' && <Documents />}
      {tab === 'expenses' && <Expenses />}
      {tab === 'analyze' && <Analyze onSaved={() => { d.reload(); setTab('offers'); }} />}
      {tab === 'settings' && <Settings onSaved={() => d.reload()} />}

      <Modal open={cmdOut !== null} title={t('sh.command')} onClose={() => setCmdOut(null)}>
        <pre className="pre small">{cmdOut}</pre>
      </Modal>
    </>
  );
}

// ---------------------------------------------------------------- opérations
function Offers({ d, run, openClaim }: { d: ShopDashboard; run: Run; openClaim: (id: number) => void }) {
  const { t } = useI18n();
  const [sec, setSec] = useState<typeof OFFER_SECTIONS[number]>('available');
  const list = d[sec];
  return (
    <>
      <div className="row gap wrap" role="group" aria-label={t('sh.sections')}>
        {OFFER_SECTIONS.map((k) => (
          <button key={k} className={`btn btn-sm${sec === k ? ' btn-primary' : ''}`} aria-pressed={sec === k} onClick={() => setSec(k)}>
            {t(`sh.sec.${k}`)} <span className="count count-muted">{d[k].length}</span>
          </button>
        ))}
      </div>
      <p className="muted small">{d.realtime_note}</p>
      {list.length === 0 ? <p className="empty">{t('sh.noOffer')}</p> : (
        <div className="stack">{list.map((o) => <OfferCard key={o.id} o={o} run={run} openClaim={openClaim} />)}</div>
      )}
      {sec === 'available' && d.excluded.length > 0 && (
        <details className="card" style={{ marginTop: '1rem' }}>
          <summary>{t('sh.excluded', { n: d.excluded.length })}</summary>
          <ul className="small">{d.excluded.map((x) => <li key={x.id}>{x.title} : {x.reason}</li>)}</ul>
        </details>
      )}
    </>
  );
}

function OfferCard({ o, run, openClaim }: { o: ShopOffer; run: Run; openClaim: (id: number) => void }) {
  const { t, lang } = useI18n();
  const [avail, setAvail] = useState(false);
  const f = o.finance;
  const href = safeHref(o.rules_url || o.url);
  const createClaim = async () => {
    try { const c = await api.newShopClaim(o.id); openClaim(c.id); } catch (e) { void run(() => Promise.reject(e)); }
  };
  return (
    <article className="card">
      <div className="row between wrap gap">
        <h3 style={{ margin: 0 }}>{o.title}</h3>
        <div className="row gap wrap">
          <Badge tone={catTone[o.category]}>{o.category} · {f.category_label}</Badge>
          <Badge>{t(`sh.kind.${o.kind}`)}</Badge>
          {o.over_cap && <Badge tone="bad">{t('sh.overCap')}</Badge>}
        </div>
      </div>
      <p className="small muted">
        {o.brand && <>{o.brand} · </>}
        {o.retailers.length ? o.retailers.join(', ') : o.retailers_note}
        {o.end_date && <> · {t('sh.until')} {fmtDate(o.end_date, lang)}</>}
        {o.reliability !== null && <> · {t('sh.reliability')} {o.reliability} %</>}
        {o.contest_id && <> · <Link to={`/contests/${o.contest_id}`}>{t('sh.contest')}</Link></>}
        {href && <> · <a href={href} target="_blank" rel="noopener noreferrer">{t('sh.rules')}</a></>}
      </p>
      <dl className="kv small">
        <div><dt>{t('sh.price')}</dt><dd>{eur(f.price_eur, lang)}</dd></div>
        {o.kind === 'purchase_game'
          ? <div><dt>{t('sh.prize')}</dt><dd>{eur(f.random_prize_value_eur, lang)} ({t('sh.random')})</dd></div>
          : <div><dt>{t('sh.refund')}</dt><dd>{eur(f.refund_announced_eur, lang)}</dd></div>}
        {f.extra_counted_eur ? <div><dt>{t('sh.extra')}</dt><dd>{eur(f.extra_counted_eur, lang)}</dd></div> : null}
        {f.fees_eur ? <div><dt>{t('sh.fees')}</dt><dd>{eur(f.fees_eur, lang)}</dd></div> : null}
        <div><dt>{t('sh.net')}</dt><dd><strong>{eur(f.net_cost_forecast_eur, lang)}</strong></dd></div>
        <div><dt>{t('sh.availability')}</dt><dd><Badge tone={levelTone[o.availability.level]}>{o.availability.text}</Badge></dd></div>
        <div><dt>{t('sh.ean')}</dt><dd>{o.eans.length ? `${o.eans.join(', ')} · ` : ''}{o.ean_status}</dd></div>
      </dl>
      <p className="small muted">{f.disclaimer}</p>
      {f.conditions.length > 0 && <p className="small">{f.conditions.join(' · ')}</p>}
      {[...f.notes, ...o.warnings].length > 0 && (
        <ul className="small warn-list">{[...f.notes, ...o.warnings].map((w) => <li key={w}>{w}</li>)}</ul>
      )}
      <p className="small"><strong>{t('sh.next')} :</strong> {o.action}</p>
      <div className="row gap wrap">
        {o.claim_id
          ? <button className="btn btn-sm btn-primary" onClick={() => openClaim(o.claim_id as number)}>{t('sh.openClaim')}</button>
          : <button className="btn btn-sm btn-primary" onClick={createClaim}>{t(o.kind === 'purchase_game' ? 'sh.newParticipation' : 'sh.newClaim')}</button>}
        {o.status !== 'to_buy' && <button className="btn btn-sm" onClick={() => run(() => api.patchShopOffer(o.id, { status: 'to_buy' }), t('sh.markedToBuy'))}>{t('sh.toBuy')}</button>}
        {o.status === 'to_buy' && <button className="btn btn-sm" onClick={() => run(() => api.patchShopOffer(o.id, { status: 'to_watch' }))}>{t('sh.unToBuy')}</button>}
        <button className="btn btn-sm" onClick={() => setAvail(true)}>{t('sh.addAvail')}</button>
        <button className="btn btn-sm btn-danger" onClick={() => run(() => api.patchShopOffer(o.id, { status: 'ignored' }), t('sh.ignored'))}>{t('sh.ignore')}</button>
      </div>
      <AvailModal open={avail} offer={o} onClose={() => setAvail(false)} run={run} />
    </article>
  );
}

function AvailModal({ open, offer, onClose, run }: { open: boolean; offer: ShopOffer; onClose: () => void; run: Run }) {
  const { t } = useI18n();
  const [retailer, setRetailer] = useState(offer.retailers[0] ?? '');
  const [store, setStore] = useState('');
  const [level, setLevel] = useState('store_confirmed');
  const [price, setPrice] = useState('');
  const [source, setSource] = useState('');
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    await run(() => api.addAvailability(offer.id, { retailer, store: store || undefined, level, price_eur: num(price), source: source || undefined }), t('sh.availSaved'));
    onClose();
  };
  return (
    <Modal open={open} title={t('sh.addAvail')} onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        <label className="field">{t('sh.retailer')}<input required value={retailer} onChange={(e) => setRetailer(e.target.value)} /></label>
        <label className="field">{t('sh.store')}<input value={store} onChange={(e) => setStore(e.target.value)} /></label>
        <label className="field">{t('sh.level')}
          <select value={level} onChange={(e) => setLevel(e.target.value)}>{LEVELS.map((l) => <option key={l} value={l}>{t(`sh.level.${l}`)}</option>)}</select>
        </label>
        <label className="field">{t('sh.price')} (€)<input inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} /></label>
        <label className="field full">{t('sh.source')}<input value={source} required={level !== 'unknown'} onChange={(e) => setSource(e.target.value)} placeholder={t('sh.sourceHint')} /></label>
        <p className="small muted full">{t('sh.availHelp')}</p>
        <div className="full"><button className="btn btn-primary">{t('common.save')}</button></div>
      </form>
    </Modal>
  );
}

// ---------------------------------------------------------------- dossiers
function Claims({ d, claimId, setClaimId, reloadAll }: { d: ShopDashboard; claimId: number | null; setClaimId: (n: number | null) => void; reloadAll: () => void }) {
  const { t } = useI18n();
  const [sec, setSec] = useState<typeof CLAIM_SECTIONS[number]>('claims_to_complete');
  if (claimId !== null) return <ClaimView id={claimId} onBack={() => { setClaimId(null); reloadAll(); }} />;
  const list = d[sec];
  return (
    <>
      <div className="row gap wrap" role="group" aria-label={t('sh.sections')}>
        {CLAIM_SECTIONS.map((k) => (
          <button key={k} className={`btn btn-sm${sec === k ? ' btn-primary' : ''}`} aria-pressed={sec === k} onClick={() => setSec(k)}>
            {t(`sh.sec.${k}`)} <span className="count count-muted">{d[k].length}</span>
          </button>
        ))}
      </div>
      {list.length === 0 ? <p className="empty">{t('sh.noClaim')}</p> : (
        <ul className="stack plain">
          {list.map((c, i) => (
            <li key={`${c.promotion_id}-${c.id ?? i}`} className="card row between wrap gap">
              <span>{c.id ? `#${c.id} ` : ''}{c.promotion_title}</span>
              <span className="row gap wrap">
                <Badge tone={statusTone[c.status]}>{t(`sh.st.${c.status}`)}</Badge>
                {c.late && <Badge tone="bad">{t('sh.late')}</Badge>}
                {c.id && <button className="btn btn-sm" onClick={() => setClaimId(c.id as number)}>{t('sh.open')}</button>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function CheckList({ checks }: { checks: ShopCheck[] }) {
  const { t } = useI18n();
  return (
    <ol className="checks">
      {checks.map((c) => (
        <li key={c.step} className="row gap wrap">
          <Badge tone={checkTone[c.status]}>{t(`sh.chk.${c.status}`)}</Badge>
          <strong>{c.label}</strong>
          <span className="small muted">{c.detail}</span>
        </li>
      ))}
    </ol>
  );
}

function ClaimView({ id, onBack }: { id: number; onBack: () => void }) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const c = useAsync(() => api.shopClaim(id), [id]);
  const [preview, setPreview] = useState<ShopPreview | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const set = (k: string) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const act = async (action: string, body?: Record<string, unknown>, msg?: string) => {
    try { await api.shopClaimAction(id, action, body); c.reload(); if (msg) toast.ok(msg); } catch (e) { toast.err(e); }
  };
  const askPreview = async () => {
    try { const r = await api.shopPreview(id); setPreview(r.preview); c.reload(); } catch (e) { toast.err(e); }
  };
  return (
    <>
      <button className="btn btn-sm" onClick={onBack}>← {t('sh.back')}</button>
      <Async state={c}>
        {(x: ShopClaim) => {
          const st = x.status;
          const open = !['refunded', 'refused', 'cancelled'].includes(st);
          const beforeValidation = ['draft', 'incomplete', 'ready'].includes(st);
          return (
            <div className="stack" style={{ marginTop: '.6rem' }}>
              <section className="card">
                <div className="row between wrap gap">
                  <h2 style={{ margin: 0 }}>#{x.id} {x.promotion_title}</h2>
                  <span className="row gap"><Badge tone={statusTone[st]}>{t(`sh.st.${st}`)}</Badge>{x.late && <Badge tone="bad">{t('sh.late')}</Badge>}</span>
                </div>
                <p className="small muted">
                  {t(x.kind === 'purchase_game' ? 'sh.kind.purchase_game' : 'sh.refundClaim')}
                  {x.purchase_date && <> · {t('sh.bought')} {fmtDate(x.purchase_date, lang)}</>}
                  {x.retailer && <> · {x.retailer}</>}
                  {x.amount_paid_eur !== null && <> · {t('sh.paid')} {eur(x.amount_paid_eur, lang)}</>}
                  {x.amount_requested_eur !== null && <> · {t('sh.requested')} {eur(x.amount_requested_eur, lang)}</>}
                  {x.amount_received_eur !== null && <> · {t('sh.received')} {eur(x.amount_received_eur, lang)}</>}
                </p>
                {x.channel && <p className="small">{t('sh.channel')} : {t(`sh.ch.${x.channel}`)}{x.channel_target && <> · <span className="pre">{x.channel_target}</span></>}</p>}
                <CheckList checks={x.checks ?? []} />
                {open && <button className="btn btn-sm" onClick={() => act('check', undefined, t('sh.checked'))}>{t('sh.recheck')}</button>}
              </section>

              {open && (
                <section className="card">
                  <h3>{t('sh.docs')}</h3>
                  <DocUpload claimId={x.id} onDone={() => c.reload()} />
                  <div className="stack" style={{ marginTop: '.6rem' }}>
                    {(x.documents ?? []).map((doc) => <DocCard key={doc.id} doc={doc} onChange={() => c.reload()} />)}
                  </div>
                </section>
              )}

              {beforeValidation && (
                <section className="card">
                  <h3>{t('sh.purchaseInfo')}</h3>
                  <form className="form-grid" onSubmit={(e) => { e.preventDefault(); void act('purchase', { amount_eur: num(form.amount ?? ''), date: form.date || today() }, t('sh.saved')); }}>
                    <label className="field">{t('sh.paid')} (€)<input required inputMode="decimal" value={form.amount ?? ''} onChange={set('amount')} /></label>
                    <label className="field">{t('sh.purchaseDate')}<input type="date" max={today()} value={form.date ?? ''} onChange={set('date')} /></label>
                    <div><button className="btn">{t('common.save')}</button></div>
                  </form>
                  <form className="form-grid" style={{ marginTop: '.6rem' }} onSubmit={(e) => { e.preventDefault(); void act('codes', { codes: (form.codes ?? '').split(/[\s,;]+/) }, t('sh.saved')); }}>
                    <label className="field wide">{t('sh.codes')}<input value={form.codes ?? (x.codes ?? []).join(' ')} onChange={set('codes')} /></label>
                    <div><button className="btn">{t('common.save')}</button></div>
                  </form>
                  <p className="small muted">{t('sh.purchaseHelp')}</p>
                  <div><button className="btn btn-primary" onClick={askPreview}>{t('sh.askValidation')}</button></div>
                </section>
              )}

              {st === 'awaiting_validation' && <div><button className="btn btn-primary" onClick={askPreview}>{t('sh.reviewValidate')}</button></div>}

              {st === 'validated' && (
                <section className="card">
                  <h3>{t('sh.transmit')}</h3>
                  <p className="small">{t('sh.transmitHelp')}</p>
                  <form className="form-grid" onSubmit={(e) => { e.preventDefault(); void act('sent', { sent_on: form.sent || today(), confirmation_ref: form.ref || undefined }, t('sh.sentSaved')); }}>
                    <label className="field">{t('sh.sentOn')}<input type="date" max={today()} value={form.sent ?? ''} onChange={set('sent')} /></label>
                    <label className="field">{t('sh.ref')}<input value={form.ref ?? ''} onChange={set('ref')} /></label>
                    <div><button className="btn btn-primary">{t('sh.markSent')}</button></div>
                  </form>
                </section>
              )}

              {['sent', 'confirmed', 'refund_pending'].includes(st) && (
                <section className="card">
                  <h3>{t('sh.follow')}</h3>
                  {st === 'sent' && (
                    <form className="form-grid" onSubmit={(e) => { e.preventDefault(); void act('confirm', { confirmation_ref: form.cref || undefined, amount_eur: num(form.camount ?? '') }, t('sh.saved')); }}>
                      <label className="field">{t('sh.ref')}<input value={form.cref ?? ''} onChange={set('cref')} /></label>
                      <label className="field">{t('sh.confirmedAmount')} (€)<input inputMode="decimal" value={form.camount ?? ''} onChange={set('camount')} /></label>
                      <div><button className="btn">{t('sh.markConfirmed')}</button></div>
                    </form>
                  )}
                  {x.kind === 'refund' && (
                    <form className="form-grid" style={{ marginTop: '.6rem' }} onSubmit={(e) => { e.preventDefault(); void act('refunded', { amount_eur: num(form.ramount ?? ''), received_on: form.rdate || undefined }, t('sh.refundSaved')); }}>
                      <label className="field">{t('sh.receivedAmount')} (€)<input required inputMode="decimal" value={form.ramount ?? ''} onChange={set('ramount')} /></label>
                      <label className="field">{t('sh.receivedOn')}<input type="date" required max={today()} value={form.rdate ?? ''} onChange={set('rdate')} /></label>
                      <div><button className="btn btn-ok">{t('sh.markRefunded')}</button></div>
                    </form>
                  )}
                  <p className="small muted">{t('sh.refundHelp')}</p>
                  <form className="form-grid" style={{ marginTop: '.6rem' }} onSubmit={(e) => { e.preventDefault(); void act('refused', { reason: form.reason ?? '' }, t('sh.saved')); }}>
                    <label className="field wide">{t('sh.refusalReason')}<input required value={form.reason ?? ''} onChange={set('reason')} /></label>
                    <div><button className="btn btn-danger">{t('sh.markRefused')}</button></div>
                  </form>
                </section>
              )}

              {x.refusal_reason && <p className="alert alert-err">{t('sh.refusalReason')} : {x.refusal_reason}</p>}
              {open && <div><button className="btn btn-sm btn-danger" onClick={() => act('cancel', undefined, t('sh.cancelled'))}>{t('sh.cancelClaim')}</button></div>}

              {(x.history ?? []).length > 0 && (
                <details className="card"><summary>{t('sh.history')}</summary>
                  <ul className="small">{(x.history ?? []).map((h, i) => <li key={i}>{fmtDate(h.at, lang, true)} · {h.event}{h.detail ? ` · ${h.detail}` : ''}</li>)}</ul>
                </details>
              )}
              <ValidateModal claim={x} preview={preview} onClose={() => setPreview(null)} onDone={() => { setPreview(null); c.reload(); }} />
            </div>
          );
        }}
      </Async>
    </>
  );
}

function ValidateModal({ claim, preview, onClose, onDone }: { claim: ShopClaim; preview: ShopPreview | null; onClose: () => void; onDone: () => void }) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const [ok, setOk] = useState(false);
  const [sensitiveOk, setSensitiveOk] = useState(false);
  if (!preview) return null;
  const hasSensitive = preview.documents.some((d) => d.sensitive);
  const channelBad = preview.channel_status === 'fail';
  const validate = async () => {
    try {
      await api.shopClaimAction(claim.id, 'validate', { confirm: true, document_ids: preview.documents.map((d) => d.id) });
      toast.ok(t('sh.validated'));
      setOk(false); setSensitiveOk(false);
      onDone();
    } catch (e) { toast.err(e); }
  };
  return (
    <Modal open title={t('sh.validationTitle')} onClose={onClose}>
      <p className="alert alert-warn small">{preview.warning}</p>
      <dl className="kv small">
        <div><dt>{t('sh.channel')}</dt><dd>{preview.channel ? t(`sh.ch.${preview.channel}`) : '—'} {preview.channel_target && <span className="pre">{preview.channel_target}</span>}</dd></div>
        <div><dt>{t('sh.channelCheck')}</dt><dd><Badge tone={checkTone[preview.channel_status]}>{preview.channel_detail}</Badge></dd></div>
        <div><dt>{t('sh.docs')}</dt><dd>{preview.documents.map((d) => `${t(`sh.doc.${d.kind}`)}${d.sensitive ? ` (${t('sh.sensitive')})` : ''}`).join(', ') || '—'}</dd></div>
        <div><dt>{t('sh.personal')}</dt><dd>{preview.personal_data.join(', ')}</dd></div>
        {preview.physical_items.length > 0 && <div><dt>{t('sh.physical')}</dt><dd>{preview.physical_items.join(', ')}</dd></div>}
        {preview.codes && preview.codes.length > 0 && <div><dt>{t('sh.codes')}</dt><dd>{preview.codes.join(', ')}</dd></div>}
        <div><dt>{t('sh.requested')}</dt><dd>{eur(preview.amount_requested_eur, lang)}</dd></div>
      </dl>
      {channelBad ? <p className="alert alert-err">{t('sh.channelBlocked')}</p> : (
        <>
          <label className="field inline"><input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} /> {t('sh.confirmValidation')}</label>
          {hasSensitive && <label className="field inline"><input type="checkbox" checked={sensitiveOk} onChange={(e) => setSensitiveOk(e.target.checked)} /> {t('sh.confirmSensitive')}</label>}
          <div className="row gap" style={{ marginTop: '.6rem' }}>
            <button className="btn btn-primary" disabled={!ok || (hasSensitive && !sensitiveOk)} onClick={validate}>{t('sh.validate')}</button>
            <button className="btn" onClick={onClose}>{t('common.cancel')}</button>
          </div>
        </>
      )}
    </Modal>
  );
}

// ---------------------------------------------------------------- justificatifs
function DocUpload({ claimId, onDone }: { claimId?: number; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [kind, setKind] = useState('receipt');
  const [file, setFile] = useState<File | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    try {
      await api.addShopDoc({ kind, data_url: await readFile(file), claim_id: claimId });
      toast.ok(t('sh.docAdded'));
      setFile(null);
      (e.target as HTMLFormElement).reset();
      onDone();
    } catch (err) { toast.err(err); }
  };
  return (
    <form className="form-grid" onSubmit={submit}>
      <label className="field">{t('sh.docKind')}
        <select value={kind} onChange={(e) => setKind(e.target.value)}>{DOC_KINDS.map((k) => <option key={k} value={k}>{t(`sh.doc.${k}`)}</option>)}</select>
      </label>
      <label className="field wide">{t('sh.file')}<input type="file" required accept="image/png,image/jpeg,image/webp,application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></label>
      <div><button className="btn" disabled={!file}>{t('sh.addDoc')}</button></div>
      <p className="small muted full">{t('sh.docHelp')}</p>
    </form>
  );
}

const FIELD_KEYS = ['retailer', 'store', 'purchase_date', 'ticket_number', 'total_eur', 'ean'] as const;

function DocCard({ doc, onChange }: { doc: ShopDoc; onChange: () => void }) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const [text, setText] = useState(doc.ocr_text ?? '');
  const [edit, setEdit] = useState<Record<string, string>>({});
  const f = doc.fields;
  const lines = Array.isArray(f.lines) ? (f.lines as unknown[]).map((l) => {
    if (l && typeof l === 'object') { const o = l as { label?: string; price_eur?: number }; return `${o.label ?? ''}${o.price_eur !== undefined ? ` (${eur(o.price_eur, lang)})` : ''}`; }
    return String(l);
  }) : [];
  const call = async (fn: () => Promise<unknown>, msg: string) => { try { await fn(); toast.ok(msg); onChange(); } catch (e) { toast.err(e); } };
  const openFile = async () => {
    if (doc.sensitive && !window.confirm(t('sh.confirmOpenSensitive'))) return;
    try {
      const headers: Record<string, string> = {};
      const tok = getToken();
      if (tok) headers['X-CH-Token'] = tok;
      const r = await fetch(`/api/shop/documents/${doc.id}/file${doc.sensitive ? '?confirm=true' : ''}`, { headers });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const url = URL.createObjectURL(await r.blob());
      window.open(url, '_blank', 'noopener');
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (e) { toast.err(e); }
  };
  const saveFields = (e: FormEvent) => {
    e.preventDefault();
    const body: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(edit)) body[k] = k === 'total_eur' ? num(v) ?? null : v;
    void call(() => api.patchShopDoc(doc.id, body), t('sh.saved'));
  };
  return (
    <article className="card">
      <div className="row between wrap gap">
        <strong>#{doc.id} {t(`sh.doc.${doc.kind}`)}</strong>
        <span className="row gap wrap">
          {doc.sensitive && <Badge tone="warn">{t('sh.sensitive')}</Badge>}
          {doc.readability && <Badge tone={doc.readability === 'ok' ? 'ok' : doc.readability === 'unreadable' ? 'bad' : 'warn'}>{t(`sh.read.${doc.readability}`)}</Badge>}
          <button className="btn btn-sm" onClick={openFile}>{t('sh.openFile')}</button>
        </span>
      </div>
      <p className="small muted">{doc.mime} · {Math.round(doc.size / 1024)} Ko · {fmtDate(doc.created_at, lang, true)} · SHA-256 {doc.sha256.slice(0, 12)}…</p>
      <dl className="kv small">
        {FIELD_KEYS.filter((k) => f[k] !== undefined && f[k] !== null && f[k] !== '').map((k) => <div key={k}><dt>{t(`sh.f.${k}`)}</dt><dd>{String(f[k])}</dd></div>)}
        {lines.length > 0 && <div><dt>{t('sh.f.lines')}</dt><dd>{lines.join(' · ')}</dd></div>}
      </dl>
      {Array.isArray(f.missing) && (f.missing as unknown[]).length > 0 && <p className="small warn">{t('sh.missing')} : {(f.missing as unknown[]).join(', ')}</p>}
      <details>
        <summary>{t('sh.ocr')}</summary>
        <p className="small muted">{t('sh.ocrHelp')}</p>
        <label className="sr-only" htmlFor={`ocr-${doc.id}`}>{t('sh.ocr')}</label>
        <textarea id={`ocr-${doc.id}`} rows={5} value={text} onChange={(e) => setText(e.target.value)} style={{ width: '100%' }} />
        <div className="row gap wrap">
          <button className="btn btn-sm" onClick={() => call(() => api.ocrShopDoc(doc.id, text), t('sh.ocrDone'))} disabled={!text.trim()}>{t('sh.useText')}</button>
          <button className="btn btn-sm" onClick={() => call(() => api.ocrShopDoc(doc.id), t('sh.ocrDone'))}>{t('sh.autoOcr')}</button>
        </div>
      </details>
      <details>
        <summary>{t('sh.correct')}</summary>
        <p className="small muted">{t('sh.correctHelp')}</p>
        <form className="form-grid" onSubmit={saveFields}>
          {FIELD_KEYS.map((k) => (
            <label key={k} className="field">{t(`sh.f.${k}`)}
              <input type={k === 'purchase_date' ? 'date' : 'text'} value={edit[k] ?? String(f[k] ?? '')} onChange={(e) => setEdit((s) => ({ ...s, [k]: e.target.value }))} />
            </label>
          ))}
          <div><button className="btn btn-sm">{t('common.save')}</button></div>
        </form>
      </details>
    </article>
  );
}

function Documents() {
  const { t } = useI18n();
  const docs = useAsync(() => api.shopDocs(), []);
  return (
    <>
      <section className="card"><h3>{t('sh.addDoc')}</h3><DocUpload onDone={docs.reload} /></section>
      <Async state={docs} isEmpty={(l) => l.length === 0} empty={t('sh.noDoc')}>
        {(l) => <div className="stack">{l.map((d) => <DocCard key={d.id} doc={d} onChange={docs.reload} />)}</div>}
      </Async>
    </>
  );
}

// ---------------------------------------------------------------- dépenses
function Expenses() {
  const { t, lang } = useI18n();
  const toast = useToast();
  const [month, setMonth] = useState<string>(today().slice(0, 7));
  const m = useAsync(() => api.shopExpenses(month), [month]);
  const h = useAsync(() => api.shopHistory(), []);
  const [gain, setGain] = useState('');
  const [gainNote, setGainNote] = useState('');
  const addGain = async (e: FormEvent) => {
    e.preventDefault();
    const v = num(gain);
    if (!v) return;
    try { await api.shopGain({ amount_eur: v, note: gainNote || undefined }); setGain(''); setGainNote(''); m.reload(); h.reload(); toast.ok(t('sh.saved')); } catch (err) { toast.err(err); }
  };
  const KEYS = ['expenses_eur', 'savings_realized_eur', 'refunds_pending_eur', 'refunds_refused_eur', 'random_gains_eur', 'net_real_cost_eur', 'cap_left_eur'] as const;
  return (
    <>
      <div className="row gap wrap">
        <label className="field inline">{t('sh.month')}<input type="month" value={month} onChange={(e) => setMonth(e.target.value)} /></label>
      </div>
      <Async state={m}>
        {(s) => (
          <>
            <section className="tiles" aria-label={t('sh.tab.expenses')} style={{ marginTop: '.6rem' }}>
              {KEYS.map((k) => (
                <div key={k} className={`tile${k === 'cap_left_eur' && s.cap_left_eur < 0 ? ' tile-bad' : ''}`}>
                  <div className="tile-label">{t(`sh.m.${k}`)}</div><div className="tile-value">{eur(s[k], lang)}</div>
                </div>
              ))}
            </section>
            <p className="small muted">{s.note} {t('sh.capIs', { cap: eur(s.monthly_cap_eur, lang) })}</p>
            {(s.entries ?? []).length > 0 && (
              <div className="table-wrap">
                <table className="table small">
                  <thead><tr><th>{t('sh.date')}</th><th>{t('sh.entry')}</th><th>{t('sh.amount')}</th><th>{t('sh.note')}</th></tr></thead>
                  <tbody>{(s.entries ?? []).map((e, i) => (
                    <tr key={i}><td>{fmtDate(e.at, lang)}</td><td>{t(`sh.l.${e.kind}`)}</td><td>{eur(e.amount_eur, lang)}</td><td>{e.note}</td></tr>
                  ))}</tbody>
                </table>
              </div>
            )}
          </>
        )}
      </Async>
      <section className="card" style={{ marginTop: '1rem' }}>
        <h3>{t('sh.addGain')}</h3>
        <form className="form-grid" onSubmit={addGain}>
          <label className="field">{t('sh.amount')} (€)<input required inputMode="decimal" value={gain} onChange={(e) => setGain(e.target.value)} /></label>
          <label className="field wide">{t('sh.note')}<input value={gainNote} onChange={(e) => setGainNote(e.target.value)} /></label>
          <div><button className="btn">{t('common.save')}</button></div>
        </form>
        <p className="small muted">{t('sh.gainHelp')}</p>
      </section>
      <Async state={h}>
        {(l) => (
          <details className="card"><summary>{t('sh.history12')}</summary>
            <div className="table-wrap">
              <table className="table small">
                <thead><tr><th>{t('sh.month')}</th><th>{t('sh.m.expenses_eur')}</th><th>{t('sh.m.savings_realized_eur')}</th><th>{t('sh.m.refunds_pending_eur')}</th><th>{t('sh.m.net_real_cost_eur')}</th></tr></thead>
                <tbody>{l.map((r) => <tr key={r.month}><td>{r.month}</td><td>{eur(r.expenses_eur, lang)}</td><td>{eur(r.savings_realized_eur, lang)}</td><td>{eur(r.refunds_pending_eur, lang)}</td><td>{eur(r.net_real_cost_eur, lang)}</td></tr>)}</tbody>
              </table>
            </div>
          </details>
        )}
      </Async>
    </>
  );
}

// ---------------------------------------------------------------- analyse
const ANALYZE_KEYS = ['kind', 'brand', 'refund_percent', 'refund_eur', 'refund_max_eur', 'purchase_start', 'end_date', 'send_deadline', 'request_delay_days',
  'refund_delay_days', 'eans', 'variant', 'retailers', 'limit_per', 'limit_count', 'cumulable', 'channel', 'channel_target', 'required_docs', 'fees_eur',
  'prize_value_eur', 'reliability', 'category'];

function Analyze({ onSaved }: { onSaved: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [text, setText] = useState('');
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [res, setRes] = useState<Record<string, unknown> | null>(null);
  const go = async (save: boolean) => {
    try {
      const r = await api.shopAnalyze({ text, url: url || undefined, title: title || undefined, save });
      if (save) { toast.ok(t('sh.analyzeSaved')); onSaved(); } else if ('analysis' in r) setRes(r.analysis);
    } catch (e) { toast.err(e); }
  };
  const show = (v: unknown) => (Array.isArray(v) ? v.join(', ') : v && typeof v === 'object' ? Object.entries(v).map(([k, x]) => `${k} : ${String(x)}`).join(' · ') : String(v));
  const warnings = res && Array.isArray(res.warnings) ? (res.warnings as unknown[]).map(String) : [];
  const evidence = res && res.evidence && typeof res.evidence === 'object' ? Object.entries(res.evidence as Record<string, unknown>) : [];
  return (
    <section className="card">
      <p className="small muted">{t('sh.analyzeHelp')}</p>
      <div className="form-grid">
        <label className="field">{t('sh.offerTitle')}<input value={title} onChange={(e) => setTitle(e.target.value)} /></label>
        <label className="field wide">{t('sh.rulesUrl')}<input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" /></label>
        <label className="field full">{t('sh.rulesText')}<textarea rows={10} value={text} onChange={(e) => setText(e.target.value)} /></label>
      </div>
      <div className="row gap wrap" style={{ marginTop: '.6rem' }}>
        <button className="btn" disabled={!text.trim()} onClick={() => go(false)}>{t('sh.analyze')}</button>
        <button className="btn btn-primary" disabled={!text.trim()} onClick={() => go(true)}>{t('sh.analyzeSave')}</button>
      </div>
      {res && (
        <div style={{ marginTop: '1rem' }}>
          <dl className="kv small">
            {ANALYZE_KEYS.filter((k) => res[k] !== null && res[k] !== undefined && !(Array.isArray(res[k]) && (res[k] as unknown[]).length === 0)).map((k) => (
              <div key={k}><dt>{t(`sh.a.${k}`)}</dt><dd>{show(res[k])}</dd></div>
            ))}
          </dl>
          {warnings.length > 0 && <ul className="small warn-list">{warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
          {evidence.length > 0 && (
            <details><summary>{t('sh.evidence')}</summary>
              <ul className="small">{evidence.map(([k, v]) => <li key={k}><strong>{k}</strong> : « {String(v)} »</li>)}</ul>
            </details>
          )}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- réglages
const list = (s: string) => s.split(/[,\n]/).map((x) => x.trim()).filter(Boolean);

function Settings({ onSaved }: { onSaved: () => void }) {
  const p = useAsync(() => api.shopPrefs(), []);
  return <Async state={p}>{(x) => <SettingsForm key={JSON.stringify(x)} p={x} onSaved={() => { p.reload(); onSaved(); }} />}</Async>;
}

function SettingsForm({ p, onSaved }: { p: ShopPrefs; onSaved: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [v, setV] = useState({
    retailers: p.retailers.join(', '), stores: p.stores.map((s) => `${s.retailer} | ${s.name}`).join('\n'), postal_code: p.postal_code,
    radius_km: String(p.radius_km), categories: p.categories.join(', '), max_price_eur: String(p.max_price_eur), monthly_cap_eur: String(p.monthly_cap_eur),
    accepted_products: p.accepted_products.join(', '), refused_products: p.refused_products.join(', '), min_category: p.min_category,
  });
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV((s) => ({ ...s, [k]: e.target.value }));
  const save = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api.putShopPrefs({
        retailers: list(v.retailers),
        stores: v.stores.split('\n').map((l) => l.split('|').map((x) => x.trim())).filter((a) => a[1]).map(([retailer, name]) => ({ retailer, name })),
        postal_code: v.postal_code.trim(), radius_km: num(v.radius_km), categories: list(v.categories), max_price_eur: num(v.max_price_eur),
        monthly_cap_eur: num(v.monthly_cap_eur), accepted_products: list(v.accepted_products), refused_products: list(v.refused_products),
        min_category: v.min_category as ShopPrefs['min_category'],
      });
      toast.ok(t('sh.prefsSaved'));
      onSaved();
    } catch (err) { toast.err(err); }
  };
  return (
    <form className="card form-grid" onSubmit={save}>
      <label className="field full">{t('sh.p.retailers')}<input value={v.retailers} onChange={set('retailers')} /></label>
      <label className="field full">{t('sh.p.stores')}<textarea rows={3} value={v.stores} onChange={set('stores')} placeholder="Carrefour | Carrefour Montpellier Lattes" /></label>
      <label className="field">{t('sh.p.postal_code')}<input value={v.postal_code} onChange={set('postal_code')} inputMode="numeric" /></label>
      <label className="field">{t('sh.p.radius_km')}<input value={v.radius_km} onChange={set('radius_km')} inputMode="numeric" /></label>
      <label className="field">{t('sh.p.max_price_eur')}<input value={v.max_price_eur} onChange={set('max_price_eur')} inputMode="decimal" /></label>
      <label className="field">{t('sh.p.monthly_cap_eur')}<input value={v.monthly_cap_eur} onChange={set('monthly_cap_eur')} inputMode="decimal" /></label>
      <label className="field">{t('sh.p.min_category')}
        <select value={v.min_category} onChange={set('min_category')}>{['A', 'B', 'C'].map((c) => <option key={c} value={c}>{c}</option>)}</select>
      </label>
      <label className="field full">{t('sh.p.categories')}<input value={v.categories} onChange={set('categories')} /></label>
      <label className="field full">{t('sh.p.accepted_products')}<input value={v.accepted_products} onChange={set('accepted_products')} /></label>
      <label className="field full">{t('sh.p.refused_products')}<input value={v.refused_products} onChange={set('refused_products')} /></label>
      <div className="full"><button className="btn btn-primary">{t('common.save')}</button></div>
    </form>
  );
}
