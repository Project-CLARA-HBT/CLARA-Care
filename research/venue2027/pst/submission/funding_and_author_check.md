# PST 2027 · Submission, funding, and author check (PST-funding, phase P09)

> **Task:** `PST-funding` · **Venue:** `pst` (IEEE PST — Privacy, Security and Trust) · **Phase:** `P09` · **Contract version:** `1.0.0`
>
> **Paper:** *ReceiptMin: Measuring Forensic Reconstructability under Purpose-Bound Audit Minimization* — see `research/venue2027/CONTEXT/PAPERS/pst/SPEC.md` and `research/venue2027/pst/novelty_contract.md`.
> **Dependencies satisfied:** `PST-scope` PASS, `SH-venue_formats` PASS (proof reports and logs under `research/venue2027/proof/`).
> **Base SHA of this worktree:** `573d5369abd2e9d35f8039a99cf647e6ba9b3f32`.
>
> **Honesty rule (binding):** every external CFP/fee/deadline/waiver fact in this document is **UNVERIFIED** unless it carries a verification URL and an ISO date on the same line. This agent cannot fetch the live PST 2027 CFP, registration site, or fee schedule; no network fetch occurred during this task. No line in this document asserts a verified external fact, no deadline is verified by this file, and no waiver entitlement is claimed. Nothing in this document authorizes a submission or a payment. A failed hypothesis is not a failed study; concealment or false provenance is (P09 gate: "Dual archival submission or invented acceptance" is the STOP signal).

## 1. Machine-readable check block

The labeled lines below are the contract surface consumed by
`research/venue2027/_shared/tools/submission_contract.py` (`check_submission() -> Decision`, all
fields REQUIRED; validator version `1.0.0`).

- cfp_url: https://www.pstnet.ca/pst2027/callforpapers.html (per
  `research/venue2027/CONTEXT/PAPERS/pst/SPEC.md`; live CFP not fetched; re-verify at submission)
- template: IEEE double-blind 2-column conference template (candidate per PST SPEC section 0
  "Submission formatting"); arXiv draft is NOT submission format; official 2027 template file not
  yet verified (live CFP not fetched; re-verify at submission)
- page_limit: not established (candidate spec: 6-page short / 10-page regular inclusive of
  references — not established for 2027; live CFP not fetched; re-verify at submission)
- fee_or_registration: UNVERIFIED — author registration expected mandatory per candidate SPEC with
  the fee TBA; no amount, tier, or author-vs-listener boundary is verified; budget as nonzero with
  amounts not yet verified (live CFP not fetched; re-verify at submission)
- waiver_path: UNVERIFIED — no waiver program for PST 2027 has been located by this agent. The
  funding plan in the PST SPEC (remote presentation to avoid travel cost; request an author-rate
  reduction; seek school or institutional underwriting) is a *plan*, not an entitlement. No waiver
  may be presented as guaranteed, assured, or automatic (live CFP not fetched; re-verify at
  submission)
- authorship_and_contribution: all listed authors must satisfy authorship criteria; per-author
  contribution statement expected but the exact 2027 format is not established; author list and
  order frozen by the human lead before submission, not by this agent; AI-use disclosure expected
  per SPEC G8 but 2027 venue wording unverified (live CFP not fetched; re-verify at submission)
- conflicts_policy: conflicts of interest (advisor/committee, same-institution reviewers) must be
  declared per the venue's official mechanism; the 2027 process is not established; internal
  firewall — the PoPETs 2027 cache-privacy study distinction per
  `research/venue2027/_shared/publication_overlap_registry.yaml` (study `pst`, `reuses_archive: []`)
  and `research/venue2027/CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md` applies; overlap audit re-run
  required before any submission decision (live CFP not fetched; re-verify at submission)
- simultaneous_submission_policy: double submission is refused — while this manuscript is under
  review at PST 2027 it must not be simultaneously under review at any other archival venue (the
  exact official 2027 wording is not yet verified; live CFP not fetched; re-verify at submission)
- verification_status: UNVERIFIED — live CFP not fetched; re-verify at submission
- decision: HOLD — all verification pending; do not submit, do not pay, do not register until a
  human re-checks the live CFP and records a dated verification

## 2. Verification status detail (per fact)

Every row below carries the same reason: **live CFP not fetched; re-verify at submission**.

| Fact | Candidate value (source: PST SPEC / SH-venue_formats) | Status |
|---|---|---|
| CFP URL | https://www.pstnet.ca/pst2027/callforpapers.html | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Full-paper deadline | 2027-04-10 (claimed by PST SPEC) | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Template | IEEE double-blind 2-column | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Page limit | 6-page short / 10-page regular inclusive of references | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Anonymity | double-blind | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Author registration | mandatory, fee TBA | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Remote presentation | allowed per CFP text (candidate SPEC) | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Student discount / waiver | no PST 2027 program located | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Artifact/badge | not established | UNVERIFIED — live CFP not fetched; re-verify at submission |

No deadline or fee is verified by this file. A deadline marked UNVERIFIED here must never be
treated as scheduling authority; the live CFP is the only authority.

## 3. cfp_url — official sources to re-verify

- Call for papers: https://www.pstnet.ca/pst2027/callforpapers.html (UNVERIFIED; re-check the live
  CFP immediately before submission, because fee schedules, anonymization rules and presentation
  policies can change).
- The PST 2027 site navigation (registration page, author information) must also be re-checked; no
  URL in this document substitutes for the live page.

## 4. fee_or_registration — honest cost structure

- PST is an IEEE-hosted conference series; the candidate SPEC states author registration is
  mandatory with the fee TBA for 2027. No amount, tier structure (member/non-member/student), or
  author-vs-listener distinction is verified for PST 2027.
- **Every fee amount in this document is UNVERIFIED.** No dollar/euro figure may enter a budget
  line as a verified cost until a human re-checks the live registration page and the row is
  rewritten with a verification URL and date on the same line.
- A nonrefundable registration must not be committed before acceptance and a funded go decision;
  the SPEC G9 gate ("cost and presentation feasibility established before a nonrefundable
  registration commitment") applies.

## 5. waiver_path — funding and support routes (a request, not an entitlement)

- **Remote presentation:** the candidate SPEC records that the official CFP allows remote
  presentation if unable to travel; this lowers travel cost but does not waive registration, and
  the 2027 policy is UNVERIFIED.
- **Author-rate reduction:** the SPEC funding plan is to request an author-rate reduction from the
  organizers; this is a request whose approval, amount, and deadline are UNVERIFIED and must not be
  assumed.
- **Institutional underwriting:** school/institution underwriting is the fallback route per SPEC
  section 9; pursuit is contingent on a human go decision.
- **No guaranteed waiver:** there is no evidence of any guaranteed fee waiver for this paper; support must be applied for and approved, and denial is a possible outcome (then the decision reverts to NO-GO unless a payer exists). Re-verify any support call at https://www.pstnet.ca/pst2027/callforpapers.html before relying on it. Any claim that registration costs nothing, or that support is assured without an application, would be false and is out of scope for this program.
- **Student status proof:** if a student-rate path is established at conversion time, an enrollment
  letter or equivalent proof is the expected requirement; this expectation itself is UNVERIFIED for
  PST 2027.

## 6. authorship_and_contribution

- All listed authors must meet authorship criteria; each author's contribution must be describable
  (CRediT-style statement is the expected shape; the exact 2027 format is not established).
- Author order and the corresponding author must be fixed by the human lead before submission; no
  author may be added or removed after acceptance without venue approval (general practice —
  re-verify).
- AI-use disclosure: the SPEC G8 gate requires an AI-use disclosure section in the manuscript; the
  2027 venue policy wording must be re-checked at conversion time.

## 7. conflicts_policy

- Conflicts of interest (advisor/committee members, same-institution reviewers) must be declared
  per the venue's submission system; the 2027 mechanism is not established.
- Internal firewall: this PST study must not overlap the PoPETs 2027 cache-privacy study or any
  other 2027 sibling; `research/venue2027/pst/novelty_contract.md` (non-overlap with PoPETs) and
  `_shared/publication_overlap_registry.yaml` remain binding. Any scope drift reopens the overlap
  audit before this file's decision may change.

## 8. simultaneous_submission_policy — double submission refused

- **Double submission is prohibited:** while this paper is under PST 2027 review it must not be
  simultaneously under review at any other archival venue, nor may substantially overlapping
  material be published elsewhere in the interim (the precise 2027 wording must be re-verified
  against the live CFP).
- The P09 STOP signal in `research/venue2027/GATES/PHASE_GATE_MATRIX.md` ("Dual archival submission
  or invented acceptance") applies: dual submission is forbidden; no acceptance may be claimed or
  implied anywhere.

## 9. verification_status and re-verification protocol

- Current status: **UNVERIFIED** (as of 2026-11-15). The live CFP was not fetched during this task;
  no network fetch of `pstnet.ca` occurred.
- Conversion-time protocol: a human must (1) fetch the live CFP and registration pages, (2) rewrite
  any row that becomes verified **with the verification URL and an ISO date on the same line**,
  (3) record the amounts in the sponsor request packet (§11), and (4) only then may `decision`
  move off HOLD via a fresh task run.

## 10. decision and action ledger

- **Decision: HOLD.**
- Rationale: experiments are not released yet (P05–P08 upstream), every cost and deadline fact is
  UNVERIFIED, and the venue's 2027 fee and support specifics are unpublished or unfetched. HOLD is
  the only honest state.
- **No submission action was taken** by this task: no manuscript was uploaded, no account was
  created, no deadline was entered as verified. **No fee was paid** and no registration, waiver,
  or support application was initiated. **Human authorization is required** before any submission
  or fee action; nothing in this document constitutes such authorization.

## 11. Sponsor request packet (prepared, contingent on live-CFP verification)

The go/no-go packet for the sponsor must contain, each marked UNVERIFIED until cited: registration
tier table (member/non-member/student if offered), author-registration deadline, remote-presentation
policy, author-rate-reduction request path, student-status-proof requirement (if a student rate
exists), and the no-assured-waiver statement from §5. This packet is not an authorization to spend.

---

*Contract: `check_submission() -> Decision` evaluated by
`submission_contract.validate_submission_check` (version 1.0.0); result for this document: all
REQUIRED_FIELDS present, no verified row lacking citation, no assured-waiver claim,
double/simultaneous submission policy stated, decision `HOLD`.*
