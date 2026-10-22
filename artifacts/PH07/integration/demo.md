# PH07 Demonstration Scenarios

## Scenario 1: GLHS 3-Digest Continuity Verification
Execute the transport verification unit check proving that D1 clinical projection, D2 semantic envelope, and D3 outbound transport bytes maintain exact cryptographic continuity:
```bash
python3 -c "
from clara_api.glhs.transport_verifier import GlhsTransportVerifier as V
raw = b'{\"model\":\"deepseek-reasoner\",\"messages\":[]}'
res = V.verify_egress_payload(model_projection={'vitals':[]}, semantic_envelope={'req':1}, raw_transport_bytes=raw)
assert res.valid
print('3-Digest continuity verified:', res.d1_projection_digest[:8], res.d2_semantic_digest[:8], res.d3_transport_digest[:8])
"
```
**Expected Output:**
```text
3-Digest continuity verified: <d1> <d2> <d3>
```
This confirms that the egress bytes match the computed D3 digest and link to the original model projection.

## Scenario 2: GLHS Transport & Attestation Quality Gate Execution
Execute the automated PH07 quality gate:
```bash
python3 scripts/ci/ph07_quality_gate.py
```
**Expected Output:**
```text
================================================================================
PH07 QUALITY GATE: GLHS TRANSPORT, MODEL-DISPATCH & RECEIPT INTEGRITY
================================================================================
[PASS] Pinned Baseline SHA
[PASS] Worktree Topology (10 Subagents)
[PASS] 3-Digest Continuity & Receipt Attestation Suite
[PASS] Python AST Bytecode Compilation
[PASS] Alembic Migration Downgrade Completeness
[PASS] Secret Hygiene & Credential Invariant
[PASS] A10 Path Lane Integrity
================================================================================
PH07 QUALITY GATE VERDICT: PASSED
```
This demonstrates complete cryptographic non-repudiation and receipt attestation integrity.
