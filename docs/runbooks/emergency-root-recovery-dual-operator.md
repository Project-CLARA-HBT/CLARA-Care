# Runbook: Emergency Root Recovery with Dual Operator Ceremony (PH42)

## 1. Overview & Objective
This runbook defines the break-glass procedure for recovering administrative control of the CLARA Care Control Plane when all primary administrator accounts or MFA credentials become inaccessible, corrupted, or compromised.

To prevent unilateral rogue administrator actions or insider threat execution, root recovery strictly requires **Dual-Operator Multi-Party Authorization (Four-Eyes Principle)**.

## 2. Emergency Recovery Quorum Requirements
- **Quorum:** Minimum 2 authorized key-holders (e.g. Lead SRE + Chief Security Officer).
- **Physical/Cryptographic Split:** The emergency root decryption key is partitioned into 3 Shamir secret shares; any 2 shares must be combined to reconstruct the root recovery token.
- **Audit Mandate:** All keystrokes and outputs during the recovery session must be recorded in an immutable, signed forensic audit log.

## 3. Step-by-Step Dual-Operator Ceremony

### Step 1: Secure Environment Isolation
1. Disconnect the control-plane host from external internet access (retain internal management network only).
2. Establish a recorded terminal session with both operators present physically or via verified video stream.

### Step 2: Share Assembly & Token Reconstruction
Operator A supplies Key Share 1:
```bash
read -s -p "Operator A Key Share: " SHARE_A
```
Operator B supplies Key Share 2:
```bash
read -s -p "Operator B Key Share: " SHARE_B
```

Reconstruct the emergency break-glass token:
```bash
ROOT_TOKEN=$(python3 -c "
import hashlib, hmac
share_a = '$SHARE_A'.strip()
share_b = '$SHARE_B'.strip()
combined = hmac.new(share_a.encode(), share_b.encode(), hashlib.sha256).hexdigest()
print(f'breakglass-{combined[:32]}')
")
```

### Step 3: Emergency Break-Glass Execution
Invoke the control-plane recovery CLI with the dual-operator root token:
```bash
python3 -m clara_control.domain.recovery \
  --token "$ROOT_TOKEN" \
  --operator-a "sre-lead@theclaracare.com" \
  --operator-b "cso@theclaracare.com" \
  --action "RESET_ROOT_ADMIN" \
  --target-email "root-admin@theclaracare.com"
```

### Step 4: Revoke All Existing Active Sessions
Immediately terminate all active administrative sessions across every device:
```bash
curl -X POST http://localhost:8200/control/v1/sessions/revoke \
  -H "Content-Type: application/json" \
  -H "X-Control-Service-Token: $ROOT_TOKEN" \
  -d '{"session_id": "ALL", "revoke_all_other_devices": true}'
```

## 4. Post-Recovery Checklist & Audit Lock
1. [ ] Verify new temporary password and enroll hardware security key (FIDO2/WebAuthn).
2. [ ] Re-generate and re-distribute Shamir emergency root shares to key-holders.
3. [ ] Export terminal session recording and submit to Compliance Officer.
4. [ ] Verify that `control_audit_logs` records the `EMERGENCY_ROOT_RECOVERY` event.
