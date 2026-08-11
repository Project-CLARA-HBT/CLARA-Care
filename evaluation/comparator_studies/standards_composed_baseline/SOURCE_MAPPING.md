# Standards mapping

The mapping targets the permanent HL7 FHIR R4 (4.0.1) specification:

| Composed capability | Primary standard source | Local semantic mechanism |
| --- | --- | --- |
| Valid-time/knowledge-time resolution and explicit conflict retention | Repository mechanism-mapped bitemporal comparator | `resolve()` delegates to the tested arbitration engine with explicit cutoffs |
| Version-aware update / optimistic contention | <https://hl7.org/fhir/R4/http.html> | `observed_base_version == state_version` |
| Provenance recording | <https://hl7.org/fhir/R4/provenance.html> | non-empty `provenance_ids` stored per resource |
| Purpose/current authorization input | <https://hl7.org/fhir/R4/consent.html> | current `(actor_id, purpose)` authorization set |
| Security/audit event recording | <https://hl7.org/fhir/R4/auditevent.html> | accepted and rejected decision records |

The first row is a local mechanism composition, not a FHIR capability claim.
Overall this is a composition of concepts, not a claim that these resources
alone define GLHS or that the local object model is wire-compatible FHIR.
