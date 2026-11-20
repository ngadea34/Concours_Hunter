import { Link } from 'react-router-dom';
import { api } from '../api';
import { Async } from '../components/Async';
import { ContestCard } from '../components/ContestCard';
import { PageHeader } from '../components/PageHeader';
import { useAsync } from '../hooks';
import { useI18n } from '../i18n';
import { fmtEur } from '../util';

function Tile({ label, value, help, tone }: { label: string; value: string | number; help?: string; tone?: string }) {
  return (
    <div className={`tile ${tone ?? ''}`}>
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
      {help && <div className="tile-help">{help}</div>}
    </div>
  );
}

export function Dashboard() {
  const { t, lang } = useI18n();
  const stats = useAsync(() => api.stats(), []);
  const closing = useAsync(() => api.contests({ closing_within_days: 3, sort: 'end_date', page_size: 5 }), []);
  const review = useAsync(() => api.reviewQueue(), []);
  return (
    <>
      <PageHeader title={t('dash.title')}>
        <button className="btn" onClick={() => { stats.reload(); closing.reload(); review.reload(); }}>{t('common.refresh')}</button>
      </PageHeader>
      <Async state={stats}>
        {(s) => (
          <>
            <section aria-label={t('dash.title')} className="tiles">
              <Tile label={t('dash.detected')} value={s.contests_total} />
              <Tile label={t('dash.qualified')} value={s.contests_qualified} />
              <Tile label={t('dash.toVerify')} value={s.contests_to_verify} />
              <Tile label={t('dash.closing')} value={s.contests_closing_soon} tone={s.contests_closing_soon > 0 ? 'warn' : ''} />
              <Tile label={t('dash.valid')} value={s.participations_valid} />
              <Tile label={t('dash.pending')} value={s.participations_pending} />
              <Tile label={t('dash.wins')} value={s.wins} />
              <Tile label={t('dash.time')} value={t('common.minutes', { n: s.time_spent_minutes })} />
              <Tile label={t('dash.claims')} value={s.claims_open} tone={s.claims_open > 0 ? 'warn' : ''} />
            </section>
            <section className="card money" aria-labelledby="money-h">
              <h2 id="money-h" className="sr-only">{t('dash.twoNumbers')}</h2>
              <div className="money-grid">
                <div className="money-col potential">
                  <div className="tile-label">{t('dash.playedValue')}</div>
                  <div className="tile-value">{fmtEur(s.prize_value_participated_eur, lang)}</div>
                  <div className="tile-help">{t('dash.playedValueHelp')}</div>
                </div>
                <div className="money-col real">
                  <div className="tile-label">{t('dash.gains')}</div>
                  <div className="tile-value">{fmtEur(s.gains_obtained_eur, lang)}</div>
                  <div className="tile-help">{t('dash.gainsHelp')}</div>
                </div>
              </div>
              <p className="note">{t('dash.twoNumbers')}</p>
            </section>
            {s.claims_open > 0 && (
              <p className="alert alert-warn"><Link to="/results">{t('dash.claims')} : {s.claims_open}</Link></p>
            )}
            <section>
              <h2>{t('dash.bySource')}</h2>
              {s.by_source.length === 0 ? <p className="empty">{t('common.empty')}</p> : (
                <div className="table-wrap">
                  <table>
                    <thead><tr>
                      <th scope="col">{t('dash.source')}</th><th scope="col" className="num">{t('dash.contests')}</th>
                      <th scope="col" className="num">{t('dash.participations')}</th><th scope="col" className="num">{t('dash.winsCol')}</th>
                    </tr></thead>
                    <tbody>
                      {s.by_source.map((r) => (
                        <tr key={r.source}><th scope="row">{r.source}</th><td className="num">{r.contests}</td><td className="num">{r.participations}</td><td className="num">{r.wins}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        )}
      </Async>
      <div className="cols">
        <section>
          <h2>{t('dash.closingList')}</h2>
          <Async state={closing} isEmpty={(p) => p.items.length === 0} empty={t('dash.noClosing')}>
            {(p) => <div className="stack">{p.items.map((c) => <ContestCard key={c.id} c={c} compact />)}</div>}
          </Async>
        </section>
        <section>
          <h2>{t('dash.reviewList')}</h2>
          <Async state={review} isEmpty={(l) => l.length === 0} empty={t('dash.noReview')}>
            {(l) => (
              <>
                <div className="stack">{l.slice(0, 5).map((c) => <ContestCard key={c.id} c={c} compact />)}</div>
                {l.length > 5 && <p><Link to="/review">{t('dash.seeAll')} ({l.length})</Link></p>}
              </>
            )}
          </Async>
        </section>
      </div>
    </>
  );
}
