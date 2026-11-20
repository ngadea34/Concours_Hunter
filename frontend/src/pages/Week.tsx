import { useState, type FormEvent, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { Async } from '../components/Async';
import { Badge, type Tone } from '../components/Badge';
import { Modal } from '../components/Modal';
import { PageHeader } from '../components/PageHeader';
import { useToast } from '../components/Toast';
import { useAsync } from '../hooks';
import { useI18n } from '../i18n';
import type { PromoBrief, WeekContest, WeekItem, WeekPrefs, WeekReport, WeekTask, WeekView } from '../types';
import { fmtDate, fmtEur, safeHref } from '../util';

const TABS = ['program', 'results', 'deadlines', 'opportunities', 'shop', 'tasks', 'reports', 'settings'] as const;
type Tab = typeof TABS[number];
const prioTone: Record<string, Tone> = { high: 'bad', medium: 'warn', low: 'neutral' };
const RESULT_MANUAL = ['draw_pending', 'drawn', 'not_published', 'published', 'not_winner', 'unverifiable'];
const TASK_STATUSES = ['todo', 'in_progress', 'waiting', 'done', 'cancelled', 'expired'];
const PROMO_STATUSES = ['to_watch', 'to_buy', 'bought', 'to_send', 'sent', 'refund_pending', 'refunded', 'refused', 'expired', 'cancelled'];
const PROMO_KINDS = ['full_refund', 'partial_refund', 'purchase_game', 'discount'];

function addDays(iso: string, n: number): string {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

function readFile(f: File): Promise<string> {
  return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(String(r.result)); r.onerror = rej; r.readAsDataURL(f); });
}

export function Week() {
  const { t, lang } = useI18n();
  const toast = useToast();
  const [week, setWeek] = useState<string | undefined>(undefined);
  const [tab, setTab] = useState<Tab>('program');
  const [cmd, setCmd] = useState('/hunter-week ');
  const [cmdOut, setCmdOut] = useState<string | null>(null);
  const v = useAsync(() => api.week(week), [week]);

  const run = async (fn: () => Promise<unknown>, msg?: string) => {
    try { const r = await fn(); if (r && typeof r === 'object' && 'kpis' in (r as object)) v.setData(r as WeekView); else v.reload(); if (msg) toast.ok(msg); }
    catch (e) { toast.err(e); }
  };
  const onCmd = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const r = await api.weekCommand(cmd);
      if ((TABS as readonly string[]).includes(r.tab)) setTab(r.tab as Tab);
      if (r.week) setWeek(r.week);
      setCmdOut(r.text);
      v.reload();
    } catch (err) { toast.err(err); }
  };

  return (
    <>
      <PageHeader title={t('wk.title')}>
        <button className="btn" onClick={() => v.reload()}>{t('common.refresh')}</button>
      </PageHeader>
      <Async state={v}>
        {(w) => (
          <>
            <section className="card no-print">
              <div className="row between wrap gap">
                <div className="row gap wrap">
                  <button className="btn" onClick={() => setWeek(addDays(w.week_start, -7))} aria-label={t('wk.prev')}>◀</button>
                  <strong>{w.label}</strong>
                  <span className="muted">{fmtDate(w.week_start, lang)} → {fmtDate(w.week_end, lang)}</span>
                  <button className="btn" onClick={() => setWeek(addDays(w.week_start, 7))} aria-label={t('wk.next')}>▶</button>
                  {!w.is_current && <button className="btn btn-sm" onClick={() => setWeek(undefined)}>{t('wk.thisWeek')}</button>}
                  {w.is_past && <Badge>{t('wk.past')}</Badge>}
                </div>
                {!w.is_past && <button className="btn btn-primary" onClick={() => run(() => api.makePlan(w.week_start), t('wk.planned'))}>{t('wk.makePlan')}</button>}
              </div>
              <form className="row gap wrap" onSubmit={onCmd} style={{ marginTop: '.6rem' }}>
                <label htmlFor="wk-cmd" className="sr-only">{t('wk.command')}</label>
                <input id="wk-cmd" value={cmd} onChange={(e) => setCmd(e.target.value)} style={{ flex: 1, minWidth: '12rem' }}
                  placeholder="/hunter-week plan | results | deadlines | opportunities | tasks | report | next | settings" />
                <button className="btn">{t('wk.run')}</button>
              </form>
            </section>

            <section className="tiles" aria-label={t('wk.kpis')}>
              {(['priority', 'done', 'closing', 'results_expected', 'results_published', 'gains_to_claim', 'promotions', 'refund_files'] as const).map((k) => (
                <div key={k} className="tile"><div className="tile-label">{t(`wk.kpi.${k}`)}</div><div className="tile-value">{w.kpis[k]}</div></div>
              ))}
            </section>
            <p className="muted small">
              {t('wk.time')} : {w.plan.planned_minutes} / {w.plan.capacity_minutes} min · {t('wk.goal')} : {w.plan.weekly_goal} · {w.timezone}
            </p>

            <div className="tabs no-print" role="tablist">
              {TABS.map((k) => (
                <button key={k} role="tab" aria-selected={tab === k} className={`btn btn-sm${tab === k ? ' btn-primary' : ''}`} onClick={() => setTab(k)}>
                  {t(`wk.tab.${k}`)}
                </button>
              ))}
            </div>

            {tab === 'program' && <Program w={w} run={run} />}
            {tab === 'results' && <Results w={w} run={run} />}
            {tab === 'deadlines' && <Deadlines w={w} />}
            {tab === 'opportunities' && <Opportunities w={w} run={run} />}
            {tab === 'shop' && <Shop w={w} run={run} />}
            {tab === 'tasks' && <Tasks w={w} run={run} />}
            {tab === 'reports' && <Reports week={w.week_start} />}
            {tab === 'settings' && <Settings onSaved={() => v.reload()} />}
          </>
        )}
      </Async>
      <Modal open={cmdOut !== null} title={t('wk.command')} onClose={() => setCmdOut(null)}>
        <pre className="pre small">{cmdOut}</pre>
      </Modal>
    </>
  );
}

type Run = (fn: () => Promise<unknown>, msg?: string) => Promise<void>;

function ContestLine({ c, head, children }: { c: WeekContest; head?: ReactNode; children?: ReactNode }) {
  const { t, lang } = useI18n();
  const href = safeHref(c.url);
  return (
    <article className="card">
      <div className="row between wrap gap">
        <h3 style={{ margin: 0 }}><Link to={`/contests/${c.contest_id}`}>{c.title}</Link></h3>
        {head}
      </div>
      <p className="small muted">
        {c.organizer && <>{c.organizer} · </>}
        {c.prize && <>{c.prize} · </>}
        {c.value_eur ? <>{fmtEur(c.value_eur, lang)} · </> : null}
        {c.end_date ? <>{t('wk.until')} {fmtDate(c.end_date, lang)}{!c.end_date_verified && ' (?)'} · </> : null}
        ~{c.est_minutes} min
        {href && <> · <a href={href} target="_blank" rel="noopener noreferrer">{t('wk.official')}</a></>}
      </p>
      {c.conditions.length > 0 && <p className="small">{c.conditions.join(' · ')}</p>}
      {children}
    </article>
  );
}

function Program({ w, run }: { w: WeekView; run: Run }) {
  const { t, lang } = useI18n();
  const [doneFor, setDoneFor] = useState<WeekItem | null>(null);
  const [note, setNote] = useState('');
  const [minutes, setMinutes] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [postpone, setPostpone] = useState<Record<number, string>>({});
  if (w.priority.length === 0) return <p className="empty">{t('wk.noPriority')}</p>;
  const submitDone = async (e: FormEvent) => {
    e.preventDefault();
    if (!doneFor) return;
    const data_url = file ? await readFile(file) : undefined;
    await run(() => api.weekItemDone(doneFor.item_id, { proof_note: note.trim() || undefined, data_url, minutes: minutes ? Number(minutes) : undefined }), t('wk.doneSaved'));
    setDoneFor(null); setNote(''); setMinutes(''); setFile(null);
  };
  return (
    <>
      {w.priority.map((i) => (
        <ContestLine key={i.item_id} c={i} head={
          <div className="badges">
            <Badge tone={prioTone[i.priority]}>{t(`wk.prio.${i.priority}`)}</Badge>
            <Badge tone={i.decision === 'accepted' ? 'ok' : i.decision === 'done' ? 'info' : 'neutral'}>{t(`wk.dec.${i.decision}`)}</Badge>
            <Badge>{i.scheduled_day ? `${t('wk.on')} ${fmtDate(i.scheduled_day, lang)}` : t('wk.ifTime')}</Badge>
            {i.favorite && <Badge tone="warn">★</Badge>}
          </div>}>
          <details className="small" style={{ width: '100%' }}><summary>{t('wk.why')}</summary><ul>{i.reasons.map((r) => <li key={r}>{r}</li>)}</ul></details>
          {!w.is_past && !['done', 'obsolete'].includes(i.decision) && (
            <div className="row gap wrap" style={{ width: '100%' }}>
              <button className="btn btn-sm btn-ok" onClick={() => run(() => api.weekItem(i.item_id, 'accept'))}>{t('wk.accept')}</button>
              <button className="btn btn-sm" onClick={() => run(() => api.weekItem(i.item_id, 'refuse'))}>{t('wk.refuse')}</button>
              <input type="date" className="input-auto" aria-label={t('wk.postponeTo')} value={postpone[i.item_id] ?? ''} min={w.today} max={i.end_date ?? undefined}
                onChange={(e) => setPostpone({ ...postpone, [i.item_id]: e.target.value })} />
              <button className="btn btn-sm" disabled={!postpone[i.item_id]} onClick={() => run(() => api.weekItem(i.item_id, 'postpone', postpone[i.item_id]))}>{t('wk.postpone')}</button>
              <button className="btn btn-sm" onClick={() => run(() => api.weekItem(i.item_id, i.favorite ? 'unfavorite' : 'favorite'))}>{i.favorite ? t('wk.unfav') : t('wk.fav')}</button>
              <button className="btn btn-sm" onClick={() => setDoneFor(i)}>{t('wk.markDone')}</button>
            </div>
          )}
        </ContestLine>
      ))}
      <Modal open={doneFor !== null} title={t('wk.markDone')} onClose={() => setDoneFor(null)}>
        <form className="stack" onSubmit={submitDone}>
          <p className="note small">{t('wk.proofHelp')}</p>
          <div className="field"><label htmlFor="pf-note">{t('wk.proofNote')}</label>
            <textarea id="pf-note" rows={3} value={note} onChange={(e) => setNote(e.target.value)} /></div>
          <div className="field"><label htmlFor="pf-file">{t('wk.proofFile')}</label>
            <input id="pf-file" type="file" accept="image/png,image/jpeg" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></div>
          <div className="field"><label htmlFor="pf-min">{t('wk.minutes')}</label>
            <input id="pf-min" type="number" min={0} value={minutes} onChange={(e) => setMinutes(e.target.value)} /></div>
          <button className="btn btn-primary" disabled={note.trim().length < 10 && !file}>{t('common.save')}</button>
        </form>
      </Modal>
    </>
  );
}

function Results({ w, run }: { w: WeekView; run: Run }) {
  const { t, lang } = useI18n();
  if (w.results.length === 0) return <p className="empty">{t('wk.noResults')}</p>;
  return (
    <div className="table-wrap"><table>
      <thead><tr>
        <th scope="col">{t('wk.contest')}</th><th scope="col">{t('wk.draw')}</th><th scope="col">{t('wk.publish')}</th>
        <th scope="col">{t('common.status')}</th><th scope="col">{t('wk.checked')}</th>
      </tr></thead>
      <tbody>{w.results.map((r) => {
        const href = safeHref(r.verify_url);
        return (
          <tr key={r.id}>
            <th scope="row"><Link to={`/contests/${r.contest_id}`}>{r.title}</Link>{r.organizer && <div className="small muted">{r.organizer}</div>}
              {r.prizes_count ? <div className="small muted">{r.prizes_count} {t('wk.prizes')}</div> : null}
              {href && <div className="small"><a href={href} target="_blank" rel="noopener noreferrer">{t('wk.verify')}</a></div>}
              {r.note && <div className="small">{r.note}</div>}</th>
            <td>{fmtDate(r.draw_date, lang)}{r.draw_date_estimated && <div className="small muted">{t('wk.estimated')}</div>}</td>
            <td>{fmtDate(r.publish_date, lang)}</td>
            <td>
              {['winner'].includes(r.status) ? <Badge tone="ok">{t(`wk.res.${r.status}`)}</Badge> : (
                <select aria-label={t('common.status')} value={r.status} onChange={(e) => run(() => api.patchWeekResult(r.id, { status: e.target.value }), t('wk.saved'))}>
                  {[...new Set([r.status, ...RESULT_MANUAL])].map((s) => <option key={s} value={s}>{t(`wk.res.${s}`)}</option>)}
                </select>
              )}
            </td>
            <td>{fmtDate(r.last_checked_at, lang, true)}</td>
          </tr>
        );
      })}</tbody>
    </table><p className="small muted" style={{ padding: '0 .6rem' }}>{t('wk.winHelp')}</p></div>
  );
}

function Deadlines({ w }: { w: WeekView }) {
  const { t } = useI18n();
  const groups = (['h24', 'h48', 'd7', 'd14'] as const);
  if (groups.every((g) => w.last_chances[g].length === 0)) return <p className="empty">{t('wk.noDeadlines')}</p>;
  return (
    <>
      {groups.map((g) => w.last_chances[g].length > 0 && (
        <section key={g}>
          <h2>{t(`wk.lc.${g}`)} ({w.last_chances[g].length})</h2>
          {w.last_chances[g].map((c) => <ContestLine key={c.contest_id} c={c} head={<Badge>{t(`status.${c.status}`)}</Badge>} />)}
        </section>
      ))}
    </>
  );
}

function Opportunities({ w, run }: { w: WeekView; run: Run }) {
  const { t } = useI18n();
  if (w.opportunities.length === 0) return <p className="empty">{t('wk.noOpp')}</p>;
  return (
    <>
      <p className="muted small">{t('wk.oppHelp')}</p>
      {w.opportunities.map((o) => (
        <ContestLine key={o.contest_id} c={o} head={
          <div className="row gap wrap">
            <button className="btn btn-sm" onClick={() => run(() => api.followOpportunity({ contest_id: o.contest_id, follow: !o.followed }), t('wk.saved'))}>
              {o.followed ? t('wk.unfollow') : t('wk.follow')}
            </button>
            <button className="btn btn-sm" onClick={() => run(() => api.followOpportunity({ contest_id: o.contest_id, dismiss: true }), t('wk.saved'))}>{t('wk.dismiss')}</button>
          </div>}>
          <ul className="small" style={{ width: '100%', margin: 0 }}>{o.why.map((x) => <li key={x}>{x}</li>)}</ul>
        </ContestLine>
      ))}
    </>
  );
}

function PromoRow({ p, run }: { p: PromoBrief; run: Run }) {
  const { t, lang } = useI18n();
  const [got, setGot] = useState('');
  const href = safeHref(p.url);
  return (
    <li className="row between wrap gap">
      <div>
        <strong>{p.contest_id && !p.id ? <Link to={`/contests/${p.contest_id}`}>{p.title}</Link> : p.title}</strong>
        <div className="small muted">
          {t(`wk.pk.${p.kind}`)}
          {p.price_eur != null && <> · {t('wk.price')} {fmtEur(p.price_eur, lang)}</>}
          {p.refund_eur != null && <> · {t('wk.refundPromised')} {fmtEur(p.refund_eur, lang)}</>}
          {p.net_cost_forecast_eur != null && p.kind !== 'purchase_game' && <> · {t('wk.netForecast')} {fmtEur(p.net_cost_forecast_eur, lang)}</>}
          {p.end_date && <> · {t('wk.until')} {fmtDate(p.end_date, lang)}</>}
          {href && <> · <a href={href} target="_blank" rel="noopener noreferrer">{t('wk.official')}</a></>}
          {p.note && <> · {p.note}</>}
        </div>
      </div>
      {p.id != null && (
        <div className="row gap wrap">
          <select aria-label={t('common.status')} value={p.status} onChange={(e) => {
            const st = e.target.value;
            if (st === 'refunded') { if (!got) { return; } run(() => api.patchPromotion(p.id!, { status: st, refund_received_eur: Number(got) }), t('wk.saved')); }
            else run(() => api.patchPromotion(p.id!, { status: st }), t('wk.saved'));
          }}>
            {PROMO_STATUSES.map((s) => <option key={s} value={s}>{t(`wk.ps.${s}`)}</option>)}
          </select>
          {['sent', 'refund_pending'].includes(p.status) && (
            <input type="number" min={0} step="0.01" style={{ width: '7rem' }} placeholder={t('wk.received')} aria-label={t('wk.received')}
              value={got} onChange={(e) => setGot(e.target.value)} />
          )}
        </div>
      )}
    </li>
  );
}

function Shop({ w, run }: { w: WeekView; run: Run }) {
  const { t, lang } = useI18n();
  const s = w.shop;
  const [f, setF] = useState({ title: '', kind: 'full_refund', price_eur: '', refund_eur: '', end_date: '', url: '' });
  const add = (e: FormEvent) => {
    e.preventDefault();
    run(() => api.addPromotion({ title: f.title.trim(), kind: f.kind, url: f.url || null, price_eur: f.price_eur ? Number(f.price_eur) : null,
      refund_eur: f.refund_eur ? Number(f.refund_eur) : null, end_date: f.end_date || null, status: 'to_watch', contest_id: null }), t('wk.saved'))
      .then(() => setF({ title: '', kind: 'full_refund', price_eur: '', refund_eur: '', end_date: '', url: '' }));
  };
  const cats = ['to_buy_this_week', 'ending', 'full_refund', 'partial_refund', 'purchase_game', 'to_send', 'awaiting_refund', 'received'] as const;
  return (
    <>
      <section className="tiles">
        <div className="tile"><div className="tile-label">{t('wk.spend')}</div><div className="tile-value">{fmtEur(s.totals.planned_spend_eur, lang)}</div></div>
        <div className="tile"><div className="tile-label">{t('wk.netForecast')}</div><div className="tile-value">{fmtEur(s.totals.net_cost_forecast_eur, lang)}</div>
          <div className="tile-help">{t('wk.conditional')}</div></div>
        <div className="tile"><div className="tile-label">{t('wk.awaiting')}</div><div className="tile-value">{fmtEur(s.totals.refunds_awaiting_eur, lang)}</div></div>
        <div className="tile"><div className="tile-label">{t('wk.receivedTotal')}</div><div className="tile-value">{fmtEur(s.totals.refunds_received_eur, lang)}</div></div>
      </section>
      <p className="note small">{s.note}</p>
      {cats.map((k) => s.categories[k].length > 0 && (
        <section key={k} className="card"><h2>{t(`wk.sc.${k}`)}</h2>
          <ul className="list">{s.categories[k].map((p) => <PromoRow key={`${k}-${p.id ?? `c${p.contest_id}`}`} p={p} run={run} />)}</ul></section>
      ))}
      <section className="card">
        <h2>{t('wk.addPromo')}</h2>
        <form className="form-grid" onSubmit={add}>
          <div className="field"><label htmlFor="pr-t">{t('wk.promoTitle')}</label><input id="pr-t" required value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></div>
          <div className="field"><label htmlFor="pr-k">{t('src.kind')}</label>
            <select id="pr-k" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>{PROMO_KINDS.map((k) => <option key={k} value={k}>{t(`wk.pk.${k}`)}</option>)}</select></div>
          <div className="field"><label htmlFor="pr-p">{t('wk.price')} (€)</label><input id="pr-p" type="number" min={0} step="0.01" value={f.price_eur} onChange={(e) => setF({ ...f, price_eur: e.target.value })} /></div>
          <div className="field"><label htmlFor="pr-r">{t('wk.refundPromised')} (€)</label><input id="pr-r" type="number" min={0} step="0.01" value={f.refund_eur} onChange={(e) => setF({ ...f, refund_eur: e.target.value })} /></div>
          <div className="field"><label htmlFor="pr-e">{t('wk.lastBuyDay')}</label><input id="pr-e" type="date" className="input-auto" value={f.end_date} onChange={(e) => setF({ ...f, end_date: e.target.value })} /></div>
          <div className="field"><label htmlFor="pr-u">{t('common.url')}</label><input id="pr-u" type="url" value={f.url} onChange={(e) => setF({ ...f, url: e.target.value })} placeholder="https://" /></div>
          <div className="field"><button className="btn btn-primary">{t('common.add')}</button></div>
        </form>
      </section>
    </>
  );
}

function TaskRow({ task, run }: { task: WeekTask; run: Run }) {
  const { t, lang } = useI18n();
  const [hist, setHist] = useState<null | { at: string; field: string; old: string | null; new: string | null; actor: string }[]>(null);
  const [due, setDue] = useState('');
  return (
    <li>
      <div className="row between wrap gap">
        <div>
          <strong>{task.title}</strong> <Badge tone={prioTone[task.priority]}>{t(`wk.prio.${task.priority}`)}</Badge>
          {task.status === 'expired' && <> <Badge tone="bad">{t('wk.ts.expired')}</Badge></>}
          <div className="small muted">
            {task.due_at ? `${t('wk.due')} ${fmtDate(task.due_at, lang, true)}` : t('wk.noDue')}
            {task.contest_id && <> · <Link to={`/contests/${task.contest_id}`}>{task.contest_title}</Link></>}
            {task.description && <> · {task.description}</>}
          </div>
        </div>
        <div className="row gap wrap">
          <select aria-label={t('common.status')} value={task.status} onChange={(e) => run(() => api.patchWeekTask(task.id, { status: e.target.value }), t('wk.saved'))}>
            {TASK_STATUSES.map((s) => <option key={s} value={s}>{t(`wk.ts.${s}`)}</option>)}
          </select>
          <select aria-label={t('wk.priority')} value={task.priority} onChange={(e) => run(() => api.patchWeekTask(task.id, { priority: e.target.value }), t('wk.saved'))}>
            {['high', 'medium', 'low'].map((p) => <option key={p} value={p}>{t(`wk.prio.${p}`)}</option>)}
          </select>
          <input type="date" className="input-auto" aria-label={t('wk.postponeTo')} value={due} onChange={(e) => setDue(e.target.value)} />
          <button className="btn btn-sm" disabled={!due} onClick={() => run(() => api.patchWeekTask(task.id, { due }), t('wk.saved'))}>{t('wk.postpone')}</button>
          <button className="btn btn-sm" onClick={() => hist ? setHist(null) : api.weekTaskHistory(task.id).then(setHist)}>{t('wk.history')}</button>
        </div>
      </div>
      {hist && <ul className="small muted">{hist.map((h, k) => <li key={k}>{fmtDate(h.at, lang, true)} · {h.field} : {h.old ?? '—'} → {h.new ?? '—'} ({h.actor})</li>)}</ul>}
    </li>
  );
}

function Tasks({ w, run }: { w: WeekView; run: Run }) {
  const { t } = useI18n();
  const [f, setF] = useState({ title: '', priority: 'medium', due: '' });
  const add = (e: FormEvent) => {
    e.preventDefault();
    run(() => api.newWeekTask({ title: f.title.trim(), priority: f.priority, due: f.due || undefined }), t('wk.saved')).then(() => setF({ title: '', priority: 'medium', due: '' }));
  };
  return (
    <>
      {w.tasks.length === 0 ? <p className="empty">{t('wk.noTasks')}</p> : <ul className="list card">{w.tasks.map((x) => <TaskRow key={x.id} task={x} run={run} />)}</ul>}
      <section className="card">
        <h2>{t('wk.newTask')}</h2>
        <form className="form-grid" onSubmit={add}>
          <div className="field"><label htmlFor="tk-t">{t('wk.taskTitle')}</label><input id="tk-t" required minLength={2} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></div>
          <div className="field"><label htmlFor="tk-p">{t('wk.priority')}</label>
            <select id="tk-p" value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })}>{['high', 'medium', 'low'].map((p) => <option key={p} value={p}>{t(`wk.prio.${p}`)}</option>)}</select></div>
          <div className="field"><label htmlFor="tk-d">{t('wk.due')}</label><input id="tk-d" type="date" className="input-auto" value={f.due} onChange={(e) => setF({ ...f, due: e.target.value })} /></div>
          <div className="field"><button className="btn btn-primary">{t('common.add')}</button></div>
        </form>
      </section>
    </>
  );
}

function Reports({ week }: { week: string }) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const list = useAsync(() => api.weekReports(), []);
  const [open, setOpen] = useState<WeekReport | null>(null);
  const make = async (kind: 'weekly' | 'daily' | 'review') => {
    try { const r = await api.makeWeekReport(kind, kind === 'daily' ? undefined : week); setOpen(r); list.reload(); } catch (e) { toast.err(e); }
  };
  return (
    <>
      <div className="row gap wrap no-print">
        <button className="btn" onClick={() => make('weekly')}>{t('wk.rk.weekly')}</button>
        <button className="btn" onClick={() => make('daily')}>{t('wk.rk.daily')}</button>
        <button className="btn" onClick={() => make('review')}>{t('wk.rk.review')}</button>
      </div>
      {open && (
        <section className="card printable">
          <div className="row between no-print"><strong>{t(`wk.rk.${open.kind}`)}</strong>
            <div className="row gap"><button className="btn btn-sm" onClick={() => window.print()}>{t('wk.print')}</button>
              <button className="btn btn-sm" onClick={() => setOpen(null)}>{t('common.close')}</button></div></div>
          <pre className="pre">{open.text}</pre>
        </section>
      )}
      <Async state={list} isEmpty={(l) => l.length === 0} empty={t('wk.noReports')}>
        {(l) => (
          <ul className="list card no-print">{l.map((r) => (
            <li key={r.id} className="row between wrap gap">
              <span>{t(`wk.rk.${r.kind}`)} · {fmtDate(r.period_start, lang)}{r.period_end !== r.period_start && ` → ${fmtDate(r.period_end, lang)}`}</span>
              <button className="btn btn-sm" onClick={() => api.weekReport(r.id).then(setOpen, (e) => toast.err(e))}>{t('wk.open')}</button>
            </li>
          ))}</ul>
        )}
      </Async>
    </>
  );
}

function Settings({ onSaved }: { onSaved: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const p = useAsync(() => api.weekPrefs(), []);
  const [draft, setDraft] = useState<Partial<WeekPrefs>>({});
  const days = [0, 1, 2, 3, 4, 5, 6];
  const save = async (e: FormEvent) => {
    e.preventDefault();
    try { const r = await api.saveWeekPrefs(draft); p.setData(r); setDraft({}); toast.ok(t('wk.saved')); onSaved(); } catch (err) { toast.err(err); }
  };
  return (
    <Async state={p}>
      {(cur) => {
        const val = { ...cur, ...draft };
        const num = (k: keyof WeekPrefs, min: number, max: number) => (
          <div className="field"><label htmlFor={`wp-${k}`}>{t(`wk.p.${k}`)}</label>
            <input id={`wp-${k}`} type="number" min={min} max={max} value={Number(val[k])} onChange={(e) => setDraft({ ...draft, [k]: Number(e.target.value) })} /></div>
        );
        const bool = (k: keyof WeekPrefs) => (
          <label className="check"><input type="checkbox" checked={Boolean(val[k])} onChange={(e) => setDraft({ ...draft, [k]: e.target.checked })} /> {t(`wk.p.${k}`)}</label>
        );
        const day = (k: 'plan_weekday' | 'review_weekday') => (
          <div className="field"><label htmlFor={`wp-${k}`}>{t(`wk.p.${k}`)}</label>
            <select id={`wp-${k}`} value={val[k]} onChange={(e) => setDraft({ ...draft, [k]: Number(e.target.value) })}>{days.map((d) => <option key={d} value={d}>{t(`wk.day.${d}`)}</option>)}</select></div>
        );
        return (
          <form className="card" onSubmit={save}>
            <div className="form-grid">
              {num('minutes_per_day', 0, 600)}{num('weekly_goal', 0, 500)}{num('min_interest', 0, 100)}{num('min_reliability', 0, 100)}
              {day('plan_weekday')}{num('plan_hour', 0, 23)}{day('review_weekday')}{num('review_hour', 0, 23)}
              {num('remind_close_hours', 1, 336)}{num('alert_close_hours', 1, 168)}{num('daily_hour', 0, 23)}
              <div className="field"><label htmlFor="wp-tz">{t('wk.p.timezone')}</label>
                <input id="wp-tz" value={val.timezone} onChange={(e) => setDraft({ ...draft, timezone: e.target.value })} /></div>
            </div>
            <fieldset><legend>{t('wk.p.active_days')}</legend><div className="row gap wrap">
              {days.map((d) => (
                <label key={d} className="check"><input type="checkbox" checked={val.active_days.includes(d)} onChange={(e) =>
                  setDraft({ ...draft, active_days: e.target.checked ? [...val.active_days, d].sort() : val.active_days.filter((x) => x !== d) })} /> {t(`wk.day.${d}`)}</label>
              ))}
            </div></fieldset>
            {bool('daily_enabled')}{bool('notifications_enabled')}{bool('remind_results')}{bool('remind_claims')}
            <fieldset><legend>{t('wk.p.filters')}</legend>
              <div className="form-grid">
                <div className="field wide"><label htmlFor="wp-am">{t('wk.p.automation_mode')}</label>
                  <select id="wp-am" value={val.automation_mode} onChange={(e) => setDraft({ ...draft, automation_mode: e.target.value as WeekPrefs['automation_mode'] })}>
                    {(['max', 'mixed', 'manual'] as const).map((m) => <option key={m} value={m}>{t(`wk.p.mode.${m}`)}</option>)}
                  </select></div>
                {num('social_share_max', 0, 100)}
              </div>
              {bool('hide_facebook')}{bool('hide_instagram')}{bool('hide_creative')}
              {bool('favor_quick_forms')}{bool('favor_instant_win')}{bool('favor_quiz')}{bool('favor_many_prizes')}
            </fieldset>
            <button className="btn btn-primary">{t('common.save')}</button>
          </form>
        );
      }}
    </Async>
  );
}
