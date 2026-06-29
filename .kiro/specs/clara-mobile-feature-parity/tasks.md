# Implementation Plan: CLARA Mobile Feature Parity + Production Quality

## Overview

This plan upgrades the Flutter mobile app to full web parity and production
quality, **additively and behind flags (all default OFF)**. Tasks are ordered so
each epic is independently shippable and verifiable, and so the highest-value
parity gaps (chat, networking/auth hardening, self-med cabinet, scribe) land
with their safety invariants and tests. Every task that touches a shared path
adds or extends a test asserting the invariant still holds.

### Testing prerequisites (set up once, in task 1.1)
- Reuse the existing `apps/mobile/test` harness (`flutter_test`), keeping the
  current unit/generated tests for analytics, the telemetry gate, and the
  session store green.
- Add fakes for `Api_Client`, `Session_Store`, and `ConnectivityService`, plus a
  recording analytics transport, so widget tests run without platform channels
  or live network.
- Tag property tests `P1..P14` mapping to the design's Correctness Properties.
- A flags-off baseline test asserts navigation/reachable-screen equivalence with
  the pre-feature app.

## Task Dependency Graph

Same-file tasks are serialized into different waves to avoid write conflicts:
`api_client.dart` (1.2→1.3→3.1→5.1→6.1→8.1), `dashboard_screen.dart`
(13.1 isolated), and the shared widget library is built before the screens that
consume it. New screens (chat, self-med, scribe, PHR) live in disjoint files and
parallelize freely once the foundations wave lands.

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.5"] },
    { "id": 1, "tasks": ["1.3", "1.4"] },
    { "id": 2, "tasks": ["2"] },
    { "id": 3, "tasks": ["3.1", "4.1", "4.2", "5.1", "6.1", "7.1", "8.1", "13.1"] },
    { "id": 4, "tasks": ["3.2", "3.3", "4.3", "5.2", "6.2", "7.2", "8.2", "13.2"] },
    { "id": 5, "tasks": ["3.4", "3.5", "3.6", "5.3", "5.4", "5.5", "6.3", "6.4", "7.3", "8.3"] },
    { "id": 6, "tasks": ["9.1", "9.2", "9.3"] },
    { "id": 7, "tasks": ["10.1", "10.2", "10.3", "11.1", "11.2"] },
    { "id": 8, "tasks": ["12.1", "12.2", "12.3", "12.4", "12.5"] },
    { "id": 9, "tasks": ["14.1"] },
    { "id": 10, "tasks": ["15.1", "15.2", "15.3", "15.4"] }
  ]
}
```

## Tasks

- [ ] 1. Foundations (networking, flags, resilience, test harness)
  - [x] 1.1 Add fakes (Api_Client, Session_Store, ConnectivityService) + recording analytics transport to `test/`; keep existing tests green.
  - [x] 1.2 Add `connectivity_service.dart` (`isOnline` stream) and bounded request/stream timeouts in `api_client.dart` (Req 9.1, 9.2).
  - [x] 1.3 Token refresh in `Api_Client`: pre-flight expiry check + single 401-retry via `POST /auth/refresh`; persist or clear session (Req 6.2, 6.3).
  - [~] 1.4 **[PBT]** Token-refresh state machine: expired+valid-refresh ⇒ refresh; failed refresh ⇒ clear+login (Property P9).
  - [x] 1.5 Mobile flag resolver: read `feature_flags` from `mobile/summary` + `--dart-define` defaults (all new flags default false) (Req 13.1, 15.1).

- [x] 2. Checkpoint — foundations land dark; flags-off navigation equivalence test green (Property P1); existing tests still pass.

- [ ] 3. Chat parity (Req 1)
  - [x] 3.1 `Api_Client.chat` + `streamChat` over `/chat` and `/chat/stream` (reuse SSE parser).
  - [-] 3.2 `ChatScreen` with progressive streaming, citations, standing disclaimer, emergency fast-path; gated by `chat_mobile_enabled`.
  - [x] 3.3 `EndUserSafeAnswer` widget — strip internal runtime fields for non-admin (Req 1.6).
  - [~] 3.4 **[PBT]** End_User-safe projection drops mode/retrieval/source_errors/policy (Property P3).
  - [~] 3.5 **[Dart widget test]** Chat loading/streaming/error states; disconnect preserves streamed content (Req 1.3).
  - [~] 3.6 **[Dart widget test]** No PII reaches analytics from chat interactions (Property P5).

- [ ] 4. Deep-research hardening (Req 2)
  - [~] 4.1 Bounded SSE timeout + background/foreground recovery (interrupted stream ⇒ recoverable error) (Req 2.6).
  - [x] 4.2 Reaffirm role-gated rail (admin-only) + fail-closed block via `evaluateTelemetryGate`.
  - [x] 4.3 **[Dart widget test]** Non-admin sees sanitized summary; unevaluable role blocks the job (Property P2).

- [ ] 5. Self-med cabinet + DDI parity (Req 3)
  - [x] 5.1 `Api_Client` cabinet ops (`getCabinet`/`addCabinetItem`/`deleteCabinetItem`) over `/selfmed/*`.
  - [-] 5.2 `SelfMedCabinetScreen` (list/add/delete) behind consent gate; gated by `selfmed_cabinet_mobile_enabled` (Req 3.1, 3.2, 3.5).
  - [~] 5.3 Wire cabinet → existing CareGuard DDI; enforce two-medicine guard before analyze (Req 3.3).
  - [~] 5.4 **[PBT]** DDI never invoked with < 2 distinct medicines (Property P10).
  - [~] 5.5 **[Dart widget test]** DDI view shows End_User-safe projection only (Property P3).

- [ ] 6. Ambient scribe parity (Req 4)
  - [-] 6.1 `Api_Client` scribe ops (sessions list/create/get, transcribe, regenerate, consent capture/revoke).
  - [~] 6.2 `ScribeScreen`: audio capture/upload → transcript append → SOAP regenerate + status; gated by `scribe_mobile_enabled` + RBAC (Req 4.1, 4.2, 4.3, 4.6, 4.7).
  - [~] 6.3 Consent capture gate (block processing when absent) + `stripTelemetryLabels` on clinical text (Req 4.4, 4.5).
  - [~] 6.4 **[Dart widget test]** Audio processing blocked without consent; clinical text sanitized (Req 4.4, 4.5).

- [ ] 7. Enhanced PHR parity (Req 5)
  - [x] 7.1 Preserve legacy GET/PUT; reaffirm provenance/verification badges + persistent self-declared disclaimer (Req 5.1, 5.2, 5.3).
  - [-] 7.2 Behind `phr_enhanced_mobile_enabled`: read-only export + emergency-card (Req 5.6).
  - [~] 7.3 **[Dart widget test]** PHR loading/success/error; inline PII-free validation errors; vi/en toggle defaults vi (Req 5.4, 5.5).

- [ ] 8. Auth lifecycle parity (Req 6)
  - [~] 8.1 `Api_Client` register/verify/forgot/reset/logout/consent-status.
  - [~] 8.2 `AuthFlows` screens (register/verify/reset) or deep-link routing; consent gate before gated medical content (Req 6.1, 6.6).
  - [~] 8.3 **[Dart widget test]** Expired session routes to login; consent gate blocks gated content (Properties P8, P9; Req 6.6).

- [ ] 9. Transparency & model disclosure (Req 7)
  - [x] 9.1 `model_disclosure.dart` (`fromResponse`, `isFallback` iff local synth) + `ModelDisclosureChip`; gated by `model_disclosure_mobile_enabled`.
  - [x] 9.2 Versioned `AiTransparencyNotice` gate before medical content; gated by `transparency_notice_mobile_enabled`.
  - [~] 9.3 **[PBT]** Disclosure correctness: chip shows fallback iff local synth; omitted when absent (Property P11).

- [ ] 10. Consent center & DSAR (Req 8)
  - [x] 10.1 `consent_state.dart` + `ConsentCenterScreen` purpose toggles; withdrawing analytics ⇒ `analytics.setConsent(false)` (Req 8.1, 8.2, 8.4).
  - [-] 10.2 `DsarScreen` submit + acknowledgement; no PII client-side (Req 8.3, 8.5); gated by `consent_center_mobile_enabled`.
  - [~] 10.3 **[PBT]** Consent suppression: zero transmission without consent; withdrawal stops it (Property P7).

- [ ] 11. Sharing & deep links (Req 12)
  - [x] 11.1 `SharedResourceScreen` read-only by token via CLARA_API; invalid/expired ⇒ clear non-PII error; gated by `sharing_mobile_enabled`.
  - [~] 11.2 **[Dart widget test]** Shared view applies End_User-safe projection; invalid token shows error (Req 12.2, 12.3).

- [ ] 12. Offline, accessibility & error discipline (Req 9, 10, 11)
  - [x] 12.1 `ErrorRetryView` / `OfflineBanner` on every data surface; block mutations offline with preserved input (Req 9.1, 9.4, 9.5).
  - [~] 12.2 **[Dart widget test]** Offline shows error state + blocks mutations (Property P12).
  - [x] 12.3 `a11y.dart`: semantics labels, ≥48dp targets, dynamic text scaling, reduced-motion resolver; status by text not color (Req 10.1, 10.2, 10.3, 10.4, 10.5).
  - [~] 12.4 **[Dart widget test]** Interactive controls expose semantics + meet target; reduced-motion suppresses animation (Property P14).
  - [x] 12.5 Screen-level exception containment (no crash, no stack trace to user) (Req 11.4).

- [ ] 13. Role-aware navigation (Req 13)
  - [x] 13.1 Derive tiles from `mobile/summary` feature_flags; fail closed when summary unloadable; never expose admin-only surfaces to non-admin (Req 13.2, 13.4, 13.5).
  - [~] 13.2 **[Dart widget test]** Summary-load failure shows no privileged tools + retry (Property P13).

- [ ] 14. Docs & config alignment (Req 15)
  - [~] 14.1 Update `apps/mobile/README.md`: persistent secure-storage session, base URL `8100`, new flags, run instructions.

- [ ] 15. Final quality-gate checkpoint
  - [~] 15.1 Full flags-off regression: navigation/reachable-screen equivalence with baseline (Property P1).
  - [~] 15.2 Per-property suite green (P1–P14) under `flutter test`; existing analytics/gate/session tests still pass (Req 14.1, 14.6).
  - [~] 15.3 `flutter analyze` clean; widget tests for every primary screen cover loading/success/empty/error (Req 14.2).
  - [~] 15.4 Staged-enablement runbook (per-flag, per-role/environment rollout order).

## Notes

### Property → implementing test task
- P1 → 2, 15.1 · P2 → 4.3 · P3 → 3.4 / 5.5 · P4 → 3.4 (label strip) ·
  P5 → 3.6 · P6 → existing analytics test · P7 → 10.3 · P8 → 8.3 ·
  P9 → 1.4 / 8.3 · P10 → 5.4 · P11 → 9.3 · P12 → 12.2 ·
  P13 → 13.2 · P14 → 12.4

### Staged enablement order (production)
1. `model_disclosure` + `transparency_notice` (user-visible, low risk)
2. `chat_mobile_enabled` (after streaming + projection verified)
3. `selfmed_cabinet_mobile_enabled` + `phr_enhanced_mobile_enabled`
4. `scribe_mobile_enabled` (after consent gate verified)
5. `consent_center_mobile_enabled` + `sharing_mobile_enabled`

### Subagent assignment guidance
- Networking/auth foundations (tasks 1, 8) — one writer.
- New screens chat/self-med/scribe (tasks 3, 5, 6) — disjoint writers.
- Compliance/consent surfaces (tasks 9, 10) — independent writer.
- Cross-cutting offline/a11y/error + tests (task 12, widget tests) — one writer.
