# Data Protection Impact Assessment (DPIA) — CLARA-Care

**Document status:** Living record · version-controlled
**Legal basis:** Decree No. 13/2023/NĐ-CP (PDPD) Art. 24 — sensitive-data impact assessment
**Last reviewed:** 2026-03

> Hồ sơ đánh giá tác động xử lý dữ liệu cá nhân (DPIA). CLARA-Care processes
> health data — sensitive personal data under PDPD Art. 2(4) — so the controller
> maintains this DPIA dossier (Req 6.4).

## 1. Scope and necessity

CLARA processes sensitive personal data (PHR, medicine cabinet, allergies,
conditions, clinical queries) to deliver a clinical decision-support service.
Processing is necessary to answer the user's medical-information questions and,
where consented, to personalize those answers. Processing is minimized to what
each purpose requires, and cross-border inference transmits only the minimized
text needed for the model call (Req 4.3).

## 2. Data flows assessed

1. **User → CLARA_API → CLARA_ML:** clinical query, optionally enriched with PHR/cabinet context when personalization consent is present.
2. **CLARA_ML → offshore processor:** minimized text to the YEScale DeepSeek LLM and YEScale embedding endpoint, gated by `cross_border_processing` consent (see `transfer-impact-assessments.md`).
3. **CLARA_ML → CLARA_API → User:** synthesized answer with model disclosure (`ai_disclosure`) and clinician-review directive.
4. **DSAR flows:** export, correction, deletion/anonymization, restriction, consent withdrawal (`dsar.py`).
5. **Compliance logging:** append-only, PII-free events for consent changes, DSARs, transfers, and incidents.

## 3. Risks to data subjects and mitigations

| Risk to the data subject | Mitigation |
|---|---|
| Sensitive health data exposed to an offshore processor without basis | Cross-border consent gate; absent consent ⇒ in-country path or local degraded fallback; payload minimized (Req 4.2, 4.3) |
| Free-text health data leaking into logs/telemetry | No-PII invariant; `redact_meta` projection on every compliance event; only counts/flags persisted (Req 7.3) |
| Subject unable to exercise rights | DSAR self-service: export, correct, delete, restrict, withdraw, with 30-day statutory tracking (Req 3) |
| Data retained longer than necessary | Per-category retention with scheduled anonymization/deletion (Req 7.1, 7.2) |
| Deletion that destroys the audit trail | Deletion irreversibly anonymizes PII while append-only, PII-free DSAR/compliance rows survive (Req 3.7, Property P4) |
| Unauthorized access to compliance records | RBAC: compliance-admin surfaces reachable only by authorized roles (Req 6.6, 8.4, Property P7) |
| CSRF on cookie-authenticated mutations | CSRF protection preserved on all new cookie-authenticated mutating endpoints (Req 8.5, Property P10) |

## 4. Lawful basis and consent

| Purpose | Consent type | Default |
|---|---|---|
| Core service | `core_service` | required for service use |
| Personalization | `personalization` | off until granted |
| Research | `research` | off |
| Cross-border processing | `cross_border_processing` | off (explicit, separately toggleable) |
| Sharing | `sharing` | off |
| AI transparency acknowledgement | `ai_transparency` | recorded on acknowledgement |

Consent is typed, versioned, and append-only: a withdrawal appends a new row and
never deletes the prior grant (Property P1). `has_consent` is the single source
of truth consulted by personalization, research, sharing, and the cross-border
gate. Withdrawal is at least as easy as granting, via the self-service Consent
Center (Req 2.6).

## 5. Data minimization

- Outbound model requests transmit only the text necessary for inference; direct identifiers are excluded where feasible (Req 4.3).
- Compliance and DSAR rows store request types, timestamps, status, and opaque hashed user references — never query text, drug lists, or free-text health data (Req 3.5).
- Telemetry, metrics, flow events, and analytics exclude PII (Req 7.3).

## 6. Data-subject rights matrix (PDPD Arts. 9, 14–16)

| Right | DSAR kind | Mechanism |
|---|---|---|
| Access / portability | `export` | Machine-readable bundle of the subject's own rows (`schema: clara.dsar.export.v1`); contains exactly that subject's data (Property P3) |
| Correction | `correct` | Subject-initiated correction request, tracked in the append-only log |
| Deletion | `delete` | Irreversible anonymization + account tombstone; audit rows survive (Property P4) |
| Restriction | `restrict` | Restriction of processing recorded; consent gate enforces exclusion |
| Consent withdrawal | `withdraw` | Append-only withdrawal row; purpose excluded on all subsequent requests (Req 2.3) |

Every DSAR is acknowledged immediately with a PII-free acknowledgement and
tracked against the **30-day statutory response window**; overdue unresolved
requests surface first in the admin queue (Req 3.6).

## 7. Residual risk and conclusion

With the mitigations above, residual risk to data subjects is assessed as
**acceptable** for a high-risk decision-support system, conditional on:

- staged enablement of compliance flags per environment;
- the no-PII CI guard remaining green;
- periodic review of the Transfer Impact Assessments and retention schedule.

This DPIA is reviewed whenever a new processing activity, processor, or data
category is introduced, and at minimum on each transparency-notice version bump.
