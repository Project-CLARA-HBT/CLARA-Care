# Risk-aware task-bounded health state

`services/api/src/clara_api/glhs/risk.py` is the code-owned policy source for
THSS sufficiency. The policy is a governance boundary, not a claim of clinical
safety or a substitute for clinical judgment.

| Domain / governed class | Authority | Lifecycle | Conflict policy | Freshness | Escalation |
| --- | --- | --- | --- | --- | --- |
| Medication | Reconciled course or reviewed source | active only | Open dose or identity conflict blocks a critical task | 90 days | Medication reconciliation |
| Allergy/adverse reaction | Patient report or reviewed clinical source | active; entered-in-error excluded | Open agent or reaction conflict blocks a critical task | 365 days | Allergy verification |
| Diagnosis/problem | Problem list or reviewed clinical source | active only | Open status or diagnosis conflict blocks a critical task | 180 days | Problem-list review |
| Lab/chronic state | Identified laboratory or chronic-state source | active only | Open value or unit conflict blocks a critical task | 30 days | Repeat measurement or clinician review |

For `risk_aware`, the compiler emits the relevant conflict IDs, stale assertion
IDs, assertions with inadequate evidence linkage, and the present/missing
task-critical classes. It returns `ABSTAIN_ESCALATE` if any critical issue is
present. Default and strict snapshots expose the same assessment but do not
silently alter their existing caller behavior.

Current critical-class bindings are intentionally narrow:

- `drugbank_ddi`: medication;
- `careguard`: medication and allergy/adverse reaction;
- `chronic_state_review`: diagnosis/problem and lab/chronic state.

Any new task must add its critical classes and be covered by an executable
gateway test before it can use `risk_aware` in a reported evaluation.
