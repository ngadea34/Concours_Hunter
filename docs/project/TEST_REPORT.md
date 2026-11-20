# Rapport de tests — 2026-11-20

Environnements : conteneur Linux (Python 3.13) ; CI GitHub Linux + Windows ; PC de Nico (Windows 10, Python 3.12) : **38/38**.

| Suite | Résultat |
|---|---|
| Backend `cd backend && python -m pytest` | **38/38 réussis** (≈5 s), Linux et Windows |
| Extension `node --test extension/test/` | **8/8 réussis** (dont e2e Chromium : remplissage, aucun submit) |
| Frontend `npm run build` (tsc strict + vite) | OK |
| UI dans Chromium, 9 pages × 2 tailles (1280px, 390px) | 0 erreur console, 0 requête en échec, pas de défilement horizontal |
| Parcours UI : fiche → préparer → participations | OK |

## Scénarios obligatoires (12.1)
| Scénario | Test |
|---|---|
| Achat obligatoire | test_purchase_required_rejected |
| Voie gratuite alternative | test_free_alternative |
| Réservé aux États-Unis | test_us_only_rejected, test_aggregator_scan_end_to_end |
| Accessible depuis la France | test_free_fr_contest_qualified |
| Expiré | test_expired |
| Dupliqué | test_dedup_across_sources, test_aggregator_scan_end_to_end (2e scan) |
| Règlement inaccessible | test_rules_inaccessible_goes_to_verify |
| Faux organisateur | test_fake_organizer_and_injection |
| CAPTCHA | test_captcha_contest_is_manual, test_robots_and_protections_respected, e2e extension |
| Double participation | test_double_participation_refused, test_api_full_flow |
| Erreur de soumission | test_prefill_and_submission_flow (failed → submitted) |
| Confirmation reçue | test_prefill_and_submission_flow |
| Faux message de gain | test_fake_win_message |
| Lot nécessitant des frais | test_fake_win_message (frais demandés), test_fake_organizer_and_injection |
| Gain avec date limite de réclamation | test_win_cycle_with_claim_deadline, test_claim_expires |

Autres : restauration (test_backup_and_restore), interruption/reprise et arrêt d'urgence (test_scheduler_interruption_recovery), sécurité (test_security_middleware), cache d'analyse et invalidation (test_fees_detected_and_cache_reuse, test_rules_change_invalidates), multilingue (test_multilingual_dates_and_age), participation automatique réelle sur formulaire de démonstration local (test_auto_participation_on_demo_form).

## Test réel
Scan Le Démon du Jeu + enrichissement sur le PC de Nico : voir PROJECT_STATE.md.

## Non testé
- Popup/options de l'extension dans un vrai Chrome (API chrome.* indisponibles en test).
- Appels Ollama réels (client testé par la validation des sorties, pas avec un modèle).
- Performance à grand volume (> 10 000 concours) : non mesurée.

## Liste détaillée
- tests/test_auto_and_api.py::test_auto_participation_on_demo_form
- tests/test_auto_and_api.py::test_auto_blocked_without_consent
- tests/test_auto_and_api.py::test_captcha_contest_is_manual
- tests/test_auto_and_api.py::test_api_full_flow
- tests/test_auto_and_api.py::test_security_middleware
- tests/test_auto_and_api.py::test_backup_and_restore
- tests/test_auto_and_api.py::test_scheduler_interruption_recovery
- tests/test_discovery.py::test_aggregator_scan_end_to_end
- tests/test_discovery.py::test_dedup_across_sources
- tests/test_discovery.py::test_robots_and_protections_respected
- tests/test_discovery.py::test_hourly_quota
- tests/test_discovery.py::test_rss_connector
- tests/test_participation_rewards.py::test_double_participation_refused
- tests/test_participation_rewards.py::test_daily_period_key
- tests/test_participation_rewards.py::test_prefill_and_submission_flow
- tests/test_participation_rewards.py::test_proof_requires_consent_and_valid_png
- tests/test_participation_rewards.py::test_auto_mode_never_exceeds_policy
- tests/test_participation_rewards.py::test_win_cycle_with_claim_deadline
- tests/test_participation_rewards.py::test_claim_expires
- tests/test_participation_rewards.py::test_fake_win_message
- tests/test_participation_rewards.py::test_profile_encrypted_at_rest
- tests/test_rules.py::test_free_fr_contest_qualified
- tests/test_rules.py::test_purchase_required_rejected
- tests/test_rules.py::test_free_alternative
- tests/test_rules.py::test_us_only_rejected
- tests/test_rules.py::test_expired
- tests/test_rules.py::test_rules_inaccessible_goes_to_verify
- tests/test_rules.py::test_fake_organizer_and_injection
- tests/test_rules.py::test_fees_detected_and_cache_reuse
- tests/test_rules.py::test_rules_change_invalidates
- tests/test_rules.py::test_multilingual_dates_and_age
- tests/test_rules.py::test_ambiguous_rules_suspended
- tests/test_rules.py::test_human_verification_unlocks
