"""PST venue2027 evaluation package.

Holds the deterministic synthetic dataset generator (:mod:`.generate_dataset`,
task PST-dataset, phase P02) for the PST 2027 study "ReceiptMin: Measuring
Forensic Reconstructability under Purpose-Bound Audit Minimization"
(``research/venue2027/VENUES/pst/RESEARCH_BLUEPRINT.md``), the baseline fidelity
adapters (:mod:`.baselines`, task PST-baselines, phase P03), plus the
downstream independent-oracle, receipt-contract and forensic-query tasks
(PST-oracle, PST-X01_receipt_contract, PST-X02_forensic_queries). Synthetic
audit-receipt fixtures only; no real PHI/PII, no live provider, no
production data access.
"""

from evaluation.venue2027.pst.baselines import (
    BASELINE_REGISTRY,
    compute_frontier,
    linkability_score,
    reconstructability,
    refuse_constant_stub,
    run_baseline,
)

__all__ = [
    "BASELINE_REGISTRY",
    "compute_frontier",
    "linkability_score",
    "reconstructability",
    "refuse_constant_stub",
    "run_baseline",
]

