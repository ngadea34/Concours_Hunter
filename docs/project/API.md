# Contrat d'API REST (v1) — référence pour frontend et extension

Base : même origine que l'UI (`http://127.0.0.1:8765`). Toutes les routes sont sous `/api`.
Auth : en-tête `X-CH-Token: <jeton>` (fichier `data/token.txt`). Les requêtes venant de 127.0.0.1 sont acceptées sans jeton si `localhost_trusted=true` (défaut). `GET /api/auth/check` → `{ok, needs_token}`.
Erreurs : `{detail: string}` avec code HTTP 4xx/5xx. Dates ISO 8601. Montants en EUR (float) + devise d'origine.

## Enums
- ContestStatus: `new` `qualified` `to_verify` `rejected` `expired` `participated` `archived`
- FreeStatus: `free` `free_alternative` `purchase_required` `unknown`
- Tri-state: `yes` `no` `unknown`
- Mode: `auto` `semi` `manual`
- ParticipationStatus: `prepared` `awaiting_human` `submitted` `confirmed` `failed` `cancelled`
- PrizeCategory: `high_tech` `auto` `travel` `home` `voucher` `product` `culture` `leisure` `experience` `show` `restaurant` `cash` `other`
- Outcome: `won` `lost` `pending`
- ClaimStatus: `to_claim` `claimed` `received` `expired` `refused`

## Types
```ts
ContestSummary { id:number; title:string; url:string; organizer_name:string|null; source_names:string[];
  status:ContestStatus; category:PrizeCategory|null; prize_summary:string|null; total_prize_value_eur:number|null;
  end_date:string|null; days_left:number|null; language:string|null; countries_allowed:string[];
  reliability_score:number|null; interest_score:number|null; free_status:FreeStatus; fr_eligible:TriState;
  participation_mode:Mode; participated:boolean; needs_human_reason:string|null; created_at:string }
Justification { field:string; decision:string; evidence:string|null; method:string }   // method: rule | llm:<model> | human | source
ContestDetail extends ContestSummary { description:string|null; start_date:string|null; entry_limit:string|null;
  notes:string|null; personal_interest:number|null; min_age:number|null; countries_excluded:string[];
  rules:{url:string|null; excerpt:string|null; content_hash:string|null; analyzed_at:string|null} | null;
  prizes:Prize[]; answers:Answer[]; justifications:Justification[];
  score_breakdown:{reliability:Record<string,number>; interest:Record<string,number>};
  participations:Participation[]; provenance:{source_name:string; source_url:string; seen_at:string}[] }
Prize { id:number; name:string; category:PrizeCategory; quantity:number; value:number|null; currency:string|null; value_eur:number|null; fees_note:string|null }
Answer { id:number; question:string; answer:string; source:string; verified:boolean; confidence:number }
Participation { id:number; contest_id:number; contest_title:string; contest_url:string; mode:Mode; status:ParticipationStatus;
  prepared_at:string; submitted_at:string|null; error:string|null; time_spent_minutes:number|null;
  proofs:{id:number; kind:string; note:string|null; path:string|null; created_at:string}[] }
Prefill { contest_url:string; fields:Record<string,string>; answers:{question:string; answer:string}[]; warnings:string[] }
Result { id:number; contest_id:number|null; contest_title:string|null; outcome:Outcome; message_text:string|null; sender:string|null;
  received_at:string; phishing_score:number; phishing_flags:string[]; verified:boolean }
Claim { id:number; result_id:number; contest_title:string|null; prize_name:string|null; status:ClaimStatus; deadline:string|null;
  days_left:number|null; fees_eur:number|null; value_eur:number|null; notes:string|null }
Notification { id:number; kind:string; title:string; body:string|null; contest_id:number|null; created_at:string; read:boolean }
Source { id:number; name:string; kind:string; url:string; enabled:boolean; language:string|null; country:string|null;
  last_scan_at:string|null; last_status:string|null; contests_found:number; tos_note:string|null }
ScanJob { id:number; source_id:number|null; source_name:string|null; status:string; started_at:string; finished_at:string|null; found:number; new:number; error:string|null }
Profile { first_name, last_name, email, phone, birth_date, address, postal_code, city, country } // tous string|null
Consents { auto_participation:boolean; store_proofs:boolean; email_notifications:boolean; updated_at:string|null }
Settings { lan_mode:boolean; llm_enabled:boolean; ollama_url:string; llm_model_small:string; llm_model_large:string;
  scan_interval_minutes:number; max_requests_per_domain_per_hour:number; interest_categories:Record<PrizeCategory,number>; ui_language:string }
Stats { contests_total, contests_qualified, contests_to_verify, contests_closing_soon, participations_valid, participations_pending,
  time_spent_minutes, prize_value_participated_eur, gains_obtained_eur, wins, claims_open:number;
  by_source:{source:string; contests:number; participations:number; wins:number}[];
  by_country:{country:string; count:number}[]; by_category:{category:string; count:number}[] }
Page<T> { items:T[]; total:number; page:number; page_size:number }
```

## Routes
| Méthode | Chemin | Corps / query | Réponse |
|---|---|---|---|
| GET | /api/health | | `{status:"ok", version}` |
| GET | /api/auth/check | | `{ok, needs_token}` |
| GET | /api/stats | | Stats |
| GET | /api/contests | `q,status,category,free_status,fr_eligible,closing_within_days,min_reliability,sort(end_date|-interest|-reliability|-created),page,page_size` | Page<ContestSummary> |
| POST | /api/contests | `{url, title?}` (ajout manuel) | ContestDetail |
| GET | /api/contests/{id} | | ContestDetail |
| PATCH | /api/contests/{id} | `{status?, notes?, personal_interest?}` | ContestDetail |
| POST | /api/contests/{id}/requalify | `{rules_text?}` (texte collé par l'utilisateur) | ContestDetail |
| POST | /api/contests/{id}/verify | `{field:"free"|"eligibility", decision, evidence?}` validation humaine | ContestDetail |
| GET | /api/review-queue | | ContestSummary[] |
| POST | /api/contests/{id}/participations | `{mode?}` | Participation |
| GET | /api/participations | `status?, url?` (url = page du concours, correspondance domaine+chemin) | Participation[] |
| POST | /api/participations/{id}/proofs | `{kind:"screenshot"|"note", data_url?, note?}` (data_url PNG base64, ≤ 5 Mo) | Participation |
| GET | /api/participations/{id}/prefill | | Prefill |
| POST | /api/participations/{id}/submitted | `{note?, time_spent_minutes?}` (l'humain confirme avoir soumis) | Participation |
| POST | /api/participations/{id}/confirmed | `{note?}` (confirmation reçue) | Participation |
| POST | /api/participations/{id}/failed | `{error}` | Participation |
| POST | /api/participations/{id}/cancel | | Participation |
| GET | /api/results | | Result[] |
| POST | /api/results | `{contest_id?, participation_id?, outcome, message_text?, sender?}` | Result (analyse anti-phishing) |
| POST | /api/results/{id}/verify | `{verified:boolean}` | Result |
| GET | /api/claims | | Claim[] |
| POST | /api/claims | `{result_id, prize_name?, deadline?, fees_eur?, value_eur?}` | Claim |
| PATCH | /api/claims/{id} | `{status?, notes?, deadline?, fees_eur?, value_eur?}` | Claim |
| GET | /api/answers | `q?` | Answer[] |
| GET | /api/notifications | `unread_only?` | Notification[] |
| POST | /api/notifications/{id}/read | | `{ok}` |
| POST | /api/notifications/read-all | | `{ok}` |
| GET | /api/sources | | Source[] |
| POST | /api/sources | `{name, kind:"rss"|"html"|"site", url, language?, country?}` | Source |
| GET | /api/sources/suggestions | | `{domain, contests, organizer_names[], examples[]}[]` : sites d'organisateurs pas encore suivis |
| POST | /api/sources/follow | `{domain}` | Source (kind `site`) ; 400 domaine invalide ou non-organisateur, 409 déjà suivi ou exclu |
| PATCH | /api/sources/{id} | `{enabled?, name?}` | Source |
| POST | /api/sources/{id}/scan | | ScanJob |
| GET | /api/scan-jobs | | ScanJob[] (50 derniers) |
| GET/PUT | /api/profile | Profile | Profile |
| GET/PUT | /api/consents | Consents | Consents |
| GET/PUT | /api/settings | Settings (partiel accepté en PUT) | Settings |
| GET | /api/scheduler/status | | `{running, paused, jobs:{id,next_run,last_run,last_status}[]}` |
| POST | /api/scheduler/pause · /resume · /stop-all | | status (stop-all = arrêt d'urgence) |
| POST | /api/scheduler/run/{job_id} | | status |
| POST | /api/admin/backup | | `{name, size}` |
| GET | /api/admin/backups | | `{name,size,created_at}[]` |
| POST | /api/admin/restore | `{name}` | `{ok}` |
| GET | /api/admin/diagnostics | | `{python, db_path, db_size, ollama:{reachable, models[]}, disk_free_gb, version}` |
| GET | /api/admin/logs | `limit?` | `{ts, actor, action, detail}[]` (audit_logs) |
