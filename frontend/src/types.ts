export type ContestStatus = 'new' | 'qualified' | 'to_verify' | 'rejected' | 'expired' | 'participated' | 'archived';
export type FreeStatus = 'free' | 'free_alternative' | 'purchase_required' | 'unknown';
export type TriState = 'yes' | 'no' | 'unknown';
export type Mode = 'auto' | 'semi' | 'manual';
export type ParticipationStatus = 'prepared' | 'awaiting_human' | 'submitted' | 'confirmed' | 'failed' | 'cancelled';
export type PrizeCategory =
  | 'high_tech' | 'auto' | 'travel' | 'home' | 'voucher' | 'product' | 'culture'
  | 'leisure' | 'experience' | 'show' | 'restaurant' | 'cash' | 'other';
export type Outcome = 'won' | 'lost' | 'pending';
export type ClaimStatus = 'to_claim' | 'claimed' | 'received' | 'expired' | 'refused';

export const CONTEST_STATUSES: ContestStatus[] = ['new', 'qualified', 'to_verify', 'rejected', 'expired', 'participated', 'archived'];
export const FREE_STATUSES: FreeStatus[] = ['free', 'free_alternative', 'purchase_required', 'unknown'];
export const TRI_STATES: TriState[] = ['yes', 'no', 'unknown'];
export const PARTICIPATION_STATUSES: ParticipationStatus[] = ['prepared', 'awaiting_human', 'submitted', 'confirmed', 'failed', 'cancelled'];
export const PRIZE_CATEGORIES: PrizeCategory[] = [
  'high_tech', 'auto', 'travel', 'home', 'voucher', 'product', 'culture',
  'leisure', 'experience', 'show', 'restaurant', 'cash', 'other',
];
export type GameType = 'instant_win' | 'creative' | 'quiz' | 'social' | 'draw';
export const GAME_TYPES: GameType[] = ['draw', 'instant_win', 'quiz', 'creative', 'social'];
export const CLAIM_STATUSES: ClaimStatus[] = ['to_claim', 'claimed', 'received', 'expired', 'refused'];

export type AutoClass = 'A1' | 'A2' | 'A3' | 'A4' | 'A5' | 'A6' | 'A7' | 'A8';
export interface ContestSummary {
  id: number; title: string; url: string; organizer_name: string | null; source_names: string[];
  status: ContestStatus; category: PrizeCategory | null; game_type: GameType | null; prize_summary: string | null;
  total_prize_value_eur: number | null; end_date: string | null; days_left: number | null;
  language: string | null; countries_allowed: string[]; reliability_score: number | null;
  interest_score: number | null; free_status: FreeStatus; fr_eligible: TriState;
  participation_mode: Mode; participated: boolean; needs_human_reason: string | null; created_at: string;
  automation_class: AutoClass | null; difficulty: number | null; social_platform: string | null;
}
export interface Justification { field: string; decision: string; evidence: string | null; method: string }
export interface Prize {
  id: number; name: string; category: PrizeCategory; quantity: number; value: number | null;
  currency: string | null; value_eur: number | null; fees_note: string | null;
}
export interface Answer { id: number; question: string; answer: string; source: string; verified: boolean; confidence: number }
export interface Proof { id: number; kind: string; note: string | null; path: string | null; created_at: string }
export interface Participation {
  id: number; contest_id: number; contest_title: string; contest_url: string; mode: Mode;
  status: ParticipationStatus; prepared_at: string; submitted_at: string | null; error: string | null;
  time_spent_minutes: number | null; proofs: Proof[];
}
export interface ContestDetail extends ContestSummary {
  description: string | null; start_date: string | null; entry_limit: string | null; notes: string | null;
  personal_interest: number | null; min_age: number | null; countries_excluded: string[];
  rules: { url: string | null; excerpt: string | null; content_hash: string | null; analyzed_at: string | null } | null;
  prizes: Prize[]; answers: Answer[]; justifications: Justification[];
  score_breakdown: { reliability: Record<string, number>; interest: Record<string, number> };
  participations: Participation[];
  provenance: { source_name: string; source_url: string; seen_at: string }[];
}
export interface Prefill { contest_url: string; fields: Record<string, string>; answers: { question: string; answer: string }[]; warnings: string[] }
export interface Result {
  id: number; contest_id: number | null; contest_title: string | null; outcome: Outcome;
  message_text: string | null; sender: string | null; received_at: string; phishing_score: number;
  phishing_flags: string[]; verified: boolean;
}
export interface Claim {
  id: number; result_id: number; contest_title: string | null; prize_name: string | null; status: ClaimStatus;
  deadline: string | null; days_left: number | null; fees_eur: number | null; value_eur: number | null; notes: string | null;
}
export interface Notification { id: number; kind: string; title: string; body: string | null; contest_id: number | null; created_at: string; read: boolean }
export interface Source {
  id: number; name: string; kind: string; url: string; enabled: boolean; language: string | null; country: string | null;
  last_scan_at: string | null; last_status: string | null; contests_found: number; tos_note: string | null; access_mode: string;
}
export interface SiteSuggestion { domain: string; contests: number; organizer_names: string[]; examples: string[] }
export interface ScanJob {
  id: number; source_id: number | null; source_name: string | null; status: string; started_at: string;
  finished_at: string | null; found: number; new: number; error: string | null;
}
export interface Profile {
  first_name: string | null; last_name: string | null; email: string | null; phone: string | null;
  birth_date: string | null; address: string | null; postal_code: string | null; city: string | null; country: string | null;
}
export const PROFILE_FIELDS: (keyof Profile)[] = [
  'first_name', 'last_name', 'email', 'phone', 'birth_date', 'address', 'postal_code', 'city', 'country',
];
export interface Consents { auto_participation: boolean; store_proofs: boolean; email_notifications: boolean; updated_at: string | null }
export interface Settings {
  lan_mode: boolean; llm_enabled: boolean; ollama_url: string; llm_model_small: string; llm_model_large: string;
  scan_interval_minutes: number; max_requests_per_domain_per_hour: number;
  interest_categories: Record<PrizeCategory, number>; ui_language: string;
  written_authorizations?: { domain: string; date: string; reference: string }[];
}
export interface Stats {
  contests_total: number; contests_qualified: number; contests_to_verify: number; contests_closing_soon: number;
  participations_valid: number; participations_pending: number; time_spent_minutes: number;
  prize_value_participated_eur: number; gains_obtained_eur: number; wins: number; claims_open: number;
  by_source: { source: string; contests: number; participations: number; wins: number }[];
  by_country: { country: string; count: number }[];
  by_category: { category: string; count: number }[];
}
export interface Page<T> { items: T[]; total: number; page: number; page_size: number }
export interface SchedulerJob { id: string; next_run: string | null; last_run: string | null; last_status: string | null }
export interface SchedulerStatus { running: boolean; paused: boolean; jobs: SchedulerJob[] }
export interface BackupInfo { name: string; size: number; created_at: string }
export interface Diagnostics {
  python: string; db_path: string; db_size: number; ollama: { reachable: boolean; models: string[] };
  disk_free_gb: number; version: string;
}
export interface AuditLog { ts: string; actor: string; action: string; detail: string }
export interface ContestQuery {
  q?: string; status?: string; category?: string; game_type?: string; free_status?: string; fr_eligible?: string;
  automation_class?: string; max_difficulty?: number; hide_platforms?: string;
  closing_within_days?: number; min_reliability?: number; sort?: string; page?: number; page_size?: number;
}

// ---------------------------------------------------------------- M15 programme de la semaine
export type Priority = 'high' | 'medium' | 'low';
export interface WeekContest {
  contest_id: number; title: string; url: string; organizer: string | null; prize: string | null; value_eur: number | null;
  end_date: string | null; end_date_verified: boolean; start_date: string | null; days_left: number | null; hours_left: number | null;
  est_minutes: number; status: string; game_type: string | null; reliability: number | null; interest: number | null;
  automation_class: AutoClass | null; difficulty: number | null; social_platform: string | null;
  conditions: string[]; participated_this_period: boolean; period: string;
}
export interface WeekItem extends WeekContest {
  item_id: number; priority: Priority; score: number; reasons: string[];
  decision: 'proposed' | 'accepted' | 'refused' | 'postponed' | 'done' | 'obsolete';
  favorite: boolean; scheduled_day: string | null; postponed_to: string | null; participation_id: number | null;
}
export interface WeekOpportunity extends WeekContest { why: string[]; followed: boolean }
export type ResultStatus = 'draw_pending' | 'drawn' | 'not_published' | 'published' | 'winner' | 'not_winner' | 'unverifiable';
export interface WeekResult {
  id: number; contest_id: number; title: string; organizer: string | null; draw_date: string | null; draw_date_estimated: boolean;
  publish_date: string | null; prizes_count: number | null; verify_url: string | null; status: ResultStatus;
  last_checked_at: string | null; note: string | null; participation_status: string;
}
export type TaskStatus = 'todo' | 'in_progress' | 'waiting' | 'done' | 'cancelled' | 'expired';
export interface WeekTask {
  id: number; title: string; description: string | null; priority: Priority; due_at: string | null; status: TaskStatus;
  action: string; contest_id: number | null; contest_title: string | null; claim_id: number | null; promotion_id: number | null;
  proof_note: string | null; auto: boolean;
}
export interface PromoBrief {
  id: number | null; title: string; brand?: string | null; kind: string; url: string | null; product?: string | null; status: string;
  price_eur?: number | null; refund_eur?: number | null; refund_received_eur?: number | null; net_cost_forecast_eur?: number | null;
  end_date: string | null; send_deadline?: string | null; days_left?: number | null; contest_id: number | null; note?: string;
}
export interface ShopSection {
  categories: Record<'full_refund' | 'partial_refund' | 'purchase_game' | 'ending' | 'to_send' | 'awaiting_refund' | 'received' | 'to_buy_this_week', PromoBrief[]>;
  totals: { planned_spend_eur: number; conditional_refunds_eur: number; net_cost_forecast_eur: number; refunds_awaiting_eur: number; refunds_received_eur: number };
  note: string;
}
export interface WeekView {
  week_start: string; week_end: string; label: string; today: string; timezone: string; is_past: boolean; is_current: boolean;
  plan: { generated_at: string | null; capacity_minutes: number; planned_minutes: number; weekly_goal: number; minutes_per_day: number };
  kpis: Record<'priority' | 'done' | 'closing' | 'results_expected' | 'results_published' | 'gains_to_claim' | 'promotions' | 'refund_files', number>;
  priority: WeekItem[]; results: WeekResult[]; last_chances: Record<'h24' | 'h48' | 'd7' | 'd14', WeekContest[]>;
  opportunities: WeekOpportunity[]; shop: ShopSection; tasks: WeekTask[];
}
export interface WeekPrefs {
  timezone: string; plan_weekday: number; plan_hour: number; review_weekday: number; review_hour: number; daily_enabled: boolean;
  daily_hour: number; notifications_enabled: boolean; remind_close_hours: number; alert_close_hours: number; remind_results: boolean;
  remind_claims: boolean; minutes_per_day: number; active_days: number[]; weekly_goal: number; min_interest: number; min_reliability: number;
  automation_mode: 'max' | 'mixed' | 'manual'; hide_facebook: boolean; hide_instagram: boolean; hide_creative: boolean;
  favor_quick_forms: boolean; favor_instant_win: boolean; favor_quiz: boolean; favor_many_prizes: boolean; social_share_max: number;
}
export interface WeekReport { id: number; kind: 'weekly' | 'daily' | 'review'; period_start: string; period_end: string; generated_at: string; text?: string }
export interface TaskHistory { at: string; field: string; old: string | null; new: string | null; actor: string }
export interface SourcePolicy {
  categories: { id: number; label: string; allowed_by_default: boolean }[];
  modes: Record<string, string>;
  matrix: { domain: string; name: string; automated_extraction: boolean; authorized_in_writing: boolean; category_of_scan: number | null; modes: string[]; reason: string; unlock: string | null }[];
  references: { domain: string; name: string; url: string; reason: string; how_to: string; unlock: string | null; modes: string[] }[];
}
export interface SourceQuality {
  source_id: number; name: string; kind: string; access_mode: string; metrics: Record<string, number>; percent: Record<string, number>;
  restrictions: { blocked_scans: number; last_block: string | null; note: string };
  last_scans: { status: string; found: number; new: number; error: string | null; finished_at: string | null }[]; issues: string[];
}
export interface ImportResult { created: number[]; existing: number[]; skipped: { line: number | null; url: string; reason: string }[] }

// ---------------------------------------------------------------- M14 Shop & Promo
export type ShopCategory = 'A' | 'B' | 'C';
export interface ShopFinance {
  price_eur: number | null; refund_announced_eur: number | null; refund_guaranteed: boolean; conditions: string[];
  extra_benefits_eur: number | null; extra_counted_eur: number | null; fees_eur: number | null; net_cost_forecast_eur: number | null;
  refund_delay_days: number | null; random_prize_value_eur: number | null; category: ShopCategory; category_label: string;
  notes: string[]; disclaimer: string;
}
export interface ShopObservation {
  retailer: string; store: string | null; level: string; price_eur: number | null; ean: string | null; source: string | null; observed_at: string | null;
}
export interface ShopAvailability { level: string; text: string; observations: ShopObservation[]; realtime_note: string }
export interface ShopOffer {
  id: number; title: string; brand: string | null; product: string | null; kind: string; status: string; url: string | null;
  rules_url: string | null; origin: string | null; contest_id: number | null; retailers: string[]; retailers_note: string | null;
  eans: string[]; ean_status: string; variant: Record<string, string>; price_eur: number | null; finance: ShopFinance;
  category: ShopCategory; reliability: number | null; required_docs: string[]; end_date: string | null; send_deadline: string | null;
  days_left: number | null; availability: ShopAvailability; action: string; claim_id: number | null; warnings: string[];
  evidence: Record<string, string>; over_cap?: boolean;
}
export interface ShopCheck { step: number; label: string; status: 'ok' | 'warn' | 'fail' | 'pending' | 'na'; detail: string }
export interface ShopClaim {
  id: number; promotion_id: number; promotion_title: string; kind: 'refund' | 'purchase_game'; status: string; late: boolean;
  purchase_date: string | null; retailer: string | null; ticket_number: string | null; amount_paid_eur: number | null;
  amount_requested_eur: number | null; amount_confirmed_eur: number | null; amount_received_eur: number | null;
  received_date: string | null; codes: string[] | null; checks: ShopCheck[] | null; validated_at: string | null; sent_at: string | null;
  confirmation_ref: string | null; refusal_reason: string | null; participation_id: number | null;
  history: { at: string; event: string; detail: string | null }[] | null; channel: string | null; channel_target: string | null;
  documents?: ShopDoc[];
}
export interface ShopDoc {
  id: number; kind: string; promotion_id: number | null; claim_id: number | null; sha256: string; mime: string; size: number;
  sensitive: boolean; ocr_method: string | null; ocr_text: string | null; readability: string | null;
  extracted: Record<string, unknown> | null; user_fields: Record<string, unknown> | null; fields: Record<string, unknown>; created_at: string;
}
export interface ShopRefusedRow { id?: number; promotion_id: number; promotion_title: string; status: string; late?: boolean; refusal_reason?: string | null }
export interface ShopDashboard {
  available: ShopOffer[]; to_buy: ShopOffer[]; full_refund: ShopOffer[]; purchase_games: ShopOffer[]; partial_refund: ShopOffer[];
  ending_soon: ShopOffer[]; claims_to_complete: ShopClaim[]; claims_sent: ShopClaim[]; refunds_awaiting: ShopClaim[];
  refunds_late: ShopClaim[]; refunds_received: ShopClaim[]; refused: ShopRefusedRow[]; history: ShopClaim[];
  excluded: { id: number; title: string; reason: string }[]; realtime_note: string;
}
export interface ShopPreview {
  claim_id: number; channel: string | null; channel_target: string | null; channel_status: string; channel_detail: string;
  documents: { id: number; kind: string; sensitive: boolean; size: number }[]; personal_data: string[]; physical_items: string[];
  codes: string[] | null; amount_requested_eur: number | null; warning: string;
}
export interface ShopPrefs {
  retailers: string[]; stores: { retailer: string; name: string }[]; postal_code: string; radius_km: number; categories: string[];
  max_price_eur: number; monthly_cap_eur: number; accepted_products: string[]; refused_products: string[]; min_category: ShopCategory;
}
export interface ShopMonth {
  month: string; expenses_eur: number; savings_realized_eur: number; refunds_pending_eur: number; refunds_refused_eur: number;
  random_gains_eur: number; net_real_cost_eur: number; monthly_cap_eur: number; cap_left_eur: number; note: string;
  entries?: { at: string; kind: string; amount_eur: number; promotion_id: number | null; claim_id: number | null; note: string | null }[];
}
export interface ShopCommandResult { tab: string; text: string; data: unknown }
