# ACNS 2027 · Funding, registration and author check (ACNS-funding, phase P09)

> **Task:** `ACNS-funding` · **Venue:** `acns` · **Phase:** `P09` · **Contract version:** `1.0.0`
>
> **Paper:** *SoK: What Can Inference Attestation Prove About AI-Visible Context?* (working title in
> `research/venue2027/acns/novelty_contract.md`: *SoK: Evidence Boundaries of Attestation in
> Tool-Using AI Systems*)
> **Dependencies satisfied:** `ACNS-scope` PASS, `SH-venue_formats` PASS (proof reports and logs
> under `research/venue2027/proof/`).
> **Base SHA of this worktree:** `9b6be889db89c2228c6ea1ac599f0000d03c63a4`.
>
> **Honesty rule (binding):** every external CFP/fee/waiver/deadline fact in this document is
> UNVERIFIED. This agent cannot fetch the live ACNS 2027 CFP, registration site, or fee schedule.
> No line in this document asserts a verified external fact, no deadline is verified by this file,
> and no waiver entitlement is claimed. Nothing in this document authorizes a submission or a
> payment. ACNS 2027 (Applied Cryptography and Network Security) is treated as a Springer LNCS
> proceedings venue per the candidate SPEC; that proceedings-series attribution itself is a
> candidate classification and is re-verified against the live CFP at submission time.

## 0. Ethics review boundary (explicit, P09 gate)

This deliverable concerns submission logistics only. The underlying study is **synthetic-only**:
all coding units and counterexample witnesses come from the registered dataset `synthetic-acns-2027`
(provenance `generated_synthetic`, per `research/venue2027/_shared/data_ethics_and_irb.md`), over a
public literature corpus, with no real PHI/PII. **No human-involved research has been performed or
is authorized by this document.** The ACNS study design requires two independent human coders and
third-party adjudication (`research/venue2027/acns/threat_model.md`, TC5). If that coder recruitment
or any other human-involved research activity is carried out, it requires
**independent ethics review (IRB/REC or equivalent) before that work begins** — review by the
authors, by this agent, or by the venue is not a substitute. No inter-rater agreement (Cohen's
kappa) number exists or may be
asserted in any submission material until coder sessions are actually executed and recorded under
`artifacts/venue2027/acns/<run_id>/manifest.json`. This synthetic-only/ethics-review boundary
statement is an internal policy statement, not a verified external fact.

## 1. Machine-readable check block

The labeled lines below are the contract surface consumed by
`research/venue2027/_shared/tools/submission_contract.py` (all fields REQUIRED).

- cfp_url: https://acns2027.isg.rhul.ac.uk/calls/papers/ (per
  `research/venue2027/CONTEXT/PAPERS/acns/SPEC.md`; live CFP not fetched; re-verify at submission)
- template: Springer LNCS official format (candidate per ACNS SPEC section 0 "Submission
  formatting"); arXiv or any preprint layout is NOT submission format; the official 2027 Springer
  author kit and LNCS template version are not yet verified (live CFP not fetched; re-verify at
  submission)
- page_limit: not established (candidate ACNS SPEC records no page count for the 2027 cycle; LNCS
  volumes commonly use 12–20 page ranges but no number may be budgeted as verified; live CFP not
  fetched; re-verify at submission)
- fee_or_registration: UNVERIFIED — general (non-student) registration and in-person presentation
  expected mandatory per candidate SPEC; no fee amount, tier structure, author-registration
  deadline, or early/late boundary has been located for ACNS 2027; budget registration and UK
  travel as nonzero with all amounts not yet verified (live CFP not fetched; re-verify at
  submission)
- waiver_path: UNVERIFIED — no waiver, student grant, or travel-support program for ACNS 2027 has
  been located by this agent. The SPEC records that the EUR 1,500 best student award is an
  *award*, not pre-acceptance funding, and that the funding plan is to seek affiliated university
  co-author support or corporate underwriting for registration and UK travel — that is a *plan*,
  not an entitlement. No waiver may be presented as assured or automatic (live CFP
  not fetched; re-verify at submission)
- authorship_and_contribution: contribution-statement format not yet verified; all listed authors
  must satisfy authorship criteria; author list and order frozen by the human lead before
  submission, not by this agent; AI systems are not authors as a matter of internal policy
  (live CFP not fetched; re-verify at submission)
- conflicts_policy: all author conflicts of interest must be declared per the official form and the
  venue's submission system; the 2027 mechanism is not established. Internal firewalls: the IFIP
  SEC mechanism distinction per `research/venue2027/CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md`
  (row "ACNS SoK": replay-resistant admission vs SoK bibliographic taxonomy) and the overlap
  firewall in `research/venue2027/acns/novelty_contract.md`; `research/venue2027/_shared/
  publication_overlap_registry.yaml` records `acns.reuses_archive: []` with dataset
  `synthetic-acns-2027`; the overlap audit must be re-run before any submission decision
- simultaneous_submission_policy: double submission is refused — the same manuscript must not be
  under review at ACNS 2027 and any other archival venue concurrently (including the sibling 2027
  studies gated by the anti-overlap matrix), and no acceptance may be claimed or implied anywhere
  (P09 STOP signal "Dual archival submission or invented acceptance"); the exact official 2027
  wording is not yet verified (live CFP not fetched; re-verify at submission)
- verification_status: UNVERIFIED — live CFP not fetched; re-verify at submission
- decision: HOLD — all verification pending; do not submit, do not pay, do not register until a
  human re-checks the live CFP and records a dated verification

## 2. Verification status detail (per fact)

Every row below carries the same reason: **live CFP not fetched; re-verify at submission**.

| Fact | Candidate value (source: ACNS SPEC) | Status |
|---|---|---|
| CFP URL | https://acns2027.isg.rhul.ac.uk/calls/papers/ | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Submission deadline (cycle 2 full) | 2027-01-21 (claimed by ACNS SPEC) | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Proceedings series | Springer LNCS (candidate) | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Template | Springer LNCS official format | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Page limit | not established | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Anonymity | candidate spec: anonymous submission — unverified for 2027 | UNVERIFIED — live CFP not fetched; re-verify at submission |
| SoK track availability | ACNS may not offer a SoK-specific track; scope check required before claiming SoK framing | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Author registration | general (non-student) registration expected mandatory; in-person presentation expected; amounts not yet verified | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Student travel support | existence unknown; SPEC plan is to seek university co-author support or corporate underwriting | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Best student award | EUR 1,500 claimed by SPEC — an award for accepted papers, NOT pre-acceptance funding and NOT a waiver | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Waiver program | none located; no entitlement | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Simultaneous-submission policy | double submission refused as internal policy; official wording not yet verified | UNVERIFIED — live CFP not fetched; re-verify at submission |
| AI-use disclosure requirement | not established for 2027 | UNVERIFIED — live CFP not fetched; re-verify at submission |

Note: the SPEC-recorded cycle-2 full deadline 2027-01-21 is over two months after today
(2026-11-15), but it is a candidate-spec value only; it must be re-checked against the live CFP
before any plan depends on it.

## 3. Sponsor / registration request packet (outline)

To be prepared by the human lead **only after paper acceptance** (per ACNS SPEC section 0 and
section 9: seek affiliated university co-author support or corporate underwriting for registration
and UK travel). This packet is an outline; nothing has been sent, requested, or committed.

1. **Cover request (1 page):** paper title, ACNS 2027 acceptance status and paper ID, presenting
   author name and role, total requested amount, itemized budget (registration, UK travel,
   lodging), and explicit statement that amounts are estimates pending the official fee schedule.
2. **Fee evidence:** the official ACNS 2027 registration page (URL + ISO capture date to be
   recorded at verification time; currently UNVERIFIED) and the author-registration requirement
   quote.
3. **Waiver / support evidence:** the official ACNS 2027 student travel-support or waiver page
   (URL + ISO capture date to be recorded at verification time; currently UNVERIFIED — existence
   not established). If none exists, this section states "no venue waiver program located; not
   assured". The best student award (if the award row verifies) must be described as a competitive
   prize, never as assured pre-acceptance funding.
4. **Student status proof:** enrollment certificate or registrar letter for the presenting author,
   current within the registration period, if any student-discount route is verified to exist.
5. **Contribution statement:** per-author contribution block matching the manuscript, in the
   format the verified CFP/author guide requires.
6. **Conflict and overlap statement:** declared conflicts, plus the overlap-audit conclusion
   (IFIP SEC distinction, row "ACNS SoK" in `PREVIOUS_ANTI_OVERLAP_MATRIX.md`; `acns.reuses_archive:
   []` in `publication_overlap_registry.yaml`).
7. **Budget cap acknowledgment:** infrastructure-agent cost caps apply; no nonrefundable
   registration is purchased before gate G9 (cost and presentation feasibility verified).
8. **Sign-off line:** human authorization signature/date for any payment or submission action.

## 4. Action ledger

- No submission action was taken. No account was created, no PDF was uploaded, no deadline was
  exercised.
- No fee was paid and no registration was purchased; no membership was bought.
- No waiver was requested; no waiver is claimed as granted, assured, or automatic.
- No email was sent to ACNS organizers or to any university/corporate sponsor; the underwriting
  request is a human task.
- **Human authorization is required** for every external action above; this document is an
  internal readiness artifact, not an authorization.

## 5. Re-verification checklist at submission time (human)

1. Fetch the live ACNS 2027 CFP at the official URL above; record URL + ISO capture date next to
   each fact in section 2; promote rows to the verified state only when a URL and an ISO date are
   recorded on the same line.
2. Re-check the proceedings series (Springer LNCS), template/author kit, page limit, anonymity
   stance, SoK-track availability, and AI-use disclosure against the live CFP and author guide.
3. Re-check registration fees, the author-registration requirement and deadline, any
   waiver/travel-support program, and any student-discount tier; update `fee_or_registration` and
   `waiver_path` with dated citations.
4. Re-run the overlap audit and re-read the official simultaneous-submission policy; record it.
5. Re-run the ethics-boundary check in section 0: any human-coder recruitment requires independent
   ethics review **before** that work starts; synthetic-only status must still hold.
6. Freeze the author list and contribution statement; collect conflict declarations.
7. Record the final go/no-go decision; flip `decision` away from HOLD only after steps 1–6 are
   complete and dependencies (released study evidence per P09 gate) hold.

---

**Decision: HOLD** — submission readiness is unverified; no external submission or fee action was
taken and human authorization is required before any such action.
