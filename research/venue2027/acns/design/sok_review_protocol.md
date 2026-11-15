# ACNS · Reproducible systematic-review selection protocol (SoK corpus)

> **Task:** `ACNS-X01_review_protocol` · **Phase:** `P01` · **Venue:** `acns` · **Status:** registered protocol, search NOT executed
> **Paper:** *SoK: Evidence Boundaries of Attestation in Tool-Using AI Systems*
> **Contract:** `clara.venue2027.acns.review-protocol.v1`
> **Depends honored:** `ACNS-scope` (signed novelty contract, Decision GO, `reuses_archive: []`), `ACNS-prior` (comparator ledger `literature_matrix.csv`), `ACNS-threat` (evidence classes L0–L4, observation/trust axes).
> **Feeds:** `ACNS-X02_citation_corpus` (retrieval ledger), `ACNS-X05_rater_manual`, `ACNS-X06_adjudication`, `ACNS-X09_screening_flow`.

**Scope declaration.** This document is the **pre-registered selection protocol** for the SoK's literature corpus. It fixes, before any search is run: the population, inclusion/exclusion criteria, exact search strings, databases, date window and cutoff date, snowballing procedure, screening stages with a count ledger, the coding scheme, inter-rater conflict resolution rules, and the risk-of-bias / evidence-boundary rubric. Per the anti-salami gate, this protocol is a **method commitment, not a result**: no live search was executed during registration (see §9), every observed count in the ledger below is **zero**, and no claim in the eventual paper may cite this document as evidence of corpus size or content.

---

## 1. Population and unit of analysis

- **Population:** peer-reviewed publications (and recognized-SDO normative standards) that make, analyze, or define claims about **what observable evidence proves about the behavior of tool-using AI systems**: attestation (remote attestation, TEE evidence), provenance/lineage, receipts and acknowledgments, execution traces, audit logs, and agent-benchmark observability categories.
- **Primary unit of analysis:** one distinct publication (for all review statistics: screening counts, corpus size, coverage). Per the blueprint's unit rule, per-event or per-claim pseudo-replication is never used as the review unit.
- **Secondary unit:** one extracted claim sentence (clustered within publication) for coding statistics (κ, ambiguous-claim fraction) — defined downstream by `ACNS-X05`/`ACNS-X06`, bounded here to "short verbatim quotation with page/section reference" so that corpus rows cannot smuggle in unanchored paraphrase.
- **Pre-registered window:** publications dated **2019-01-01 through 2026-12-31** (the novelty contract's "pre-registered 2019–2026 corpus").
- **Registered seed set:** the comparator ledger's anchor records enter as seeds and pass the same criteria as every other record: RFC 9334 (RATS), RFC 9162 (Certificate Transparency), W3C PROV-DM, HL7 FHIR R5 (AuditEvent/Provenance/Consent), Macaroons (NDSS 2014), Zanzibar (USENIX ATC 2019), AgentDojo (NeurIPS 2024 D&B), ToolEmu (ICLR 2024), tau-bench (ICLR 2025). Seeds are **not** exempt from screening; they are labeled `role=seed` and counted in every stage like any other record.

## 2. Inclusion criteria (all must hold)

- **I1 — Peer-reviewed attestation.** The record is (a) a conference, journal, or workshop paper published in **peer-reviewed proceedings** (publisher page, DBLP entry, or DOI record attests a reviewed venue; workshop papers require a proceedings page that explicitly states peer review), or (b) a **standards-track normative document from a recognized SDO** (IETF RFC, W3C Recommendation, HL7 specification) acting as a normative anchor. This criterion is checked from publisher/registry metadata, never from the authors' own description.
- **I2 — In-window publication date.** Publication date (proceedings year, or SDO publication date for standards) within 2019-01-01 … 2026-12-31.
- **I3 — Provenance-relevant topic.** The record's content concerns attestation, provenance/lineage, receipts/acknowledgments, execution evidence, audit events, or evidence/observability semantics for software systems — including, centrally, tool-using AI/LLM agent systems.
- **I4 — Agent tool-use or receipt-claim relevance.** At least one of: (a) the system studied has an AI model invoking external tools/services; (b) the record defines evidence constructs (receipts, attestations, provenance records, traces) applicable to such systems; (c) the record is a registered baseline normative standard (blueprint arms B0–B3 sources).
- **I5 — Retrievable full text with provenance.** Full text obtainable in English (or an English version) at screening time, with a durable identifier (DOI/URL), publisher metadata, and a **recorded retrieval date** entered in the corpus ledger.

## 3. Exclusion criteria (any one excludes; stable reason codes)

| Code | Criterion | Examples (non-exhaustive) |
|---|---|---|
| `EXCL_NOT_PEER_REVIEWED` | Marketing and non-peer-reviewed material: vendor white papers, product pages, blog posts, press releases, podcast/interview transcripts, magazine articles; preprints (e.g. arXiv-only) with **no** discoverable peer-reviewed version; abstracts-only, non-archival posters, talks without proceedings. | Vendor "trust platform" brochures; company engineering blogs. |
| `EXCL_OUT_OF_WINDOW` | Publication date outside 2019-01-01 … 2026-12-31 (or after the cutoff date in §4.3). | 2018 workshop version of an in-window paper → keep the in-window version, exclude the other as `EXCL_DUPLICATE` semantics apply first. |
| `EXCL_OUT_OF_TOPIC` | No claim-evidence content within I3/I4 scope: pure model-performance papers with no attestation/provenance/tool-use/receipt-claim component. | An LLM fine-tuning paper without any evidence-semantics content. |
| `EXCL_DUPLICATE` | Duplicate record of the same work (see dedup rule §4.4); keep the canonical peer-reviewed version. | arXiv preprint + conference version. |
| `EXCL_UNAVAILABLE` | Full text unobtainable after the documented retrieval attempts in I5 (three attempts on different dates/providers logged). | Paywalled with no accessible version. |
| `EXCL_RETRACTED` | Retracted or withdrawn-with-finding publication. | — |
| `EXCL_LANGUAGE` | No English full text available. | — |
| `EXCL_NOT_TRACEABLE` | Record cannot be traced to a logged search hit, a logged snowball step, or the registered seed set (see §8.2 anti-convenience rule). | A paper added "because we know it" with no logged provenance. |

Every exclusion records: stage, date, coder, code, and a one-line justification. **Silent dropping is forbidden**; `EXCL_UNAVAILABLE` and `EXCL_NOT_TRACEABLE` counts are reported in the flow (they are exclusions, not invisible events).

## 4. Search strategy

### 4.1 Databases and indexes (five registered sources)

1. **ACM Digital Library** (dl.acm.org) — full-text metadata search over ACM proceedings/journals.
2. **IEEE Xplore Digital Library** (ieeexplore.ieee.org) — All-Metadata search.
3. **Scopus** (Elsevier) — TITLE-ABS-KEY search, used as the cross-publisher index (adds Springer/Elsevier venues).
4. **DBLP** (dblp.org) — keyword search plus venue-year enumeration; canonical record resolution and duplicate arbitration.
5. **USENIX proceedings index** (usenix.org) — site search over USENIX Security / ATC / OSDI / NSDI proceedings.

The full publisher venue set (ACM, IEEE, USENIX, NDSS, ICLR, NeurIPS, Springer LNCS venues) is reached through these five indexes; no additional "hand-picked venue crawl" channel exists.

### 4.2 Exact search strings (frozen; field scope per database in §4.5)

```text
S1_attestation:
  ("attestation" OR "remote attestation" OR "trusted execution environment" OR "TEE attestation")
  AND ("LLM" OR "large language model" OR "AI agent" OR "language-model agent"
       OR "tool use" OR "tool calling")

S2_provenance:
  ("provenance" OR "data lineage" OR "auditability" OR "audit trail" OR "audit log")
  AND ("LLM" OR "large language model" OR "AI agent" OR "agent framework" OR "inference pipeline")

S3_receipts:
  ("receipt" OR "acknowledgment" OR "non-repudiation" OR "signed log")
  AND ("tool call" OR "tool invocation" OR "model invocation" OR "inference request"
       OR "agent action")

S4_benchmark_observability:
  ("agent benchmark" OR "AgentDojo" OR "ToolEmu" OR "tau-bench" OR "tool-agent evaluation")
  AND ("observability" OR "evidence" OR "monitoring" OR "attack success")

S5_supply_chain_verification:
  ("prompt injection" OR "model supply chain" OR "inference supply chain")
  AND ("attestation" OR "provenance" OR "verification" OR "integrity")
```

Strings are run **verbatim** per database; per-database field mappings and filters below are the only permitted adaptations. If a database's syntax forces a rewording, the adapted string and a screenshot/log citation are recorded in the search log and the change is justified line-by-line.

### 4.3 Date range and cutoff date

- **Search execution cutoff date: 2026-12-31 (23:59:59 UTC).** Records with publication date after this cutoff are out of scope regardless of venue.
- **Window filter applied in every query:** 2019-01-01 … 2026-12-31.
- **Protocol registration date: 2026-11-15.** The search must be executed before the corpus freeze (`ACNS-X02`) and the cutoff bounds what the executed search may capture; any database-record whose indexed date jumps past the cutoff in a later re-run is excluded as `EXCL_OUT_OF_WINDOW` and logged.

### 4.4 Deduplication rule

Exact DOI match first; otherwise normalized title (lowercase, strip non-alphanumerics, collapse whitespace) **plus** first-author surname **plus** year. Each merge decision is logged (kept record, dropped record, rule fired). The seed set is deduplicated against search hits with the same rule; seeds never bypass it.

### 4.5 Per-database field scope and filters

| Database | Field scope | Filters |
|---|---|---|
| ACM Digital Library | Title OR Abstract OR Keywords | Publication date 2019-01-01 … 2026-12-31; all venue types |
| IEEE Xplore | All Metadata | Year 2019–2026; conference, journal, early access |
| Scopus | TITLE-ABS-KEY | `PUBYEAR > 2018 AND PUBYEAR < 2027`, `DOCTYPE(cp OR ar OR re)`, `LANGUAGE(English)` |
| DBLP | title/keyword match | Publication year 2019–2026; used also to resolve canonical venue records |
| USENIX index | full record text | Proceedings years 2019–2026 |

### 4.6 Snowballing procedure (backward and forward)

- **Backward snowballing:** for every full-text-included record and every seed, screen the reference list. Each candidate reference enters at the **title-screening stage** (never directly into the corpus) with provenance `snowball:backward:<from-record-id>:<round>`.
- **Forward snowballing:** for every full-text-included record and every seed, enumerate citing works via Semantic Scholar and OpenAlex citation indexes (Google Scholar only as a documented fallback if an index fails). Each citing candidate enters at title screening with provenance `snowball:forward:<to-record-id>:<round>`.
- **Rounds and saturation:** snowballing proceeds in rounds; a round ends when every included record's backward and forward candidates have been title-screened. **Saturation rule:** stop after the first round that adds zero new full-text-included records, or after **three** rounds, whichever comes first. Every round logs: date, tool/index, query or record list, candidate count, and per-candidate screening decision.
- Snowball candidates obey the identical inclusion/exclusion criteria (§2–§3); no snowball record may skip a stage or a coder.

## 5. Screening stages and count ledger

**Execution status: NO LIVE SEARCH WAS EXECUTED.** This protocol is registered before any search run; consequently **all observed counts below are zero and are labeled planned**. The ledger table is the fixed instrument that `ACNS-X02`/`ACNS-X09` must fill with real observed counts at execution time; this document asserts no corpus size whatsoever ("no pretend corpus size", per the paper spec).

| Stage | What enters | Exit rule | Observed count | Status |
|---|---|---|---|---|
| S0 Identification | Records from the 5 databases × 5 strings + registered seeds | All raw hits logged with database, string ID, date | 0 | planned, not executed |
| S1 Deduplication | S0 records | Dedup rule §4.4; merges logged | 0 | planned, not executed |
| S2 Title screening | S1 records | Dual independent title review; conflict → advance | 0 | planned, not executed |
| S3 Abstract screening | S2 retained | Dual independent abstract review; conflict → advance | 0 | planned, not executed |
| S4 Full-text screening | S3 retained | Dual independent full-text review vs I1–I5; conflict → adjudication (§7) | 0 | planned, not executed |
| S5 Snowball rounds | S4 included + seeds | Rounds per §4.6 until saturation | 0 | planned, not executed |
| S6 Final corpus | S5 retained | Frozen for extraction/coding (X02/X05/X06) | 0 | planned, not executed |

Per-stage **inclusion and exclusion counts are recorded separately** (a stage's retained count = entered − excluded-at-stage), every excluded record carries its reason code from §3, and the executed ledger plus a PRISMA-style flow figure become the paper's selection-flow exhibit. The zero row above is the honest pre-execution state, not an observed result.

## 6. Coding scheme (applied to S6 corpus only)

Each included record is double-coded by two independent human coders (C1, C2) using fields fixed here and elaborated by `ACNS-X05`:

- **C1 Claim extraction:** short verbatim claim sentences (≤ 2 lines each) with page/section reference; paraphrase-only entries are invalid.
- **C2 Evidence class:** one of the six lattice classes — assembly, egress, transport acknowledgment, provider-attested receipt, execution trace, semantic consumption.
- **C3 Lattice level claimed:** the strongest level the record asserts (L0 `ASSUMED` … L4 `COMMITTED`, per the threat model's evidence lattice).
- **C4 Lattice level demonstrated:** the strongest level the record's actual evidence supports.
- **C5 Observer axis:** who could observe the evidence (agent host / transport stack / provider / TEE / persisting service / harness-internal).
- **C6 Trust axis:** which trusted parties the claim presupposes (and whether they are named).
- **C7 Claim type:** existence claim, boundary claim, or performance claim (performance claims are context, never corpus-anchored endpoints).
- **C8 Ambiguity flag:** `AMB` when a code is not decidable from the text; the record keeps the ambiguous flag rather than a coerced value.

Baseline arms B0–B3 coding roles follow `literature_matrix.csv`; the coverage matrix consumes the C2–C4 fields.

## 7. Inter-rater conflict resolution rules

- **Screening conflicts (S2 title / S3 abstract):** any coder disagreement **advances** the record to the next stage (conservative inclusion) and increments the stage's `SCREEN_CONFLICT` counter. Advancing on conflict is never treated as agreement.
- **Full-text conflicts (S4):** include/exclude disagreement goes to a **third-coder adjudication** within 14 days; the adjudicator is neither C1 nor C2 for that record and sees both justifications blind-coded (without the other's final label where separation is feasible). If no third coder is available, the record is retained with flag `ADJ_UNAVAILABLE` and counted in the ambiguous fraction — it is never silently dropped or silently included.
- **Coding conflicts (C2–C7):** per-field disagreement → adjudication session; the post-adjudication label is final. Cohen's κ is computed **on the post-adjudication labels** and the **pre-adjudication** raw agreement plus disagreement-resolution rate are reported alongside (both are required outputs of the blueprint).
- **Adjudication ledger:** every conflict, its resolution, date, and adjudicator identity are published in the ledger (`ACNS-X06`); the ledger is append-only and sealed before analysis (freeze gate `ACNS-freeze`).
- **INDETERMINATE retention:** any claim that cannot be classified with agreement after adjudication is retained as `INDETERMINATE`/`AMB` and reported in the ambiguous-claim fraction. Coercing an unresolvable code to a definite value to raise κ is prohibited and is a falsifying defect.

## 8. Risk-of-bias and evidence-boundary rubric

### 8.1 Risk-of-bias codes (per included record; concern about the record's claim support)

| Code | Domain | LOW concern | HIGH concern |
|---|---|---|---|
| RB1 | Evidence independence | Third-party/verifier-verified evidence | Only the system authors' own instrumentation supports the claims |
| RB2 | Observer position | Service-side or external verifier records | Benchmark/harness-internal observer (inside the agent loop) |
| RB3 | Disclosure completeness | Threat model + limitations + negative results present | None of these disclosed |
| RB4 | Reproducibility artifacts | Public code/data or artifact evaluation | No artifacts, or unverifiable |
| RB5 | Commercial framing | Academic/independent affiliation, neutral framing | Vendor-authored or promotional framing (pure promotion routes to `EXCL_NOT_PEER_REVIEWED`) |

Each code takes `LOW | HIGH | UNKNOWN`; `UNKNOWN` is reported, never defaulted to `LOW`. HIGH-bias records remain in the corpus but their claims are marked and drive a **sensitivity analysis**: any headline coverage conclusion that depends on HIGH-RB records only is reported as not robust.

### 8.2 Evidence-boundary rubric (per extracted claim)

- **`BND_VALID`** — boundary code `BND_VALID`: claim does not exceed its evidence class under the lattice.
- **`BND_OVERREAD`** — boundary code `BND_OVERREAD`: claim exceeds evidence (e.g. transport acknowledgment or provider receipt cited as proof of execution; verifiable-log inclusion cited as proof of processing). These are the witness-gallery targets (`ACNS-X07`).
- **`BND_UNDERREAD`** — boundary code `BND_UNDERREAD`: record's evidence supports more than it claims (coverage insight, not fault).
- **`BND_INDETERMINATE`** — boundary code `BND_INDETERMINATE`: boundary not decidable from the text; retained, never coerced.

A claim's boundary code must be derivable from its C1 quotation plus C2–C6 fields; a boundary code with no supporting quotation is invalid and re-opened.

## 9. Corpus anti-bias rules (own-paper cap; no convenience sampling)

- **9.1 Own-paper dominance prohibition (CLARA cap).** The authors' own paper — the CLARA project's publications and sibling-project papers (CLARA-Care, GLHS R4, the accepted HEALTHINF #97, GovRed/RIVF, GovMut/SOICT) — **may not dominate the corpus**: these records are corpus items coded like any other, never framing devices for the taxonomy. Hard caps, both of which must hold in the final corpus: **(a)** at most **3** CLARA-affiliated records in total; **(b)** if the final corpus exceeds 40 records, CLARA-affiliated records must also be ≤ floor(0.05 × N). Corpus-level statistics (coverage, κ, ambiguous fraction) are additionally reported **with and without** CLARA-affiliated records; if exclusion changes any headline conclusion, that conclusion is reported as not robust. No evidence class, implication pair, or counterexample witness may be anchored **solely** on a CLARA-affiliated record; each requires at least one independent non-CLARA corpus anchor.
- **9.2 Convenience-only sampling prohibited.** Every final-corpus record must be traceable to exactly one registered channel: (a) a logged database-search hit (§4.1–§4.5), (b) a logged snowball step (§4.6), or (c) the registered seed set (§1). Records that cannot be so traced take `EXCL_NOT_TRACEABLE`. "Known-item" additions outside these channels are forbidden **even if they satisfy I1–I5**; if the coders believe an untraceable record is essential, the protocol itself must be amended and re-registered before inclusion, with the amendment dated and versioned.
- **9.3 Competitor and negative-finding retention.** The corpus must include the strongest competing explanations (B0 RFC 9334, B1 W3C PROV/FHIR, B2 AgentDojo/ToolEmu) and negative/falsifying results; excluding unfavorable or competing records while retaining favorable ones is a falsifying defect under the anti-salami gate.
- **9.4 Cross-study firewall.** The corpus and this protocol consume **no** frozen E15–E22 experiment outcomes, no IFIP SEC mechanism inputs, and no DIMVA telemetry; sibling-study artifacts may appear in the corpus only as published literature coded like any other record. No clinical or empirical performance claim is derived from this review; the SoK's outputs are the coverage matrix, agreement statistics, and witness reproduction — all entering later via `artifacts/venue2027/acns/<run_id>/manifest.json`.

## 10. Execution status and honest reporting

- **No live search was executed** as of protocol registration (2026-11-15). Every count in §5 is a planned, zero-observed placeholder of the instrument — not an observed result — and the executed search must replace them with real per-stage counts before any corpus claim exists.
- The protocol binds the downstream tasks: `ACNS-X02` (retrieval ledger with DOIs/URLs and retrieval dates), `ACNS-X09` (screening-flow artifact with the filled count ledger), `ACNS-X05`/`ACNS-X06` (manual + adjudication). Divergence from this protocol during execution requires a dated, versioned amendment recorded before the affected stage runs; post-hoc criteria changes are forbidden.
- Any failure to meet a registered threshold downstream (κ, saturation, caps) is reported as a negative result per the blueprint falsification rule; this protocol creates no success guarantee.
