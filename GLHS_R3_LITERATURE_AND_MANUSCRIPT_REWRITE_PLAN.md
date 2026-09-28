# GLHS R3 LITERATURE & MANUSCRIPT REWRITE PLAN

## 1. Literature standard

Prefer:
- CORE/ICORE A*/A peer-reviewed systems/security/AI venues;
- Q1/Q2 health/medical-informatics journals;
- foundational peer-reviewed work;
- concurrent preprints only when uniquely close.

Do not build novelty on a citation gap created by ignoring adjacent mature fields.

---

## 2. Required core literature matrix

| Area | Work | Venue | What it establishes | GLHS consequence |
|---|---|---|---|---|
| OCC | Kung & Robinson (1981) | ACM TODS | commit-time validation/conflict control | OCC is not novelty |
| SSI | Cahill et al. (2008) | SIGMOD | serializable snapshot isolation | generic state-drift handling not novelty |
| PostgreSQL SSI | Ports & Grittner (2012) | PVLDB | production SSI | PostgreSQL safety is prior art |
| OCC | TicToc (2016) | SIGMOD | timestamp-based OCC | version validation mature |
| Privacy DB | Hippocratic Databases (2002) | VLDB | privacy/purpose responsibility | purpose binding alone not novel |
| Purpose control | Byun & Li (2008) | VLDB Journal | purpose-based access | purpose-aware authorization prior art |
| Proof auth | PCFS (2010) | IEEE S&P | proof-carrying dynamic authorization | machine-verifiable auth prior art |
| Capability | Macaroons (2014) | NDSS | contextual caveat credentials | compact-token baseline mandatory |
| Provenance | Semiring provenance (2007) | PODS | derivation provenance | provenance itself not novel |
| Provenance enforcement | LPM (2015) | USENIX Security | secure whole-system provenance and enforcement | cannot claim first provenance enforcement |
| Clinical DSS provenance | Curcin et al. (2017) | JBI | clinical decision provenance/evidence tracing | clinical provenance prior art |
| Health provenance | Margheri et al. (2020) | IJMI | healthcare provenance + consent/audit | consent+provenance prior art |
| Consent | Kaye et al. (2015) | EJHG | dynamic consent | mutable consent prior art |
| AI governance | FUTURE-AI (2025) | BMJ | lifecycle traceability/governance | GLHS is a runtime mechanism |
| Clinical AI governance | SMART (2026) | JAMIA | lifecycle governance and audit history | model lifecycle governance prior art |
| Long-term memory | LongMemEval (2025) | ICLR | temporal/update memory evaluation | long-term memory itself not novelty |
| Memory privacy | Wang et al. (2025) | ACL | memory extraction risk | motivates memory as governance boundary |
| Transactional memory | MemTX (2026) | preprint | transactional belief commit | closest concurrent work |
| Transactional memory | MemTxn (2026) | preprint | source-supported transactional memory | closest concurrent work |

---

## 3. Central gap sentence

Use wording equivalent to:

> Prior work separately establishes transactional freshness, purpose-aware authorization, dynamic consent, provenance, proof-carrying access, clinical-AI lifecycle governance, and transactional agent memory. The remaining boundary addressed here is narrower: whether a later persistent mutation can be admitted only when it remains verifiably continuous with the exact governed disclosure actually supplied to the inference that produced its lineage, while current state and governance are revalidated at admission.

---

## 4. Related Work rules

Do:
- compare properties;
- cite the strongest neighboring field;
- state clearly what prior work already solves;
- isolate one missing property.

Do not:
- say “no prior work” without support;
- use strawman comparison tables;
- treat recent preprints as stronger evidence than mature top-tier peer-reviewed work;
- omit MemTX/MemTxn.

---

## 5. Manuscript rewrite map

### Introduction
Delete broad “co-versioned” novelty language.
Open with the cross-time problem:
- governed disclosure at inference;
- mutable state/governance;
- later persistent write.

### Related Work
Use:
1. transactional freshness;
2. purpose/usage control;
3. proof-carrying/capabilities;
4. provenance;
5. health provenance and clinical-AI governance;
6. persistent agent memory;
7. gap.

### Methods
Start with the invariant before introducing THSS.

### Evaluation
Headline:
- actual inference-consumption integrity;
- minimal comparator;
- real PostgreSQL TOCTOU;
- dependency completeness.

Secondary:
- canonicalization;
- bounded formal assurance;
- systems overhead;
- model utility.

### Discussion
Lead with:
- invariant vs representation;
- minimal-token result;
- relation to MemTX/MemTxn;
- inability to prove semantic causality inside the model.

### Limitations
Explicitly state:
- GLHS cannot prove that the model reasoned only from disclosed content;
- application/DB trusted boundary;
- dependency semantics remain operation-defined;
- claims are bounded to audited routes/schedules;
- clinical validity is absent unless real external/human validation is run.

---

## 6. Figure plan

Figure 1:
`t1 governed disclosure H → actual inference binding I → proposal P → t2 drift → t3 admission`

Figure 2:
property comparison across OCC / purpose control / provenance / transactional memory / GLHS.

Figure 3:
E01/E02 invalid-admission by arm.

Figure 4:
real PostgreSQL TOCTOU families.

Optional:
systems overhead.

---

## 7. Main table plan

Table 1:
nearest-neighbor property matrix.

Table 2:
formal coordinates/admission predicates.

Table 3:
component ablation + minimal baseline.

Table 4:
real PostgreSQL TOCTOU.

Table 5:
bounded formal assurance.

Supplement:
canonicalization, performance, provider utility, malformed outputs.

---

## 8. Contribution statement

Recommended contribution hierarchy:

1. **Invariant contribution**
   - Governed Read-to-Write Continuity / Exact-Disclosure Admission.

2. **Systems contribution**
   - a concrete longitudinal-health realization using governed disclosure, server-owned inference binding, immutable lineage, dependency contracts, and atomic admission.

3. **Empirical contribution**
   - component/baseline tests, real PostgreSQL adversarial schedules, bounded formal assurance, and reproducibility artifacts.

Do not list:
- provenance;
- consent;
- bitemporal storage;
- hashing;
- OCC;
as separate novel contributions.

---

## 9. Bibliographic anchors

- Agrawal R, Kiernan J, Srikant R, Xu Y. *Hippocratic Databases*. VLDB 2002.
- Byun JW, Li N. *Purpose based access control for privacy protection in relational database systems*. VLDB Journal. 2008;17:603–619.
- Garg D, Jia L, Datta A. *A Proof-Carrying File System*. IEEE Symposium on Security and Privacy. 2010. DOI: 10.1109/SP.2010.28.
- Birgisson A, et al. *Macaroons: Cookies with Contextual Caveats for Decentralized Authorization in the Cloud*. NDSS 2014.
- Bates A, Tian DJ, Butler KRB, Moyer T. *Trustworthy Whole-System Provenance for the Linux Kernel*. USENIX Security 2015.
- Curcin V, Fairweather E, Danger R, Corrigan D. *Templates as a method for implementing data provenance in decision support systems*. J Biomed Inform. 2017;65:1–21. DOI: 10.1016/j.jbi.2016.10.022.
- Margheri A, et al. *Decentralised provenance for healthcare data*. Int J Med Inform. 2020;141:104197. DOI: 10.1016/j.ijmedinf.2020.104197.
- Kaye J, et al. *Dynamic consent: a patient interface for twenty-first century research networks*. Eur J Hum Genet. 2015;23:141–146. DOI: 10.1038/ejhg.2014.71.
- Lekadir K, et al. *FUTURE-AI*. BMJ. 2025;388:e081554. DOI: 10.1136/bmj-2024-081554.
- *SMART: structured, meaningful, auditable, responsible, and transparent documentation for clinical AI*. JAMIA. 2026. DOI: 10.1093/jamia/ocag117.
- Wang B, et al. *Unveiling Privacy Risks in LLM Agent Memory*. ACL 2025.
- *MemTX: Transactional Belief Commit for Stateful Agent Memory*. arXiv:2607.23929.
- *MemTxn: A Transaction Boundary for Source-Supported Updates and Complete-State Recovery in Agent Memory*. arXiv:2607.27834.

At manuscript freeze, verify bibliographic metadata, DOI, pages, venue status, and current rank from authoritative sources.
