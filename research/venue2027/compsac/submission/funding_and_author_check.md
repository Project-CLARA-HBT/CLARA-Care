# COMPSAC-funding · Submission, funding, and author check — IEEE COMPSAC 2027

- **Task:** `COMPSAC-funding` (Phase `P09`, venue `compsac`, priority venue)
- **Contract signature:** `check_submission() -> Decision` (validated by the REQUIRED shared tool `research/venue2027/_shared/tools/submission_contract.py`, version `1.0.0`)
- **Paper (context only):** *Dependency-Complete Optimistic Admission for Concurrent Clinical AI Writes* — see `research/venue2027/CONTEXT/PAPERS/compsac/SPEC.md`
- **Document version:** `compsac-funding-check-v1`
- **Honesty rule (binding):** every fee amount, deadline and support claim below is **UNVERIFIED** until a human re-checks the official CFP at conversion time. Rows marked verified require both a verification URL and a date. This document records a planning posture, not a commitment; it asserts no COMPSAC 2027 fact that the live CFP has not established.

## 1. Field summary (machine-checked required fields)

| Field | Value | Status |
|---|---|---|
| `cfp_url` | https://ieeecompsac.computer.org/2027/information-for-authors/ (per `research/venue2027/CONTEXT/PAPERS/compsac/SPEC.md`; live CFP not fetched) | UNVERIFIED |
| `template` | IEEE 2-column US Letter conference template (candidate); arXiv PDF is draft-only and NOT a submission format | UNVERIFIED |
| `page_limit` | candidate spec: long paper max 10 pages — not established | UNVERIFIED |
| `fee_or_registration` | author registration expected mandatory; IEEE Computer Society member / non-member / student tiers and an optional separate IEEE open-access APC are the plausible cost structure — **all amounts UNVERIFIED, no number may be budgeted as verified** | UNVERIFIED |
| `waiver_path` | IEEE Computer Society membership discount path and student travel/support possibilities are candidate routes only; **no assured fee waiver exists** — any support request is a request, not an entitlement (re-verify at https://ieeecompsac.computer.org/2027/information-for-authors/) | UNVERIFIED |
| `authorship_and_contribution` | all listed authors must satisfy authorship; per-author contribution statement expected but exact 2027 format not established | UNVERIFIED |
| `conflicts_policy` | COI declaration expected at/with submission; mechanism for 2027 not established; DSN concurrency-schedule firewall per `research/venue2027/_shared/publication_overlap_registry.yaml` (`compsac.reuses_archive: []`) applies internally | UNVERIFIED |
| `simultaneous_submission_policy` | **IEEE policy: a paper must not be under review elsewhere (double submission prohibited).** This work may not be concurrently submitted to DSN 2027, AIME 2027, or any other venue while under COMPSAC review; the venue-specific 2027 wording must be re-checked against the live CFP | UNVERIFIED (venue row) / binding (internal posture) |
| `verification_status` | UNVERIFIED — live CFP not fetched; must be re-verified at conversion time | UNVERIFIED |
| `decision` | HOLD | HOLD |

## 2. cfp_url — official sources to re-verify

- Author information: https://ieeecompsac.computer.org/2027/information-for-authors/ (UNVERIFIED; re-check the live CFP immediately before submission because fee schedules, anonymity rules and presentation policies can change).
- The IEEE Computer Society conference listing for COMPSAC 2027 (venue and dates) must also be re-checked; no URL in this document substitutes for the live page.

## 3. template — format requirements

- Candidate: IEEE 2-column US Letter conference template; the arXiv PDF is for internal drafts only and is not the submission format. The page-limit claim (long max 10 pages) is a candidate-spec value and is not established.
- Before any conversion: re-download the official template from the COMPSAC author page and re-check page limits, anonymity stance (COMPSAC has historically been non-blind — unverified for 2027) and any AI-use disclosure requirement.

## 4. fee_or_registration — honest cost structure

- COMPSAC is an IEEE conference; it **typically has registration fees with IEEE Computer Society member, non-member and student tiers**, and at least one author per accepted paper is expected to register at a required author rate. None of these amounts, tier boundaries, or author-vs-listener distinctions is verified for COMPSAC 2027.
- The optional IEEE open-access APC (hybrid route) is separate from registration and avoidable if the standard proceedings route is available; whether COMPSAC 2027 offers that choice is not established.
- **Every fee amount in this document is UNVERIFIED.** No euro/dollar figure may enter a budget line as a verified cost until a human re-checks the live registration page and the row is rewritten with a verification URL and date.
- A nonrefundable registration must not be committed before acceptance (IEEE conferences register after notification; re-verify the exact author-registration deadline at conversion time).

## 5. waiver_path — funding and discount routes (support is a request, not an entitlement)

- **IEEE Computer Society membership discount path:** becoming an IEEE/IEEE-CS member typically reduces the member-tier registration fee relative to non-member; this is a discount mechanism, not a waiver, and the 2027 delta is UNVERIFIED.
- **Student travel support possibilities:** IEEE Computer Society and COMPSAC editions have historically offered student volunteer/travel-support possibilities; availability, amount, eligibility (student-status proof such as an enrollment letter) and application deadlines for 2027 are UNVERIFIED and must not be assumed.
- **No guaranteed waiver:** there is no evidence of any guaranteed fee waiver for this paper; support must be applied for and approved, and denial is a possible outcome (then the decision reverts to NO-GO unless a payer exists). Re-verify any support call at https://ieeecompsac.computer.org/2027/information-for-authors/ before relying on it.
- **School/institution underwriting:** per `research/venue2027/CONTEXT/PAPERS/compsac/SPEC.md`, the funding plan is to request IEEE Computer Society student support and school underwriting, and to avoid optional OA charges until funding is in hand.
- Any claim that registration costs nothing, or that support is assured without an application, would be false and is out of scope for this program.

## 6. authorship_and_contribution

- All listed authors must meet authorship criteria; the contribution of each author must be describable (CRediT-style statement is the expected shape, exact 2027 format not established).
- Author order and the corresponding author must be fixed before submission; no author may be added or removed after acceptance without venue approval (general IEEE practice — re-verify).
- AI-use disclosure: the SPEC requires an AI-use disclosure section in the manuscript; the 2027 venue policy wording must be re-checked at conversion time.

## 7. conflicts_policy

- Conflicts of interest (advisor/committee, same-institution reviewers) must be declared per the venue's submission system; the 2027 mechanism is not established.
- Internal firewall: this COMPSAC study must not overlap the DSN 2027 concurrency-schedule paper or any other 2027 sibling; `research/venue2027/compsac/overlap_audit.md` (Decision: PASS) and `_shared/publication_overlap_registry.yaml` remain binding. Any scope drift reopens the overlap audit before this file's decision may change.

## 8. simultaneous_submission_policy

- **Double submission is prohibited under IEEE policy:** while this paper is under COMPSAC 2027 review it must not be simultaneously under review at any other archival venue, nor may substantially overlapping material be published elsewhere in the interim. The precise 2027 wording (and any extension or journal-transition allowances) must be re-verified against the live CFP.
- The STOP signal for P09 in `research/venue2027/GATES/PHASE_GATE_MATRIX.md` ("Dual archival submission or invented acceptance") applies: dual submission is forbidden; no acceptance may be claimed or implied anywhere.

## 9. verification_status and re-verification protocol

- Current status: **UNVERIFIED** (as of 2026-11-15). The live CFP was not fetched during this task; no network fetch of `ieeecompsac.computer.org` occurred.
- Conversion-time protocol: a human must (1) fetch the live CFP and registration pages, (2) rewrite any row that becomes verified **with the verification URL and an ISO date on the same line**, (3) record the amounts in the sponsor request packet, and (4) only then may `decision` move off HOLD via a fresh task run.

## 10. decision

- **Decision: HOLD.**
- No submission action, fee payment, registration commitment, membership purchase, or support application has been taken by this task, and none may be taken on the basis of this document alone. **Human authorization is required** before any submission or fee action.
- Rationale: experiments are not released yet (P05–P08 upstream), every cost fact is UNVERIFIED, and the venue's 2027 fee and support specifics are unpublished or unfetched. HOLD is the only honest state.

## 11. Sponsor request packet (prepared, contingent on live-CFP verification)

The go/no-go packet for the sponsor must contain, each marked UNVERIFIED until cited: registration tier table (member/non-member/student), author-registration deadline, optional APC amount, student travel-support call URL and deadline, student-status-proof requirement, and the no-assured-waiver statement from §5. This packet is not an authorization to spend.

---

*Contract: `check_submission() -> Decision` evaluated by `submission_contract.validate_submission_check`; result for this document: all REQUIRED_FIELDS present, no verified row lacking citation, no assured-waiver claim, double/simultaneous submission policy stated, decision `HOLD`.*
