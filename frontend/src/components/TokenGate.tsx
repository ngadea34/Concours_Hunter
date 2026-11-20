import { useState, type FormEvent } from 'react';
import { api, clearToken, setToken } from '../api';
import { useI18n } from '../i18n';

export function TokenGate({ onOk }: { onOk: () => void }) {
  const { t } = useI18n();
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setToken(value.trim());
    try {
      const r = await api.authCheck();
      if (r.needs_token) { clearToken(); setError(t('auth.invalid')); } else onOk();
    } catch (err) {
      clearToken();
      setError(err instanceof Error && err.message !== 'network' ? err.message : t('common.error.network'));
    } finally { setBusy(false); }
  };
  return (
    <main className="gate">
      <form className="card" onSubmit={submit}>
        <h1>{t('auth.title')}</h1>
        <p>{t('auth.help')}</p>
        <label htmlFor="tok">{t('auth.label')}</label>
        <input id="tok" type="password" autoComplete="off" value={value} onChange={(e) => setValue(e.target.value)} required />
        {error && <p className="alert alert-err" role="alert">{error}</p>}
        <button className="btn btn-primary" disabled={busy || !value.trim()}>{t('auth.submit')}</button>
      </form>
    </main>
  );
}
