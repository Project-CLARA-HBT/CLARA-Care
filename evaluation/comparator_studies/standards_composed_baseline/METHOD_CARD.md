# Standards-composed mechanism baseline

Status: **frozen semantic/mechanism comparator; not a FHIR server or product**.

The baseline executes the repository's mechanism-mapped bitemporal resolver at
explicit valid-time and knowledge-time cutoffs, then combines that class of
resolved state with FHIR-R4-style version-aware optimistic write semantics,
current actor/purpose authorization, provenance linkage and an append-only
in-memory audit record. It deliberately does not check the exact THSS snapshot
ID, digest, task or disclosed evidence set. This isolates the incremental
disclosure-to-write binding clause without using stale-write prevention as a
weak comparator.

Executable behavior is in `engine.py` and `test_engine.py`. It is suitable for
deterministic mechanism isolation only, not interoperability, clinical, server
performance or security certification claims.
