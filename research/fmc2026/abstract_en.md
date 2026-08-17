# FMC 2026 abstract (English)

## From Longitudinal Context to Safe Action: A Co-Versioned Governance Contract for Persistent Health AI

**Background:** Persistent health-AI systems may receive authorized longitudinal-record context and later return a proposed update after the record, consent, or policy conditions have changed.

**Objectives:** To describe a clinical-facing governance contract for preventing a persistent AI proposal from relying on stale or no-longer-authorized context.

**Research methods:** We describe a task- and purpose-bounded health-state snapshot (THSS) disclosed to an AI. Each later proposal remains linked to that disclosure context. Before persistence, a trusted governed state transition (GST) rechecks the current record state, consent, and policy conditions.

**Results:** The contract separates AI proposal generation from the governed decision to persist. A proposal whose bound snapshot no longer matches current governance conditions is rejected rather than written. This presentation reports the design and makes no clinical-outcome, diagnostic-performance, or regulatory result claim.

**Conclusion:** Binding a persistent proposal to its disclosed context and revalidating at the write boundary provides a clear governance pattern for longitudinal health AI. Clinical effectiveness, medical-device status, and regulatory compliance require separate evaluation.

**Keywords:** health AI; governance; longitudinal records; consent; provenance
