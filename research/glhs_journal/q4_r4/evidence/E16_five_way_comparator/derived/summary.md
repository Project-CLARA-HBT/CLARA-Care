# E16 Five-Way Prior-Art Comparator Architecture Study Summary

- **Total Executions:** 2,500 (500 unique schedules × 5 comparator arms)
- **Comparator Arms Evaluated:**
  1. **C0 (CURRENT_STATE_ONLY):** False Admission Rate = 75.00%, Forensic Score = 0/100
  2. **C1 (OCC_READSET):** False Admission Rate = 75.00%, Forensic Score = 20/100
  3. **C2 (PROVENANCE_ONLY):** False Admission Rate = 75.00%, Forensic Score = 60/100
  4. **C3 (SIGNED_EXACT_DISCLOSURE_TOKEN):** False Admission Rate = 0.00%, Forensic Score = 75/100
  5. **C4 (FULL_GRWC):** False Admission Rate = 0.00%, Forensic Score = 100/100

### Novelty Outcome Rule Verdict
- **C3 vs C4 Decision Concordance:** 100.0% (0 disagreements across all 500 schedules).
- **Novelty Demarcation:** GLHS R4 surrenders decision-safety superiority over compact capability tokens (C3) and confines novelty to lifecycle state machine, server-attested two-digest receipts, tamper-evident proposal lineage, and bit-exact forensic reconstructability.
