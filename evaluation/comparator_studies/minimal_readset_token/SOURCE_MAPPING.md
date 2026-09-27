# Source Mapping: Minimal Read-Set Token Comparator

| Minimal Token Field | GLHS Manifest / Proposal Coordinate | Enforcement Mechanism |
| :--- | :--- | :--- |
| `schema` | N/A (`glhs.v1`) | Schema discriminator |
| `profile_id` | `PhrProfile.public_id` / `target_profile_public_id` | Target patient scope matching |
| `actor_id` | `User.id` / `actor_user_id` | Caller identity match |
| `actor_role` | `actor_role` (`owner`, `clinician`, etc.) | Role-based authorization gate |
| `purpose` | `purpose` (`self_care`, `clinical_review`, etc.) | Purpose limitation check |
| `task` | `task` (e.g. `monitoring_repeat`) | Task boundary check |
| `snapshot_id` | `GlhsSnapshotManifest.id` | Snapshot identity binding |
| `snapshot_digest` | `GlhsSnapshotManifest.snapshot_digest` | Exact content tamper detection |
| `evidence_commitment` | `GlhsSnapshotManifest.disclosed_evidence_ids` | SHA-256 evidence set commitment |
| `state_dependencies` | `GlhsStateVersion.version` | Base-state freshness verification |
| `policy_version` | Active system policy version epoch | Policy invariant adherence |
| `consent_version` | `UserConsent.consent_version` | Active patient consent validation |
| `expires_at` | `GlhsSnapshotManifest.lease_expires_at` | Lease expiration enforcement |
| `signature` | Optional transport HMAC-SHA256 | Transport anti-tampering verification |
