import type { ReactNode } from 'react';
import { useI18n } from '../i18n';
import type { AsyncState } from '../hooks';

export function Loading() {
  const { t } = useI18n();
  return <p className="muted" role="status">{t('common.loading')}</p>;
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useI18n();
  return (
    <div className="alert alert-err" role="alert">
      <span>{message}</span>
      {onRetry && <button className="btn btn-sm" onClick={onRetry}>{t('common.retry')}</button>}
    </div>
  );
}

export function Empty({ children }: { children?: ReactNode }) {
  const { t } = useI18n();
  return <p className="empty">{children ?? t('common.empty')}</p>;
}

export function Async<T>({ state, children, isEmpty, empty }: {
  state: AsyncState<T>; children: (d: T) => ReactNode; isEmpty?: (d: T) => boolean; empty?: ReactNode;
}) {
  if (state.error) return <ErrorBox message={state.error} onRetry={state.reload} />;
  if (state.data === null) return state.loading ? <Loading /> : null;
  if (isEmpty && isEmpty(state.data)) return <Empty>{empty}</Empty>;
  return <>{children(state.data)}</>;
}
