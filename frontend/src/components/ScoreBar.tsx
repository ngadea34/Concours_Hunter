import { fmtNum } from '../util';

export function ScoreBar({ label, value }: { label: string; value: number | null }) {
  const pct = value === null ? 0 : Math.max(0, Math.min(100, value));
  return (
    <div className="score">
      <div className="score-head"><span>{label}</span><strong>{value === null ? '—' : fmtNum(value)}<span className="muted">/100</span></strong></div>
      <div className="bar" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={value ?? undefined}>
        <div className="bar-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
