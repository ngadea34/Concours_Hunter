import { useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { Async } from '../components/Async';
import { ContestCard } from '../components/ContestCard';
import { Modal } from '../components/Modal';
import { PageHeader } from '../components/PageHeader';
import { Pagination } from '../components/Pagination';
import { useToast } from '../components/Toast';
import { useAsync } from '../hooks';
import { useI18n } from '../i18n';
import { CONTEST_STATUSES, FREE_STATUSES, PRIZE_CATEGORIES, TRI_STATES, type ContestQuery } from '../types';
import { emptyToUndef } from '../util';

const PAGE_SIZE = 12;
const SORTS = ['end_date', '-interest', '-reliability', '-created'];

export function Catalog() {
  const { t } = useI18n();
  const toast = useToast();
  const nav = useNavigate();
  const [sp, setSp] = useSearchParams();
  const [showAdv, setShowAdv] = useState<boolean>(() => typeof window === 'undefined' || window.innerWidth >= 768);
  const [addOpen, setAddOpen] = useState(false);
  const [addUrl, setAddUrl] = useState('');
  const [addTitle, setAddTitle] = useState('');
  const [busy, setBusy] = useState(false);

  const get = (k: string) => sp.get(k) ?? '';
  const set = (k: string, v: string) => {
    const n = new URLSearchParams(sp);
    if (v === '') n.delete(k); else n.set(k, v);
    if (k !== 'page') n.delete('page');
    setSp(n, { replace: true });
  };
  const page = Math.max(1, Number(get('page')) || 1);
  const query: ContestQuery = {
    q: emptyToUndef(get('q')), status: get('status') || undefined, category: get('category') || undefined,
    free_status: get('free_status') || undefined, fr_eligible: get('fr_eligible') || undefined,
    closing_within_days: get('closing') ? Number(get('closing')) : undefined,
    min_reliability: get('minrel') ? Number(get('minrel')) : undefined,
    sort: get('sort') || 'end_date', page, page_size: PAGE_SIZE,
  };
  const key = sp.toString();
  const list = useAsync(() => api.contests(query), [key]);

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const c = await api.addContest({ url: addUrl.trim(), title: emptyToUndef(addTitle) });
      toast.ok(t('cat.added'));
      setAddOpen(false); setAddUrl(''); setAddTitle('');
      nav(`/contests/${c.id}`);
    } catch (err) { toast.err(err); } finally { setBusy(false); }
  };

  const sel = (id: string, label: string, k: string, opts: { v: string; l: string }[]) => (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={get(k)} onChange={(e) => set(k, e.target.value)}>
        <option value="">{t('common.any')}</option>
        {opts.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
      </select>
    </div>
  );

  return (
    <>
      <PageHeader title={t('cat.title')}>
        <button className="btn btn-primary" onClick={() => setAddOpen(true)}>{t('cat.addByUrl')}</button>
      </PageHeader>
      <p className="muted small">{t('disclaimer.scores')}</p>
      <form className="card filters" role="search" aria-label={t('cat.filters')} onSubmit={(e) => e.preventDefault()}>
        <div className="field wide">
          <label htmlFor="f-q">{t('cat.search')}</label>
          <input id="f-q" type="search" value={get('q')} placeholder={t('cat.searchPh')} onChange={(e) => set('q', e.target.value)} />
        </div>
        <div className="field filters-toggle">
          <button type="button" className="btn" aria-expanded={showAdv} aria-controls="adv-filters" onClick={() => setShowAdv((v) => !v)}>
            {showAdv ? t('cat.hideFilters') : t('cat.showFilters')}
          </button>
        </div>
        <div id="adv-filters" className={showAdv ? 'adv-filters' : 'adv-filters adv-hidden'}>
        {sel('f-status', t('common.status'), 'status', CONTEST_STATUSES.map((v) => ({ v, l: t(`status.${v}`) })))}
        {sel('f-cat', t('cat.category'), 'category', PRIZE_CATEGORIES.map((v) => ({ v, l: t(`prize.${v}`) })))}
        {sel('f-free', t('cat.free'), 'free_status', FREE_STATUSES.map((v) => ({ v, l: t(`free.${v}`) })))}
        {sel('f-fr', t('cat.fr'), 'fr_eligible', TRI_STATES.map((v) => ({ v, l: t(`tri.${v}`) })))}
        <div className="field">
          <label htmlFor="f-close">{t('cat.closingWithin')}</label>
          <input id="f-close" type="number" min={0} value={get('closing')} onChange={(e) => set('closing', e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="f-rel">{t('cat.minRel')} : {get('minrel') || 0}</label>
          <input id="f-rel" type="range" min={0} max={100} step={5} value={get('minrel') || 0} onChange={(e) => set('minrel', e.target.value === '0' ? '' : e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="f-sort">{t('cat.sort')}</label>
          <select id="f-sort" value={get('sort') || 'end_date'} onChange={(e) => set('sort', e.target.value)}>
            {SORTS.map((s) => <option key={s} value={s}>{t(`cat.sort.${s}`)}</option>)}
          </select>
        </div>
        <div className="field"><button type="button" className="btn" onClick={() => setSp({}, { replace: true })}>{t('cat.reset')}</button></div>
        </div>
      </form>
      <Async state={list} isEmpty={(p) => p.items.length === 0}>
        {(p) => (
          <>
            <p className="muted" aria-live="polite">{t('common.total', { n: p.total })}</p>
            <div className="grid">{p.items.map((c) => <ContestCard key={c.id} c={c} />)}</div>
            <Pagination page={p.page} pageSize={p.page_size} total={p.total} onPage={(n) => set('page', String(n))} />
          </>
        )}
      </Async>
      <Modal open={addOpen} title={t('cat.addTitle')} onClose={() => setAddOpen(false)}>
        <form onSubmit={add} className="stack">
          <div className="field">
            <label htmlFor="add-url">{t('cat.addUrl')}</label>
            <input id="add-url" type="url" required value={addUrl} onChange={(e) => setAddUrl(e.target.value)} placeholder="https://" />
          </div>
          <div className="field">
            <label htmlFor="add-title">{t('cat.addName')}</label>
            <input id="add-title" value={addTitle} onChange={(e) => setAddTitle(e.target.value)} />
          </div>
          <div className="row gap">
            <button className="btn btn-primary" disabled={busy}>{t('common.add')}</button>
            <button type="button" className="btn" onClick={() => setAddOpen(false)}>{t('common.cancel')}</button>
          </div>
        </form>
      </Modal>
    </>
  );
}
