# Council shadow evidence packet

`COUNCIL_EVIDENCE_PACKET_SHADOW_ENABLED=false` is the default. The API and ML
services must both receive this setting. When it and
`COUNCIL_LLM_SHADOW_ENABLED=true` are explicitly enabled, a doctor can attach
one of their completed, provenance-compatible Research snapshots to a Council
case; the registry-bound `COUNCIL_SHADOW` task may then receive its bounded
*availability* packet alongside immutable case facts.

This is a shadow-only observation path. It does not change the deterministic
Council assessment, emergency path, CareGuard/DrugBank floor, recommendation,
case state, access, consent or audit decision. Disable the flag and restart
both API and ML to hide the selector, reject attachment writes, omit the
internal packet and restore the legacy request path; stored outputs and
attachments stay untouched.

## API attachment boundary

The feature is doctor-RBAC and owner scoped. With the API gate enabled, a
doctor may call these case-scoped endpoints only for their own case and their
own completed Research job:

- `GET /council/cases/{case_id}/evidence-snapshots` lists eligible opaque
  snapshot metadata (completion time, category set and evidence count).
- `POST /council/cases/{case_id}/evidence-snapshots/{job_id}/attach` appends a
  server-built attachment.
- `GET /council/cases/{case_id}/evidence-attachments` lists safe attachment
  projections for review.

The browser only names a selected job in the path; it cannot send a packet or
Research content. The API derives an attachment from the stored snapshot's
release provenance and writes `council_evidence_attachments` through additive
Alembic revision `20260731_0046`. Attachments are append-only: rerunning an
assessment reads and revalidates the newest valid attachment without changing
the case's persisted clinical request/facts. A disabled API gate returns 404
for all three endpoints and performs no attachment write.

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
schema. It is a server-side retrieval handoff after its source, snapshot and
release checks exist. Research query text, report text, source text, titles,
URLs and scores never leave the Research record for this path. Until a
compatible snapshot exists, the UI has no eligible choice; it does not claim
clinical retrieval grounding.

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

## Operations and rollback

Set `COUNCIL_EVIDENCE_PACKET_SHADOW_ENABLED=false` in both API and ML runtime
environments and restart both services for the immediate safe rollback. This
leaves the append-only audit rows intact but removes the selector, prevents
new writes and excludes the packet from future runs. Database rollback is
available only for a deployment that has first disabled the flag and confirmed
there are no required retained attachments: run `alembic downgrade 20260729_0045`
from `services/api` to drop the additive table. Do not use a schema downgrade
as routine operational rollback when audit retention is required.
