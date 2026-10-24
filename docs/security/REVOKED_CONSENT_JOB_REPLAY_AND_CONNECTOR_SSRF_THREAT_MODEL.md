# Threat Model: Revoked-Consent Job Replay & Connector SSRF Mitigation

## Document Metadata
- **Phase**: PH51 (Job queues, outbox, connectors and webhooks console)
- **Agent**: A08 (Security / Negative Tests)
- **Classification**: Medical Cyber-Physical & Statutory Data Compliance (Vietnam Nghị định 13/2023/NĐ-CP & Luật Khám bệnh, chữa bệnh 2023)
- **Status**: Production Security Baseline

---

## 1. Threat Scenario 1: Replay of Jobs Following Patient Consent Revocation (STRIDE: Elevation of Privilege / Information Disclosure)

### 1.1 Threat Characterization
In a distributed clinical system, background tasks (e.g. external EMR synchronization, research registry export, insurance claim outbox relay) may fail transiently due to partner network outages and get moved to a Dead-Letter Queue (DLQ).
During the dormant period while in the DLQ, the patient withdraws their explicit statutory consent for the processing purpose (`revoked`).

If the DLQ management console permits unconditional manual replay or automated retries without re-evaluating consent status:
- Protected Health Information (PHI) will be transmitted downstream in direct violation of statutory consent.
- Healthcare organizations face administrative penalties and loss of medical operating licenses.

### 1.2 Defense-in-Depth Mitigation Architecture
1. **Dynamic Statutory Purpose Re-Check**:
   Before transitioning any job from `DEAD_LETTER` to `PENDING`, the requeue kernel queries the consent ledger. If the required consent purpose is revoked, the requeue is aborted with status code `BLOCKED_CONSENT_REVOKED`.
2. **Audit & Traceability**:
   Every requeue attempt records an immutable audit record containing the administrator ID, user consent version, and rationale.

---

## 2. Threat Scenario 2: Connector & Webhook Server-Side Request Forgery (STRIDE: Elevation of Privilege / Tampering)

### 2.1 Threat Characterization
When configuring third-party EMR webhook endpoints, HL7/FHIR push destinations, or wearable cloud integrations, an adversary attempts to provide internal network endpoints:
- AWS/GCP instance metadata: `http://169.254.169.254/latest/meta-data/`
- Local control-plane loopback: `http://127.0.0.1:8200`
- Intranet private IP CIDRs: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`

### 2.2 Defense-in-Depth Mitigation Architecture
1. **Strict Scheme & Destination Validation**:
   Only `https://` is permitted for external webhook egress. Unencrypted `http://` is strictly prohibited.
2. **DNS Rebinding & IP CIDR Blocklist**:
   Connector outgoing HTTP client resolves hostnames prior to connection and blocks private, loopback, multicast, and link-local ranges:
   - `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, `::1`.
3. **Redacted Outbox Payloads**:
   Administrative failure inspectors display only status codes and sanitized trace identifiers. API secrets, OAuth tokens, and clinical payloads are filtered out before console rendering.
