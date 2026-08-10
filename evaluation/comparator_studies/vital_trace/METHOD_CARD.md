# Vital Trace comparator method card

Status: **NOT RUN — reproducible implementation not source-reviewed**.

The candidate comparator is the 2026 preprint *Vital Trace: Protocol-Constrained
Patient-State Reasoning for Longitudinal Clinical Trajectories* (arXiv:2602.12833v2).
The reported design is a compact state memory and staged Router/Reasoner/Auditor/
Steward process for ICU trajectory prediction. It is a strong temporal-state
comparator, not a strawman or a GLHS ablation.

This repository currently has no source-reviewed public code, frozen protocol,
or reproducible benchmark assets for a faithful execution. Consequently this
package exposes no simulated Vital Trace results and every GLHS-only operation
returns `UNSUPPORTED_BY_METHOD`. A methods reviewer must pin primary source,
repository revision, model configuration, data access, and task mapping before
changing this status.
