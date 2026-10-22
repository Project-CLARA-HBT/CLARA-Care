# GLHS Stale-Write & Attestation Downgrade Threat Model (PH06)

## Executive Summary
This threat specification defines adversarial vectors targeting Optimistic Concurrency Control (OCC) partition versioning and clinical proposal attestation integrity in GLHS R4.

## Threat Vectors & Invariants

### Vector 1: Stale-Write & Lost Update Attack
- **Threat Scenario:** A client observes entity partition version $v_0$ (e.g. current active medication list). Another clinician commits a modification updating the version to $v_1$. The original client submits an overwrite based on stale $v_0$.
- **Countermeasure (Phase 3 & 5):**
  - Commit Kernel locks entity partitions lexicographically.
  - Phase 3 revalidates `observed_version == partition.current_version`.
  - Stale version raises `GlhsInvariantError("dependency_revalidation_failed: observed_version != current_version")` with HTTP 409 Conflict.

### Vector 2: Attestation Rank Downgrade Attack
- **Threat Scenario:** An adversarial reviewer attempts to strip cryptographic provider execution receipts ($L3$) from a model proposal and downgrade it to unverified server dispatch ($L0$).
- **Countermeasure (GRWC Step 6 & LineageAntiDowngradeVerifier):**
  - Traversal validates that review descendants satisfy $Rank(L_{descendant}) \ge Rank(L_{parent})$.
  - Descendant cannot sever the link to `inference_context_binding_id` or discard `source_snapshot_id`.

### Vector 3: Proposal Lineage Cycle & Depth Exhaustion
- **Threat Scenario:** Adversary creates circular reviewed proposal IDs ($A \to B \to A$) or deep delegation chains attempting to cause CPU/stack DoS during traversal.
- **Countermeasure (GRWC Step 4):**
  - Lineage traversal tracks visited proposal IDs in an immutable set; duplicate ID raises `lineage_cycle: commitment_lineage_cycle_detected`.
  - Traversal depth is strictly capped at $depth \le 4$; exceeding raises `lineage_depth_exceeded`.
