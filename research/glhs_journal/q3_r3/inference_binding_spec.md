# Formal Specification: Governed Inference Context Binding & Canonical Envelope (`clara.inference-envelope.v1`)

**Program:** GLHS R3 — Governed Read-to-Write Continuity (GRWC)  
**Module:** `services/api/src/clara_api/glhs/` (`models.py`, `gateway.py`, `commitment_gateway.py`)  
**Author / Curator:** Agent B — Systems & Formal Architecture  
**Status:** Frozen Phase 1 Systems Specification  
**Date:** Tue Sep 29 2026  

---

## 1. Executive Summary & Problem Formulation

In medical AI decision support and autonomous clinical assistants, non-deterministic Large Language Model (LLM) agents execute asynchronous reasoning passes over patient health data. A fundamental vulnerability in un-governed agent systems is the temporal and structural disconnect between:
1. **Governed Disclosure Compilation ($t_{\text{snap}}$):** The instant a bounded Temporal Health State Snapshot (THSS) $H$ is authorized and compiled.
2. **Provider Dispatch ($t_{\text{dispatch}}$):** The instant the final request envelope is transmitted across the network to an external LLM provider.
3. **Provider Response ($t_{\text{response}}$):** The instant the LLM output is received by the application boundary.
4. **Commit Admission ($t_{\text{commit}}$):** The instant a clinical mutation proposal $P$ derived from the model output is submitted to PostgreSQL for atomic transaction execution.

If an application merely records a snapshot ID without binding the **exact request envelope dispatched** and the **exact model-visible projection presented inside the prompt**, subtle context drift, prompt tampering, undisclosed evidence injection, or provider substitution can occur unnoticed between $t_{\text{snap}}$ and $t_{\text{commit}}$.

GLHS R3 resolves this vulnerability by introducing **Exact Inference Consumption Binding** backed by a server-owned, append-only ledger (`GlhsInferenceContextBinding`), a 5-partition canonical request envelope (`clara.inference-envelope.v1`), and a deterministic state transition machine enforcing that **ONLY `COMPLETED` bindings can be cited in admitted clinical proposals**.

---

## 2. Existing Schema Audit & R3 Delta Analysis

### 2.1 Audit of `GlhsInferenceContextBinding`

The authoritative database model is declared in `services/api/src/clara_api/db/models.py` (`GlhsInferenceContextBinding`) and managed via `services/api/src/clara_api/glhs/gateway.py`.

The table below audits the R3 required fields, their database column mapping, nullability, immutability constraints, and scientific purpose.

| R3 Abstract Coordinate | Database Column Name | DB Datatype | Nullable | Immutability / Event Guard | Scientific & Security Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Binding Identity** | `public_id` | `String(36)` | No | Fully Immutable (Canonical Protection) | Globally unique UUIDv4 identity for the inference context binding. |
| **Profile Anchor** | `profile_id` | `Integer (FK)` | No | Fully Immutable (Canonical Protection) | Anchors the binding to the patient's PHR profile. |
| **Source Snapshot** | `source_snapshot_id` | `String(36)` | Yes* | Fully Immutable (Canonical Protection) | Cited THSS snapshot ID. *Required when `consumed_thss=True`. |
| **Snapshot Digest** | `source_snapshot_digest` | `String(64)` | Yes* | Fully Immutable (Canonical Protection) | SHA-256 digest of the bounded THSS snapshot. |
| **Manifest Digest** | `source_manifest_digest` | `String(64)` | Yes* | Fully Immutable (Canonical Protection) | SHA-256 digest of the snapshot provenance manifest. |
| **Projection Digest ($H_{\text{proj}}$)** | `projection_digest` | `String(64)` | Yes | Fully Immutable (Canonical Protection) | SHA-256 digest over the exact model-visible health projection. |
| **Envelope Digest ($H_{\text{env}}$)** | `request_envelope_digest` | `String(64)` | Yes | Fully Immutable (Canonical Protection) | SHA-256 digest over the full 5-partition canonical request envelope. |
| **Requested Model ID** | `requested_model_id` | `String(128)` | Yes | Fully Immutable (Canonical Protection) | Target model ID specified in request pre-dispatch (e.g. `deepseek-reasoner`). |
| **Reported Model ID** | `reported_model_id` | `String(128)` | Yes | Projection Mutable (Finalization Only) | Actual model ID returned by provider response headers/payload (e.g. `deepseek-reasoner-v3`). |
| **Response Digest** | `response_digest` | `String(64)` | Yes | Projection Mutable (Finalization Only) | Cryptographic SHA-256 digest of raw/canonical provider response payload. |
| **Binding Status** | `status` | `String(32)` | No | Projection Mutable (Finalization Only) | FSM status (`PENDING`, `COMPLETED`, `FAILED`, `ABORTED`). Default `PENDING` at dispatch. |
| **Dispatch Timestamp** | `request_started_at` | `DateTime(TZ)` | Yes | Fully Immutable (Canonical Protection) | High-precision UTC timestamp at provider dispatch ($t_{\text{dispatch}}$ / `provider_dispatch_at_utc`). |
| **Response Timestamp** | `request_completed_at` | `DateTime(TZ)` | Yes | Projection Mutable (Finalization Only) | High-precision UTC timestamp at provider response completion ($t_{\text{response}}$ / `provider_response_at_utc`). |
| **Governance Base State** | `base_state_version` | `Integer` | No | Fully Immutable (Canonical Protection) | CAS partition state version of patient record at disclosure compilation time. |
| **Policy Version** | `policy_version` | `String(64)` | No | Fully Immutable (Canonical Protection) | System access and disclosure policy version active at inference creation. |
| **Consent Version** | `consent_version` | `String(96)` | No | Fully Immutable (Canonical Protection) | Versioned patient consent directive active at inference creation. |
| **Actor & Role** | `actor_user_id`, `actor_role` | `Int`, `String` | Yes/No | Fully Immutable (Canonical Protection) | User ID and RBAC role executing the inference flow. |
| **Purpose & Task** | `purpose`, `task` | `String` | No | Fully Immutable (Canonical Protection) | Governed usage purpose and clinical task objective. |
| **Evidence Set Digest** | `evidence_set_digest` | `String(64)` | No | Fully Immutable (Canonical Protection) | SHA-256 digest over disclosed evidence IDs. |
| **Binding Seal Digest** | `binding_digest` | `String(64)` | No | Recomputed at Finalization | Cryptographic seal covering all security-relevant fields in `inference_binding_envelope()`. |

### 2.2 Database Integrity Constraints & Immutability Rules

To guarantee ledger immutability and prevent post-hoc tampering or forgery of inference bindings, the database schema and SQLAlchemy ORM layer enforce strict invariants:

1. **Database Check Constraint (`ck_glhs_inference_binding_snapshot_required`):**
   ```sql
   CHECK (
       (consumed_thss IS TRUE AND source_snapshot_id IS NOT NULL AND source_snapshot_digest IS NOT NULL AND source_manifest_digest IS NOT NULL) OR
       (consumed_thss IS FALSE AND source_snapshot_id IS NULL AND source_snapshot_digest IS NULL AND source_manifest_digest IS NULL)
   )
   ```
2. **Database Check Constraint (`ck_glhs_inference_binding_schema_version`):**
   Requires non-empty `binding_schema_version`.
3. **ORM Event Listener (`_protect_glhs_inference_binding_content`):**
   Intercepts `before_update` events on `GlhsInferenceContextBinding`. Allows mutations **ONLY** to the lifecycle transition fields: `frozenset({"status", "reported_model_id", "request_completed_at", "response_digest", "binding_digest"})`. Any attempt to modify canonical request parameters ($H_{\text{proj}}$, $H_{\text{env}}$, snapshot ID, actor, task, purpose) raises `ValueError("GLHS ledger rows are immutable...")`.
4. **ORM Event Listener (`_reject_glhs_ledger_mutation`):**
   Intercepts `before_delete` events on `GlhsInferenceContextBinding` and raises `ValueError("GLHS ledger rows are immutable and append-only")`.

---

## 3. Canonical Request Envelope Specification (`clara.inference-envelope.v1`)

### 3.1 Architectural Partitioning

The canonical request envelope `clara.inference-envelope.v1` structures the entire LLM prompt payload into **5 strictly isolated partitions**. This partitioning enforces cryptographic boundary separation, ensuring health state projections cannot be confused with system instructions or conversation context.

```text
+-----------------------------------------------------------------------------------+
|                        clara.inference-envelope.v1                                |
+-----------------------------------------------------------------------------------+
| 1. System Prompt Partition (system_prompt)                                        |
|    - prompt_template_version, system_prompt_version, role_definition, constraints|
+-----------------------------------------------------------------------------------+
| 2. Health State Projection Partition (health_state_projection) [H_proj Target]     |
|    - profile_id, active_medications, active_conditions, observations, THSS ref   |
+-----------------------------------------------------------------------------------+
| 3. Conversation Context Partition (conversation_context)                          |
|    - message_history, dialogue_turns, prior_agent_responses                       |
+-----------------------------------------------------------------------------------+
| 4. Task Instructions Partition (task_instructions)                                |
|    - purpose, task, reasoning_directives, expected_output_schema                  |
+-----------------------------------------------------------------------------------+
| 5. Runtime Parameters Partition (runtime_parameters)                              |
|    - model_route, requested_model_id, provider, temperature, max_tokens           |
+-----------------------------------------------------------------------------------+
```

### 3.2 Partition Breakdown & Descriptions

#### 1. System Prompt Partition (`system_prompt`)
Contains system-level role definitions, safety guardrails, clinical guidelines, and prompt versioning.
* **Fields:** `prompt_template_version`, `system_prompt_version`, `base_system_prompt_digest`, `clinical_guardrails`.
* **Purpose:** Ensures the system prompt version is explicitly sealed. Any alteration to system instructions alters $H_{\text{env}}$.

#### 2. Model-Visible Health State Projection Partition (`health_state_projection`)
Contains the exact clinical patient data extracted from the THSS snapshot and formatted for model consumption.
* **Fields:** `profile_id`, `active_medications`, `allergies`, `vital_signs`, `lab_results`, `disclosed_evidence_ids`, `disclosure_metadata` (`snapshot_id`, `manifest_digest`).
* **Digest Definition ($H_{\text{proj}}$):**
  $$H_{\text{proj}} = \text{SHA-256}\left(\text{JCS}\left(\text{health\_state\_projection}\right)\right)$$
* **Purpose:** Serves as the exact projection target for GRWC admission. At commit time, the admission kernel verifies that the proposal's cited binding contains a `projection_digest` matching $H_{\text{proj}}$.

#### 3. Conversation Context Partition (`conversation_context`)
Contains previous dialogue turns between the user, clinician, and assistant.
* **Fields:** `messages` (list of `{"role": "user"|"assistant"|"system", "content": "..."}` objects), `turn_count`, `context_window_strategy`.
* **Purpose:** Prevents dialogue injection or historical message manipulation from corrupting health state lineage.

#### 4. Task Instructions Partition (`task_instructions`)
Specifies the goal-directed clinical task and reasoning requirements.
* **Fields:** `purpose` (e.g. `treatment_planning`), `task` (e.g. `reconcile_medication_order`), `task_parameters`, `output_format_spec`.
* **Purpose:** Prevents task-confusion attacks where a binding created for one task (e.g., summary generation) is illegitimately cited for a high-risk mutation task (e.g., medication deletion).

#### 5. Runtime Parameters Partition (`runtime_parameters`)
Specifies LLM execution parameters and adapter route targets.
* **Fields:** `model_route`, `requested_model_id`, `provider`, `temperature`, `max_tokens`, `top_p`, `seed`.
* **Purpose:** Seals model execution parameters, ensuring deterministic verification of model invocation context.

### 3.3 Cryptographic Digest Definitions & Hierarchy

1. **Projection Digest ($H_{\text{proj}}$):**
   $$H_{\text{proj}} = \text{SHA-256}\left(\text{JCS}\left(\text{envelope.health\_state\_projection}\right)\right)$$
2. **Request Envelope Digest ($H_{\text{env}}$):**
   $$H_{\text{env}} = \text{SHA-256}\left(\text{JCS}\left(\text{envelope}\right)\right)$$
3. **Canonical Serialization Standard:**
   All digests MUST be computed using **RFC 8785 JSON Canonicalization Scheme (JCS)** via `services/api/src/clara_api/glhs/canonical_json.py` (`canonicalization_profile = "glhs.jcs.v1"`). Dynamic transport headers, authorization tokens, API keys, dynamic request UUIDs, and network timestamps are strictly excluded from the canonical envelope payload.

### 3.4 Concrete Schema Representation (`clara.inference-envelope.v1`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ClaraInferenceEnvelopeV1",
  "type": "object",
  "required": [
    "schema",
    "system_prompt",
    "health_state_projection",
    "conversation_context",
    "task_instructions",
    "runtime_parameters"
  ],
  "properties": {
    "schema": {
      "type": "string",
      "const": "clara.inference-envelope.v1"
    },
    "system_prompt": {
      "type": "object",
      "required": ["prompt_template_version", "system_prompt_version"],
      "properties": {
        "prompt_template_version": { "type": "string" },
        "system_prompt_version": { "type": "string" },
        "base_system_prompt_digest": { "type": "string" }
      }
    },
    "health_state_projection": {
      "type": "object",
      "required": ["disclosure_metadata", "model_visible_projection"],
      "properties": {
        "disclosure_metadata": {
          "type": "object",
          "required": ["snapshot_id", "manifest_digest"],
          "properties": {
            "snapshot_id": { "type": "string" },
            "manifest_digest": { "type": "string" }
          }
        },
        "model_visible_projection": { "type": "object" }
      }
    },
    "conversation_context": {
      "type": "object",
      "required": ["messages"],
      "properties": {
        "messages": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["role", "content"],
            "properties": {
              "role": { "type": "string", "enum": ["system", "user", "assistant"] },
              "content": { "type": "string" }
            }
          }
        }
      }
    },
    "task_instructions": {
      "type": "object",
      "required": ["purpose", "task"],
      "properties": {
        "purpose": { "type": "string" },
        "task": { "type": "string" }
      }
    },
    "runtime_parameters": {
      "type": "object",
      "required": ["model_route", "requested_model_id"],
      "properties": {
        "model_route": { "type": "string" },
        "requested_model_id": { "type": "string" },
        "provider": { "type": "string" },
        "temperature": { "type": "number" },
        "max_tokens": { "type": "integer" }
      }
    }
  }
}
```

---

## 4. Inference Binding Finite State Machine (FSM)

### 4.1 State Definitions

The lifecycle of a `GlhsInferenceContextBinding` is governed by a strict four-state finite state machine:

```text
               +-----------------------------------+
               |               INIT                |
               |  (In-memory request construction) |
               +-----------------+-----------------+
                                 |
                                 |  create_inference_context_binding(status="PENDING")
                                 v
               +-----------------------------------+
               |              PENDING              |
               |  (Persisted pre-dispatch record)  |
               +--------+-----------------+--------+
                        |                 |
     finalize_...()     |                 |  fail_...() / timeout / abort
     (provider success) |                 |  (provider failure / error)
                        v                 v
     +--------------------+             +--------------------+
     |     COMPLETED      |             |  FAILED / ABORTED  |
     | (Terminal Success) |             |  (Terminal Failure)|
     +--------------------+             +--------------------+
```

1. **`INIT` (Conceptual Pre-Persistence):**
   The API server compiles the THSS snapshot and builds the canonical request envelope `clara.inference-envelope.v1` in memory.
2. **`PENDING` (Persisted Pre-Dispatch):**
   Immediately prior to executing the HTTP network request to the provider, the API server inserts a `GlhsInferenceContextBinding` record with `status = "PENDING"`, `request_started_at = utcnow()`, $H_{\text{proj}}$, $H_{\text{env}}$, and initial seal digest.
3. **`COMPLETED` (Terminal Success):**
   Upon receiving a valid 200 OK response from the LLM provider, the API server calls `finalize_inference_context_binding()`. It records `reported_model_id`, `response_digest`, `request_completed_at = utcnow()`, transitions status to `"COMPLETED"`, and updates the binding seal digest.
4. **`FAILED` / `ABORTED` (Terminal Error / Timeout):**
   If the LLM provider returns an HTTP error, malformed output, or exceeds timeout limits, the API server calls `fail_inference_context_binding()`. Status transitions to `"FAILED"` or `"ABORTED"`, recording `request_completed_at` and error metadata.

### 4.2 State Transition Matrix & Invariants

| Current State | Target State | Triggering Function | Permitted | Conditions & Invariants |
| :--- | :--- | :--- | :--- | :--- |
| **`INIT`** | **`PENDING`** | `create_inference_context_binding(status="PENDING")` | **YES** | Creates pre-dispatch record. `request_started_at` set to UTC now. |
| **`INIT`** | **`COMPLETED`** | `create_inference_context_binding(status="COMPLETED")` | **YES** | Synchronous test/stub path. `request_started_at` and `completed_at` set. |
| **`PENDING`** | **`COMPLETED`** | `finalize_inference_context_binding()` | **YES** | Valid response received. Seals `reported_model_id`, `response_digest`, `request_completed_at`. |
| **`PENDING`** | **`FAILED`** | `fail_inference_context_binding(status="FAILED")` | **YES** | Network error, API error, safety block. Seals `request_completed_at`. |
| **`PENDING`** | **`ABORTED`** | `fail_inference_context_binding(status="ABORTED")` | **YES** | Timeout, client cancellation, circuit breaker trip. Seals `request_completed_at`. |
| **`COMPLETED`**| *Any* | *Any* | **NO** | `COMPLETED` is terminal. Re-editing raises `inference_binding_not_pending`. |
| **`FAILED`** | *Any* | *Any* | **NO** | `FAILED` is terminal. Re-editing raises `inference_binding_not_pending`. |
| **`ABORTED`** | *Any* | *Any* | **NO** | `ABORTED` is terminal. Re-editing raises `inference_binding_not_pending`. |

### 4.3 Proposal Citation Invariant (GRWC Admission Rule)

The formal GRWC admission contract (`evaluate_grwc_admission` / `validate_inference_consumption_continuity`) enforces the following fundamental invariant:

$$\forall P \in \text{Proposals}, b = \text{LookupBinding}(P.\text{inference\_binding\_id}) : \text{Admit}(P) \implies b.\text{status} = \text{"COMPLETED"}$$

* **Fail-Closed Enforcement:**
  * If $b$ is missing $\implies$ raise `inference_binding_not_found`.
  * If $b.\text{status} = \text{"PENDING"}$ $\implies$ raise `binding_not_completed`.
  * If $b.\text{status} \in \{\text{"FAILED"}, \text{"ABORTED"}\}$ $\implies$ raise `binding_not_completed`.
  * If $P.\text{projection\_digest} \neq b.\text{projection\_digest}$ $\implies$ raise `projection_digest_mismatch`.
  * If $P.\text{request\_envelope\_digest} \neq b.\text{request\_envelope\_digest}$ $\implies$ raise `request_envelope_mismatch`.

---

## 5. System Integration & Admission Verification Workflows

### 5.1 End-to-End Execution Sequence

```text
  [API Server]            [PostgreSQL DB]           [LLM Provider]
       |                         |                        |
 1. Compile THSS Snapshot        |                        |
       |                         |                        |
 2. Build Envelope (v1)          |                        |
       |                         |                        |
 3. Compute H_proj & H_env       |                        |
       |                         |                        |
 4. create_binding(PENDING) ---->|                        |
       |                   Insert row (PENDING)           |
       |                         |                        |
 5. Dispatch LLM Request -------------------------------->|
       |                         |                  Execute Inference
       |<-------------------------------------------------+ 200 OK (Response)
       |                         |                        |
 6. finalize_binding() --------->|                        |
       |                   Update row -> COMPLETED        |
       |                         |                        |
 7. Emit Proposal (P)            |                        |
       | (citing binding_id)     |                        |
       |                         |                        |
 8. Submit Proposal Commit ----->| [Atomic Commit Kernel] |
                                 |  a. Lock Plan (1-7)    |
                                 |  b. Check Binding Status==COMPLETED
                                 |  c. Check H_proj & H_env equality
                                 |  d. Revalidate state & governance
                                 |  e. Write Domain Mutation & CAS advance
                                 |  COMMIT TRANSACTION
```

### 5.2 Lineage Preservation & Non-Downgrade Rules

1. **Model Proposal Ancestry (I11 / ARCH-005):**
   Any proposal originated by a model (`origin = "model"`) MUST have `context_binding_mode = "snapshot_bound"` and a non-null `inference_binding_id`.
2. **Human Adaptation & Lineage Continuity (I13):**
   When a clinician or user edits a model proposal in the UI (`origin = "human_review"`), the child proposal inherits `root_proposal_id` and `inference_binding_id` from the model proposal. Human adaptation is **forbidden** from stripping the inference binding or switching the proposal to `base_version_only`.
3. **Anti-Laundering Check:**
   `commitment_gateway.py` validates that:
   ```python
   if proposal.origin == "human_review" and root_proposal.origin == "model":
       assert proposal.inference_context_binding_id == root_proposal.inference_context_binding_id
       assert proposal.context_binding_mode == "snapshot_bound"
   ```

---

## 6. Verification & Test Safety Net

The specification and FSM rules described in this document are fully operationalized in `services/api/src/clara_api/glhs/gateway.py` and validated by the test suite in `services/api/tests/test_glhs_inference_consumption.py`.

### Verified Test Scenarios:
1. `test_build_canonical_inference_envelope`: Verifies canonical JCS envelope construction and hash determinism.
2. `test_normal_predispatch_to_postresponse_lifecycle`: Verifies `PENDING` $\rightarrow$ `COMPLETED` lifecycle, timestamp recording, and successful proposal commit.
3. `test_pending_binding_rejected_at_admission`: Verifies that proposals citing `PENDING` bindings are rejected fail-closed with `binding_not_completed`.
4. `test_failed_binding_rejected_at_admission`: Verifies that proposals citing `FAILED` bindings are rejected fail-closed with `binding_not_completed`.
5. `test_projection_digest_tampering_rejected`: Verifies that modifying $H_{\text{proj}}$ triggers immediate rejection with `projection_digest_mismatch`.
6. `test_request_envelope_tampering_rejected`: Verifies that modifying $H_{\text{env}}$ triggers immediate rejection with `request_envelope_mismatch`.
7. `test_snapshot_substitution_rejected`: Verifies that swapping snapshot IDs triggers rejection with `snapshot_identity_mismatch`.
