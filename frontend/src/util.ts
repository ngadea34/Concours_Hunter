import { ApiError } from './api';
import type { TFn } from './i18n';

export function errMsg(e: unknown, t: TFn): string {
  if (e instanceof ApiError) return e.status === 0 ? t('common.error.network') : e.message;
  return e instanceof Error ? e.message : String(e);
}

export function fmtDate(iso: string | null | undefined, lang: string, withTime = false): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(lang === 'en' ? 'en-GB' : 'fr-FR', withTime
    ? { dateStyle: 'medium', timeStyle: 'short' } : { dateStyle: 'medium' });
}

export function fmtEur(v: number | null | undefined, lang: string): string {
  if (v === null || v === undefined) return '—';
  return v.toLocaleString(lang === 'en' ? 'en-GB' : 'fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });
}

export function fmtNum(v: number | null | undefined): string {
  return v === null || v === undefined ? '—' : String(Math.round(v * 10) / 10);
}

export function daysLabel(d: number | null, t: TFn): string {
  if (d === null) return t('common.noDeadline');
  if (d < 0) return t('common.expired');
  return t('common.daysLeft', { n: d });
}

export function safeHref(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === 'http:' || u.protocol === 'https:' ? u.href : null;
  } catch { return null; }
}

export function emptyToUndef(s: string): string | undefined {
  const v = s.trim();
  return v === '' ? undefined : v;
}
