import { useEffect, useState, type ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api';
import { Async } from '../components/Async';
import { ContestBadges } from '../components/ContestCard';
import { PageHeader } from '../components/PageHeader';
import { ScoreBar } from '../components/ScoreBar';
import { useToast } from '../components/Toast';
import { useAsync } from '../hooks';
import { useI18n } from '../i18n';
import { CONTEST_STATUSES, type ContestDetail, type ContestStatus } from '../types';
import { daysLabel, emptyToUndef, fmtDate, fmtEur, fmtNum, safeHref } from '../util';

function Section({ title, children }: { title: string; children: ReactNode }) {
  return <section className="card"><h2>{title}</h2>{children}</section>;
}

function Breakdown({ title, data }: { title: string; data: Record<string, number> }) {
  const entries = Object.entries(data);
  return (
    <div>
      <h3>{title}</h3>
      {entries.length === 0 ? <p className="muted">—</p> : (
        <dl className="kv">
          {entries.map(([k, v]) => (<div key={k}><dt>{k}</dt><dd>{fmtNum(v)}</dd></div>))}
        </dl>
      )}
    </div>
  );
}

function VerifyBox({ id, field, label, current, onDone }: {
  id: number; field: 'free' | 'eligibility'; label: string; current: string; onDone: (c: ContestDetail) => void;
}) {
  const { t } = useI18n();
  const toast = useToast();
  const [evidence, setEvidence] = useState('');
  const [busy, setBusy] = useState(false);
  const send = async (decision: 'yes' | 'no') => {
    setBusy(true);
    try {
      onDone(await api.verify(id, { field, decision, evidence: emptyToUndef(evidence) }));
      toast.ok(t('det.verified'));
      setEvidence('');
    } catch (e) { toast.err(e); } finally { setBusy(false); }
  };
  return (
    <fieldset className="verify">
      <legend>{label} <span className="muted">({current})</span></legend>
      <label htmlFor={`ev-${field}`}>{t('det.evidence')}</label>
      <input id={`ev-${field}`} value={evidence} onChange={(e) => setEvidence(e.target.value)} />
      <div className="row gap">
        <button className="btn btn-ok" disabled={busy} onClick={() => send('yes')}>{t('det.validate')}</button>
        <button className="btn btn-danger" disabled={busy} onClick={() => send('no')}>{t('det.invalidate')}</button>
      </div>
    </fieldset>
  );
}

function Detail({ c, onChange }: { c: ContestDetail; onChange: (c: ContestDetail) => void }) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const nav = useNavigate();
  const [status, setStatus] = useState<ContestStatus>(c.status);
  const [notes, setNotes] = useState(c.notes ?? '');
  const [interest, setInterest] = useState<number>(c.personal_interest ?? 5);
  const [interestSet, setInterestSet] = useState(c.personal_interest !== null);
  const [rules, setRules] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setStatus(c.status); setNotes(c.notes ?? '');
    setInterest(c.personal_interest ?? 5); setInterestSet(c.personal_interest !== null);
  }, [c]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    try { await fn(); } catch (e) { toast.err(e); } finally { setBusy(false); }
  };
  const href = safeHref(c.url);
  const rulesHref = safeHref(c.rules?.url);

  return (
    <>
      <PageHeader title={c.title}>
        <Link className="btn" to="/catalog">{t('det.back')}</Link>
      </PageHeader>
      <div className="card">
        <ContestBadges c={c} />
        <p className="muted">
          {c.organizer_name && `${t('cat.by', { name: c.organizer_name })} · `}
          {c.source_names.join(', ')}
        </p>
        <dl className="kv">
          <div><dt>{t('cat.prize')}</dt><dd>{c.prize_summary ?? '—'}</dd></div>
          <div><dt>{t('cat.value')}</dt><dd>{fmtEur(c.total_prize_value_eur, lang)}</dd></div>
          <div><dt>{t('det.start')}</dt><dd>{fmtDate(c.start_date, lang)}</dd></div>
          <div><dt>{t('det.end')}</dt><dd>{fmtDate(c.end_date, lang)} ({daysLabel(c.days_left, t)})</dd></div>
          <div><dt>{t('det.entryLimit')}</dt><dd>{c.entry_limit ?? '—'}</dd></div>
          <div><dt>{t('det.minAge')}</dt><dd>{c.min_age ?? '—'}</dd></div>
          <div><dt>{t('det.countriesAllowed')}</dt><dd>{c.countries_allowed.join(', ') || '—'}</dd></div>
          <div><dt>{t('det.countriesExcluded')}</dt><dd>{c.countries_excluded.join(', ') || '—'}</dd></div>
          <div><dt>{t('common.language')}</dt><dd>{c.language ?? '—'}</dd></div>
          <div><dt>{t('det.mode')}</dt><dd>{t(`mode.${c.participation_mode}`)}</dd></div>
        </dl>
        {c.needs_human_reason && <p className="note"><strong>{t('det.humanReason')} :</strong> {c.needs_human_reason}</p>}
        {c.description && <><h3>{t('det.description')}</h3><p className="pre">{c.description}</p></>}
      </div>

      <Section title={t('det.actions')}>
        <p className="note">{t('disclaimer.manual')}</p>
        <div className="row gap wrap">
          <button className="btn btn-primary" disabled={busy} onClick={() => run(async () => {
            await api.createParticipation(c.id, {});
            toast.ok(t('det.prepared'));
            nav('/participations');
          })}>{t('det.prepare')}</button>
          {href && <a className="btn" href={href} target="_blank" rel="noopener noreferrer">{t('common.openSite')} <span className="sr-only">{t('common.newTab')}</span></a>}
        </div>
        <div className="cols">
          <form className="stack" onSubmit={(e) => { e.preventDefault(); run(async () => { onChange(await api.patchContest(c.id, { status })); toast.ok(t('common.saved')); }); }}>
            <div className="field">
              <label htmlFor="st">{t('det.setStatus')}</label>
              <select id="st" value={status} onChange={(e) => setStatus(e.target.value as ContestStatus)}>
                {CONTEST_STATUSES.map((s) => <option key={s} value={s}>{t(`status.${s}`)}</option>)}
              </select>
            </div>
            <button className="btn" disabled={busy || status === c.status}>{t('common.save')}</button>
          </form>
          <form className="stack" onSubmit={(e) => { e.preventDefault(); run(async () => { onChange(await api.patchContest(c.id, { personal_interest: interest })); toast.ok(t('common.saved')); }); }}>
            <div className="field">
              <label htmlFor="pi">{t('det.personalInterest')} : {interestSet ? interest : t('det.notSet')}</label>
              <input id="pi" type="range" min={0} max={10} step={1} value={interest} onChange={(e) => { setInterest(Number(e.target.value)); setInterestSet(true); }} />
            </div>
            <button className="btn" disabled={busy}>{t('common.save')}</button>
          </form>
        </div>
        <form className="stack" onSubmit={(e) => { e.preventDefault(); run(async () => { onChange(await api.patchContest(c.id, { notes })); toast.ok(t('common.saved')); }); }}>
          <div className="field">
            <label htmlFor="notes">{t('det.notes')}</label>
            <textarea id="notes" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <div><button className="btn" disabled={busy}>{t('common.save')}</button></div>
        </form>
        <h3>{t('det.verifyFree')} / {t('det.verifyElig')}</h3>
        <p className="muted small">{t('det.verifyHelp')}</p>
        <div className="cols">
          <VerifyBox id={c.id} field="free" label={t('det.verifyFree')} current={t(`free.${c.free_status}`)} onDone={onChange} />
          <VerifyBox id={c.id} field="eligibility" label={t('det.verifyElig')} current={t(`elig.${c.fr_eligible}`)} onDone={onChange} />
        </div>
        <form className="stack" onSubmit={(e) => { e.preventDefault(); run(async () => { onChange(await api.requalify(c.id, { rules_text: emptyToUndef(rules) })); toast.ok(t('det.requalified')); setRules(''); }); }}>
          <div className="field">
            <label htmlFor="rules">{t('det.requalify')} — {t('det.rulesText')}</label>
            <textarea id="rules" rows={5} value={rules} onChange={(e) => setRules(e.target.value)} aria-describedby="rules-h" />
            <span id="rules-h" className="muted small">{t('det.requalifyHelp')}</span>
          </div>
          <div><button className="btn" disabled={busy}>{t('det.requalify')}</button></div>
        </form>
      </Section>

      <Section title={t('det.scores')}>
        <div className="scores">
          <ScoreBar label={t('det.reliability')} value={c.reliability_score} />
          <ScoreBar label={t('det.interest')} value={c.interest_score} />
        </div>
        <p className="note">{t('disclaimer.scores')}</p>
        <div className="cols">
          <Breakdown title={t('det.reliability')} data={c.score_breakdown.reliability} />
          <Breakdown title={t('det.interest')} data={c.score_breakdown.interest} />
        </div>
      </Section>

      <Section title={t('det.justifications')}>
        {c.justifications.length === 0 ? <p className="empty">{t('common.empty')}</p> : (
          <div className="table-wrap"><table>
            <thead><tr><th scope="col">{t('common.field')}</th><th scope="col">{t('common.decision')}</th><th scope="col">{t('common.evidence')}</th><th scope="col">{t('common.method')}</th></tr></thead>
            <tbody>{c.justifications.map((j, i) => (
              <tr key={i}><th scope="row">{j.field}</th><td>{j.decision}</td><td>{j.evidence ? <q>{j.evidence}</q> : '—'}</td><td><code>{j.method}</code></td></tr>
            ))}</tbody>
          </table></div>
        )}
      </Section>

      <Section title={t('det.rules')}>
        {c.rules === null ? <p className="empty">{t('common.empty')}</p> : (
          <>
            {rulesHref && <p><a href={rulesHref} target="_blank" rel="noopener noreferrer">{t('det.rulesUrl')} {t('common.newTab')}</a></p>}
            <p className="muted small">{t('det.analyzedAt')} {fmtDate(c.rules.analyzed_at, lang, true)}</p>
            {c.rules.excerpt && <p className="pre">{c.rules.excerpt}</p>}
          </>
        )}
      </Section>

      <Section title={t('det.prizes')}>
        {c.prizes.length === 0 ? <p className="empty">{t('common.empty')}</p> : (
          <div className="table-wrap"><table>
            <thead><tr><th scope="col">{t('common.name')}</th><th scope="col">{t('cat.category')}</th><th scope="col" className="num">{t('det.quantity')}</th><th scope="col" className="num">{t('common.value')}</th><th scope="col">{t('det.fees')}</th></tr></thead>
            <tbody>{c.prizes.map((p) => (
              <tr key={p.id}><th scope="row">{p.name}</th><td>{t(`prize.${p.category}`)}</td><td className="num">{p.quantity}</td>
                <td className="num">{p.value !== null ? `${p.value} ${p.currency ?? ''}` : '—'}{p.value_eur !== null && p.currency !== 'EUR' ? ` (${fmtEur(p.value_eur, lang)})` : ''}</td>
                <td>{p.fees_note ?? '—'}</td></tr>
            ))}</tbody>
          </table></div>
        )}
      </Section>

      <Section title={t('det.answers')}>
        {c.answers.length === 0 ? <p className="empty">{t('common.empty')}</p> : (
          <div className="table-wrap"><table>
            <thead><tr><th scope="col">{t('det.question')}</th><th scope="col">{t('det.answer')}</th><th scope="col">{t('common.source')}</th><th scope="col">{t('common.verified')}</th><th scope="col" className="num">{t('det.confidence')}</th></tr></thead>
            <tbody>{c.answers.map((a) => (
              <tr key={a.id}><td>{a.question}</td><td>{a.answer}</td><td>{a.source}</td>
                <td>{a.verified ? <span className="badge badge-ok">{t('common.verified')}</span> : <span className="badge badge-warn">{t('common.unverified')}</span>}</td>
                <td className="num">{fmtNum(a.confidence)}</td></tr>
            ))}</tbody>
          </table></div>
        )}
      </Section>

      <Section title={t('det.provenance')}>
        {c.provenance.length === 0 ? <p className="empty">{t('common.empty')}</p> : (
          <ul>{c.provenance.map((p, i) => {
            const h = safeHref(p.source_url);
            return <li key={i}>{p.source_name} — {h ? <a href={h} target="_blank" rel="noopener noreferrer">{p.source_url}</a> : p.source_url} — {t('det.seenAt')} {fmtDate(p.seen_at, lang, true)}</li>;
          })}</ul>
        )}
      </Section>

      <Section title={t('det.participations')}>
        {c.participations.length === 0 ? <p className="empty">{t('par.empty')}</p> : (
          <ul>{c.participations.map((p) => (
            <li key={p.id}>{t(`pstatus.${p.status}`)} — {t(`mode.${p.mode}`)} — {fmtDate(p.prepared_at, lang, true)} · <Link to="/participations">{t('common.details')}</Link></li>
          ))}</ul>
        )}
      </Section>
    </>
  );
}

export function ContestPage() {
  const { id } = useParams();
  const num = Number(id);
  const st = useAsync(() => api.contest(num), [num]);
  return (
    <Async state={st}>
      {(c) => <Detail c={c} onChange={(n) => st.setData(n)} />}
    </Async>
  );
}
