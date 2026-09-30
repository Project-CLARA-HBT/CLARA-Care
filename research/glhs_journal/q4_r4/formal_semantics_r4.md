# Formal Specification: GLHS R4 Formal Semantics, Three-Digest Model & Attestation Hierarchy

**Program:** GLHS R4 — Governed Read-to-Write Continuity (GRWC)  
**Module:** `research/glhs_journal/q4_r4/formal_semantics_r4.md`  
**Author / Curator:** Agent B — Systems & Formal Architecture  
**Status:** Frozen Phase 0 Systems Specification  
**Date:** Wed Sep 30 2026  

---

## 1. Executive Summary & Problem Formulation

Governed Read-to-Write Continuity (GRWC), established in GLHS R3, addressed the fundamental concurrency and governance vulnerability in AI-assisted clinical workflows: the temporal and structural gap between reading patient state at inference time ($t_{\text{snap}}$) and committing persistent clinical mutations to the database ($t_{\text{commit}}$).

In R3, GRWC proved that a persistent write proposal $P$ derives from an immutable server-owned inference context binding $I$, which in turn anchors to a Temporal Health State Snapshot (THSS) $H$. However, R3 treated the inference binding primarily as an **application-level semantic abstraction** (`clara.inference-envelope.v1` serialized via RFC 8785 JSON Canonicalization Scheme).

In production distributed healthcare architectures, an application-level JSON dictionary does not execute directly on a neural network. Instead, the application passes the request through runtime adapters, HTTP client serialization engines, transport network stacks (TLS sockets), external network proxies, and provider-specific gateway deserializers before reaching provider inference hardware:

```text
+----------------------------------------------------------------------------------------------------+
|                                    GLHS R4 System Boundary Map                                     |
+----------------------------------------------------------------------------------------------------+
|  [Governed State]  --->  [THSS Snapshot H]                                                         |
|                                |                                                                   |
|                                v                                                                   |
|             [Canonical Semantic Envelope E]  <--- D1 (H_proj) & D2 (H_sem)                         |
|                                |                                                                   |
|                                v  (Transport Serialization / Provider SDK)                         |
|             [Serialized Transport Request T] <--- D3 (H_trans)                                     |
|                                |                                                                   |
|   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~ TLS Network Boundary ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~  |
|                                |                                                                   |
|                                v                                                                   |
|             [External Provider API Gateway]                                                        |
|                                |                                                                   |
|                                v                                                                   |
|             [Provider Inference Engine / TEE] ---> [Signed Receipt R] / [Execution Proof Pi]       |
+----------------------------------------------------------------------------------------------------+
```

This physical reality exposes critical vulnerabilities if not formalized:
1. **Serialization Drift & SDK Mutation:** The exact byte sequence transmitted across the network ($T$) may diverge from the canonical in-memory envelope ($E$) due to SDK default transformations, header injection, whitespace changes, or parameter re-encoding.
2. **Transport Deserialization Ambiguity:** An adversary or buggy proxy at the network egress can substitute prompt content while preserving application-level hashes if hashes only bind partial fields.
3. **Provider Non-Repudiation Void:** Without cryptographically verifiable provider receipts, the system cannot prove to external auditors whether the remote provider received the exact payload constructed by the application.
4. **The "Verifiable Inference" Fallacy:** Even if a cryptographic proof or Trusted Execution Environment (TEE) attests that an LLM executed over input bytes $T$, this **does NOT prove** that the non-deterministic attention mechanism inside the neural network actually attended to, understood, or respected the disclosed clinical evidence $H$.

GLHS R4 formalizes these boundaries through:
- A rigorous **Three-Digest Model** ($D1: H_{\text{proj}}$, $D2: H_{\text{sem}}$, $D3: H_{\text{trans}}$).
- A 4-tier **Attestation Hierarchy** ($L0 \to L3$).
- The unified **R4 Base Invariant** governing persistent clinical write admission.
- Explicit non-implication proofs preventing false assurance regarding neural semantic consumption.

---

## 2. Defined Mathematical Symbols & Domains

We establish the formal symbols and domains governing GLHS R4:

| Symbol | Formal Domain | Systems Representation | Definition & Operational Scope |
| :--- | :--- | :--- | :--- |
| $H$ | $\mathcal{H}_{\text{disc}}$ | `GlhsSnapshotManifest` | **Governed Disclosure Object:** The bounded Temporal Health State Snapshot (THSS) containing patient clinical records, evidence manifest $M(H)$, governance epoch coordinates $\langle v_s, c_s, p_s \rangle$, validity interval $[\tau_{\text{start}}, \tau_{\text{exp}}]$, purpose, and task. |
| $E$ | $\mathcal{E}$ | `clara.inference-envelope.v1` | **Canonical Semantic Envelope:** The 5-partition structured in-memory representation containing system prompt, health projection, conversation context, task instructions, and runtime parameters. |
| $T$ | $\mathcal{T} \subset \{0, 1\}^*$ | Raw HTTP Request Body | **Serialized Transport Request:** The exact octet sequence transmitted over the wire (TLS socket payload) to the inference provider endpoint. |
| $I$ | $\mathcal{I}$ | `GlhsInferenceContextBinding` | **Server-Owned Inference Binding:** The immutable database ledger row tracking the lifecycle of an inference pass, holding cryptographic digests, timestamps, status, and attestation level. |
| $R$ | $\mathcal{R} \cup \{\bot\}$ | Provider Response Receipt | **Provider Receipt:** An optional cryptographically signed or verifiable token emitted by the inference provider attesting to the receipt and execution of transport request $T$. |
| $P$ | $\mathcal{P}$ | `GlhsClinicalProposal` | **Persistent-Write Proposal:** Proposed clinical state mutation (target entity, operation kind, mutation payload, asserted evidence) submitted for commit admission. |
| $L(P)$ | $\text{Seq}(\mathcal{P})$ | Lineage Path | **Proposal Lineage:** The directed acyclic derivation path $P = P_0 \leftarrow P_1 \leftarrow \dots \leftarrow P_k = P_{\text{root}}$ linking proposal $P$ back to the root model proposal and its inference binding $I$. |
| $D(P)$ | $\mathcal{P}(\mathcal{E}_{\text{part}})$ | Dependency Vector | **Dependency Set:** The schema-derived minimum set of entity partitions, versions, and digests that must remain stable for $P$ to commit without write skew or causal invalidation. |
| $S(t)$ | $\mathcal{S}$ | Relational State | **Mutable State at time $t$:** The global database state of clinical entity partitions, state versions, and records at timestamp $t$. |
| $G(t)$ | $\mathcal{G}$ | Governance State | **Governance State at time $t$:** The system-wide policy epoch $p(t)$, subject consent epoch $c(t)$, and active actor role authorization at timestamp $t$. |
| $t_{\text{snap}}$ | $\mathbb{R}^+$ | Snapshot Timestamp | Instant when disclosure snapshot $H$ is compiled and authorized. |
| $t_{\text{dispatch}}$ | $\mathbb{R}^+$ | Transport Timestamp | Instant when transport payload $T$ is written to the network socket. |
| $t_c$ | $\mathbb{R}^+$ | Commit Timestamp | Instant when commit kernel executes Phase 3 revalidation under database locks. |
| $\mathcal{H}(\cdot)$ | $\{0,1\}^* \to \{0,1\}^{256}$ | `hashlib.sha256` | Cryptographic SHA-256 collision-resistant hash function. |
| $\text{JCS}(\cdot)$ | $\Omega \to \{0,1\}^*$ | RFC 8785 Canonical JSON | Deterministic serialization of JSON objects eliminating whitespace and ordering ambiguities. |

---

## 3. The Three-Digest Model ($D1, D2, D3$)

To guarantee end-to-end provenance across application, adapter, and network boundaries, GLHS R4 establishes a **Three-Digest Model**. Each digest operates at a strictly separated abstraction layer with an exact preimage specification.

```text
+----------------------------------------------------------------------------------------------------+
|                                    The Three-Digest Architecture                                   |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [THSS Snapshot H]                                                                                 |
|         |                                                                                          |
|         v                                                                                          |
|  [model_visible_health_projection] ---> JCS ---> SHA-256 ---> [D1: H_proj] (Projection Digest)     |
|         |                                                           |                              |
|         v                                                           |                              |
|  [clara.inference-envelope.v1]                                      |                              |
|  (sys_prompt, context, projection, task, runtime_params)             |                              |
|         |                                                           |                              |
|         +-----------------------------> JCS ---> SHA-256 ---> [D2: H_sem]  (Semantic Digest)        |
|         |                                                           |                              |
|         v                                                           |                              |
|  [Wire Serializer / Adapter]                                        |                              |
|         |                                                           |                              |
|         v                                                           |                              |
|  [raw_request_body_bytes (T)] --------> Octets -> SHA-256 --> [D3: H_trans](Transport Digest)     |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### 3.1 Digest D1: Disclosure Projection Digest ($H_{\text{proj}}$)

- **Domain:** Clinical Data Projection Layer.
- **Formal Definition:**
  $$H_{\text{proj}} = \mathcal{H}\left(\text{JCS}\left(\text{model\_visible\_health\_projection}\right)\right)$$
- **Preimage Specification:**
  The preimage of $D1$ is strictly the clinical data payload extracted from THSS snapshot $H$ and formatted for model prompt disclosure. It includes:
  - `profile_id`: Patient identifier.
  - `active_medications`: Array of canonical medication records active at $t_{\text{snap}}$.
  - `active_conditions`: Array of verified active diagnoses.
  - `observations`: Laboratory measurements, vital signs, and diagnostic findings.
  - `allergies`: Documented patient substance intolerances.
  - `disclosed_evidence_ids`: Lexicographically sorted array of evidence identifiers cited in the projection.
  - `disclosure_metadata`: Snapshot public ID, manifest digest, and state version coordinate.
- **Invariance & Systems Role:**
  $H_{\text{proj}}$ isolates clinical ground truth from conversational context or prompt engineering. If an engineer adjusts prompt wording, adds few-shot examples, or alters conversational memory, $H_{\text{proj}}$ remains **strictly invariant**. At commit time ($t_c$), the GRWC admission kernel verifies:
  $$I.\text{projection\_digest} = H.\text{projection\_digest} = H_{\text{proj}}$$

### 3.2 Digest D2: Semantic Envelope Digest ($H_{\text{sem}}$)

- **Domain:** Application Semantic Layer (`clara.inference-envelope.v1`).
- **Formal Definition:**
  $$H_{\text{sem}} = \mathcal{H}\left(\text{JCS}\left(E\right)\right) = \mathcal{H}\left(\text{JCS}\left(\langle \text{model\_route}, \text{model\_id}, \text{system\_prompt}, \text{context}, \text{projection}, \text{task}, \text{params} \rangle\right)\right)$$
- **Preimage Specification:**
  The preimage of $D2$ is the complete 5-partition canonical semantic envelope:
  1. `system_prompt`: Role definition, prompt template version, system prompt version, clinical safety instructions.
  2. `health_state_projection`: The exact clinical projection matching $D1$.
  3. `conversation_context`: Ordered array of prior dialogue turns ($\text{role} \in \{\text{user}, \text{assistant}, \text{system}\}$).
  4. `task_instructions`: Clinical task objective (e.g., `reconcile_medication_order`), clinical purpose, output schema constraints.
  5. `runtime_parameters`: Target model route, requested model ID, sampling temperature, max tokens, seed.
- **Invariance & Systems Role:**
  $H_{\text{sem}}$ binds the full cognitive context delivered to the model. Any modification to safety guardrails, conversational history, or task objectives alters $H_{\text{sem}}$. In R3, this was designated `request_envelope_digest`.

### 3.3 Digest D3: Transport Payload Digest ($H_{\text{trans}}$)

- **Domain:** Network Transport & Serialization Layer (Socket Egress).
- **Formal Definition:**
  $$H_{\text{trans}} = \mathcal{H}\left(T\right) = \text{SHA-256}\left(\text{exact\_serialized\_request\_body\_bytes}\right)$$
- **Preimage Specification:**
  The preimage of $D3$ is the **exact, raw byte sequence $T \in \{0, 1\}^*$** passed to the transport layer (e.g., `httpx.Request.content` or libcurl socket buffer) for transmission over TLS.
- **Why D3 Cannot Be Replaced by D2:**
  In real-world systems, provider SDKs (e.g. OpenAI Python client, DeepSeek API client, Anthropic SDK) convert the abstract semantic envelope $E$ into provider-specific wire schemas:
  - Transforming 5 partitions into `{"model": "...", "messages": [...], "temperature": ...}`.
  - Adding transport metadata (`stream: false`, `response_format: {"type": "json_object"}`).
  - Standard JSON serialization libraries introduce formatting discrepancies (key ordering, space after colon, UTF-8 escape encoding vs raw code points).
  Consequently:
  $$\text{JCS}(E) \neq T \implies H_{\text{sem}} \neq H_{\text{trans}}$$
  Binding $H_{\text{trans}}$ directly at the socket egress guarantees that what the application *claims* it sent is **byte-for-byte identical** to what crossed the network boundary.

### 3.4 Cross-Digest Relationship & Boundary Hierarchy

The Three-Digest Model creates a strict cryptographic containment and transformation chain:

$$\begin{array}{rcccl}
\text{Clinical Domain} & H & \xrightarrow{\text{Project}} & \text{model\_visible\_health\_projection} & \implies D1 = \mathcal{H}(\text{JCS}(\text{projection})) \\
& & & \downarrow \text{Embed into Partition 2} & \\
\text{Semantic Domain} & & & E = \langle E_{\text{sys}}, E_{\text{proj}}, E_{\text{ctx}}, E_{\text{task}}, E_{\text{params}} \rangle & \implies D2 = \mathcal{H}(\text{JCS}(E)) \\
& & & \downarrow \text{Transport Serialization / SDK Adapter} & \\
\text{Physical Wire} & & & T \in \{0, 1\}^* & \implies D3 = \mathcal{H}(T)
\end{array}$$

#### Deterministic Structural Invariants:
1. **Projection Immersion:** $\text{JCS}(\text{projection})$ is a strict sub-component of $E$. Any alteration of clinical facts in $H$ alters $D1$, $D2$, and $D3$.
2. **Context Isolation:** Altering conversation history $E_{\text{ctx}}$ alters $D2$ and $D3$, but leaves $D1$ untouched.
3. **Transport Conformance:** Transforming $E$ into wire format $T$ via adapter $\Phi$ must be deterministic:
   $$T = \Phi(E, \text{adapter\_config}) \implies H_{\text{trans}} = \mathcal{H}(\Phi(E, \text{adapter\_config}))$$

---

## 4. The 4 Attestation Levels ($L0 \to L3$)

GLHS R4 establishes a rigorous 4-tier attestation hierarchy governing the degree of proof anchoring an inference binding $I$ to physical execution. The levels form a strict total order of assurance:

$$L0 \prec L1 \prec L2 \prec L3$$

```text
+----------------------------------------------------------------------------------------------------+
|                                    GLHS R4 Attestation Hierarchy                                   |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [L0: APPLICATION_ENVELOPE_ONLY]                                                                   |
|   - Proof: D1 (H_proj) and D2 (H_sem) generated in-memory.                                         |
|   - Boundary: Application memory only. Wire bytes uncaptured.                                      |
|                                                                                                    |
|                                    | (Capture raw socket bytes)                                    |
|                                    v                                                               |
|                                                                                                    |
|  [L1: TRANSPORT_DISPATCH_ATTESTED]                                                                 |
|   - Proof: D3 (H_trans) computed over exact socket egress bytes T; egress timestamp logged.        |
|   - Boundary: Server network boundary. Provider receipt unverified.                                |
|                                                                                                    |
|                                    | (Receive signed provider receipt)                             |
|                                    v                                                               |
|                                                                                                    |
|  [L2: PROVIDER_RECEIPT_VERIFIED]                                                                   |
|   - Proof: Upstream receipt R verified; R.request_digest == H_trans; provider signature valid.     |
|   - Boundary: Remote provider gateway boundary. Internal model execution unproven.                 |
|                                                                                                    |
|                                    | (Hardware TEE / Verifiable Inference ZKML)                    |
|                                    v                                                               |
|                                                                                                    |
|  [L3: PROVIDER_EXECUTION_ATTESTED]                                                                 |
|   - Proof: Cryptographic proof Pi_exec (TEE quote / ZKML) proving weights W evaluated over T.      |
|   - Boundary: Silicon execution core. Semantic adherence still unproven (Theorem T4).              |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### 4.1 Level L0: `APPLICATION_ENVELOPE_ONLY`

- **Formal Definition:**
  $$\text{AttestationLevel}(I) = L0 \iff \text{ServerConstructed}(E) \land I.\text{envelope\_digest} = \mathcal{H}(\text{JCS}(E)) \land I.\text{projection\_digest} = H_{\text{proj}}$$
- **Operational Reality:**
  The server constructs canonical envelope $E$ and computes $D1$ and $D2$. However, the HTTP transport layer does not record the raw bytes $T$ written to the socket, or the provider client is an uninstrumented mock/adapter.
- **Assurance Boundary:**
  - *Guarantees:* The application server intended to send envelope $E$ at timestamp $t_{\text{snap}}$.
  - *Vulnerabilities:* Malicious or buggy client middleware (e.g. logging hooks, token injectors, proxy filters) could alter bytes on the wire without detection.
- **Permitted Use Cases:** Development environments, synthetic fixture smoke tests (`make eval-smoke`), non-persistent conversational queries.

### 4.2 Level L1: `TRANSPORT_DISPATCH_ATTESTED`

- **Formal Definition:**
  $$\begin{aligned}
  \text{AttestationLevel}(I) \ge L1 \iff & \text{AttestationLevel}(I) \ge L0 \\
  & \land \exists T \in \mathcal{T}: \text{SerializedFrom}(T, E) \\
  & \land I.\text{transport\_payload\_digest} = \mathcal{H}(T) \\
  & \land \text{DispatchAttempt}(I, T, t_{\text{dispatch}})
  \end{aligned}$$
- **Operational Reality:**
  The egress HTTP transport layer (e.g., custom HTTP transport adapter or ASGI interceptor) captures the exact raw byte stream $T$ immediately prior to socket write, computes $D3 = \mathcal{H}(T)$, records $t_{\text{dispatch}}$, and stores $D3$ into `GlhsInferenceContextBinding`.
- **Assurance Boundary:**
  - *Guarantees:* Egress tamper-evidence. Proves beyond dispute what exact byte sequence left the application boundary towards the provider endpoint.
  - *Vulnerabilities:* The upstream provider may crash, drop the request, or return an unverified response; the provider could substitute models internally without cryptographic accountability.
- **Permitted Use Cases:** Default production standard for commercial model APIs lacking hardware attestation (e.g., standard DeepSeek, OpenAI, Anthropic endpoints).

### 4.3 Level L2: `PROVIDER_RECEIPT_VERIFIED`

- **Formal Definition:**
  $$\begin{aligned}
  \text{AttestationLevel}(I) \ge L2 \iff & \text{AttestationLevel}(I) \ge L1 \\
  & \land \exists R \in \mathcal{R}: \text{VerifyProviderSignature}(R, \text{PK}_{\text{provider}}) \\
  & \land R.\text{request\_digest} = I.\text{transport\_payload\_digest} \\
  & \land R.\text{timestamp} \in [t_{\text{dispatch}}, t_{\text{dispatch}} + \Delta_{\text{timeout}}]
  \end{aligned}$$
- **Operational Reality:**
  The inference provider returns a cryptographically signed receipt $R$ (e.g., Ed25519 or ECDSA signature over $\langle H_{\text{trans}}, \text{timestamp}, \text{model\_id}, H_{\text{resp}} \rangle$) or a verifiable signed response header. The server verifies the provider's signature against a pinned public key.
- **Assurance Boundary:**
  - *Guarantees:* Non-repudiation of receipt. Proves that the authorized provider received and acknowledged the exact transport payload $T$ matching $H_{\text{trans}}$.
  - *Vulnerabilities:* Does not prove that the provider's GPU executed the weights without quantization, pruning, or internal fallback routing.
- **Permitted Use Cases:** Enterprise clinical cloud contracts, governed cross-hospital federated inference networks.

### 4.4 Level L3: `PROVIDER_EXECUTION_ATTESTED`

- **Formal Definition:**
  $$\begin{aligned}
  \text{AttestationLevel}(I) = L3 \iff & \text{AttestationLevel}(I) \ge L2 \\
  & \land \exists \Pi_{\text{exec}}: \text{VerifyExecutionProof}(\Pi_{\text{exec}}, \text{model\_id}, T, Y, \text{PK}_{\text{tee}})
  \end{aligned}$$
- **Operational Reality:**
  Inference executes inside a hardware Trusted Execution Environment (TEE) (e.g. Intel SGX/TDX, AMD SEV-SNP, NVIDIA Confidential Computing) or produces a cryptographic Zero-Knowledge Proof of Model Execution (ZKML). The proof $\Pi_{\text{exec}}$ verifies that model weights $\mathcal{W}$ were evaluated over input tokens $\text{Tokenize}(T)$ producing output tokens $\text{Tokenize}(Y)$.
- **Assurance Boundary:**
  - *Guarantees:* Silicon-level execution integrity. Proves exact execution of model architecture $\mathcal{M}_{\mathcal{W}}$ on wire tokens.
  - *Crucial Systems Limitation (Theorem T4):* **Does NOT prove semantic adherence.** Even with a valid TEE quote, the model may hallucinate, fail to attend to disclosed facts, or prioritize system prompt priors over patient data.

---

## 5. The R4 Base Invariant

### 5.1 Full Invariant Statement

Let $P$ be a persistent clinical mutation proposal submitted for database commit at timestamp $t_c$. The GLHS R4 commit kernel enforces that:

$$\begin{aligned}
\text{Admit}(P, t_c) \implies \exists H, E, I: \quad & \text{Persisted}(H) \\
& \land \text{ServerConstructed}(E) \\
& \land \text{Binds}(E, H) \\
& \land \text{DispatchAttested}(I, E) \\
& \land \text{DescendsFrom}(P, I) \\
& \land \text{ExactDisclosure}(P, I, H) \\
& \land \text{EvidenceCovered}(P, H) \\
& \land \text{DependencyComplete}(P, D(P)) \\
& \land \text{StateCurrent}(P, S(t_c)) \\
& \land \text{GovernanceCurrent}(P, G(t_c))
\end{aligned}$$

### 5.2 Predicate Definitions & Operational Semantics

Each predicate in the base invariant is grounded in concrete systems logic:

1. **$\text{Persisted}(H)$:**
   $$\text{Persisted}(H) \iff \text{SELECT 1 FROM glhs\_snapshot\_manifests WHERE public\_id} = H.\text{id} \land \text{manifest\_digest} = H.\text{manifest\_digest}$$
   The disclosure snapshot $H$ was compiled by the server, authorized under active governance at $t_{\text{snap}}$, and stored in the append-only snapshot ledger.

2. **$\text{ServerConstructed}(E)$:**
   $$\text{ServerConstructed}(E) \iff E.\text{schema} = \text{"clara.inference-envelope.v1"} \land \text{ValidEnvelopeSchema}(E)$$
   The semantic envelope $E$ was assembled strictly by authorized server-side pipeline code, never accepted directly from an untrusted client or client-supplied HTTP payload.

3. **$\text{Binds}(E, H)$:**
   $$\text{Binds}(E, H) \iff E.E_{\text{proj}}.\text{disclosure\_metadata}.\text{snapshot\_id} = H.\text{id} \land \mathcal{H}(\text{JCS}(E.E_{\text{proj}}.\text{model\_visible\_projection})) = H.\text{projection\_digest}$$
   The semantic envelope embeds the exact health projection generated from $H$ without alteration.

4. **$\text{DispatchAttested}(I, E)$:**
   $$\begin{aligned}
   \text{DispatchAttested}(I, E) \iff & I.\text{status} = \text{"COMPLETED"} \\
   & \land I.\text{request\_envelope\_digest} = \mathcal{H}(\text{JCS}(E)) \\
   & \land \exists T \in \mathcal{T}: \text{SerializedFrom}(T, E) \land I.\text{transport\_payload\_digest} = \mathcal{H}(T) \land \text{DispatchAttempt}(I, T)
   \end{aligned}$$
   The server captured the wire serialization $T$, computed $D3 = \mathcal{H}(T)$, logged the socket egress attempt, and transitioned $I$ to `COMPLETED` upon receiving a valid response.

5. **$\text{DescendsFrom}(P, I)$:**
   $$\text{DescendsFrom}(P, I) \iff \text{RootProposal}(L(P)).\text{inference\_binding\_id} = I.\text{id}$$
   Proposal $P$ traces its lineage through the acyclic chain $L(P)$ of human clinician edits or agent refinements back to the root proposal generated by inference binding $I$.

6. **$\text{ExactDisclosure}(P, I, H)$:**
   $$\begin{aligned}
   \text{ExactDisclosure}(P, I, H) \iff & I.\text{source\_snapshot\_id} = H.\text{id} \\
   & \land I.\text{source\_snapshot\_digest} = H.\text{snapshot\_digest} \\
   & \land I.\text{projection\_digest} = H.\text{projection\_digest} \\
   & \land P.\text{source\_snapshot\_id} = H.\text{id}
   \end{aligned}$$
   Strict identity matching across the entire chain: the proposal cites the exact snapshot that the binding attested for dispatch, with zero digest mismatch.

7. **$\text{EvidenceCovered}(P, H)$:**
   $$\text{EvidenceCovered}(P, H) \iff \forall e \in P.\text{asserted\_evidence\_ids} : e \in H.\text{disclosed\_evidence\_ids}$$
   Every clinical evidence identifier asserted by proposal $P$ to justify its clinical recommendation must be an element of the evidence set disclosed in snapshot $H$. Un-disclosed evidence (even if globally present in the database) is rejected (Invariant I14).

8. **$\text{DependencyComplete}(P, D(P))$:**
   $$\text{DependencyComplete}(P, D(P)) \iff \text{MinDependencies}(P.\text{operation\_kind}, P.\text{target}) \subseteq D(P)$$
   The proposal's dependency vector covers all entity partitions and causal dependencies required by the canonical dependency contract specification for that clinical operation.

9. **$\text{StateCurrent}(P, S(t_c))$:**
   $$\text{StateCurrent}(P, S(t_c)) \iff \forall \langle \text{part\_id}, v_{\text{obs}}, \delta_{\text{obs}} \rangle \in D(P) : S(t_c)[\text{part\_id}].\text{version} = v_{\text{obs}} \land S(t_c)[\text{part\_id}].\text{digest} = \delta_{\text{obs}}$$
   All entity partitions observed during snapshot construction remain at the exact same version and digest at the instant of commit under PostgreSQL row/advisory locks.

10. **$\text{GovernanceCurrent}(P, G(t_c))$:**
    $$\text{GovernanceCurrent}(P, G(t_c)) \iff G(t_c).\text{policy\_epoch} = H.\text{policy\_epoch} \land G(t_c).\text{consent\_epoch} = H.\text{consent\_epoch} \land \text{Authorized}(G(t_c).\text{actor})$$
    Patient consent directives and system disclosure policies have not drifted or been revoked between $t_{\text{snap}}$ and $t_c$.

11. **$\text{ProviderAttested}(I)$ (Conditional for $L2/L3$):**
    $$\text{ProviderAttested}(I) \implies \exists R : \text{Verify}(R) \land R.\text{request\_digest} = I.\text{transport\_payload\_digest}$$
    When the system or policy mandates attestation level $\ge L2$, commit admission requires a cryptographically verified provider receipt matching $D3$.

---

## 6. Crucial Non-Implication & Systems Limitations

A core architectural tenet of GLHS R4 is **epistemic humility regarding AI reasoning**. We explicitly formalize what the systems layer **cannot** guarantee:

$$\begin{aligned}
\text{DispatchAttested}(I, E) & \not\implies \text{SemanticUseByModel}(H) \\
\text{ProviderAttested}(I) & \not\implies \text{SemanticUseByModel}(H) \\
\text{AttestationLevel}(I) = L3 & \not\implies \text{SemanticUseByModel}(H)
\end{aligned}$$

### Systems Rationale:
1. **Network Proof $\neq$ Cognitive Proof:** Proving that 4,096 bytes representing patient lab results crossed a network card and entered an Nvidia H100 GPU proves only **physical transport and exposure**.
2. **Attention Distribution Arbitrariness:** Transformer self-attention can assign near-zero weights to the token positions containing $H$. The model may hallucinate clinical recommendations derived entirely from pre-trained parametric weights or conversational context.
3. **Independent Clinical Guardrails:** Therefore, attestation levels $L0-L3$ serve solely to prove **carrier sufficiency and provenance non-repudiation**. Clinical safety invariants (such as FIDES critical dosage verification, contraindication blocking, and human clinician review) remain independent, non-redundant, and non-bypassable safety gates.

---

## 7. Commit Kernel Integration & Transition Engine

The R4 invariants are enforced directly within **Phase 3 (Revalidation under Locks)** of the 6-Phase Atomic Commit Kernel (`execute_atomic_glhs_commit` in `commit_kernel.py`):

```text
+----------------------------------------------------------------------------------------------------+
|                             Commit Kernel Phase 3: R4 Admission Engine                             |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  1. Verify Base State & Lock Ownership (Class 1-7 locks held)                                      |
|  2. Revalidate Policy & Consent Epochs (G(t_c) == G(t_snap))                                       |
|  3. Revalidate Entity Partition Versions (S(t_c) == S(t_snap))                                     |
|  4. Lineage Traversal: P -> P_root -> I (Depth <= 4, Cycle-Free)                                   |
|  5. Check Attestation Level Requirement:                                                           |
|     - If policy requires L1: verify I.transport_payload_digest is NOT NULL                         |
|     - If policy requires L2: verify I.provider_receipt_verified IS TRUE                            |
|     - If policy requires L3: verify I.provider_execution_attested IS TRUE                          |
|  6. Three-Digest Matching:                                                                         |
|     - Assert I.projection_digest == H.projection_digest (D1)                                       |
|     - Assert I.request_envelope_digest == H_sem (D2)                                               |
|     - Assert I.transport_payload_digest == H_trans (D3)                                            |
|  7. Evidence Scope Closure: P.asserted_evidence_ids <= H.disclosed_evidence_ids                    |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### 7.1 Fail-Closed Error Taxonomy
If any predicate of the R4 Base Invariant fails during Phase 3, the transaction immediately rolls back and raises an invariant exception:

| Predicate Failure | Invariant Error Code | Fail-Closed System Action |
| :--- | :--- | :--- |
| Snapshot missing or invalid | `snapshot_manifest_invalid` | Abort transaction; rollback locks |
| Projection digest mismatch ($D1$) | `projection_digest_mismatch` | Abort transaction; log tampering alert |
| Semantic envelope mismatch ($D2$) | `semantic_envelope_digest_mismatch` | Abort transaction; log prompt drift |
| Transport digest mismatch ($D3$) | `transport_payload_digest_mismatch` | Abort transaction; log transport corruption |
| Attestation level insufficient | `attestation_level_unmet` | Abort transaction; reject un-attested provider |
| Provider receipt unverified | `provider_receipt_verification_failed`| Abort transaction; reject unacknowledged dispatch |
| Lineage cycle or depth $> 4$ | `commitment_lineage_depth_exceeded` | Abort transaction; reject corrupt proposal |
| Weak route downgrade attempt | `commitment_lineage_base_only_forbidden`| Abort transaction; prevent validation bypass |
| Undisclosed evidence cited | `proposal_evidence_not_disclosed` | Abort transaction; prevent evidence hallucination |
| Entity partition version drift | `stale_entity_partition` | Abort transaction; OCC retry or reject |
| Consent / Policy epoch drift | `stale_consent_version` | Abort transaction; dynamic governance block |

---

## 8. Summary of R4 Theoretical Guarantees

GLHS R4 establishes the following definitive system properties:

1. **Carrier Sufficiency:** The Three-Digest cascade guarantees that no clinical fact disclosed in $H$ can be altered, truncated, or forged on the wire without triggering an immediate fail-closed abort at commit time.
2. **Current-State Indistinguishability Elimination:** Cryptographic attestation at inference time is formally proven insufficient without transactional OCC revalidation at commit time under database locks (Theorem T1).
3. **Audit Non-Repudiation:** With Level $L1$ and $L2$ attestations, every committed proposal is cryptographically tied to the exact socket-level byte sequence dispatched and the provider receipt acknowledged.
4. **Architectural Epistemic Honesty:** The system formally recognizes that transport proofs do not equal semantic proofs, maintaining mandatory post-generation clinical guardrails and clinician review.
