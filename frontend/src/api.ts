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
  addSource: (b: { name: string; kind: 'rss' | 'html' | 'site'; url: string; language?: string; country?: string }) =>
    post<T.Source>('/sources', b),
  patchSource: (id: number, b: { enabled?: boolean; name?: string }) => patch<T.Source>(`/sources/${id}`, b),
  siteSuggestions: () => get<T.SiteSuggestion[]>('/sources/suggestions'),
  followSite: (domain: string) => post<T.Source>('/sources/follow', { domain }),
  scanSource: (id: number) => post<T.ScanJob>(`/sources/${id}/scan`),
  sourcePolicy: () => get<T.SourcePolicy>('/sources/policy'),
  sourceQuality: (id: number) => get<T.SourceQuality>(`/sources/${id}/quality`),
  importContests: (text: string) => post<T.ImportResult>('/contests/import', { text }),
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
  // M15 programme de la semaine
  week: (week?: string) => get<T.WeekView>('/weekly', { week }),
  makePlan: (week?: string) => request<T.WeekView>('POST', `/weekly/plan${week ? `?week=${week}` : ''}`, {}),
  weekItem: (id: number, action: string, postpone_to?: string) => post<T.WeekView>(`/weekly/items/${id}`, { action, postpone_to }),
  weekItemDone: (id: number, b: { proof_note?: string; data_url?: string; minutes?: number }) => post<T.WeekView>(`/weekly/items/${id}/done`, b),
  followOpportunity: (b: { contest_id: number; follow?: boolean; dismiss?: boolean }) => post<{ ok: boolean }>('/weekly/opportunities', b),
  patchWeekResult: (id: number, b: { status: string; note?: string; verify_url?: string }) => patch<{ ok: boolean }>(`/weekly/results/${id}`, b),
  weekTasks: (all = false) => get<T.WeekTask[]>('/weekly/tasks', { all }),
  newWeekTask: (b: { title: string; description?: string; priority: string; due?: string; action?: string }) => post<T.WeekTask>('/weekly/tasks', b),
  patchWeekTask: (id: number, b: Partial<{ title: string; description: string; priority: string; status: string; due: string; proof_note: string }>) =>
    patch<T.WeekTask>(`/weekly/tasks/${id}`, b),
  weekTaskHistory: (id: number) => get<T.TaskHistory[]>(`/weekly/tasks/${id}/history`),
  weekPrefs: () => get<T.WeekPrefs>('/weekly/preferences'),
  saveWeekPrefs: (b: Partial<T.WeekPrefs>) => put<T.WeekPrefs>('/weekly/preferences', b),
  weekReports: (kind?: string) => get<T.WeekReport[]>('/weekly/reports', { kind }),
  weekReport: (id: number) => get<T.WeekReport>(`/weekly/reports/${id}`),
  makeWeekReport: (kind: 'weekly' | 'daily' | 'review', week?: string) => request<T.WeekReport>('POST', `/weekly/reports/${kind}${week ? `?week=${week}` : ''}`, {}),
  weekCommand: (line: string) => post<{ tab: string; text: string; week: string | null }>('/weekly/command', { line }),
  promotions: () => get<T.PromoBrief[]>('/promotions'),
  addPromotion: (b: Partial<T.PromoBrief> & { title: string }) => post<T.PromoBrief>('/promotions', b),
  patchPromotion: (id: number, b: Partial<T.PromoBrief>) => patch<T.PromoBrief>(`/promotions/${id}`, b),

  // M14 Shop & Promo
  shopDashboard: () => get<T.ShopDashboard>('/shop/dashboard'),
  shopPrefs: () => get<T.ShopPrefs>('/shop/preferences'),
  putShopPrefs: (b: Partial<T.ShopPrefs>) => put<T.ShopPrefs>('/shop/preferences', b),
  shopCommand: (command: string) => post<T.ShopCommandResult>('/shop/command', { command }),
  shopDiscover: () => post<Record<string, unknown>>('/shop/discover'),
  shopAnalyze: (b: { text: string; url?: string; title?: string; save?: boolean }) =>
    post<{ analysis: Record<string, unknown> } | T.ShopOffer>('/shop/analyze', b),
  shopOffer: (id: number) => get<T.ShopOffer & { documents: T.ShopDoc[]; claims: T.ShopClaim[] }>(`/shop/promotions/${id}`),
  patchShopOffer: (id: number, b: Record<string, unknown>) => patch<T.ShopOffer>(`/shop/promotions/${id}`, b),
  addAvailability: (id: number, b: { retailer: string; level: string; store?: string; price_eur?: number; source?: string }) =>
    post<T.ShopAvailability>(`/shop/promotions/${id}/availability`, b),
  shopDocs: () => get<T.ShopDoc[]>('/shop/documents'),
  addShopDoc: (b: { kind: string; data_url: string; promotion_id?: number; claim_id?: number }) => post<T.ShopDoc>('/shop/documents', b),
  ocrShopDoc: (id: number, text?: string) => post<T.ShopDoc>(`/shop/documents/${id}/ocr`, text !== undefined ? { text } : {}),
  patchShopDoc: (id: number, b: Record<string, unknown>) => patch<T.ShopDoc>(`/shop/documents/${id}`, b),
  shopClaim: (id: number) => get<T.ShopClaim>(`/shop/claims/${id}`),
  newShopClaim: (promotion_id: number) => post<T.ShopClaim>('/shop/claims', { promotion_id }),
  shopClaimAction: (id: number, action: string, b?: Record<string, unknown>) => post<T.ShopClaim>(`/shop/claims/${id}/${action}`, b ?? {}),
  shopPreview: (id: number) => post<{ claim: T.ShopClaim; preview: T.ShopPreview }>(`/shop/claims/${id}/preview`),
  shopExpenses: (month?: string) => get<T.ShopMonth>('/shop/expenses', { month }),
  shopHistory: () => get<T.ShopMonth[]>('/shop/expenses/history'),
  shopGain: (b: { amount_eur: number; date?: string; note?: string }) => post<T.ShopMonth>('/shop/gains', b),
};
