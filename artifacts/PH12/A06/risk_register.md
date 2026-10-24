# Risk Register — PH12 A06 (Mobile Flutter: LifeMap Longitudinal Health Timeline)

| Risk ID | Description | Severity | Likelihood | Mitigation | Status |
|---------|-------------|----------|------------|------------|--------|
| RISK-PH12-A06-01 | Exposure of longitudinal health events across users on shared mobile devices | High | Low | Read cache strictly scoped per authenticated user (`clara.lifemap.timeline.$userId.read_projection`) in secure storage; completely wiped on sign-out via `PersistentSessionStore._purgeOfflineCaches`. | Mitigated |
| RISK-PH12-A06-02 | Clinical misunderstanding between event occurrence time ($\tau_v$) and system recording time ($\tau_k$) | Medium | Low | Prominent bitemporal perspective selector with clear localized Vietnamese and English descriptions and visual indicators on every timeline node card. | Mitigated |
| RISK-PH12-A06-03 | Accidental offline mutations causing inconsistent state or data divergence | High | Low | Offline view is strictly a read-only projection; action buttons (Correct, Dispute) are explicitly disabled in offline mode and guarded with clear warning notices. | Mitigated |
| RISK-PH12-A06-04 | Accessibility degradation or touch target tap failures on mobile devices | Medium | Low | All interactive controls, chips, and action buttons are wrapped in `MinTapTarget` ensuring a minimum touch target dimension $\ge 48\text{dp}$. | Mitigated |
| RISK-PH12-A06-05 | Premature exposure of timeline interface before backend and clinical verification | Medium | Low | Entire feature is gated behind `lifemap_timeline_mobile_enabled`, defaulting to `false` (fail-closed); UI components remain dark unless explicitly enabled. | Mitigated |
| RISK-PH12-A06-06 | Stale or invalid longitudinal health projections displayed indefinitely | Low | Low | Offline cache enforces a strict 15-minute TTL (`validUntil`); stale projections return `null` and prompt an automatic network refresh. | Mitigated |
