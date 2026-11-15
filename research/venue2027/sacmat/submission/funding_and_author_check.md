# SACMAT 2027 · Funding, registration and author check (SACMAT-funding, phase P09)

> **Task:** `SACMAT-funding` · **Venue:** `sacmat` · **Phase:** `P09` · **Contract version:** `1.0.0`
>
> **Paper:** *PolicyTrace: Temporal Conformance Testing of Delegated Consent across Heterogeneous
> Policy Engines*
> **Dependencies satisfied:** `SACMAT-scope` PASS, `SH-venue_formats` PASS (proof reports and logs
> under `research/venue2027/proof/`).
> **Base SHA of this worktree:** `573d5369abd2e9d35f8039a99cf647e6ba9b3f32`.
>
> **Honesty rule (binding):** every external CFP/fee/waiver fact in this document is UNVERIFIED.
> This agent cannot fetch the live SACMAT 2027 CFP, the ACM publication fee schedule, or any
> registration page. No line in this document asserts a verified external fact, no deadline is
> verified by this file, and no waiver entitlement is claimed. Nothing in this document
> authorizes a submission or a payment. SACMAT is an ACM venue (ACM acmart template, ACM
> publication fees/registration regime); the fee facts below are candidate values from
> `research/venue2027/CONTEXT/PAPERS/sacmat/SPEC.md` only.

## 1. Machine-readable check block

The labeled lines below are the contract surface consumed by
`research/venue2027/_shared/tools/submission_contract.py` (all fields REQUIRED).

- cfp_url: https://www.sacmat.org/2027/call-for-papers.php (per
  `research/venue2027/CONTEXT/PAPERS/sacmat/SPEC.md`; live CFP not fetched; re-verify at
  submission)
- template: ACM acmart sigconf (candidate per SACMAT SPEC section 0 "Submission formatting");
  track labels and limits are mandatory and must be set exactly as the live CFP requires; arXiv
  draft is NOT submission format; official 2027 acmart settings not yet verified (live CFP not
  fetched; re-verify at submission)
- page_limit: not established (candidate SACMAT SPEC recorded Dataset/Tool track 5 pages plus
  1 bibliography/appendix, main-track length not recorded; live CFP not fetched; re-verify at
  submission)
- fee_or_registration: UNVERIFIED — candidate spec lists potential ACM 2027 APC of USD 500 (ACM
  member) or USD 750 (nonmember) PLUS full author registration and in-person presentation; all
  amounts are candidates, budget as nonzero, and no institutional coverage is established (live
  CFP and ACM fee schedule not fetched; re-verify at submission)
- waiver_path: UNVERIFIED — no waiver program for SACMAT 2027 has been verified by this agent.
  The funding plan in the SACMAT SPEC (check ACM Open institutional membership and the ACM
  discretionary APC-waiver route first; ask host organizers about student support) is a *plan*,
  not an entitlement. No waiver may be presented as assured or automatic; approval is at ACM's
  and the organizers' sole discretion (live CFP not fetched; re-verify at submission)
- authorship_and_contribution: per-author contribution statement expected in the ACM style but
  exact 2027 format not yet verified; author list, order and ORCIDs frozen by the human lead
  before submission, not by this agent (live CFP not fetched; re-verify at submission)
- conflicts_policy: all author conflicts of interest must be declared per the official ACM
  conflict form; the GovMut corpus distinction per
  `research/venue2027/_shared/PREVIOUS_ANTI_OVERLAP_MATRIX.md` applies (PolicyTrace studies
  semantic conformance of delegated-consent timelines; GovMut studies mutant-adequacy testing
  strategy; no recycled mutant scores); the overlap audit must be re-run before any submission
  decision
- simultaneous_submission_policy: double submission is refused — per ACM policy, a manuscript
  under review at SACMAT 2027 must not be simultaneously under review at any other archival
  venue, and must not substantially duplicate the authors' own published or concurrently
  submitted work; dual archival submission is a hard STOP signal in
  `research/venue2027/GATES/PHASE_GATE_MATRIX.md` (P09). The exact official 2027 wording is not
  yet verified (live CFP not fetched; re-verify at submission)
- verification_status: UNVERIFIED — live CFP not fetched; re-verify at submission
- decision: HOLD — all verification pending; do not submit, do not pay, do not register until a
  human re-checks the live CFP and records a dated verification

## 2. Verification status detail (per fact)

Every row below carries the same reason: **live CFP not fetched; re-verify at submission**.

| Fact | Candidate value (source: SACMAT SPEC) | Status |
|---|---|---|
| CFP URL | https://www.sacmat.org/2027/call-for-papers.php | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Deadline (cycle 2) | 2027-02-12 (claimed by SACMAT SPEC) | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Template | ACM acmart sigconf; track labels/limits mandatory | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Page limit | Dataset/Tool track 5 pages + 1 bibliography/appendix; main track not recorded | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Anonymity | double-blind (candidate) | UNVERIFIED — live CFP not fetched; re-verify at submission |
| ACM Open APC | USD 500 (member) / USD 750 (nonmember), candidate amounts | UNVERIFIED — live CFP and ACM fee schedule not fetched; re-verify at submission |
| Author registration | full registration + in-person presentation expected; amounts not yet verified | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Waiver program | none verified; ACM Open membership / discretionary waiver route is a plan, not an entitlement | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Student status proof | enrollment certificate for presenting author, to be collected at packet time | UNVERIFIED — not yet collected; re-verify at submission |
| Simultaneous-submission policy | double submission refused per ACM policy; official 2027 wording not yet verified | UNVERIFIED — live CFP not fetched; re-verify at submission |

Note: the SPEC-recorded deadline 2027-02-12 lies after today (2026-11-15), but cycle structure,
abstract deadlines and any earlier cycle-1 date must be re-checked against the live CFP before
any plan depends on them; the SPEC is a development plan, not evidence of the official calendar.

## 3. Sponsor / registration request packet (outline)

To be prepared by the human lead **only after paper acceptance** (per SACMAT SPEC section 0 and
section 9: check ACM Open membership and discretionary APC waiver first; seek school or industry
underwriting only after acceptance). This packet is an outline; nothing has been sent, requested,
or committed.

1. **Cover request (1 page):** paper title, SACMAT 2027 acceptance status and paper ID,
   presenting author name and role, total requested amount, itemized budget (APC if the accepted
   route requires it, registration, travel, lodging), and explicit statement that amounts are
   estimates pending the official ACM fee schedule.
2. **Fee evidence:** the official SACMAT 2027 / ACM publication and registration pages (URL +
   capture date to be recorded at verification time; currently UNVERIFIED) and the
   author-registration requirement quote.
3. **Waiver / support evidence:** the official ACM Open membership status of the institution and
   the ACM discretionary APC-waiver page (URL + capture date to be recorded at verification
   time; currently UNVERIFIED — eligibility not established). If no route exists, this section
   states "no waiver program verified; not assured".
4. **Student status proof:** enrollment certificate or registrar letter for the presenting
   author, current within the registration period.
5. **Contribution statement:** per-author contribution block matching the manuscript.
6. **Conflict and overlap statement:** declared conflicts, plus the overlap-audit conclusion
   (GovMut corpus firewall, study `sacmat` in `publication_overlap_registry.yaml`).
7. **Budget cap acknowledgment:** infrastructure-agent cost caps apply; no nonrefundable
   registration is purchased before gate G9 (cost and presentation feasibility verified).
8. **Sign-off line:** human authorization signature/date for any payment or submission action.

## 4. Action ledger

- No submission action was taken. No account was created, no PDF was uploaded, no deadline was
  exercised.
- No fee was paid and no registration was purchased.
- No waiver was requested; no waiver is claimed as granted, assured, or automatic.
- No email was sent to SACMAT organizers or ACM; the membership/waiver check is a human task.
- **Human authorization is required** for every external action above; this document is an
  internal readiness artifact, not an authorization.

## 5. Re-verification checklist at submission time (human)

1. Fetch the live SACMAT 2027 CFP at the official URL above; record URL + ISO capture date next
   to each fact in section 2; promote rows to the verified state only when a URL and an ISO date
   are recorded on the same line.
2. Re-check template (acmart sigconf settings), track labels, page limit, anonymity, and AI-use
   disclosure against the live author guide.
3. Re-check ACM publication fees, author-registration requirement, in-person/remote presentation
   option, and any waiver or APC-support route; update `fee_or_registration` and `waiver_path`
   with dated citations.
4. Re-run the overlap audit and re-read the official simultaneous-submission policy; record it.
5. Freeze the author list and contribution statement; collect conflict declarations.
6. Record the final go/no-go decision; flip `decision` away from HOLD only after steps 1–5 are
   complete and dependencies (released study evidence per P09 gate) hold.

---

**Decision: HOLD** — submission readiness is unverified; no external submission or fee action was
taken and human authorization is required before any such action.
