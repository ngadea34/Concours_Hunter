import { useEffect, useState, type FormEvent } from 'react';
import { api } from '../api';
import { Async } from '../components/Async';
import { Badge } from '../components/Badge';
import { PageHeader } from '../components/PageHeader';
import { useToast } from '../components/Toast';
import { useAsync } from '../hooks';
import { useI18n, type Lang } from '../i18n';
import { PRIZE_CATEGORIES, PROFILE_FIELDS, type Consents, type Profile, type Settings } from '../types';
import { fmtDate, fmtNum } from '../util';

function ProfileSection() {
  const { t } = useI18n();
  const toast = useToast();
  const st = useAsync(() => api.profile(), []);
  const [form, setForm] = useState<Profile | null>(null);
  useEffect(() => { if (st.data) setForm(st.data); }, [st.data]);
  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (!form) return;
    try { st.setData(await api.saveProfile(form)); toast.ok(t('common.saved')); } catch (err) { toast.err(err); }
  };
  return (
    <section className="card" aria-labelledby="h-profile">
      <h2 id="h-profile">{t('set.profile')}</h2>
      <p className="note">{t('set.profileWarn')}</p>
      <Async state={st}>
        {() => form && (
          <form className="form-grid" onSubmit={save}>
            {PROFILE_FIELDS.map((f) => (
              <div className="field" key={f}>
                <label htmlFor={`pf-${f}`}>{t(`profile.${f}`)}</label>
                <input id={`pf-${f}`} value={form[f] ?? ''} type={f === 'email' ? 'email' : f === 'birth_date' ? 'date' : 'text'}
                  autoComplete="off" onChange={(e) => setForm({ ...form, [f]: e.target.value === '' ? null : e.target.value })} />
              </div>
            ))}
            <div className="field"><button className="btn btn-primary">{t('common.save')}</button></div>
          </form>
        )}
      </Async>
    </section>
  );
}

function ConsentsSection() {
  const { t, lang } = useI18n();
  const toast = useToast();
  const st = useAsync(() => api.consents(), []);
  const toggle = async (k: 'auto_participation' | 'store_proofs' | 'email_notifications', v: boolean) => {
    if (k === 'auto_participation' && v && !window.confirm(t('set.autoPartHelp'))) return;
    try { st.setData(await api.saveConsents({ [k]: v })); toast.ok(t('common.saved')); } catch (e) { toast.err(e); }
  };
  const row = (c: Consents, k: 'auto_participation' | 'store_proofs' | 'email_notifications', label: string, help: string) => (
    <div className="check" key={k}>
      <input id={`co-${k}`} type="checkbox" checked={c[k]} aria-describedby={`co-${k}-h`} onChange={(e) => toggle(k, e.target.checked)} />
      <label htmlFor={`co-${k}`}>{label}</label>
      <p id={`co-${k}-h`} className="muted small">{help}</p>
    </div>
  );
  return (
    <section className="card" aria-labelledby="h-cons">
      <h2 id="h-cons">{t('set.consents')}</h2>
      <Async state={st}>
        {(c) => (
          <>
            {row(c, 'auto_participation', t('set.autoPart'), t('set.autoPartHelp'))}
            {row(c, 'store_proofs', t('set.storeProofs'), t('set.storeProofsHelp'))}
            {row(c, 'email_notifications', t('set.emailNotif'), t('set.emailNotifHelp'))}
            {c.updated_at && <p className="muted small">{fmtDate(c.updated_at, lang, true)}</p>}
          </>
        )}
      </Async>
    </section>
  );
}

function SettingsSection() {
  const { t, setLang } = useI18n();
  const toast = useToast();
  const st = useAsync(() => api.settings(), []);
  const [f, setF] = useState<Settings | null>(null);
  useEffect(() => { if (st.data) setF(st.data); }, [st.data]);
  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (!f) return;
    try {
      const s = await api.saveSettings(f);
      st.setData(s);
      if (s.ui_language === 'fr' || s.ui_language === 'en') setLang(s.ui_language as Lang);
      toast.ok(t('common.saved'));
    } catch (err) { toast.err(err); }
  };
  return (
    <section className="card" aria-labelledby="h-set">
      <h2 id="h-set">{t('set.settings')}</h2>
      <Async state={st}>
        {() => f && (
          <form className="stack" onSubmit={save}>
            <fieldset>
              <legend>{t('set.llm')}</legend>
              <div className="check">
                <input id="s-llm" type="checkbox" checked={f.llm_enabled} onChange={(e) => setF({ ...f, llm_enabled: e.target.checked })} />
                <label htmlFor="s-llm">{t('set.llmEnabled')}</label>
              </div>
              <div className="form-grid">
                <div className="field wide"><label htmlFor="s-url">{t('set.ollamaUrl')}</label><input id="s-url" type="url" value={f.ollama_url} onChange={(e) => setF({ ...f, ollama_url: e.target.value })} /></div>
                <div className="field"><label htmlFor="s-ms">{t('set.modelSmall')}</label><input id="s-ms" value={f.llm_model_small} onChange={(e) => setF({ ...f, llm_model_small: e.target.value })} /></div>
                <div className="field"><label htmlFor="s-ml">{t('set.modelLarge')}</label><input id="s-ml" value={f.llm_model_large} onChange={(e) => setF({ ...f, llm_model_large: e.target.value })} /></div>
              </div>
            </fieldset>
            <div className="form-grid">
              <div className="field"><label htmlFor="s-int">{t('set.interval')}</label><input id="s-int" type="number" min={1} value={f.scan_interval_minutes} onChange={(e) => setF({ ...f, scan_interval_minutes: Number(e.target.value) })} /></div>
              <div className="field"><label htmlFor="s-q">{t('set.quota')}</label><input id="s-q" type="number" min={1} value={f.max_requests_per_domain_per_hour} onChange={(e) => setF({ ...f, max_requests_per_domain_per_hour: Number(e.target.value) })} /></div>
              <div className="field"><label htmlFor="s-lang">{t('set.uiLang')}</label>
                <select id="s-lang" value={f.ui_language} onChange={(e) => setF({ ...f, ui_language: e.target.value })}>
                  <option value="fr">{t('lang.fr')}</option><option value="en">{t('lang.en')}</option>
                </select></div>
            </div>
            <fieldset>
              <legend>{t('set.weights')}</legend>
              <div className="form-grid">
                {PRIZE_CATEGORIES.map((c) => (
                  <div className="field" key={c}>
                    <label htmlFor={`w-${c}`}>{t(`prize.${c}`)} : {fmtNum(f.interest_categories[c] ?? 0)}</label>
                    <input id={`w-${c}`} type="range" min={0} max={10} step={1} value={f.interest_categories[c] ?? 0}
                      onChange={(e) => setF({ ...f, interest_categories: { ...f.interest_categories, [c]: Number(e.target.value) } })} />
                  </div>
                ))}
              </div>
            </fieldset>
            <fieldset>
              <legend>{t('set.lan')}</legend>
              <div className="check">
                <input id="s-lan" type="checkbox" checked={f.lan_mode} aria-describedby="s-lan-h" onChange={(e) => setF({ ...f, lan_mode: e.target.checked })} />
                <label htmlFor="s-lan">{t('set.lan')}</label>
                <p id="s-lan-h" className="muted small">{t('set.lanHelp')}</p>
              </div>
            </fieldset>
            <div><button className="btn btn-primary">{t('common.save')}</button></div>
          </form>
        )}
      </Async>
    </section>
  );
}

function SchedulerSection() {
  const { t, lang } = useI18n();
  const toast = useToast();
  const st = useAsync(() => api.scheduler(), []);
  const act = async (fn: () => Promise<unknown>, msg: string) => {
    try { await fn(); toast.ok(msg); st.reload(); } catch (e) { toast.err(e); }
  };
  return (
    <section className="card" aria-labelledby="h-sch">
      <h2 id="h-sch">{t('set.scheduler')}</h2>
      <Async state={st}>
        {(s) => (
          <>
            <p>
              <Badge tone={s.running ? 'ok' : 'neutral'}>{s.running ? t('set.running') : t('set.stopped')}</Badge>{' '}
              {s.paused && <Badge tone="warn">{t('set.paused')}</Badge>}
            </p>
            <div className="row gap wrap">
              <button className="btn" disabled={s.paused} onClick={() => act(() => api.schedulerAction('pause'), t('set.schedulerActionDone'))}>{t('set.pause')}</button>
              <button className="btn" disabled={!s.paused} onClick={() => act(() => api.schedulerAction('resume'), t('set.schedulerActionDone'))}>{t('set.resume')}</button>
              <button className="btn btn-danger-solid" onClick={() => { if (window.confirm(t('set.stopAllConfirm'))) act(() => api.schedulerAction('stop-all'), t('set.schedulerActionDone')); }}>{t('set.stopAll')}</button>
            </div>
            {s.jobs.length > 0 && (
              <div className="table-wrap"><table>
                <thead><tr><th scope="col">{t('set.job')}</th><th scope="col">{t('set.nextRun')}</th><th scope="col">{t('set.lastRun')}</th><th scope="col">{t('set.lastStatus')}</th><th scope="col"><span className="sr-only">{t('common.actions')}</span></th></tr></thead>
                <tbody>{s.jobs.map((j) => (
                  <tr key={j.id}>
                    <th scope="row">{j.id}</th><td>{fmtDate(j.next_run, lang, true)}</td><td>{fmtDate(j.last_run, lang, true)}</td><td>{j.last_status ?? '—'}</td>
                    <td><button className="btn btn-sm" onClick={() => act(() => api.runJob(j.id), t('set.jobStarted'))}>{t('set.runNow')}<span className="sr-only"> {j.id}</span></button></td>
                  </tr>
                ))}</tbody>
              </table></div>
            )}
          </>
        )}
      </Async>
    </section>
  );
}

function Backups() {
  const { t, lang } = useI18n();
  const toast = useToast();
  const st = useAsync(() => api.backups(), []);
  const create = async () => {
    try { const r = await api.backup(); toast.ok(t('set.backupDone', { name: r.name })); st.reload(); } catch (e) { toast.err(e); }
  };
  const restore = async (name: string) => {
    if (!window.confirm(t('set.restoreConfirm', { name }))) return;
    try { await api.restore(name); toast.ok(t('set.restored')); } catch (e) { toast.err(e); }
  };
  return (
    <div>
      <h3>{t('set.backups')}</h3>
      <button className="btn btn-primary" onClick={create}>{t('set.backup')}</button>
      <Async state={st} isEmpty={(l) => l.length === 0} empty={t('set.noBackups')}>
        {(l) => (
          <div className="table-wrap"><table>
            <thead><tr><th scope="col">{t('common.name')}</th><th scope="col">{t('common.date')}</th><th scope="col" className="num">{t('common.size')}</th><th scope="col"><span className="sr-only">{t('common.actions')}</span></th></tr></thead>
            <tbody>{l.map((b) => (
              <tr key={b.name}>
                <th scope="row">{b.name}</th><td>{fmtDate(b.created_at, lang, true)}</td><td className="num">{(b.size / 1048576).toFixed(2)} Mo</td>
                <td><button className="btn btn-sm btn-danger" onClick={() => restore(b.name)}>{t('set.restore')}<span className="sr-only"> {b.name}</span></button></td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Async>
    </div>
  );
}

function Diagnostics() {
  const { t } = useI18n();
  const st = useAsync(() => api.diagnostics(), []);
  return (
    <div>
      <h3>{t('set.diag')}</h3>
      <Async state={st}>
        {(d) => (
          <dl className="kv">
            <div><dt>{t('set.version')}</dt><dd>{d.version}</dd></div>
            <div><dt>Python</dt><dd>{d.python}</dd></div>
            <div><dt>{t('set.dbPath')}</dt><dd>{d.db_path}</dd></div>
            <div><dt>{t('set.dbSize')}</dt><dd>{(d.db_size / 1048576).toFixed(2)} Mo</dd></div>
            <div><dt>{t('set.disk')}</dt><dd>{fmtNum(d.disk_free_gb)} Go</dd></div>
            <div><dt>{t('set.ollama')}</dt><dd><Badge tone={d.ollama.reachable ? 'ok' : 'bad'}>{d.ollama.reachable ? t('set.reachable') : t('set.unreachable')}</Badge>{' '}
              {d.ollama.models.length > 0 && `${t('set.models')} : ${d.ollama.models.join(', ')}`}</dd></div>
          </dl>
        )}
      </Async>
    </div>
  );
}

function Logs() {
  const { t, lang } = useI18n();
  const st = useAsync(() => api.logs(100), []);
  return (
    <div>
      <h3>{t('set.logs')}</h3>
      <Async state={st} isEmpty={(l) => l.length === 0} empty={t('set.noLogs')}>
        {(l) => (
          <div className="table-wrap"><table>
            <thead><tr><th scope="col">{t('common.date')}</th><th scope="col">{t('set.actor')}</th><th scope="col">{t('set.action')}</th><th scope="col">{t('set.detail')}</th></tr></thead>
            <tbody>{l.map((r, i) => (<tr key={i}><td>{fmtDate(r.ts, lang, true)}</td><td>{r.actor}</td><td>{r.action}</td><td>{r.detail}</td></tr>))}</tbody>
          </table></div>
        )}
      </Async>
    </div>
  );
}

function AdminSection() {
  const { t } = useI18n();
  const [diag, setDiag] = useState(false);
  const [logs, setLogs] = useState(false);
  return (
    <section className="card" aria-labelledby="h-adm">
      <h2 id="h-adm">{t('set.admin')}</h2>
      <Backups />
      <div className="row gap wrap">
        <button className="btn" aria-expanded={diag} onClick={() => setDiag((v) => !v)}>{t('set.loadDiag')}</button>
        <button className="btn" aria-expanded={logs} onClick={() => setLogs((v) => !v)}>{t('set.loadLogs')}</button>
      </div>
      {diag && <Diagnostics />}
      {logs && <Logs />}
    </section>
  );
}

function AuthorizationsSection() {
  const { t } = useI18n();
  const toast = useToast();
  const st = useAsync(() => api.settings(), []);
  const pol = useAsync(() => api.sourcePolicy(), []);
  const [domain, setDomain] = useState('');
  const [date, setDate] = useState('');
  const [reference, setReference] = useState('');
  const save = async (list: { domain: string; date: string; reference: string }[]) => {
    try { const s = await api.saveSettings({ written_authorizations: list }); st.setData(s); pol.reload(); toast.ok(t('auth.saved')); } catch (e) { toast.err(e); }
  };
  return (
    <section className="card" aria-labelledby="h-auth">
      <h2 id="h-auth">{t('wauth.title')}</h2>
      <p className="muted small">{t('wauth.help')}</p>
      <Async state={st}>
        {(s) => {
          const list = s.written_authorizations ?? [];
          const domains = (pol.data?.matrix ?? []).filter((m) => !m.authorized_in_writing && m.modes.length > 0);
          return (
            <>
              {list.length > 0 && <ul className="list">{list.map((a) => (
                <li key={a.domain} className="row between wrap gap">
                  <span><strong>{a.domain}</strong> · {a.date} · {a.reference}</span>
                  <button className="btn" onClick={() => save(list.filter((x) => x.domain !== a.domain))}>{t('auth.remove')}<span className="sr-only"> {a.domain}</span></button>
                </li>))}</ul>}
              <form className="form-grid" onSubmit={(e: FormEvent) => { e.preventDefault(); save([...list, { domain, date, reference: reference.trim() }]).then(() => setReference('')); }}>
                <div className="field"><label htmlFor="au-d">{t('auth.site')}</label>
                  <select id="au-d" required value={domain} onChange={(e) => setDomain(e.target.value)}>
                    <option value="">—</option>{domains.map((m) => <option key={m.domain} value={m.domain}>{m.name}</option>)}
                  </select></div>
                <div className="field"><label htmlFor="au-dt">{t('auth.date')}</label><input id="au-dt" type="date" required value={date} onChange={(e) => setDate(e.target.value)} /></div>
                <div className="field wide"><label htmlFor="au-r">{t('auth.reference')}</label>
                  <input id="au-r" required minLength={5} value={reference} onChange={(e) => setReference(e.target.value)} /></div>
                <div className="field"><button className="btn btn-primary">{t('common.add')}</button></div>
              </form>
            </>
          );
        }}
      </Async>
    </section>
  );
}

export function SettingsPage() {
  const { t } = useI18n();
  return (
    <>
      <PageHeader title={t('set.title')} />
      <ProfileSection />
      <ConsentsSection />
      <SettingsSection />
      <AuthorizationsSection />
      <SchedulerSection />
      <AdminSection />
    </>
  );
}
