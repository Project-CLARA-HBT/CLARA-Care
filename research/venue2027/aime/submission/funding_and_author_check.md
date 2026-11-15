# AIME 2027 · Funding, registration and author check (AIME-funding, phase P09)

> **Task:** `AIME-funding` · **Venue:** `aime` · **Phase:** `P09` · **Contract version:** `1.0.0`
>
> **Paper:** *Counterfactual Clinical Workflow Safety under Changing Consent and Medication Histories*
> **Dependencies satisfied:** `AIME-scope` PASS, `SH-venue_formats` PASS (proof reports and logs under
> `research/venue2027/proof/`).
> **Base SHA of this worktree:** `573d5369abd2e9d35f8039a99cf647e6ba9b3f32`.
>
> **Honesty rule (binding):** every external CFP/fee/waiver/deadline fact in this document is
> UNVERIFIED. This agent cannot fetch the live AIME 2027 CFP, registration site, or fee schedule.
> No line in this document asserts a verified external fact, no deadline is verified by this file,
> and no waiver entitlement is claimed. Nothing in this document authorizes a submission or a
> payment. AIME 2027 (Artificial Intelligence in Medicine) is a Springer LNCS/LNAI proceedings
> venue; the proceedings-series attribution itself is a candidate classification from the AIME
> SPEC and is re-verified against the live CFP at submission time.

## 0. Ethics review boundary (explicit, P09 gate)

This deliverable concerns submission logistics only. The underlying study is **synthetic-only**:
all cases come from the registered dataset `synthetic-aime-2027` (provenance `generated_synthetic`,
per `research/venue2027/_shared/data_ethics_and_irb.md`), with no real PHI/PII. **No
human-involved research has been performed or is authorized by this document.** If the study is
extended to involve humans in any research capacity (clinician reviewers beyond the synthetic-only
boundary, human-subjects data collection, or any interaction with patients or patient data), it
requires **independent ethics review (IRB/REC or equivalent) before that work begins** — review by
the authors, by this agent, or by the venue is not a substitute. The blinded independent clinician
adjudication contract in `research/venue2027/aime/novelty_contract.md` §5.0 is a *prospective*
requirement gated on human recruitment, compensation terms, and this independent ethics review; no
clinical-validity claim exists or may be made until all of those are satisfied. This
synthetic-only/ethics-review boundary statement is an internal policy statement, not a verified
external fact.

## 1. Machine-readable check block

The labeled lines below are the contract surface consumed by
`research/venue2027/_shared/tools/submission_contract.py` (all fields REQUIRED).

- cfp_url: https://aime27.aimedicine.info/call-for-papers/ (per
  `research/venue2027/CONTEXT/PAPERS/aime/SPEC.md`; live CFP not fetched; re-verify at submission)
- template: Springer proceedings template (LNCS/LNAI candidate per AIME SPEC section 0
  "Submission formatting"); arXiv or any preprint layout is NOT submission format; the official
  2027 template file and author kit are not yet verified (live CFP not fetched; re-verify at
  submission)
- page_limit: not established for 2027 (candidate AIME SPEC records 10-page full / 5-page short
  including references — not established; live CFP not fetched; re-verify at submission)
- fee_or_registration: UNVERIFIED — candidate AIME SPEC records an accepted paper requiring one
  FULL registration (EUR 700 early claim) and states a student-only EUR 500 registration does not
  cover an accepted paper; **all amounts UNVERIFIED**; budget as nonzero; travel not verified as
  waived (live CFP not fetched; re-verify at submission)
- waiver_path: UNVERIFIED — no waiver program for AIME 2027 has been located by this agent. The
  funding plan in the AIME SPEC (partial student registration grants; apply by 2027-04-30 with
  letter, student proof, and a <=150-word need statement to aime27@amsterdamumc.nl; seek sponsor
  for the remainder) is a *plan*, not an entitlement. No waiver may be presented as assured,
  guaranteed, or automatic (live CFP not fetched; re-verify at submission)
- authorship_and_contribution: contribution-statement format not yet verified; author list and
  order frozen by the human lead before submission, not by this agent; AI systems are not authors
  as a matter of internal policy (live CFP not fetched; re-verify at submission)
- conflicts_policy: all author conflicts of interest must be declared per the official form;
  the HEALTHINF endpoint distinction per
  `research/venue2027/CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md` (row AIME) and the overlap firewall
  in `research/venue2027/aime/novelty_contract.md` §7 apply; the overlap audit must be re-run
  before any submission decision
- simultaneous_submission_policy: double submission is refused — the same manuscript must not be
  under review at AIME 2027 and any other venue concurrently; the exact official wording for 2027
  is not yet verified (live CFP not fetched; re-verify at submission)
- verification_status: UNVERIFIED — live CFP not fetched; re-verify at submission
- decision: HOLD — all verification pending; do not submit, do not pay, do not register until a
  human re-checks the live CFP and records a dated verification

## 2. Verification status detail (per fact)

Every row below carries the same reason: **live CFP not fetched; re-verify at submission**.

| Fact | Candidate value (source: AIME SPEC) | Status |
|---|---|---|
| CFP URL | https://aime27.aimedicine.info/call-for-papers/ | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Abstract deadline | 2027-01-31 (claimed by AIME SPEC) | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Full-paper deadline | 2027-02-07 (claimed by AIME SPEC) | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Proceedings series | Springer LNCS/LNAI (candidate) | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Template | Springer proceedings template | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Page limit | 10-page full / 5-page short including references (candidate) | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Anonymity | not established for 2027 | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Author registration | one FULL registration required for accepted paper (EUR 700 early claim); student-only EUR 500 claimed not to cover accepted paper | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Student grant / waiver program | partial student registration grants claimed; existence and terms not established; no entitlement | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Sponsor request timing | claimed: apply by 2027-04-30 to aime27@amsterdamumc.nl after acceptance | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Simultaneous-submission policy | double submission refused as internal policy; official wording not yet verified | UNVERIFIED — live CFP not fetched; re-verify at submission |
| AI-use disclosure requirement | not established for 2027 | UNVERIFIED — live CFP not fetched; re-verify at submission |

## 3. Sponsor / registration request packet (outline)

To be prepared by the human lead **only after paper acceptance** (per AIME SPEC section 0 and
section 9: apply for partial student registration grants by the claimed 2027-04-30 date with
letter, student proof, and a <=150-word need statement; concurrently seek school or industry
sponsorship for the remaining full fee/travel). This packet is an outline; nothing has been sent,
requested, or committed.

1. **Cover request (1 page):** paper title, AIME 2027 acceptance status and paper ID, presenting
   author name and role, total requested amount, itemized budget (registration, travel, lodging),
   and explicit statement that amounts are estimates pending the official fee schedule.
2. **Fee evidence:** the official AIME 2027 registration page (URL + ISO capture date to be
   recorded at verification time; currently UNVERIFIED) and the author-registration requirement
   quote.
3. **Waiver / grant evidence:** the official AIME 2027 student registration-grant or waiver page
   (URL + ISO capture date to be recorded at verification time; currently UNVERIFIED — existence
   not established). If none exists, this section states "no venue waiver program located; not
   assured".
4. **Student status proof:** enrollment certificate or registrar letter for the presenting author,
   current within the registration period.
5. **Contribution statement:** per-author contribution block matching the manuscript, in the
   format the verified CFP/author guide requires.
6. **Conflict and overlap statement:** declared conflicts, plus the overlap-audit conclusion
   (HEALTHINF distinction, row AIME in `PREVIOUS_ANTI_OVERLAP_MATRIX.md`).
7. **Budget cap acknowledgment:** infrastructure-agent cost caps apply; no nonrefundable
   registration is purchased before gate G9 (cost and presentation feasibility verified).
8. **Sign-off line:** human authorization signature/date for any payment or submission action.

## 4. Action ledger

- No submission action was taken. No account was created, no PDF was uploaded, no deadline was
  exercised.
- No fee was paid and no registration was purchased.
- No waiver was requested; no waiver is claimed as granted, assured, or automatic.
- No email was sent to AIME organizers; the post-acceptance grant application and sponsor-request
  steps are human tasks.
- **Human authorization is required** for every external action above; this document is an
  internal readiness artifact, not an authorization.

## 5. Re-verification checklist at submission time (human)

1. Fetch the live AIME 2027 CFP at the official URL above; record URL + ISO capture date next to
   each fact in section 2; promote rows to the verified state only when a URL and an ISO date are
   recorded on the same line.
2. Re-check proceedings series (LNCS/LNAI), template, page limit, anonymity, and AI-use disclosure
   against the live CFP and author guide.
3. Re-check registration fees, the full-registration requirement for accepted papers, and any
   waiver/student-grant program; update `fee_or_registration` and `waiver_path` with dated
   citations.
4. Re-run the overlap audit and re-read the official simultaneous-submission policy; record it.
5. Re-run the ethics-boundary check in section 0: any human-involved extension requires
   independent ethics review **before** that work starts; synthetic-only status must still hold.
6. Freeze the author list and contribution statement; collect conflict declarations.
7. Record the final go/no-go decision; flip `decision` away from HOLD only after steps 1–6 are
   complete and dependencies (released study evidence per P09 gate) hold.

---

**Decision: HOLD** — submission readiness is unverified; no external submission or fee action was
taken and human authorization is required before any such action.
