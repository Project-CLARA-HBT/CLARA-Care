# W8 Survivor Analysis — 25 all-survive mutants, descriptive engineering diagnosis

Status: **descriptive diagnosis** (GMT-06). This classifies each of the 25 W8
all-survive mutants into the prespecified categories below. It is NOT a
retroactive equivalent-mutant exclusion: no W8 mutant is removed from any W8
denominator, no W8 score changes, and the sealed study
(`govmut-soict-2026-final-v2`, `seal/*`, `results/final-analysis.json`,
`final_run.json`, `final_freeze.json`) is immutable and untouched (GMT-01).

All kill/survive facts are read from `results/final-analysis.json`
(`per_mutant_method.detected_any_seed`) and cross-referenced against
`mutation_adequacy_audit.md`. The layer/family/invariant mapping follows
`mutation_adequacy_audit.md` section 1–2 and `mutation_manifest.json`.

## Method

Each of the 25 all-survive mutants is mapped to **exactly one** prespecified
category using a fixed evidence rule:

1. **Replay/reconstruction blind spot** — the fault lives on a read-side
   reconstruction/replay path (`reconstruct_snapshot_artifact`,
   `reconstruct_state`, commitment decision reconstruction) and the frozen
   method matrix never drives that path with the violating condition.
2. **Missing path/test target** — the enforcement site is in a function or
   binding flow the frozen method matrix does not exercise at all for the
   violating flow (e.g. the commitment review flow, the base-only binding
   cross-mode admission path).
3. **Missing oracle** — the enforcement site is reached by the frozen matrix
   (a sibling mutant at the same site/path is killed), but no frozen
   regression test constructs the violating condition, so removing the guard
   is unobservable.
4. **Possible weak mutant** — a dedicated frozen test exists for the
   condition, and/or an identical guard at a sibling site IS killed, so the
   removal is masked by a duplicated/deeper check on every path the matrix
   drives. This is a hypothesis about test-construction redundancy, not an
   equivalence claim.
5. **Generator reach** — the Hypothesis generators structurally cannot
   construct the violating condition.
6. **Budget exhaustion** — the condition is within generator reach but
   requires more examples/steps than the frozen budget.
7. **API layer absence** — the enforcement lives at the API/route boundary
   with no route-level method target.
8. **Other-with-rationale** — any mutant not fitting the above, with a stated
   reason.

Where a guard is "masked by a sibling", the sibling is named. Categories 1–4
carry the rationale; categories 5–7 are reported as zero in this corpus (the
method-matrix gap they describe is documented in `mutation_adequacy_audit.md`
sections 3.1–3.2 and `W9_FOLLOWUP_CORPUS_PROPOSAL.json` `remaining_gap`).

## Distribution summary

| Category | Count | Mutants |
| --- | --- | --- |
| missing oracle | 17 | M01-C, M01-D, M03-C, M03-D, M04-B, M04-C, M04-D, M06-B, M06-C, M08-D, M09-D, M11-B, M11-C, M11-D, M13-C, M14-B, M14-C |
| possible weak mutant | 2 | M02-C, M07-C |
| missing path/test target | 3 | M05-C, M09-B, M09-E |
| replay/reconstruction blind spot | 3 | M08-B, M08-C, M13-B |
| generator reach | 0 | — |
| budget exhaustion | 0 | — |
| API layer absence | 0 | — (gap documented; see note below) |
| other-with-rationale | 0 | — |
| **Total** | **25** | |

Note on **API layer absence = 0**: none of the 25 survivors is an API-layer
mutant — the sealed corpus contains zero API-layer mutants at all
(`mutation_adequacy_audit.md` layer table: API 0). The absence of this category
here is expected and is itself a coverage finding; the gap is tracked as
`remaining_gap` in `W9_FOLLOWUP_CORPUS_PROPOSAL.json`.

## Per-mutant classification

Kill facts (M0/M1/M2/M3 = `detected_any_seed` from the sealed analysis) are
0/0/0/0 for every mutant below unless stated otherwise. "Sibling killed" refers
to another mutant of the same fault family whose guard sits at a matching site
that the frozen matrix did detect.

### Missing oracle (17)

| Mutant | Family / layer | Site | Rationale |
| --- | --- | --- | --- |
| M01-C | M01 / commitment | stale-base guard in `apply_commitment_transition` | Siblings M01-A/M01-B at the generic `apply_transition` stale-base guard are killed by M0/M3, and the concurrent-commit path is exercised (`test_commitment_transition_shares_state_counter_and_reconstructs`), but no frozen test constructs a *mismatched base* on the commitment apply path, so the guard removal is unobservable. |
| M01-D | M01 / commitment | stale-base guard in `propose_bound` | The commitment bounded-proposal path is reached (siblings M02-D/M07-B/M07-D killed at other `propose*` guards), but no test constructs `observed_base_state_version != base_state_version`. |
| M03-C | M03 / commitment | consent-version guard in `validate_base` | Consent gating is tested at route level (`test_commitment_route_requires_current_medical_consent`, `test_revoked_medical_consent_blocks_commitment_and_can_be_reaccepted`), but no frozen test stamps a proposal with an outdated `consent_version` while current consent differs; the version-mismatch condition is never constructed. Generic siblings M03-A/M03-B are killed by M2/M3, showing the matrix can observe consent revalidation where it is driven. |
| M03-D | M03 / commitment | consent-version guard in `validate_current` | Same construction gap as M03-C at the current-consent revalidation site. |
| M04-B | M04 / generic | subject-equality guard in `_validate_proposal_snapshot` | `_validate_proposal_snapshot` is heavily exercised (siblings M07-A, M08-A killed there), and a foreign-profile snapshot is rejected at route level (`test_commitment_proposal_api_rejects_foreign_profile_snapshot`), but that rejection fires upstream during scope resolution; the `source.profile_id != profile_id` condition inside snapshot validation is never the decisive check on an exercised path. |
| M04-C | M04 / commitment | subject-equality guard in `propose` | Foreign-profile tests resolve the subject mismatch before this guard; the commitment `propose` subject condition is never constructed as the decisive check. |
| M04-D | M04 / commitment | subject-equality guard in `propose_bound` | Same construction gap at the bounded-proposal subject check. |
| M06-B | M06 / commitment | purpose-equality guard in `propose` | Purpose-change tests target the generic THSS path (`test_thss_bound_snapshot_rejects_purpose_change`, `test_thss_bound_transition_revalidates_current_actor_and_purpose`), which exercises a different function; the commitment `propose` purpose condition is never constructed. |
| M06-C | M06 / generic | purpose-equality guard in `compile_thss` | `compile_thss` is reached by pipeline/risk tests (`test_thss_pipeline_trace_...`, `test_risk_aware_thss_abstains_...`) but always with a matching scope; no test passes a mismatched purpose into the compiler. |
| M08-D | M08 / generic | digest-algorithm guard in `validate_snapshot_manifest` | The function is exercised (siblings M07-A, M03-A, M02-A killed there), but every frozen test uses the configured digest algorithm, so the `digest_algorithm != DIGEST_ALGORITHM` condition is never constructed. |
| M09-D | M09 / generic | THSS-downgrade guard in `validate_snapshot_manifest` | The snapshot-manifest path is exercised, and THSS-bound downgrade is tested at other sites (M09-A/M09-C killed); the missing `snapshot_id`/`manifest_digest` condition inside manifest validation is never constructed. |
| M11-B | M11 / generic | provenance guard in `record_evidence` | Provenance closure is partly tested (sibling M11-A killed by M1/M3 in `compile_thss`), but no frozen test calls `record_evidence` with zero rows where the empty-evidence guard is decisive. |
| M11-C | M11 / commitment | provenance guard on commitment evidence | Commitment evidence flows use disclosed, same-profile evidence; no frozen commitment test constructs foreign-profile or missing evidence at this site. |
| M11-D | M11 / commitment | evidence-subset guard on commitment proposal | Commitment tests exercise disclosed evidence (e.g. `test_commitment_proposal_api_never_admits_an_unbound_thss_input`) but never construct `evidence_ids` outside the proposal's `observed_evidence_ids`. |
| M13-C | M13 / generic | superseded-selection guard in `compile_thss` | `compile_thss` is reached but no frozen test constructs overlapping/superseded assertion rows with `valid_to >= valid_at` inside the compiler; the admission-time supersession sibling M13-A IS killed, isolating the gap to the compile path. |
| M14-B | M14 / commitment | idempotency request-digest guard in `commit` | Idempotency is exercised on the generic admission path (M14-A killed by all methods), but no frozen commitment test replays the same idempotency key with a *different* request digest on the commit path. |
| M14-C | M14 / commitment | post-lock idempotency recheck | Same construction gap as M14-B at the post-lock recheck site. |

### Missing path/test target (3)

| Mutant | Family / layer | Site | Rationale |
| --- | --- | --- | --- |
| M05-C | M05 / commitment | actor-role guard in commitment `review` | The commitment review flow is not driven by any frozen target in the method matrix; no test invokes `review` with a scope whose `actor_role` is outside `policy.actor_roles`. |
| M09-B | M09 / commitment | binding-mode guard in `validate_bound` | The mandatory-THSS binding tests (`test_glhs_mandatory_thss_binding.py`) cover the generic admission path (M09-A/M09-C killed); the commitment `validate_bound` path is never driven with a non-`snapshot_bound` mode. |
| M09-E | M09 / commitment | binding-mode guard in `validate_base` | Base-only proposals are exercised (`test_base_version_only_proposal_is_explicit_and_can_commit`) but always with an actually-base-only proposal; the *cross-mode admission attempt* (a snapshot-bound proposal driven through `validate_base`) is never constructed, so removing the `!= "base_version_only"` check is unobservable. |

### Possible weak mutant (2)

| Mutant | Family / layer | Site | Rationale |
| --- | --- | --- | --- |
| M02-C | M02 / commitment | policy-version guard in `validate_base` | A dedicated test exists (`test_base_version_only_proposal_rejects_a_stale_policy_coordinate`) and the identical guard at the sibling site `validate_current` (M02-D) IS killed by M0/M3. The stale-policy rejection the test asserts fires at a deeper/duplicated check, so removing the `validate_base` guard is masked on every path the matrix drives. Descriptive hypothesis about redundancy — not an equivalence-based exclusion. |
| M07-C | M07 / generic | expired-scope guard in `compile_thss` | Expired-scope rejection is asserted by `test_expired_scope_and_mismatched_proposal_fail_closed`, and siblings M07-B/M07-D (expired scope at `propose`/`propose_base`) ARE killed, meaning expiry fails closed before `compile_thss`. The compiler-level guard is masked by the earlier scope-expiry rejection on exercised paths. Descriptive hypothesis about redundancy — not an equivalence-based exclusion. |

### Replay/reconstruction blind spot (3)

| Mutant | Family / layer | Site | Rationale |
| --- | --- | --- | --- |
| M08-B | M08 / generic | digest guard in `reconstruct_snapshot_artifact` | Reconstruction linkage is asserted (`test_reconstruction_rejects_transition_not_linked_to_snapshot`) but the reconstruction *artifact* digest path is never driven with a tampered/diverged payload; the matrix observes admission-time digests (M08-A killed) but not the replay path. |
| M08-C | M08 / generic | manifest self-digest guard in `reconstruct_snapshot_artifact` | Same reconstruction blind spot at the manifest-digest site; no frozen test replays a manifest whose self-digest is inconsistent. |
| M13-B | M13 / generic | superseded-selection guard in `reconstruct_state` | Read-side state reconstruction is not driven with overlapping valid intervals; the admission-time supersession sibling M13-A IS killed, isolating the gap to the reconstruction path. |

## What this means for W9 (cross-reference)

- The dominant diagnosis is **missing oracle** (17/25): the method matrix reaches
  the functions but never constructs the violating condition. These are
  add-a-test gaps, not proof of equivalence.
- The **replay/reconstruction blind spot** (3) and **missing path/test target**
  (3) categories are the two design gaps the W9 follow-up corpus targets
  directly (`W9_FOLLOWUP_CORPUS_PROPOSAL.json` layers commitment-gateway
  reconstruction, governance-cache, persistence-reconstruction).
- The **possible weak mutant** category (2) is the only one that questions
  whether the mutation can be observed at all; it is recorded as a hypothesis
  and, per GMT-06, does not remove either mutant from any W8 denominator. W9
  human non-equivalence review (W9_PROTOCOL.md §7) will revisit each W9
  candidate on its own merits; W8 survivors are not re-adjudicated.

## Sealed artifacts consulted (immutable)

- `results/final-analysis.json` (byte-identical to
  `seal/govmut-soict-2026-final_analysis-v2`)
- `mutation_adequacy_audit.md` (family/layer/invariant mapping, coverage findings)
- `mutation_manifest.json`, `mutation_site_candidates.json`
- Test names quoted from `services/api/tests/test_commitloop_gateway.py`,
  `test_glhs_gateway.py`, `test_commitment_endpoints_integration.py`,
  `test_glhs_mandatory_thss_binding.py` at revision `0a6c5940`.

No W8 artifact is modified by this analysis.