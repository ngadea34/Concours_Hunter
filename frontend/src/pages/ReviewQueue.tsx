import { api } from '../api';
import { Async } from '../components/Async';
import { ContestCard } from '../components/ContestCard';
import { PageHeader } from '../components/PageHeader';
import { useAsync } from '../hooks';
import { useI18n } from '../i18n';

export function ReviewQueue() {
  const { t } = useI18n();
  const q = useAsync(() => api.reviewQueue(), []);
  return (
    <>
      <PageHeader title={t('rev.title')}>
        <button className="btn" onClick={q.reload}>{t('common.refresh')}</button>
      </PageHeader>
      <p className="muted">{t('rev.help')}</p>
      <Async state={q} isEmpty={(l) => l.length === 0} empty={t('rev.empty')}>
        {(l) => (
          <div className="grid">
            {l.map((c) => (
              <div key={c.id} className="stack">
                <p className="reason"><strong>{t('common.reason')} :</strong> {c.needs_human_reason ?? t('common.unknown')}</p>
                <ContestCard c={{ ...c, needs_human_reason: null }} />
              </div>
            ))}
          </div>
        )}
      </Async>
    </>
  );
}
