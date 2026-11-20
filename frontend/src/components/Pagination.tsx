import { useI18n } from '../i18n';

export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const { t } = useI18n();
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <nav className="pagination" aria-label="Pagination">
      <button className="btn" disabled={page <= 1} onClick={() => onPage(page - 1)}>{t('common.prev')}</button>
      <span>{t('common.page', { page, pages })}</span>
      <button className="btn" disabled={page >= pages} onClick={() => onPage(page + 1)}>{t('common.next')}</button>
    </nav>
  );
}
