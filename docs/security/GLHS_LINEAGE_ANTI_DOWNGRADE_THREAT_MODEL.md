# GLHS Lineage Anti-Downgrade & False Audit Reconstruction Threat Model (PH49)

## Executive Summary
This threat specification evaluates adversarial vectors attempting to subvert GLHS R4 provenance tracking, downgrade cryptographic attestation levels, or fabricate plausible historical audit chains.

## Threat Vectors & Invariants

### 1. Attestation Rank Stripping & Downgrade Attack
- **Threat Vector:** A compromised clinician account attempts to adopt an AI proposal while stripping the `inference_context_binding_id` or downgrading `attestation_level` from $L3$ (Provider Execution Attested) to $L0$ (Application Envelope Only) to mask AI assistance during medical malpractice inquiries.
- **Countermeasure (GRWC Step 6 & LineageAntiDowngradeVerifier):**
  - Lineage traversal traverses review descendants to the root model proposal.
  - Invariant: $Rank(L_{descendant}) \ge Rank(L_{parent})$.
  - Severing `inference_context_binding_id` or omitting root snapshot manifests raises `commitment_lineage_tampered` (HTTP 409).

### 2. False Historical Audit Reconstruction Attack
- **Threat Vector:** An adversary with read access attempts to synthesize a fake historical sequence of proposal digests ($P_0 \to P_1 \to P_2$) to justify an erroneous medication change.
- **Countermeasure:**
  - Every proposal digest $P_i$ computes an HMAC/SHA-256 over its immutable fields, including the exact hash of the preceding parent proposal:
    $$P_i = \text{SHA-256}(P_{i-1} \parallel \text{action} \parallel \text{actor\_id} \parallel \text{timestamp})$$
  - Hash chain breaks if any intermediate proposal is omitted or modified.

## Threat Evaluation Matrix

| Threat ID | Description | Severity | Likelihood | Mitigation | Residual Risk |
|---|---|---|---|---|---|
| TM-LIN-01 | Stripping model provenance during review | Critical | Low | Lineage traversal enforces root binding preservation | None |
| TM-LIN-02 | Fabricating intermediate proposal hashes | High | Low | Cryptographic hash chaining over RFC 8785 canonical JSON | Negligible |
| TM-LIN-03 | Injecting circular proposal lineage references | Medium | Low | Cycle detection set + depth <= 4 bound | None |
| TM-LIN-04 | Replaying expired proposal under new snapshot | High | Low | Strict snapshot digest match required | None |
