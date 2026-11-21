# Which COMPSAC claim survives the SmallBank comparison?

**Selective locking on declared transaction dependencies already has close prior
work.** Vandevoort, Ketsman, Koch and Neven decide robustness of transaction
templates under multiversion READ COMMITTED and evaluate promoting selected reads to
updates to obtain safe executions at lower cost. Their extension uses functional
constraints to refine the dependencies and explicitly models SmallBank. This is
closer to the bank experiment than a generic comparison with Silo. Their Appendix A
charges one extra unit for an overdrawn check. The pinned BenchBase Java source
debits one unit less. The replay follows the executable source. The present
handwritten row-lock choices implement neither paper's analyzer. The authors'
scope also includes guarantees over possible schedules, whereas this replay
checks a finite set of observed histories.
[PVLDB 2021](https://doi.org/10.14778/3476249.3476268) · [LMCS 2023, §§2, 7 and Appendix A](https://lmcs.episciences.org/12744/pdf)

SmallBank's provenance leads back to Alomari, Cahill, Fekete and Röhm's study
of serializability costs under snapshot isolation. Ports and Grittner document
PostgreSQL SSI's conservative conflict detection, predicate-lock granularity and
workload-dependent performance. Serialization failures alone cannot identify
avoidable aborts. Our matched request streams constrain inputs, while each arm
induces its own execution and retry schedule.
[ICDE 2008](https://doi.org/10.1109/ICDE.2008.4497466) · [Ports and Grittner, §§2, 5, 8](https://www.vldb.org/pvldb/vol5/p1850_danrkports_vldb2012.pdf)

Clinical infrastructure already has service-declared data needs through CDS Hooks
prefetch templates. FHIR R4 supplies version-aware updates and atomic transaction
bundles. A proposed clinical method therefore needs evidence for how it obtains a
*necessary* read set, including the dependencies of a decision made before commit,
and how it handles changing consent or policy while that decision is outstanding.
[CDS Hooks 2.0, Prefetch Template](https://cds-hooks.hl7.org/2.0/) · [FHIR R4 HTTP, version-aware updates and transactions](https://hl7.org/fhir/R4/http.html)

**Decision.** Retain the bank result as external development evidence about one
implementation component. A narrower open question is whether a rule-derived
clinical dependency set can catch omitted evidence and policy edges, at acceptable
cost against an equally informed manually declared set and native SSI with the
same predicates. A discriminating test would freeze independent policy/rule labels,
introduce omitted-edge and irrelevant-change cases on held-out workflows, and
compare forbidden writes, false rejections and committed throughput. Reproducing
the same safety and cost with declared templates would remove the empirical basis
for a distinct derivation benefit. These three bank procedures exercise concurrent
business-state changes and contain no clinical rules or detached decision. The
surviving gap is a hypothesis. This targeted primary-source review establishes
overlap, without establishing priority for the remaining hypothesis.
