# GovRed-Health adversarial boundary evaluation

Status: **NOT RUN**. This directory contains protocol tooling, not RIVF
results. Historic VPS transport observations are not compatible with this
protocol and must not be reported as attack outcomes.

The final frozen manifest must contain all 9 prespecified **primary
authorization-drift** schedules and evaluates only synthetic sentinel fixtures:
cross-subject retrieval/proposal write, revoked-consent cache/index reuse,
role/purpose mismatch, stale THSS replay, concurrent stale write,
authorization/consent TOCTOU, and policy-version change. Six retained prompt,
cache, expiry, and audit stress families are secondary-only and must be
reported separately, never pooled into the headline endpoint. Every compatible logical case is paired
across the research-only arms `UNBOUND`, `STATE_VERSION_ONLY`,
`SNAPSHOT_BOUND_STATE_ONLY`, and `GLHS_STRICT`. These arm configs require
`CLARA_GOVRED_ISOLATED_RESEARCH=1`; production code neither imports nor accepts
them.

`research_arms.evaluate_commit_admission` defines the four prespecified
commit-time ablation decisions using only sanitized adapter facts. It is guarded
by the same isolated-research flag and is tested as a mechanism contract. It
does not itself perform HTTP, persistence, caching, or audit observation, so it
is not executable RIVF evidence until an isolated boundary adapter calls it on
the real write path.

`isolated_boundary_adapter.py` is the minimal concrete adapter for the mounted
synthetic GovRed research API. It refuses production or unattested projects,
uses ordinary HTTP disclosure/proposal/commit and audit requests, and observes
PostgreSQL/Redis/audit only through `remote_store_observer.py`. It never issues
cache or database mutation commands. Unsupported schedules are `NOT_RUN`.

`execute.py` is the current frozen-manifest executor. It accepts only an
operator-owned `module:function` adapter, an explicit isolated-research
attestation, and an adapter attestation per arm. The adapter must return a
`BoundaryObservation` built from the real boundary; it may report `NOT_RUN`,
which is preserved rather than converted to a negative attack result.

An `EXECUTED` adapter result must also contain an arm-implementation attestation
whose binding/state/governance semantics exactly match the requested arm, plus
an isolated-only runtime guard, production-default guard, revision, and hashed
implementation artifact. A name/config declaration alone is rejected.

`remote_store_observer.py` independently fails closed unless
`CLARA_GOVRED_ISOLATED_RESEARCH=1` and both explicitly named Docker containers
begin with `clara-rivf-`. This protects shared stacks from accidental store
inspection; it is an operational guard, not outcome evidence.

## Development before final freeze

```bash
SHA256=$(sha256sum research/govred_rivf/statistics_plan.json | cut -d' ' -f1)
PYTHONPATH=services/api/src:. services/api/.venv/bin/python \
  -m evaluation.governance_adversarial.build_manifest \
  --seed 20260816 --statistics-plan-sha256 "$SHA256" \
  --output /secure/govred-development-manifest.json
```

Development data may guide protocol implementation. The final manifest must be
independently reviewed, use a distinct locked-test partition, be marked
`frozen`, and include the endpoint-manifest hash and isolated-environment
attestation before any headline execution.

## Final boundary execution contract

The operator-owned adapter must traverse and observe:

```text
test driver → HTTP API → auth/policy → cache/index → GST/GLHS → PostgreSQL → audit
```

For every retry-collapsed logical case and arm it must record only sanitized
observations: HTTP status/category, response SHA-256, sentinel occurrence,
commit occurrence, DB state before/after signatures, cache/index observation,
audit reconstruction result, latency, and availability state. It must not write
credentials, response bodies, patient-like free text, or raw audit payloads to
the artifact.

After operator classification, validate and analyze rather than manually
transcribe a table:

```bash
PYTHONPATH=services/api/src:. services/api/.venv/bin/python \
  -m evaluation.governance_adversarial.validate_results \
  --manifest /secure/govred-locked-manifest.json \
  --results artifacts/govred/<run-id>/raw_results.csv
PYTHONPATH=services/api/src:. services/api/.venv/bin/python \
  -m evaluation.governance_adversarial.analyze \
  --manifest /secure/govred-locked-manifest.json \
  --results artifacts/govred/<run-id>/raw_results.csv \
  --output artifacts/govred/<run-id>/analysis.json
```

The validator requires a row for every frozen case/compatible arm. `NOT RUN`
is explicit and excluded from denominators; it is never encoded as zero
failures. The analysis reports Wilson intervals and unadjusted exact McNemar
values; the final reporting pipeline must apply the prespecified Holm family
correction before claiming an arm contrast.

The executor additionally requires `--artifact-root` for every future run. An
`EXECUTED` row is accepted only when its observation artifact and arm
implementation artifact are relative files beneath that root and their declared
SHA-256 values match the local bytes. This is an integrity gate for future
isolated adapters, not evidence that any adapter or headline run exists.
