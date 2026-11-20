import { Link } from 'react-router-dom';
import { api } from '../api';
import { Async } from '../components/Async';
import { NOTIF_EVENT } from '../components/Layout';
import { PageHeader } from '../components/PageHeader';
import { useToast } from '../components/Toast';
import { useAsync } from '../hooks';
import { useI18n } from '../i18n';
import { fmtDate } from '../util';

export function Notifications() {
  const { t, lang } = useI18n();
  const toast = useToast();
  const list = useAsync(() => api.notifications(), []);
  const changed = () => { list.reload(); window.dispatchEvent(new Event(NOTIF_EVENT)); };
  const markRead = async (id: number) => { try { await api.readNotification(id); changed(); } catch (e) { toast.err(e); } };
  const markAll = async () => { try { await api.readAllNotifications(); changed(); } catch (e) { toast.err(e); } };
  const unread = list.data ? list.data.filter((n) => !n.read).length : 0;
  return (
    <>
      <PageHeader title={t('not.title')}>
        <button className="btn" onClick={list.reload}>{t('common.refresh')}</button>
        <button className="btn btn-primary" disabled={unread === 0} onClick={markAll}>{t('not.readAll')}</button>
      </PageHeader>
      <Async state={list} isEmpty={(l) => l.length === 0} empty={t('not.empty')}>
        {(l) => (
          <>
            <p className="muted" aria-live="polite">{t('not.unread', { n: unread })}</p>
            <ul className="plain stack">
              {l.map((n) => (
                <li key={n.id} className={`card notif${n.read ? ' read' : ''}`}>
                  <div className="row between wrap">
                    <strong>{!n.read && <span className="dot" aria-hidden="true" />}{n.title}</strong>
                    <span className="muted small">{fmtDate(n.created_at, lang, true)}</span>
                  </div>
                  {n.body && <p>{n.body}</p>}
                  <div className="row gap">
                    {n.contest_id !== null && <Link className="btn btn-sm" to={`/contests/${n.contest_id}`}>{t('not.openContest')}</Link>}
                    {!n.read && <button className="btn btn-sm" onClick={() => markRead(n.id)}>{t('not.markRead')}</button>}
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </Async>
    </>
  );
}
