"""PST venue2027 evaluation package.

Holds the deterministic synthetic dataset generator (:mod:`.generate_dataset`,
task PST-dataset, phase P02) for the PST 2027 study "ReceiptMin: Measuring
Forensic Reconstructability under Purpose-Bound Audit Minimization"
(``research/venue2027/VENUES/pst/RESEARCH_BLUEPRINT.md``), plus the
downstream independent-oracle, receipt-contract and forensic-query tasks
(PST-oracle, PST-X01_receipt_contract, PST-X02_forensic_queries). Synthetic
audit-receipt fixtures only; no real PHI/PII, no live provider, no
production data access.
"""
