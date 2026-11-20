import { useCallback, useEffect, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { api } from '../api';
import { useI18n, type Lang } from '../i18n';

const items = [
  { to: '/', key: 'nav.dashboard', icon: '▦', end: true },
  { to: '/week', key: 'nav.week', icon: '◷' },
  { to: '/shop', key: 'nav.shop', icon: '€' },
  { to: '/catalog', key: 'nav.catalog', icon: '☰' },
  { to: '/review', key: 'nav.review', icon: '?' },
  { to: '/participations', key: 'nav.participations', icon: '✎' },
  { to: '/results', key: 'nav.results', icon: '★' },
  { to: '/notifications', key: 'nav.notifications', icon: '●', badge: true },
  { to: '/sources', key: 'nav.sources', icon: '⇄' },
  { to: '/settings', key: 'nav.settings', icon: '⚙' },
];

export const NOTIF_EVENT = 'ch:notifications-changed';

export function Layout() {
  const { t, lang, setLang } = useI18n();
  const [unread, setUnread] = useState(0);
  const refresh = useCallback(() => {
    api.notifications(true).then((l) => setUnread(l.length), () => undefined);
  }, []);
  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 60000);
    window.addEventListener(NOTIF_EVENT, refresh);
    return () => { window.clearInterval(id); window.removeEventListener(NOTIF_EVENT, refresh); };
  }, [refresh]);
  return (
    <div className="shell">
      <a className="skip" href="#main">{t('nav.skip')}</a>
      <header className="sidebar">
        <div className="brand">
          <strong>{t('app.name')}</strong>
          <span className="muted small tagline">{t('app.tagline')}</span>
        </div>
        <nav aria-label={t('nav.main')}>
          <ul>
            {items.map((i) => (
              <li key={i.to}>
                <NavLink to={i.to} end={i.end} className={({ isActive }) => `navlink${isActive ? ' active' : ''}`}>
                  <span className="navicon" aria-hidden="true">{i.icon}</span>
                  <span className="navlabel">{t(i.key)}</span>
                  {i.badge && unread > 0 && (
                    <span className="count" aria-label={t('not.unreadBadge', { n: unread })}>{unread > 99 ? '99+' : unread}</span>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <div className="langsw">
          <label htmlFor="lang" className="sr-only">{t('common.language')}</label>
          <select id="lang" value={lang} onChange={(e) => setLang(e.target.value as Lang)}>
            <option value="fr">{t('lang.fr')}</option>
            <option value="en">{t('lang.en')}</option>
          </select>
        </div>
      </header>
      <main id="main" className="main" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}
