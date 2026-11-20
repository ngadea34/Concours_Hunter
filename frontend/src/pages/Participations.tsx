import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { Async } from '../components/Async';
import { Badge, type Tone } from '../components/Badge';
import { CopyButton } from '../components/CopyButton';
import { PageHeader } from '../components/PageHeader';
import { useToast } from '../components/Toast';
import { useAsync } from '../hooks';
import { useI18n } from '../i18n';
import { PARTICIPATION_STATUSES, type Participation, type ParticipationStatus } from '../types';
import { emptyToUndef, fmtDate, safeHref } from '../util';

const tone: Record<ParticipationStatus, Tone> = {
  prepared: 'info', awaiting_human: 'warn', submitted: 'info', confirmed: 'ok', failed: 'bad', cancelled: 'neutral',
};

function PrefillPanel({ id }: { id: number }) {
  const { t } = useI18n();
  const pf = useAsync(() => api.prefill(id), [id]);
  return (
    <Async state={pf}>
      {(p) => {
        const fields = Object.entries(p.fields);
        return (
          <div className="prefill">
            {p.warnings.length > 0 && (
              <div className="alert alert-warn" role="alert">
                <strong>{t('par.warnings')}</strong>
                <ul>{p.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
              </div>
            )}
            {fields.length === 0 && p.answers.length === 0 && <p className="empty">{t('par.noPrefill')}</p>}
            {fields.length > 0 && (
              <>
                <h4>{t('par.fields')}</h4>
                <ul className="copylist">
                  {fields.map(([k, v]) => (
                    <li key={k}>
                      <span className="copykey">{t(`profile.${k}`) === `profile.${k}` ? k : t(`profile.${k}`)}</span>
                      <code className="copyval">{v}</code>
                      <CopyButton text={v} label={`${t('common.copy')} ${k}`} />
                    </li>
                  ))}
                </ul>
              </>
            )}
            {p.answers.length > 0 && (
              <>
                <h4>{t('par.answers')}</h4>
                <ul className="copylist">
                  {p.answers.map((a, i) => (
                    <li key={i}>
                      <span className="copykey">{a.question}</span>
                      <code className="copyval">{a.answer}</code>
                      <CopyButton text={a.answer} label={`${t('common.copy')} : ${a.question}`} />
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        );
      }}
    </Async>
  );
}

function Card({ p, onChange }: { p: Participation; onChange: () => void }) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const [showPrefill, setShowPrefill] = useState(false);
  const [panel, setPanel] = useState<'submitted' | 'failed' | null>(null);
  const [minutes, setMinutes] = useState('');
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const href = safeHref(p.contest_url);
  const open = p.status === 'prepared' || p.status === 'awaiting_human';
  const live = open || p.status === 'submitted';

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try { await fn(); toast.ok(t('par.done')); setPanel(null); onChange(); } catch (e) { toast.err(e); } finally { setBusy(false); }
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const m = minutes.trim() === '' ? undefined : Number(minutes);
    run(() => api.submitted(p.id, { note: emptyToUndef(note), time_spent_minutes: m }));
  };
  const fail = (e: FormEvent) => { e.preventDefault(); run(() => api.failed(p.id, { error: error.trim() })); };

  return (
    <article className="card">
      <div className="row between wrap">
        <h3><Link to={`/contests/${p.contest_id}`}>{p.contest_title}</Link></h3>
        <Badge tone={tone[p.status]}>{t(`pstatus.${p.status}`)}</Badge>
      </div>
      <p className="muted small">
        {t(`mode.${p.mode}`)} · {t('par.preparedAt')} {fmtDate(p.prepared_at, lang, true)}
        {p.submitted_at && ` · ${t('par.submittedAt')} ${fmtDate(p.submitted_at, lang, true)}`}
        {p.time_spent_minutes !== null && ` · ${t('common.minutes', { n: p.time_spent_minutes })}`}
        {p.proofs.length > 0 && ` · ${t('par.proofs')} : ${p.proofs.length}`}
      </p>
      {p.error && <p className="alert alert-err">{p.error}</p>}
      <div className="row gap wrap">
        {live && (
          <button className="btn" aria-expanded={showPrefill} onClick={() => setShowPrefill((v) => !v)}>
            {showPrefill ? t('par.hidePrefill') : t('par.showPrefill')}
          </button>
        )}
        {href && live && <a className="btn btn-primary" href={href} target="_blank" rel="noopener noreferrer">{t('common.openSite')} <span className="sr-only">{t('common.newTab')}</span></a>}
        {open && <button className="btn" disabled={busy} onClick={() => setPanel(panel === 'submitted' ? null : 'submitted')}>{t('par.submitted')}</button>}
        {p.status === 'submitted' && <button className="btn btn-ok" disabled={busy} onClick={() => run(() => api.confirmed(p.id, {}))}>{t('par.confirmed')}</button>}
        {live && <button className="btn" disabled={busy} onClick={() => setPanel(panel === 'failed' ? null : 'failed')}>{t('par.failed')}</button>}
        {live && <button className="btn btn-danger" disabled={busy} onClick={() => { if (window.confirm(t('par.confirmCancel'))) run(() => api.cancel(p.id)); }}>{t('par.cancel')}</button>}
      </div>
      {panel === 'submitted' && (
        <form className="subform" onSubmit={submit}>
          <div className="field">
            <label htmlFor={`min-${p.id}`}>{t('par.timeSpent')}</label>
            <input id={`min-${p.id}`} type="number" min={0} value={minutes} onChange={(e) => setMinutes(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor={`note-${p.id}`}>{t('par.note')}</label>
            <input id={`note-${p.id}`} value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
          <button className="btn btn-primary" disabled={busy}>{t('common.confirm')}</button>
        </form>
      )}
      {panel === 'failed' && (
        <form className="subform" onSubmit={fail}>
          <div className="field">
            <label htmlFor={`err-${p.id}`}>{t('par.error')}</label>
            <input id={`err-${p.id}`} required value={error} onChange={(e) => setError(e.target.value)} />
          </div>
          <button className="btn btn-danger" disabled={busy || !error.trim()}>{t('common.confirm')}</button>
        </form>
      )}
      {showPrefill && live && <PrefillPanel id={p.id} />}
    </article>
  );
}

export function Participations() {
  const { t } = useI18n();
  const [status, setStatus] = useState('');
  const list = useAsync(() => api.participations(status ? { status } : undefined), [status]);
  return (
    <>
      <PageHeader title={t('par.title')}>
        <div className="field inline">
          <label htmlFor="pst">{t('common.status')}</label>
          <select id="pst" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">{t('common.all')}</option>
            {PARTICIPATION_STATUSES.map((s) => <option key={s} value={s}>{t(`pstatus.${s}`)}</option>)}
          </select>
        </div>
      </PageHeader>
      <p className="note">{t('disclaimer.manual')}</p>
      <Async state={list} isEmpty={(l) => l.length === 0} empty={t('par.empty')}>
        {(l) => <div className="stack">{l.map((p) => <Card key={p.id} p={p} onChange={list.reload} />)}</div>}
      </Async>
    </>
  );
}
