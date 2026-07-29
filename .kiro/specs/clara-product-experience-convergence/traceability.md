# Traceability — CLARA Product Experience Convergence

Status: planning and verification map, updated 2026-07-29.

This matrix links requirements to design, implementation phases, and the
evidence required to close them. A row being mapped does **not** mean the
requirement is implemented or approved. Task checkboxes in
[`tasks.md`](tasks.md) remain the execution record. Human review, studies,
production drills, deployment, and rollback evidence remain incomplete until
their corresponding unchecked task is genuinely completed.

| Requirement | Design and baseline | Delivery phases/tasks | Evidence required for closure |
| --- | --- | --- | --- |
| R1 — One primary job per page | [`audit.md`](audit.md); design §§1, 5, 8 | 0.3; 1.1–1.3; 3.1–7.4; 9.1–9.3; 10.5 | Final active-route inventory; route/component review showing one primary job/action; no duplicate creation canvas |
| R2 — Guided-flow contract | Design §§1–5 | 1.1–1.5; 3.1–7.4; 10.1, 10.5 | Component and route E2E for progress, Back, resume, optional steps, review, commit, expiry, and abandon |
| R3 — Validation and recovery | Design §§1, 2, 4, 9 | 1.1, 1.4, 1.5; 3.2; 4.3; 5.4; 6.4; 7.5; 10.1 | Error-focus/accessibility tests; recoverable network/auth tests; idempotency/revision tests; emergency and destructive-action regression evidence |
| R4 — Setup center | Design §§2, 3, 5 | 3.1, 3.3–3.5; 9.4; 10.4, 10.6 | Consumer/professional/admin readiness walkthroughs; secret-sanitization tests; clean-install rehearsal and production smoke evidence |
| R5 — Modern light mode | Design §6 | 0.4; 2.1–2.5; 10.2 | Approved light/dark screenshots; token audit; contrast, zoom/reflow, text-scale, reduced-motion, forced-colors, keyboard, and screen-reader evidence |
| R6 — Navigation and IA | [`audit.md`](audit.md); design §§1, 5, 8 | 0.3, 0.6; 1.3; 3.1–9.3; 10.5 | Approved role/capability navigation map; redirect/adapter tests; safe-exit/draft behavior; telemetry-backed legacy retirement |
| R7 — Authentication and onboarding | Design §§1, 4, 5 | 3.1; 10.1, 10.6 | Web/mobile route E2E for identity, method, role, profile, measurement, consent, optional connection, review, reset, and verification |
| R8 — Today and LifeMap | Design §§4, 5, 8 | 4.1–4.5; 10.1, 10.5 | Today priority-task usability evidence; LifeMap/Capture draft-to-confirm E2E; source/conflict/correction tests; parity before old-panel removal |
| R9 — Medicines | Design §§4, 5, 8 | 5.1–5.4; 10.1, 10.5 | Add/edit/end/import and DDI E2E; OCR/normalization provenance; unknown/readiness/fail-safe/FIDES tests; parity before legacy removal |
| R10 — Visits, Family, PHR, Evidence | Design §§4, 5, 8 | 6.1, 6.4; 7.1–7.3, 7.5; 10.1, 10.5 | Per-flow route E2E; authority/consent/revocation; source/provenance/correction; stale-pack and unknown-applicability tests |
| R11 — Chat, RAG, Council, Scribe | Design §§5, 7, 9 | 6.2–6.4; 8.1–8.7; 10.1, 10.3 | Uncluttered Chat review; citation/source/conflict UX; Council/Scribe consent and correction E2E; exact-version scientific release package |
| R12 — Community, account, admin | Design §§1, 2, 5, 8 | 3.2; 7.4, 7.5; 9.1–9.4; 10.1, 10.5 | Moderation fail-closed tests; consent/DSAR consequence and receipt E2E; admin RBAC, secret handling, immutable audit, and rollback tests |
| R13 — Evidence-governed Chat/RAG | Design §7; [dated evidence map](../../../docs/research/clara-chat-rag-evidence-2026-07-29.md) | 8.1–8.6; 9.1, 9.4; 10.3, 10.4 | Frozen stage metrics and baselines; exact immutable manifest; bilingual clinician adjudication; red-team, shadow, pilot/prospective, subgroup, monitoring, and rollback evidence proportional to risk |
| R14 — Research freshness | Design §7; [dated evidence map](../../../docs/research/clara-chat-rag-evidence-2026-07-29.md) | 8.1, 8.7; 10.6 | Named owner and review calendar; dated review record; change-triggered evaluation record; applicable DECIDE-AI/SPIRIT-AI/CONSORT-AI protocol/report |

## Program acceptance trace

| Acceptance condition | Primary tasks | Completion evidence |
| --- | --- | --- |
| Every active surface classified and owned | 0.1, 0.3, 0.6 | Current audit plus approved canonical navigation/legacy disposition |
| Shared guided-flow system and migrated priority flows | 1.1–1.5; 3.1–7.4; 9.1–9.3 | Web/mobile tests and route E2E, including recovery and accessibility |
| Modern, accessible light mode | 0.4; 2.1–2.5; 10.2 | Automated matrices plus real-device human/design approval |
| Easy, documented clean setup | 3.3–3.5; 10.4, 10.6 | Clean-environment rehearsal, sanitized readiness, migration/worker/backup evidence |
| Exact-version scientific AI evidence | 8.1–8.7; 9.4; 10.3 | Frozen evaluation and manifest package; clinician/human and prospective evidence where applicable |
| Safety and privacy invariants preserved | 1.4–1.5; 3.2; 4.3; 5.4; 6.4; 7.5; 9.4; 10.1, 10.3–10.4 | API/ML/web/mobile safety regression, penetration/privacy, and no-PII telemetry evidence |
| Legacy duplication retired safely | 4.5; 10.5 | Parity, redirects, telemetry window, migration, and tested rollback |
| Production release is operable and reversible | 10.3–10.7 | Green full gates, commit/push/deploy record, production smoke, and verified rollback |
