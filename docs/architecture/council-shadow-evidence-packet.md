# Council shadow evidence packet

`COUNCIL_EVIDENCE_PACKET_SHADOW_ENABLED=false` is the default. When it and
`COUNCIL_LLM_SHADOW_ENABLED=true` are explicitly enabled, the registry-bound
`COUNCIL_SHADOW` task may receive a bounded *availability* packet alongside its
immutable case facts.

This is a shadow-only observation path. It does not change the deterministic
Council assessment, emergency path, CareGuard/DrugBank floor, recommendation,
case state, access, consent or audit decision. Disable the flag and restart ML
to remove the packet immediately; stored Council outputs stay untouched.

## Boundary and allowlist

The only accepted input is a server-created retrieval snapshot:

```json
{
  "tool": "retrieval_snapshot",
  "retrieval_snapshot_id": "snapshot-20260731-01",
  "evidence": [
    {"evidence_id": "PMID:123456", "category": "clinical_guideline"}
  ]
}
```

The validator rejects unknown tools, invalid IDs, duplicate-only lists and all
extra fields. In particular it rejects text snippets, URLs, titles, search
queries, scores, prompts, tool arguments and raw source payloads. The only
categories are `clinical_guideline`, `systematic_review`, `randomized_trial`,
`observational_study`, `regulatory_label`, and `public_health_guidance`.

The specialist prompt receives only the snapshot ID plus each opaque evidence
ID/category. It is explicitly forbidden to treat those availability labels as
clinical support. A specialist finding still requires one or more immutable
Council case-fact IDs, and the deterministic contract verifier drops any
unsupported finding. The output exposes only a bounded audit projection
(`status`, snapshot ID, category set and count), never retrieval text or
chain-of-thought.

The packet is intentionally not exposed through the public Council request
schema. It is for a server-side retrieval handoff after its own source,
snapshot and FIDES/release checks exist. Until that handoff is provisioned, the
feature does not claim clinical retrieval grounding and remains disabled.

## Governance

The task contract is `COUNCIL_SHADOW`, prompt
`council-shadow-assessment.v3`, output
`case_packet_bound_specialist_opinion_v4_json`; it requires the deterministic
`safety_policy` and `council_evidence_packet_validator` tools. The model is
chosen only via the DeepSeek registry. No request selects a provider, model,
endpoint, tool, or prompt version.

The packet cannot lower triage, confirm a diagnosis, prescribe/change a dose,
write a LifeMap/case fact, make an RBAC or consent choice, or serve as its own
verifier. Human clinical review remains mandatory.
