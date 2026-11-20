import { useEffect, useState } from 'react';
import { Route, Routes } from 'react-router-dom';
import { api } from './api';
import { Layout } from './components/Layout';
import { TokenGate } from './components/TokenGate';
import { ErrorBox, Loading } from './components/Async';
import { useI18n } from './i18n';
import { errMsg } from './util';
import { Dashboard } from './pages/Dashboard';
import { Shop } from './pages/Shop';
import { Week } from './pages/Week';
import { Catalog } from './pages/Catalog';
import { ContestPage } from './pages/ContestPage';
import { ReviewQueue } from './pages/ReviewQueue';
import { Participations } from './pages/Participations';
import { Results } from './pages/Results';
import { Notifications } from './pages/Notifications';
import { Sources } from './pages/Sources';
import { SettingsPage } from './pages/SettingsPage';

export function App() {
  const { t } = useI18n();
  const [state, setState] = useState<'checking' | 'ok' | 'token'>('checking');
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let off = false;
    setState('checking');
    setError(null);
    api.authCheck().then(
      (r) => { if (!off) setState(r.needs_token ? 'token' : 'ok'); },
      (e) => { if (!off) { setError(errMsg(e, t)); setState('ok'); } },
    );
    return () => { off = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick]);
  if (state === 'checking') return <main className="gate"><Loading /></main>;
  if (state === 'token') return <TokenGate onOk={() => setTick((n) => n + 1)} />;
  if (error) return <main className="gate"><ErrorBox message={error} onRetry={() => setTick((n) => n + 1)} /></main>;
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="week" element={<Week />} />
        <Route path="shop" element={<Shop />} />
        <Route path="catalog" element={<Catalog />} />
        <Route path="contests/:id" element={<ContestPage />} />
        <Route path="review" element={<ReviewQueue />} />
        <Route path="participations" element={<Participations />} />
        <Route path="results" element={<Results />} />
        <Route path="notifications" element={<Notifications />} />
        <Route path="sources" element={<Sources />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Dashboard />} />
      </Route>
    </Routes>
  );
}
