# Domain portability protocol

Clinician-adjudicated portability remains **NOT RUN**. A separate MIMIC-IV Demo
on FHIR run now reports source-timestamp-derived operational results for
medication, diagnosis/problem, and lab state. It is not clinical ground truth
and must not be pooled into a clinical headline result.

`policies.json` defines three intentionally different policies: medication,
allergy/adverse reaction, diagnosis/problem, and lab state. A curator must freeze its
SHA-256 in the program freeze manifest before comparative execution.

Use `python3 -m evaluation.domain_portability.validate_policy --policy
evaluation/domain_portability/policies.json` to verify the draft schema; add
`--final` only after a curator freezes it.

Source-derived execution:

```bash
python3 -m evaluation.domain_portability.run_source_derived \
  --records artifacts/evidence-program/<run-id>/fhir-source-derived/records.jsonl \
  --output artifacts/evidence-program/<run-id>/domain-source-derived
```
