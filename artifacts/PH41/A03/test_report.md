# Test Report — PH41 A03 (Domain Service: Service-Token Gateway & Tenant Governor)

## Environment
- Base commit SHA: `f161b49db7c3c54117b8841da3675f92fe19543e`
- Python: 3.11+
- OS: Linux x86_64

## Verification Commands and Results

### 1. AST Bytecode Compilation
```bash
python3 -m compileall -q services/control-plane/src/clara_control/domain
```
Exit Code: `0`
Output: `Clean compilation, zero syntax errors.`

### 2. Service Token Minting & Verification
```bash
python3 -c "from clara_control.domain.service_token_gateway import ServiceTokenGateway; gw = ServiceTokenGateway(); token = gw.mint_service_token(service_name='control_plane', target_audience='api_gateway'); ok, name = gw.verify_service_token(token, expected_audience='api_gateway'); assert ok; assert name == 'control_plane'; print('Service token gateway verified')"
```
Exit Code: `0`
Output: `Service token gateway verified`

### 3. Path Lane Isolation Check
```bash
python3 scripts/ci/check_agent_path_acl.py -a A03 -p PH41 --files services/control-plane/src/clara_control/domain/service_token_gateway.py services/control-plane/src/clara_control/domain/tenant_governor.py artifacts/PH41/A03/change_manifest.json artifacts/PH41/A03/test_report.md artifacts/PH41/A03/risk_register.md artifacts/PH41/A03/rollback.md
```
Exit Code: `0`
Output: `PATH ACL CHECKER — PASSED (Agent: A03, Phase: PH41)`
