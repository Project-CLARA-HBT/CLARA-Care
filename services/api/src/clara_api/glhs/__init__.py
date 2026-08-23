"""Governed Longitudinal Health State (GLHS) trusted API primitives.

GLHS is additive to the existing LifeMap/PHR schema during convergence.  The
package owns canonical evidence, assertions, transitions and task-bounded
snapshots; UI and derived-index projections remain consumers of this ledger.
"""

from clara_api.glhs.commit_kernel import (
    DependencySpec,
    GlhsCommitContext,
    GlhsCommitResult,
    compute_dependency_vector_digest,
    execute_atomic_glhs_commit,
)

__all__ = [
    "DependencySpec",
    "GlhsCommitContext",
    "GlhsCommitResult",
    "compute_dependency_vector_digest",
    "execute_atomic_glhs_commit",
]

