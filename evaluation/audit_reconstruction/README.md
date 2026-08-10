# Governed decision audit reconstruction

This workstream verifies the bitemporal audit chain, not clinical outcomes.

The canonical implementation is `reconstruct_governed_decision` in the API
gateway. A reportable run must retain a frozen snapshot payload digest and show
the requested transition's base/result state versions, policy/consent versions,
proposal source snapshot link, transition action, review state, and reason code.
It also reports the valid-time and known-at cutoffs and replays the append-only
ledger at those cutoffs; the persisted payload remains the authoritative record
of exactly what the AI saw.

Status: **IMPLEMENTED_NOT_HEADLINE**. The gateway/property tests prove the
mechanism; independent audit usability and clinical utility remain NOT RUN.
