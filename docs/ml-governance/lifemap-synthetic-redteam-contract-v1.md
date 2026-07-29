# LifeMap synthetic red-team contract v1

Status: generation and review infrastructure only; no promotion authority.

## Purpose

The LifeMap red-team generator creates adversarial test candidates from bounded
synthetic scenario seeds. An approved LLM provider may implement the
provider-neutral callback, but the callback receives no production record,
profile identifier, real personal data, or held-out case.

Generated output is schema-bound to a prompt, expected safety behaviors, and a
small risk taxonomy. The boundary rejects malformed labels, obvious email or
phone data, oversized content, and unknown dimensions. Unicode-normalized
prompt fingerprints remove duplicates before review.

## Human review and versioning

Every candidate starts `pending`. A candidate may be accepted or rejected once
by an opaque reviewer reference; pending candidates cannot enter a frozen
suite. Freezing retains accepted cases only, orders them deterministically, and
hashes a manifest containing prompt digests, generator/template lineage,
labels, and review provenance.

The implementation does not automate the human review itself. A review record
means a real authorized reviewer made the decision through a controlled
workflow; tests using fake reviewer references demonstrate the contract only.

## Separation invariants

Every generated candidate and frozen suite is permanently marked:

- `synthetic=true`;
- `held_out=false`;
- `outcome_estimate_eligible=false`; and
- `eligible_for_promotion=false`.

Synthetic red-team results may reveal failure modes. They cannot estimate
real-world outcomes, replace a held-out evaluation set, authorize a model
transition, or satisfy clinical/human-factors approval.
