import { useState, type FormEvent } from 'react';
import type { SourceQuality } from '../types';
import { api } from '../api';
import { Async } from '../components/Async';
import { Badge } from '../components/Badge';
import { PageHeader } from '../components/PageHeader';
import { useToast } from '../components/Toast';
import { useAsync } from '../hooks';
import { useI18n } from '../i18n';
import { emptyToUndef, fmtDate, safeHref } from '../util';

export function Sources() {
  const { t, lang } = useI18n();
  const toast = useToast();
  const src = useAsync(() => api.sources(), []);
  const jobs = useAsync(() => api.scanJobs(), []);
  const sug = useAsync(() => api.siteSuggestions(), []);
  const pol = useAsync(() => api.sourcePolicy(), []);
  const [quality, setQuality] = useState<Record<number, SourceQuality | undefined>>({});
  const [imp, setImp] = useState('');
  const [impRes, setImpRes] = useState<string[] | null>(null);
  const toggleQuality = async (id: number) => {
    if (quality[id]) { setQuality({ ...quality, [id]: undefined }); return; }
    try { const q = await api.sourceQuality(id); setQuality({ ...quality, [id]: q }); } catch (e) { toast.err(e); }
  };
  const doImport = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const r = await api.importContests(imp);
      toast.ok(t('src.impDone'));
      setImpRes([`${r.created.length} ${t('src.impCreated')} · ${r.existing.length} ${t('src.impExisting')} · ${r.skipped.length} ${t('src.impSkipped')}`,
        ...r.skipped.map((x) => `${x.line ?? ''} ${x.url} : ${x.reason}`)]);
      if (r.created.length) setImp('');
    } catch (err) { toast.err(err); }
  };
  const [domain, setDomain] = useState('');
  const [name, setName] = useState('');
  const [kind, setKind] = useState<'rss' | 'html'>('rss');
  const [url, setUrl] = useState('');
  const [language, setLanguage] = useState('');
  const [country, setCountry] = useState('');
  const [busy, setBusy] = useState(false);

  const act = async (fn: () => Promise<unknown>, msg: string) => {
    try { await fn(); toast.ok(msg); src.reload(); jobs.reload(); sug.reload(); } catch (e) { toast.err(e); }
  };
  const add = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.addSource({ name: name.trim(), kind, url: url.trim(), language: emptyToUndef(language), country: emptyToUndef(country) });
      toast.ok(t('src.added'));
      setName(''); setUrl(''); setLanguage(''); setCountry('');
      src.reload();
    } catch (err) { toast.err(err); } finally { setBusy(false); }
  };

  return (
    <>
      <PageHeader title={t('src.title')}>
        <button className="btn" onClick={() => { src.reload(); jobs.reload(); }}>{t('common.refresh')}</button>
      </PageHeader>
      <Async state={src} isEmpty={(l) => l.length === 0} empty={t('src.noSources')}>
        {(l) => (
          <div className="grid">
            {l.map((s) => {
              const h = safeHref(s.url);
              return (
                <article key={s.id} className="card">
                  <div className="row between wrap">
                    <h3>{s.name}</h3>
                    <div className="row gap wrap">
                      <Badge tone={s.access_mode === 'assisted' ? 'warn' : 'info'}>{t(`src.mode.${s.access_mode}`)}</Badge>
                      <Badge tone={s.enabled ? 'ok' : 'neutral'}>{s.enabled ? t('common.enabled') : t('common.disabled')}</Badge>
                    </div>
                  </div>
                  <p className="small">{s.kind.toUpperCase()} · {h ? <a href={h} target="_blank" rel="noopener noreferrer">{s.url}</a> : s.url}</p>
                  <p className="muted small">
                    {[s.language, s.country].filter(Boolean).join(' · ')}
                    {` ${t('src.lastScan')} : ${s.last_scan_at ? fmtDate(s.last_scan_at, lang, true) : t('common.never')}`}
                    {s.last_status && ` (${s.last_status})`} · {t('src.found')} : {s.contests_found}
                  </p>
                  {s.tos_note && <p className="note">{t('src.tos')} : {s.tos_note}</p>}
                  <div className="row gap wrap">
                    <button className="btn" onClick={() => act(() => api.patchSource(s.id, { enabled: !s.enabled }), t('src.updated'))}>
                      {s.enabled ? t('src.disable') : t('src.enable')}<span className="sr-only"> {s.name}</span>
                    </button>
                    <button className="btn btn-primary" disabled={!s.enabled} onClick={() => act(() => api.scanSource(s.id), t('src.scanStarted'))}>
                      {t('src.scan')}<span className="sr-only"> {s.name}</span>
                    </button>
                    <button className="btn" aria-expanded={Boolean(quality[s.id])} onClick={() => toggleQuality(s.id)}>
                      {quality[s.id] ? t('src.qualityHide') : t('src.quality')}<span className="sr-only"> {s.name}</span>
                    </button>
                  </div>
                  {quality[s.id] && <QualityView q={quality[s.id]!} />}
                </article>
              );
            })}
          </div>
        )}
      </Async>

      <section className="card">
        <h2>{t('src.sugTitle')}</h2>
        <p className="muted small">{t('src.sugHelp')}</p>
        <Async state={sug} isEmpty={(l) => l.length === 0} empty={t('src.sugNone')}>
          {(l) => (
            <ul className="list">
              {l.map((x) => (
                <li key={x.domain} className="row between wrap gap">
                  <div>
                    <strong>{x.domain}</strong> <span className="muted small">· {x.contests} {t('src.sugCount')}</span>
                    {x.examples.length > 0 && <div className="small muted">{x.examples.join(' · ')}</div>}
                  </div>
                  <button className="btn" onClick={() => act(() => api.followSite(x.domain), t('src.followed'))}>
                    {t('src.follow')}<span className="sr-only"> {x.domain}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Async>
        <form className="row gap wrap" onSubmit={(e) => { e.preventDefault(); act(() => api.followSite(domain.trim()), t('src.followed')).then(() => setDomain('')); }}>
          <div className="field"><label htmlFor="sd">{t('src.addSite')}</label>
            <input id="sd" required value={domain} onChange={(e) => setDomain(e.target.value)} placeholder={t('src.domain')} /></div>
          <div className="field"><button className="btn btn-primary">{t('src.follow')}</button></div>
        </form>
      </section>

      <section className="card">
        <h2>{t('src.impTitle')}</h2>
        <p className="muted small">{t('src.impHelp')}</p>
        <form onSubmit={doImport}>
          <div className="field wide"><label htmlFor="imp" className="sr-only">{t('src.impTitle')}</label>
            <textarea id="imp" rows={4} required value={imp} onChange={(e) => setImp(e.target.value)} placeholder={'https://marque.fr/jeu-concours ; Gagnez un vélo ; 31/12/2026'} /></div>
          <button className="btn btn-primary">{t('src.impBtn')}</button>
        </form>
        {impRes && <ul className="list small">{impRes.map((l, i) => <li key={i}>{l}</li>)}</ul>}
      </section>

      <Async state={pol}>
        {(p) => (
          <section className="card">
            <h2>{t('src.refTitle')}</h2>
            <p className="muted small">{t('src.refHelp')}</p>
            <ul className="list">
              {p.references.map((r) => {
                const h = safeHref(r.url);
                return (
                  <li key={r.domain}>
                    <div className="row between wrap gap">
                      <strong>{r.name}</strong>
                      {h && <a className="btn" href={h} target="_blank" rel="noopener noreferrer">{t('src.refOpen')}<span className="sr-only"> {r.name}</span></a>}
                    </div>
                    <p className="small">{r.how_to}</p>
                    <p className="muted small">{r.reason}{r.unlock && ` ${t('src.refUnlock')} : ${r.unlock}`}</p>
                  </li>
                );
              })}
            </ul>
            <h3>{t('src.matrixTitle')}</h3>
            <ul className="list">
              {p.matrix.map((m) => (
                <li key={m.domain}>
                  <div className="row between wrap gap">
                    <strong>{m.name}</strong>
                    <Badge tone={m.automated_extraction ? 'ok' : 'warn'}>{t('src.matrixAuto')} : {m.automated_extraction ? t('src.yes') : t('src.no')}</Badge>
                  </div>
                  <p className="muted small">{m.reason}</p>
                  {m.modes.length > 0 && <p className="small">{t('src.mode')} : {m.modes.join(', ')}</p>}
                </li>
              ))}
            </ul>
          </section>
        )}
      </Async>

      <section className="card">
        <h2>{t('src.add')}</h2>
        <form className="form-grid" onSubmit={add}>
          <div className="field"><label htmlFor="sn">{t('common.name')}</label><input id="sn" required value={name} onChange={(e) => setName(e.target.value)} /></div>
          <div className="field"><label htmlFor="sk">{t('src.kind')}</label>
            <select id="sk" value={kind} onChange={(e) => setKind(e.target.value as 'rss' | 'html')}><option value="rss">RSS</option><option value="html">HTML</option></select></div>
          <div className="field wide"><label htmlFor="su">{t('common.url')}</label><input id="su" type="url" required value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" /></div>
          <div className="field"><label htmlFor="sl">{t('src.lang')}</label><input id="sl" value={language} onChange={(e) => setLanguage(e.target.value)} /></div>
          <div className="field"><label htmlFor="sc">{t('src.ctry')}</label><input id="sc" value={country} onChange={(e) => setCountry(e.target.value)} /></div>
          <div className="field"><button className="btn btn-primary" disabled={busy}>{t('common.add')}</button></div>
        </form>
      </section>

      <section>
        <h2>{t('src.jobs')}</h2>
        <Async state={jobs} isEmpty={(l) => l.length === 0} empty={t('src.noJobs')}>
          {(l) => (
            <div className="table-wrap"><table>
              <thead><tr>
                <th scope="col">{t('dash.source')}</th><th scope="col">{t('common.status')}</th><th scope="col">{t('src.started')}</th>
                <th scope="col">{t('src.finished')}</th><th scope="col" className="num">{t('src.found2')}</th><th scope="col" className="num">{t('src.new')}</th>
              </tr></thead>
              <tbody>{l.map((j) => (
                <tr key={j.id}>
                  <th scope="row">{j.source_name ?? '—'}</th>
                  <td>{j.status}{j.error && <div className="danger small">{j.error}</div>}</td>
                  <td>{fmtDate(j.started_at, lang, true)}</td><td>{fmtDate(j.finished_at, lang, true)}</td>
                  <td className="num">{j.found}</td><td className="num">{j.new}</td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
        </Async>
      </section>
    </>
  );
}

function QualityView({ q }: { q: SourceQuality }) {
  const { t } = useI18n();
  const keys = ['official_link', 'with_rules', 'conditions_known', 'qualified', 'to_verify', 'missing_end_date', 'missing_prize', 'inconsistent_dates', 'expired'];
  return (
    <div className="note">
      <p className="small">{q.metrics.contests} · {q.metrics.merged_duplicates} {t('src.q.dups')} · {q.restrictions.blocked_scans} {t('src.q.blocked')}</p>
      <ul className="list small">{keys.map((k) => <li key={k}>{t(`src.q.${k}`)} : {q.metrics[k]} ({q.percent[k]} %)</li>)}</ul>
      <p className="small"><strong>{t('src.qIssues')}</strong> : {q.issues.length ? q.issues.join(' · ') : t('src.qNone')}</p>
    </div>
  );
}
