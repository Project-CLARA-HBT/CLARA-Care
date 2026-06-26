# AI Risk-Management File — CLARA-Care

**Document status:** Living record · version-controlled
**Legal basis:** Law on Artificial Intelligence No. 134/2025/QH15 (high-risk-system documentation duties)
**Risk classification:** High-risk AI system (health domain)
**Last reviewed:** 2026-03

> Hồ sơ quản lý rủi ro hệ thống Trí tuệ nhân tạo. This file records CLARA-Care's
> intended purpose, risk classification, identified risks, mitigations,
> human-oversight design, and evaluation summary, as AI Law 134/2025 requires of
> a high-risk system (Req 1.5, 6.1).

## 1. System identification

| Field | Value |
|---|---|
| System | CLARA-Care clinical decision-support assistant |
| Device status | Decision-support software on self-declared data — **not** a medical device, **not** an EMR/EHR |
| Risk classification | **High-risk AI system in the health domain** |
| Governing law | AI Law No. 134/2025/QH15 (effective 1 March 2026); Decree 13/2023/NĐ-CP (PDPD) |
| Primary model | DeepSeek `deepseek-v3.2` via the YEScale offshore endpoint |
| Retrieval embeddings | OpenAI-compatible endpoint via YEScale (`https://api.yescale.io/v1`) |
| Local fallback | Deterministic synthesiser `local-synth-*` (labeled degraded) |
| Transparency notice version | `2026-03-v1` |
| Medical disclaimer version | `2026-04-v1` |

## 2. Intended purpose

CLARA assists users in retrieving and understanding medical information in
Vietnamese (bilingual vi/en for legal terms of art). It supports — and never
replaces — a licensed clinician. It does **not** diagnose, prescribe, or
recommend personal dosages. Every medical response carries a directive to review
with a licensed clinician (Req 5.3).

## 3. Risk classification rationale

A clinical decision-support assistant can materially affect health, safety, and
fundamental rights, so it is treated as **high-risk** for the purposes of AI Law
134/2025. This classification triggers the documentation duties recorded here,
the human-oversight requirements in §5, and the transparency obligations in the
AI Transparency Notice.

## 4. Identified risks and mitigations

| # | Risk | Likelihood / impact | Mitigation (existing CLARA mechanism) | Status |
|---|---|---|---|---|
| R1 | Model gives an unsafe definitive diagnosis or prescription | Low / severe | Legal hard-guard blocks prescribing, definitive diagnosis, and personal-dosage outputs (Req 5.1) | Enforced |
| R2 | User in an emergency receives reasoning instead of escalation | Low / severe | Emergency fast-path directs to emergency services with no diagnostic reasoning (Req 5.2) | Enforced |
| R3 | Unverified critical drug-dosage / DDI claim reaches the user | Medium / severe | FIDES CRITICAL-claim blocking on failed drug-dosage and DDI verification (Req 5.4) | Enforced |
| R4 | User mistakes the assistant for a clinician | Medium / moderate | Versioned AI Transparency Notice + per-response clinician-review directive (Req 1, 5.3) | Enforced (flag-gated rollout) |
| R5 | Sensitive data leaves Vietnam without lawful basis | Medium / high | Cross-border consent gate; minimize payload; degrade to local fallback when consent absent (Req 4) | Enforced (flag-gated) |
| R6 | User cannot tell a degraded answer from a primary one | Medium / moderate | `ai_disclosure.is_fallback` is true iff answer came from `local-synth-*` (Req 1.4, Property P8) | Enforced (flag-gated) |
| R7 | PII leaks into telemetry / logs | Low / high | No-PII telemetry invariant; redaction projection on all compliance events (Req 7.3, 8.3) | Enforced |
| R8 | Compliance store unavailable degrades safety | Low / moderate | Fail closed for processing, open for safety: emergency fast-path and disclaimers always render | Enforced |

## 5. Human-oversight design (Giám sát của con người)

CLARA keeps a human in/over the loop:

- **Hard-guard:** prescribing, definitive diagnosis, and personal-dosage outputs are blocked at the source (Req 5.1).
- **Emergency fast-path:** emergencies are routed to emergency services without diagnostic reasoning (Req 5.2).
- **Clinician-review directive:** every medical response instructs the user to review with a licensed clinician (Req 5.3).
- **FIDES verification:** CRITICAL claims that fail drug-dosage or DDI verification are blocked (Req 5.4).
- **Recorded oversight:** for high-risk outputs, the verification verdict and whether human-review escalation was advised are recorded (Req 5.5).

## 6. Evaluation summary

- **Clinical-quality harness:** the research-quality gate (`services/ml`) evaluates synthesis quality before changes ship.
- **Verification verdicts:** FIDES verdicts on drug-dosage and DDI claims are tracked; CRITICAL failures block.
- **Regression gate:** a flags-off baseline asserts request/response shapes and side effects equal the pre-feature system (Property P6).
- **No-PII guard:** an adversarial test feeds PII into compliance log writes and asserts the persisted projection drops it (Property P5).

## 7. Change control

This file is version-controlled. Any change to intended purpose, model family,
risk classification, or oversight design requires a review and a bump of the
relevant version constants (`MEDICAL_DISCLAIMER_VERSION`,
`COMPLIANCE_TRANSPARENCY_NOTICE_VERSION`). A new transparency-notice version
forces re-acknowledgement on next access (Req 1.6).
