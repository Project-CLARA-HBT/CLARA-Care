# Deviations and exclusions

- No HTTP server, FHIR resource parser, capability statement, ETag wire format,
  search, conditional create, transaction bundle or persistence engine.
- Authorization is a minimal actor/purpose set, not a full Consent interpreter.
- Provenance and audit are semantic records, not serialized FHIR resources.
- Temporal/conflict resolution reuses the explicitly bounded local BTSA
  mechanism mapping; it is not a faithful external implementation claim.
- State version is profile-global for comparability with the current GLHS path.
- Exact snapshot ID/digest/task/disclosed-evidence binding is intentionally
  absent and must not be described as an accidental implementation defect.
- No performance, interoperability, compliance or clinical claim is permitted.
