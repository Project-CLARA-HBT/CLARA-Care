# Temporal BM25 retrieval baseline

Status: **implemented; not inserted into V21/V22**.

This is a deterministic, non-GLHS retrieval comparator for the next frozen
CommitLoop protocol.  It scores the same bitemporally visible structured
evidence supplied to every arm using BM25 over resource type, status,
provenance relation, encounter reference, and code fields.  A bounded,
declared valid-time recency component breaks close retrieval ties.

It has no GLHS canonical state, predicate engine, THSS disclosure, provenance
closure, or write contract.  It therefore measures what retrieval and temporal
ranking alone can achieve, and must not be described as a reproduction of a
published system.

The V21/V22 condition inventory remains immutable.  A future V7 freeze must
include this adapter, its tests and this method card in the hash inventory and
apply the same task, solver, decoding, schema and score to every arm.
