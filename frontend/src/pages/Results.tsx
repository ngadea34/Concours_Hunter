import { useState, type FormEvent } from 'react';
import { api } from '../api';
import { Async } from '../components/Async';
import { Badge, type Tone } from '../components/Badge';
import { PageHeader } from '../components/PageHeader';
import { useToast } from '../components/Toast';
import { useAsync } from '../hooks';
import { useI18n } from '../i18n';
import { CLAIM_STATUSES, type Claim, type ClaimStatus, type Outcome, type Result } from '../types';
import { daysLabel, emptyToUndef, fmtDate, fmtEur } from '../util';

// Le score anti-phishing peut être renvoyé en 0-1 ou 0-100 : on normalise pour l'affichage.
function pct(score: number): number { return Math.round(score <= 1 ? score * 100 : score); }

function PhishBadge({ score }: { score: number }) {
  const { t } = useI18n();
  const p = pct(score);
  const tone: Tone = p < 30 ? 'ok' : p < 60 ? 'warn' : 'bad';
  const label = p < 30 ? t('res.phishLow') : p < 60 ? t('res.phishMid') : t('res.phishHigh');
  return <Badge tone={tone}>{t('res.phishing')} : {p}/100 — {label}</Badge>;
}

function ResultCard({ r, onChange }: { r: Result; onChange: () => void }) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const verify = async () => {
    try { await api.verifyResult(r.id, { verified: !r.verified }); onChange(); } catch (e) { toast.err(e); }
  };
  const tone: Tone = r.outcome === 'won' ? 'ok' : r.outcome === 'lost' ? 'neutral' : 'info';
  return (
    <article className="card">
      <div className="row between wrap">
        <h3>{r.contest_title ?? `${t('res.resultId')} #${r.id}`}</h3>
        <Badge tone={tone}>{t(`outcome.${r.outcome}`)}</Badge>
      </div>
      <p className="muted small">{t('res.received')} {fmtDate(r.received_at, lang, true)}{r.sender && ` · ${r.sender}`}</p>
      {r.message_text && <p className="pre quote">{r.message_text}</p>}
      <p><PhishBadge score={r.phishing_score} /> <Badge tone={r.verified ? 'ok' : 'warn'}>{r.verified ? t('common.verified') : t('common.unverified')}</Badge></p>
      <p className="muted small">{t('res.phishHelp')}</p>
      <div>
        <strong>{t('res.flags')}</strong>
        {r.phishing_flags.length === 0 ? <p className="muted">{t('res.noFlags')}</p> : <ul>{r.phishing_flags.map((f, i) => <li key={i}>{f}</li>)}</ul>}
      </div>
      <button className="btn" onClick={verify}>{r.verified ? t('res.unverify') : t('res.verify')}</button>
    </article>
  );
}

function ClaimRow({ c, onChange }: { c: Claim; onChange: () => void }) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const open = c.status === 'to_claim' || c.status === 'claimed';
  const urgent = open && c.days_left !== null && c.days_left < 7;
  const setStatus = async (status: ClaimStatus) => {
    try { await api.patchClaim(c.id, { status }); toast.ok(t('res.claimUpdated')); onChange(); } catch (e) { toast.err(e); }
  };
  return (
    <tr>
      <th scope="row">{c.contest_title ?? '—'}<div className="muted small">{c.prize_name ?? ''}</div></th>
      <td>{fmtDate(c.deadline, lang)}</td>
      <td className={urgent ? 'danger strong' : ''}>{c.deadline ? daysLabel(c.days_left, t) : '—'}</td>
      <td className="num">
        {c.fees_eur !== null && c.fees_eur > 0 ? <span className="danger strong" title={t('res.feesWarn')}>{fmtEur(c.fees_eur, lang)} ⚠</span> : fmtEur(c.fees_eur, lang)}
      </td>
      <td className="num">{fmtEur(c.value_eur, lang)}</td>
      <td>
        <label className="sr-only" htmlFor={`cs-${c.id}`}>{t('common.status')}</label>
        <select id={`cs-${c.id}`} value={c.status} onChange={(e) => setStatus(e.target.value as ClaimStatus)}>
          {CLAIM_STATUSES.map((s) => <option key={s} value={s}>{t(`claim.${s}`)}</option>)}
        </select>
      </td>
    </tr>
  );
}

export function Results() {
  const { t } = useI18n();
  const toast = useToast();
  const results = useAsync(() => api.results(), []);
  const claims = useAsync(() => api.claims(), []);
  const [outcome, setOutcome] = useState<Outcome>('won');
  const [text, setText] = useState('');
  const [sender, setSender] = useState('');
  const [contestId, setContestId] = useState('');
  const [busy, setBusy] = useState(false);
  // création de réclamation
  const [cResult, setCResult] = useState('');
  const [cPrize, setCPrize] = useState('');
  const [cDeadline, setCDeadline] = useState('');
  const [cFees, setCFees] = useState('');
  const [cValue, setCValue] = useState('');

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.addResult({
        outcome, message_text: emptyToUndef(text), sender: emptyToUndef(sender),
        contest_id: contestId.trim() ? Number(contestId) : undefined,
      });
      toast.ok(t('res.saved'));
      setText(''); setSender(''); setContestId('');
      results.reload();
    } catch (err) { toast.err(err); } finally { setBusy(false); }
  };
  const addClaim = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api.addClaim({
        result_id: Number(cResult), prize_name: emptyToUndef(cPrize), deadline: emptyToUndef(cDeadline),
        fees_eur: cFees.trim() ? Number(cFees) : undefined, value_eur: cValue.trim() ? Number(cValue) : undefined,
      });
      toast.ok(t('res.claimAdded'));
      setCPrize(''); setCDeadline(''); setCFees(''); setCValue('');
      claims.reload();
    } catch (err) { toast.err(err); }
  };

  return (
    <>
      <PageHeader title={t('res.title')} />
      <section className="card">
        <h2>{t('res.record')}</h2>
        <form className="form-grid" onSubmit={submit}>
          <div className="field">
            <label htmlFor="ro">{t('res.outcome')}</label>
            <select id="ro" value={outcome} onChange={(e) => setOutcome(e.target.value as Outcome)}>
              {(['won', 'lost', 'pending'] as Outcome[]).map((o) => <option key={o} value={o}>{t(`outcome.${o}`)}</option>)}
            </select>
          </div>
          <div className="field"><label htmlFor="rs">{t('res.sender')}</label><input id="rs" value={sender} onChange={(e) => setSender(e.target.value)} /></div>
          <div className="field"><label htmlFor="rc">{t('res.contest')}</label><input id="rc" type="number" min={1} value={contestId} onChange={(e) => setContestId(e.target.value)} /></div>
          <div className="field wide full"><label htmlFor="rt">{t('res.messageText')}</label><textarea id="rt" rows={5} value={text} onChange={(e) => setText(e.target.value)} /></div>
          <div className="field"><button className="btn btn-primary" disabled={busy}>{t('common.save')}</button></div>
        </form>
        <p className="muted small">{t('res.phishHelp')}</p>
      </section>

      <section>
        <h2>{t('res.list')}</h2>
        <Async state={results} isEmpty={(l) => l.length === 0} empty={t('res.noResults')}>
          {(l) => <div className="grid">{l.map((r) => <ResultCard key={r.id} r={r} onChange={results.reload} />)}</div>}
        </Async>
      </section>

      <section>
        <h2>{t('res.claims')}</h2>
        <Async state={claims} isEmpty={(l) => l.length === 0} empty={t('res.noClaims')}>
          {(l) => (
            <div className="table-wrap"><table>
              <thead><tr>
                <th scope="col">{t('res.prize')}</th><th scope="col">{t('res.deadline')}</th><th scope="col">{t('res.daysCol')}</th>
                <th scope="col" className="num">{t('res.fees')}</th><th scope="col" className="num">{t('res.valueEur')}</th><th scope="col">{t('common.status')}</th>
              </tr></thead>
              <tbody>{l.map((c) => <ClaimRow key={c.id} c={c} onChange={claims.reload} />)}</tbody>
            </table></div>
          )}
        </Async>
        {results.data && results.data.length > 0 && (
          <form className="card form-grid" onSubmit={addClaim}>
            <h3 className="full">{t('res.addClaim')}</h3>
            <div className="field">
              <label htmlFor="cr">{t('res.resultId')}</label>
              <select id="cr" required value={cResult} onChange={(e) => setCResult(e.target.value)}>
                <option value="" disabled>—</option>
                {results.data.map((r) => <option key={r.id} value={r.id}>#{r.id} {r.contest_title ?? r.sender ?? ''} ({t(`outcome.${r.outcome}`)})</option>)}
              </select>
            </div>
            <div className="field"><label htmlFor="cp">{t('res.prizeName')}</label><input id="cp" value={cPrize} onChange={(e) => setCPrize(e.target.value)} /></div>
            <div className="field"><label htmlFor="cd">{t('res.deadline')}</label><input id="cd" type="date" value={cDeadline} onChange={(e) => setCDeadline(e.target.value)} /></div>
            <div className="field"><label htmlFor="cf">{t('res.fees')}</label><input id="cf" type="number" min={0} step="0.01" value={cFees} onChange={(e) => setCFees(e.target.value)} /></div>
            <div className="field"><label htmlFor="cv">{t('res.valueEur')}</label><input id="cv" type="number" min={0} step="0.01" value={cValue} onChange={(e) => setCValue(e.target.value)} /></div>
            <div className="field"><button className="btn btn-primary" disabled={!cResult}>{t('common.add')}</button></div>
          </form>
        )}
      </section>
    </>
  );
}
