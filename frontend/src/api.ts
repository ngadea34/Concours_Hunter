import type * as T from './types';

const TOKEN_KEY = 'ch_token';

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(token: string): void {
  try { localStorage.setItem(TOKEN_KEY, token); } catch { /* stockage indisponible */ }
}
export function clearToken(): void {
  try { localStorage.removeItem(TOKEN_KEY); } catch { /* stockage indisponible */ }
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

type Query = Record<string, string | number | boolean | undefined | null>;

function qs(q?: Query): string {
  if (!q) return '';
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(q)) {
    if (v !== undefined && v !== null && v !== '') p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : '';
}

async function request<R>(method: string, path: string, body?: unknown, query?: Query): Promise<R> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  const token = getToken();
  if (token) headers['X-CH-Token'] = token;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  let res: Response;
  try {
    res = await fetch(`/api${path}${qs(query)}`, {
      method, headers, body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError('network', 0);
  }
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data && data.detail !== undefined) {
        detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
    } catch { /* corps non JSON */ }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return undefined as R;
  return (await res.json()) as R;
}

const get = <R>(p: string, q?: Query) => request<R>('GET', p, undefined, q);
const post = <R>(p: string, b?: unknown) => request<R>('POST', p, b ?? {});
const patch = <R>(p: string, b: unknown) => request<R>('PATCH', p, b);
const put = <R>(p: string, b: unknown) => request<R>('PUT', p, b);

export const api = {
  health: () => get<{ status: string; version: string }>('/health'),
  authCheck: () => get<{ ok: boolean; needs_token: boolean }>('/auth/check'),
  stats: () => get<T.Stats>('/stats'),
  contests: (q: T.ContestQuery) => get<T.Page<T.ContestSummary>>('/contests', q as Query),
  addContest: (b: { url: string; title?: string }) => post<T.ContestDetail>('/contests', b),
  contest: (id: number) => get<T.ContestDetail>(`/contests/${id}`),
  patchContest: (id: number, b: { status?: T.ContestStatus; notes?: string; personal_interest?: number }) =>
    patch<T.ContestDetail>(`/contests/${id}`, b),
  requalify: (id: number, b: { rules_text?: string }) => post<T.ContestDetail>(`/contests/${id}/requalify`, b),
  verify: (id: number, b: { field: 'free' | 'eligibility'; decision: string; evidence?: string }) =>
    post<T.ContestDetail>(`/contests/${id}/verify`, b),
  reviewQueue: () => get<T.ContestSummary[]>('/review-queue'),
  createParticipation: (id: number, b: { mode?: T.Mode }) => post<T.Participation>(`/contests/${id}/participations`, b),
  participations: (q?: { status?: string; url?: string }) => get<T.Participation[]>('/participations', q),
  prefill: (id: number) => get<T.Prefill>(`/participations/${id}/prefill`),
  submitted: (id: number, b: { note?: string; time_spent_minutes?: number }) =>
    post<T.Participation>(`/participations/${id}/submitted`, b),
  confirmed: (id: number, b: { note?: string }) => post<T.Participation>(`/participations/${id}/confirmed`, b),
  failed: (id: number, b: { error: string }) => post<T.Participation>(`/participations/${id}/failed`, b),
  cancel: (id: number) => post<T.Participation>(`/participations/${id}/cancel`),
  results: () => get<T.Result[]>('/results'),
  addResult: (b: { contest_id?: number; participation_id?: number; outcome: T.Outcome; message_text?: string; sender?: string }) =>
    post<T.Result>('/results', b),
  verifyResult: (id: number, b: { verified: boolean }) => post<T.Result>(`/results/${id}/verify`, b),
  claims: () => get<T.Claim[]>('/claims'),
  addClaim: (b: { result_id: number; prize_name?: string; deadline?: string; fees_eur?: number; value_eur?: number }) =>
    post<T.Claim>('/claims', b),
  patchClaim: (id: number, b: { status?: T.ClaimStatus; notes?: string; deadline?: string; fees_eur?: number; value_eur?: number }) =>
    patch<T.Claim>(`/claims/${id}`, b),
  notifications: (unreadOnly?: boolean) => get<T.Notification[]>('/notifications', { unread_only: unreadOnly }),
  readNotification: (id: number) => post<{ ok: boolean }>(`/notifications/${id}/read`),
  readAllNotifications: () => post<{ ok: boolean }>('/notifications/read-all'),
  sources: () => get<T.Source[]>('/sources'),
  addSource: (b: { name: string; kind: 'rss' | 'html'; url: string; language?: string; country?: string }) =>
    post<T.Source>('/sources', b),
  patchSource: (id: number, b: { enabled?: boolean; name?: string }) => patch<T.Source>(`/sources/${id}`, b),
  scanSource: (id: number) => post<T.ScanJob>(`/sources/${id}/scan`),
  scanJobs: () => get<T.ScanJob[]>('/scan-jobs'),
  profile: () => get<T.Profile>('/profile'),
  saveProfile: (b: T.Profile) => put<T.Profile>('/profile', b),
  consents: () => get<T.Consents>('/consents'),
  saveConsents: (b: Partial<T.Consents>) => put<T.Consents>('/consents', b),
  settings: () => get<T.Settings>('/settings'),
  saveSettings: (b: Partial<T.Settings>) => put<T.Settings>('/settings', b),
  scheduler: () => get<T.SchedulerStatus>('/scheduler/status'),
  schedulerAction: (a: 'pause' | 'resume' | 'stop-all') => post<T.SchedulerStatus>(`/scheduler/${a}`),
  runJob: (id: string) => post<T.SchedulerStatus>(`/scheduler/run/${encodeURIComponent(id)}`),
  backup: () => post<{ name: string; size: number }>('/admin/backup'),
  backups: () => get<T.BackupInfo[]>('/admin/backups'),
  restore: (name: string) => post<{ ok: boolean }>('/admin/restore', { name }),
  diagnostics: () => get<T.Diagnostics>('/admin/diagnostics'),
  logs: (limit?: number) => get<T.AuditLog[]>('/admin/logs', { limit }),
};
