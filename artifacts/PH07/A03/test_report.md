# Test Report — PH07 A03 (Domain + GLHS: D3 Transport Payload Digest Verifier)

## Environment
- Base commit SHA: `e8533cb029a1470ce2d1bc027a421b47664871c5`
- Python: 3.11+
- OS: Linux x86_64

## Verification Commands and Results

### 1. AST Bytecode Compilation
```bash
python3 -m compileall -q services/api/src/clara_api/glhs/transport_verifier.py
```
Exit Code: `0`
Output: `Clean compilation, zero syntax errors.`

### 2. Transport Verifier Unit Check
```bash
python3 -c "
from clara_api.glhs.transport_verifier import GlhsTransportVerifier as V
raw = b'{\"model\":\"deepseek-reasoner\",\"messages\":[]}'
res = V.verify_egress_payload(model_projection={'vitals':[]}, semantic_envelope={'req':1}, raw_transport_bytes=raw)
assert res.valid
assert len(res.d1_projection_digest) == 64
assert len(res.d2_semantic_digest) == 64
assert len(res.d3_transport_digest) == 64
print('Transport 3-digest continuity verified')
"
```
Exit Code: `0`
Output: `Transport 3-digest continuity verified`

### 3. Path Lane Isolation Check
```bash
python3 scripts/ci/check_agent_path_acl.py -a A03 -p PH07 --files services/api/src/clara_api/glhs/transport_verifier.py artifacts/PH07/A03/change_manifest.json artifacts/PH07/A03/test_report.md artifacts/PH07/A03/risk_register.md artifacts/PH07/A03/rollback.md
```
Exit Code: `0`
Output: `PATH ACL CHECKER — PASSED (Agent: A03, Phase: PH07)`
