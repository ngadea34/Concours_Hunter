import { useState, type FormEvent } from 'react';
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
                    <Badge tone={s.enabled ? 'ok' : 'neutral'}>{s.enabled ? t('common.enabled') : t('common.disabled')}</Badge>
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
                  </div>
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
