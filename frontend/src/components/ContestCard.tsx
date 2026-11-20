import { Link } from 'react-router-dom';
import { useI18n } from '../i18n';
import type { ContestSummary, FreeStatus, TriState } from '../types';
import { daysLabel, fmtEur, safeHref } from '../util';
import { Badge, type Tone } from './Badge';
import { ScoreBar } from './ScoreBar';

const freeTone: Record<FreeStatus, Tone> = { free: 'ok', free_alternative: 'ok', purchase_required: 'bad', unknown: 'warn' };
const eligTone: Record<TriState, Tone> = { yes: 'ok', no: 'bad', unknown: 'warn' };

export function ContestBadges({ c }: { c: ContestSummary }) {
  const { t } = useI18n();
  return (
    <div className="badges">
      <Badge tone="info">{t(`status.${c.status}`)}</Badge>
      <Badge tone={freeTone[c.free_status]}>{t(`free.${c.free_status}`)}</Badge>
      <Badge tone={eligTone[c.fr_eligible]}>{t(`elig.${c.fr_eligible}`)}</Badge>
      {c.category && <Badge>{t(`prize.${c.category}`)}</Badge>}
      {c.participated && <Badge tone="info">{t('cat.participated')}</Badge>}
    </div>
  );
}

export function ContestCard({ c, compact }: { c: ContestSummary; compact?: boolean }) {
  const { t, lang } = useI18n();
  const href = safeHref(c.url);
  const urgent = c.days_left !== null && c.days_left >= 0 && c.days_left < 3;
  return (
    <article className="card contest">
      <h3><Link to={`/contests/${c.id}`}>{c.title}</Link></h3>
      <p className="muted small">
        {c.organizer_name ? t('cat.by', { name: c.organizer_name }) : ''}
        {c.source_names.length > 0 && ` · ${c.source_names.join(', ')}`}
      </p>
      {c.prize_summary && <p><strong>{t('cat.prize')} :</strong> {c.prize_summary}</p>}
      <p className="row gap">
        <span><strong>{t('cat.value')} :</strong> {fmtEur(c.total_prize_value_eur, lang)}</span>
        <span className={urgent ? 'danger' : ''}>{daysLabel(c.days_left, t)}</span>
      </p>
      <ContestBadges c={c} />
      {c.needs_human_reason && <p className="note">{t('cat.humanNeeded', { reason: c.needs_human_reason })}</p>}
      {!compact && (
        <>
          <div className="scores">
            <ScoreBar label={t('cat.reliability')} value={c.reliability_score} />
            <ScoreBar label={t('cat.interest')} value={c.interest_score} />
          </div>
          <p className="muted small">{t('disclaimer.scores')}</p>
          <div className="row gap">
            <Link className="btn btn-primary" to={`/contests/${c.id}`}>{t('common.details')}</Link>
            {href && <a className="btn" href={href} target="_blank" rel="noopener noreferrer">{t('common.openSite')} <span className="sr-only">{t('common.newTab')}</span></a>}
          </div>
        </>
      )}
    </article>
  );
}
