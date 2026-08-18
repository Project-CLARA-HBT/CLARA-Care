# W9-T01 Mutation-Adequacy Audit (sealed 45-mutant GovMut/SOICT study)

Status: **audit only**. It reads the sealed artifacts
(`mutation_site_candidates.json`, `results/final-analysis.json`) and never
modifies them. The frozen run `govmut-soict-2026-final-v2` (seal/`final_run.json`,
seal/`final-analysis`) is **immutable**; nothing here re-executes or re-scores it.

Headline frozen scores (from `results/final-analysis.json`):
`M0_regression` 0.356 (16/45), `M1_stateless_property` 0.089 (4/45),
`M2_state_machine` 0.133 (6/45), `M3_combined` 0.444 (20/45).
M3 subsumes M0 (M3 ⊇ M0 kill set, 0 `M0-only` discordant pairs) and
significantly beats M1/M2 (McNemar exact p = 3.05e-05 and 1.22e-04).

## 1. Layer taxonomy used

The layer is the enforcement surface the mutant exercises, not merely the file:

| Layer | Enforcement surface | Current mutants |
| --- | --- | --- |
| generic gateway | `services/api/src/clara_api/glhs/gateway.py` admission/commit/reconstruction | 27 |
| commitment gateway | `services/api/src/clara_api/glhs/commitment_gateway.py` propose/commit/reconstruct | 18 |
| API | route/service boundary (`api/v1/endpoints/*`) | 0 |
| governance-cache | admission-time revalidation of a persisted governance snapshot cache | 0 |
| persistence-reconstruction | transition-item write + replay/reconstruction boundary | 0 |

The sealed 45 cover exactly two layers (generic gateway 27, commitment gateway 18).
API, governance-cache, and persistence-reconstruction have **zero** mutants.

## 2. Per-mutant mapping (45 sealed mutants)

`M0/M1/M2/M3` = `detected_any_seed` from the sealed `final-analysis.json`
(1 = killed by that method, 0 = survived). `All-survive` marks mutants that no
method killed. Fault and invariant labels come from `mutation_manifest.json`
(P-numbers are the study-internal invariant identifiers used there).

| Mutant | Family | Layer | Enforcement site (anchor) | Fault | Invariants | M0 | M1 | M2 | M3 | All-survive |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M01-A | M01 | generic | `if revalidate_state and base_version != expected_state_version:` (apply_transition) | remove stale-base check | P2, P15 | 1 | 1 | 1 | 1 | no |
| M01-B | M01 | generic | `if action == "activate" and revalidate_state and assertion.base_state_version != base_version:` | remove stale-base check | P2, P15 | 1 | 0 | 0 | 1 | no |
| M01-C | M01 | commitment | `if base != expected_state_version or proposal.base_state_version != base:` (apply_commitment_transition) | remove stale-base check | P2, P15 | 0 | 0 | 0 | 0 | **yes** |
| M01-D | M01 | commitment | `if observed_base_state_version != base_state_version:` (propose_bound) | remove stale-base check | P2, P15 | 0 | 0 | 0 | 0 | **yes** |
| M02-A | M02 | generic | `if snapshot.policy_version != policy_version:` (validate_snapshot_manifest) | remove policy revalidation | P3 | 0 | 0 | 1 | 1 | no |
| M02-B | M02 | generic | `if revalidate_governance and assertion.policy_version != _effective_policy_version():` (apply_transition) | remove policy revalidation | P3 | 1 | 0 | 0 | 1 | no |
| M02-C | M02 | commitment | `if proposal.policy_version != COMMITMENT_POLICY_VERSION:` (validate_base) | remove policy revalidation | P3 | 0 | 0 | 0 | 0 | **yes** |
| M02-D | M02 | commitment | `if proposal.policy_version != COMMITMENT_POLICY_VERSION:` (validate_current) | remove policy revalidation | P3 | 1 | 0 | 0 | 1 | no |
| M03-A | M03 | generic | `if snapshot.consent_version != consent_version:` (validate_snapshot_manifest) | remove consent revalidation | P4 | 0 | 0 | 1 | 1 | no |
| M03-B | M03 | generic | `if revalidate_governance and assertion.consent_version != current_consent_version:` (apply_transition) | remove consent revalidation | P4 | 0 | 0 | 1 | 1 | no |
| M03-C | M03 | commitment | `if proposal.consent_version != consent_version:` (validate_base) | remove consent revalidation | P4 | 0 | 0 | 0 | 0 | **yes** |
| M03-D | M03 | commitment | `if proposal.consent_version != current_consent_version:` (validate_current) | remove consent revalidation | P4 | 0 | 0 | 0 | 0 | **yes** |
| M04-A | M04 | generic | `if assertion.profile_id != scope.profile.id:` (apply_transition) | remove subject equality | P5 | 1 | 0 | 0 | 1 | no |
| M04-B | M04 | generic | `if source is None or source.profile_id != profile_id:` (_validate_proposal_snapshot) | remove subject equality | P5 | 0 | 0 | 0 | 0 | **yes** |
| M04-C | M04 | commitment | `if proposal.target_profile_public_id != scope.profile.public_id:` (propose) | remove subject equality | P5 | 0 | 0 | 0 | 0 | **yes** |
| M04-D | M04 | commitment | `if commitment.profile_id != scope.profile.id:` (propose_bound) | remove subject equality | P5 | 0 | 0 | 0 | 0 | **yes** |
| M05-A | M05 | generic | `if actor_user_id is not None and snapshot.actor_user_id != actor_user_id:` | remove actor equality | P6 | 1 | 0 | 0 | 1 | no |
| M05-B | M05 | generic | `if actor_role is not None and snapshot.actor_role != actor_role:` | remove actor equality | P6 | 1 | 0 | 0 | 1 | no |
| M05-C | M05 | commitment | `if scope.actor_role not in policy.actor_roles:` (review) | remove actor equality | P6 | 0 | 0 | 0 | 0 | **yes** |
| M06-A | M06 | generic | `if snapshot.purpose != purpose:` (validate_snapshot_manifest) | remove purpose equality | P7 | 1 | 0 | 0 | 1 | no |
| M06-B | M06 | commitment | `if proposal.purpose != scope.purpose:` (propose) | remove purpose equality | P7 | 0 | 0 | 0 | 0 | **yes** |
| M06-C | M06 | generic | `if purpose != scope.purpose:` (compile_thss) | remove purpose equality | P7 | 0 | 0 | 0 | 0 | **yes** |
| M07-A | M07 | generic | `if require_unexpired and _as_utc(snapshot.expires_at) <= datetime.now(UTC):` | accept expired snapshot | P8 | 1 | 0 | 0 | 1 | no |
| M07-B | M07 | commitment | `if scope.valid_until is not None and _utc(scope.valid_until) <= datetime.now(UTC):` (propose) | accept expired snapshot | P8 | 1 | 0 | 0 | 1 | no |
| M07-C | M07 | generic | `if scope.valid_until is not None and _as_utc(scope.valid_until) <= datetime.now(UTC):` (compile_thss) | accept expired snapshot | P8 | 0 | 0 | 0 | 0 | **yes** |
| M07-D | M07 | commitment | `if scope.valid_until is not None and _utc(scope.valid_until) <= datetime.now(UTC):` (propose_base) | accept expired snapshot | P8 | 1 | 0 | 0 | 1 | no |
| M08-A | M08 | generic | `if _digest(assertion.value_json) != assertion.value_fingerprint:` | skip digest check | P8 | 1 | 0 | 0 | 1 | no |
| M08-B | M08 | generic | `if reconstructed_digest != manifest.snapshot_digest:` (reconstruct_snapshot_artifact) | skip digest check | P8 | 0 | 0 | 0 | 0 | **yes** |
| M08-C | M08 | generic | `if manifest_fingerprint != manifest.manifest_digest:` (reconstruct_snapshot_artifact) | skip digest check | P8 | 0 | 0 | 0 | 0 | **yes** |
| M08-D | M08 | generic | `if snapshot.digest_algorithm != DIGEST_ALGORITHM:` (validate_snapshot_manifest) | skip digest check | P8 | 0 | 0 | 0 | 0 | **yes** |
| M09-A | M09 | generic | `if data.proposal_consumed_thss and data.source_snapshot_id is None:` | THSS-bound downgrade | P3, P7, P15 | 1 | 0 | 0 | 1 | no |
| M09-B | M09 | commitment | `if proposal.context_binding_mode != "snapshot_bound":` (validate_bound) | THSS-bound downgrade | P3, P7, P15 | 0 | 0 | 0 | 0 | **yes** |
| M09-C | M09 | generic | `if source_snapshot_id is None: if source_snapshot_digest is not None:` | THSS-bound downgrade | P3, P7, P15 | 1 | 1 | 1 | 1 | no |
| M09-D | M09 | generic | `if not snapshot_id or not manifest_digest:` (validate_snapshot_manifest) | THSS-bound downgrade | P3, P7, P15 | 0 | 0 | 0 | 0 | **yes** |
| M09-E | M09 | commitment | `if proposal.context_binding_mode != "base_version_only":` (validate_base) | THSS-bound downgrade | P3, P7, P15 | 0 | 0 | 0 | 0 | **yes** |
| M11-A | M11 | generic | `if not _assertion_evidence_ids(db, assertion_id=assertion.id):` | drop provenance edge | P11 | 0 | 1 | 0 | 1 | no |
| M11-B | M11 | generic | `if not evidence_rows:` (record_evidence) | drop provenance edge | P11 | 0 | 0 | 0 | 0 | **yes** |
| M11-C | M11 | commitment | `if not evidence or any(item.profile_id != scope.profile.id for item in evidence):` | drop provenance edge | P11 | 0 | 0 | 0 | 0 | **yes** |
| M11-D | M11 | commitment | `if not set(evidence_ids).issubset(set(proposal.observed_evidence_ids_json)):` | drop provenance edge | P11 | 0 | 0 | 0 | 0 | **yes** |
| M13-A | M13 | generic | `GlhsAssertion.lifecycle_status.in_(ACTIVE_LIFECYCLE_STATES),` | select superseded as current | P9 | 1 | 0 | 0 | 1 | no |
| M13-B | M13 | generic | `if row.valid_to is None or row.valid_to >= valid_at` (reconstruct_state) | select superseded as current | P9 | 0 | 0 | 0 | 0 | **yes** |
| M13-C | M13 | generic | `if row.valid_to is None or row.valid_to >= valid_at` (compile_thss) | select superseded as current | P9 | 0 | 0 | 0 | 0 | **yes** |
| M14-A | M14 | generic | `key_hash = _idempotency_digest(idempotency_key)` | idempotency ineffective | P1 | 1 | 1 | 1 | 1 | no |
| M14-B | M14 | commitment | `if existing.request_digest != request_digest:` (commit) | idempotency ineffective | P1 | 0 | 0 | 0 | 0 | **yes** |
| M14-C | M14 | commitment | `if existing.request_digest != request_digest:` (post-lock recheck) | idempotency ineffective | P1 | 0 | 0 | 0 | 0 | **yes** |

## 3. Coverage findings

### 3.1 Method-matrix under-coverage

- **25 of 45 mutants survive every method (M0, M1, M2, M3 all 0).** The combined
  method M3 kills 20/45; M1 and M2 alone kill only 4 and 6. The four-method
  matrix leaves more than half of the corpus undetected.
- **Commitment gateway is the biggest blind spot:** of its 18 mutants only
  M02-D, M07-B, M07-D are killed (each only by M0/M3). 15/18 commitment-gateway
  mutants survive all four methods, and M1/M2 kill **zero** commitment-gateway
  mutants.
- **Family-level (all methods kill none):** no sealed family is fully undetected
  because M3 kills ≥ 1 mutant per family. The families that are effectively
  under-covered, with all-serve rows, are:
  - **M04** (subject equality): 3/4 all-survive (M04-B/C/D) — M1, M2 kill nothing in the family.
  - **M08** (digest): 3/4 all-survive (M08-B/C/D) — M1, M2 kill nothing.
  - **M11** (provenance): 3/4 all-survive (M11-B/C/D) — M2 kills nothing.
  - **M13** (superseded selection): 2/3 all-survive (M13-B/C) — M1, M2 kill nothing.
  - **M14** (idempotency): 2/3 all-survive (M14-B/C).
  - **M03** (consent): 2/4 all-survive (M03-C/D); M0 kills nothing in the family.
- **Families with no M1 or no M2 detection at all:** M02, M04, M05, M06, M07,
  M08, M13 (M1 and M2 each kill zero in these); M11 (M2 zero). Only M01, M09,
  M14 are detected by both property methods, and only M11-A/M14-A by M1 alone.
- **Unanchored families → zero mutants:** M10 (state/audit transaction atomicity,
  P13), M12 (stale derived snapshot/cache reuse, P10/P12), M15 (retry without
  reauthorization, P15) have no executable mutant at all (see
  `unanchored_family_rationale.md`). These are the families the method matrix
  cannot even observe, not merely failures to kill.

### 3.2 Layer under-coverage

| Layer | Mutants | Killed (M3) | All-survive | Finding |
| --- | --- | --- | --- | --- |
| generic gateway | 27 | 17 (0.630) | 10 | best covered, still 10/27 all-survive |
| commitment gateway | 18 | 3 (0.167) | 15 | severe under-coverage |
| API | 0 | — | — | **no mutants** |
| governance-cache | 0 | — | — | **no mutants** (M12 unanchored) |
| persistence-reconstruction | 0 | — | — | **no mutants** (M10 unanchored) |

### 3.3 Why the method matrix under-kills (interpretation for W9-T02)

- M0 regression and M3 hit the *admission-time* guards (policy/consent/state/
  expiry/actor/purpose), which is where the four frozen test modules assert
  rejection. The guards killed are almost all single-predicate admission checks.
- M1/M2 property/state-machine methods drive the gateway through generated
  state, but they do not reconstruct decisions, do not exercise the
  post-commit audit linkage, and do not persist-then-replay transition items —
  which is why commitment-gateway and reconstruction/persistence faults survive
  every method. This is exactly the coverage hole the W9 follow-up corpus
  (`W9_FOLLOWUP_CORPUS_PROPOSAL.json`) targets.

## 4. Invariants P1-P15 coverage (mutant-level)

Based on the `mutation_manifest.json` invariant mapping, the sealed corpus
exercises: P1 (M14), P2/P15 (M01, M09), P3 (M02, M09), P4 (M03), P5 (M04),
P6 (M05), P7 (M06, M09), P8 (M07, M08), P9 (M13), P11 (M11).
**P10 (freshness of derived snapshot/cache) and P13 (state/audit transaction
atomicity) have no sealed mutant at all** (M12 and M10 unanchored); P15 is only
touched through M01/M09. The W9 proposal adds P10/P12-adjacent (governance-cache)
and P13-adjacent (persistence-reconstruction, audit linkage) mutants.

## 5. Sealed artifacts consulted (immutable)

- `mutation_site_candidates.json` (fields `id`, `family_seed`, `source_path`,
  `anchor`, `replacement`; unanchored seeds M10/M12/M15).
- `results/final-analysis.json` (`per_mutant_method`, `mutation_scores`,
  `stratification.family_seed/source_path/anchor`, `paired_method_comparisons`,
  `robustness_scores`).
- `final_freeze.json`, `seal/README.md` (freeze `govmut-soict-2026-final-v2`,
  source `ab877e04` / seal README source SHA `7c963153`).

No artifact in this audit is modified.
