# DIMVA-funding · Submission, funding, and author check — DIMVA 2027

- **Task:** `DIMVA-funding` (Phase `P09`, venue `dimva`)
- **Contract signature:** `check_submission() -> Decision` (validated by the REQUIRED shared tool
  `research/venue2027/_shared/tools/submission_contract.py`, version `1.0.0`)
- **Paper (context only):** *GovernanceTrace: Detecting Adaptive Authorization-Boundary Probing from
  Minimal Agent Events* — see `research/venue2027/CONTEXT/PAPERS/dimva/SPEC.md`
- **Dependencies satisfied:** `DIMVA-scope` PASS (`research/venue2027/proof/DIMVA-scope.json`),
  `SH-venue_formats` PASS (`research/venue2027/_shared/submission_venue_checklist.md`, audit ok).
- **Base SHA of this worktree:** `573d5369abd2e9d35f8039a99cf647e6ba9b3f32`.
- **Document version:** `dimva-funding-check-v1`
- **Honesty rule (binding):** every external CFP/fee/waiver/deadline fact below is **UNVERIFIED**
  until a human re-checks the official CFP at conversion time. Rows promoted to a verified state
  require both a verification URL and an ISO date on the same line. This document records a
  planning posture, not a commitment; it asserts no DIMVA 2027 fact that the live CFP has not
  established. DIMVA is a Springer LNCS venue: typically there is no separate publication fee for
  the standard proceedings route, but conference registration is expected — and that statement
  itself remains UNVERIFIED for DIMVA 2027 until the live CFP is checked.

## 1. Field summary (machine-checked required fields)

The labeled lines below are the contract surface consumed by
`research/venue2027/_shared/tools/submission_contract.py` (all fields REQUIRED).

- cfp_url: https://www.dimva.org/dimva2027/ (per
  `research/venue2027/CONTEXT/PAPERS/dimva/SPEC.md`; live CFP not fetched; re-verify at submission)
- template: Springer LNCS (candidate per DIMVA SPEC sections 0 and 9 "Submission formatting");
  the official 2027 LNCS template file and any submission-system format check are not yet
  verified (live CFP not fetched; re-verify at submission)
- page_limit: candidate spec: max 18 pages body + 5 bibliography + 2 appendices — not established
  (live CFP not fetched; re-verify at submission)
- fee_or_registration: UNVERIFIED — full registration and in-person presentation expected; DIMVA
  is a Springer LNCS venue where the standard proceedings route typically carries no separate
  publication/APC fee, but conference registration applies and the 2027 fee amount was not
  published in the inspected CFP; budget as nonzero with amounts not yet verified (live CFP not
  fetched; re-verify at submission)
- waiver_path: UNVERIFIED — no waiver program for DIMVA 2027 has been located by this agent. The
  funding plan in the DIMVA SPEC section 0/9 (request student travel sponsorship through
  organizer/society and school/industry; "does not appear travel-free by default") is a *plan*,
  not an entitlement. No waiver may be treated as assured, promised, or automatic (live CFP
  not fetched; re-verify at submission)
- authorship_and_contribution: all listed authors must satisfy authorship; contribution statement
  format not yet established — expected shape is a per-author contribution block, exact 2027
  format not
  established; author list and order are frozen by the human lead before submission, not by this
  agent; the candidate spec is double-blind, so author-identifying information must be withheld
  from the submission PDF until the venue's anonymity requirement is re-verified (live CFP not
  fetched; re-verify at submission)
- conflicts_policy: all author conflicts of interest must be declared per the venue's submission
  mechanism (2027 form not established); the IFIP SEC detection-vs-rejection distinction per
  `research/venue2027/CONTEXT/PREVIOUS_ANTI_OVERLAP_MATRIX.md` and the `dimva` study entry in
  `research/venue2027/_shared/publication_overlap_registry.yaml` (`reuses_archive: []`) apply;
  the overlap audit must be re-run before any submission decision
- simultaneous_submission_policy: double submission is refused — while this manuscript is under
  DIMVA 2027 review it must not be under review at any other archival venue, including the
  sibling IFIP SEC 2027 study, nor may substantially overlapping material be published elsewhere
  in the interim; the exact official 2027 wording is not yet verified (live CFP not fetched;
  re-verify at submission)
- verification_status: UNVERIFIED — live CFP not fetched; re-verify at submission
- decision: HOLD — all verification pending; do not submit, do not pay, do not register until a
  human re-checks the live CFP and records a dated verification

| Field | Value | Status |
|---|---|---|
| `cfp_url` | https://www.dimva.org/dimva2027/ | UNVERIFIED |
| `template` | Springer LNCS (candidate) | UNVERIFIED |
| `page_limit` | 18 + 5 bibliography + 2 appendices (candidate) | UNVERIFIED |
| `fee_or_registration` | registration expected, amount not published | UNVERIFIED |
| `waiver_path` | none located; plan only | UNVERIFIED |
| `authorship_and_contribution` | contribution statement format not yet established | UNVERIFIED |
| `conflicts_policy` | declaration expected; IFIP SEC firewall applies | UNVERIFIED |
| `simultaneous_submission_policy` | double submission refused (internal posture) | UNVERIFIED (venue row) / binding (internal posture) |
| `verification_status` | UNVERIFIED | UNVERIFIED |
| `decision` | HOLD | HOLD |

## 2. Verification status detail (per fact)

Every row below carries the same reason: **live CFP not fetched; re-verify at submission**.

| Fact | Candidate value (source: DIMVA SPEC) | Status |
|---|---|---|
| CFP URL | https://www.dimva.org/dimva2027/ | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Abstract deadline | 2027-02-11 (claimed by DIMVA SPEC) | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Full-paper deadline | 2027-02-18 cycle-2 paper (claimed by DIMVA SPEC) | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Template | Springer LNCS | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Page limit | max 18 pages body + 5 bibliography + 2 appendices | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Anonymity | double-blind (candidate) | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Publication fee (Springer LNCS proceedings route) | typically no separate publication/APC fee for standard LNCS proceedings; NOT verified for DIMVA 2027 | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Author registration | full registration and in-person presentation expected; 2027 fee not published in inspected CFP | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Waiver program | none located; no entitlement | UNVERIFIED — live CFP not fetched; re-verify at submission |
| AI-use disclosure policy | not established for 2027 | UNVERIFIED — live CFP not fetched; re-verify at submission |
| Simultaneous-submission policy | double submission refused as internal policy; official wording not yet verified | UNVERIFIED — live CFP not fetched; re-verify at submission |

Note: the SPEC-recorded deadlines 2027-02-11 / 2027-02-18 are candidate values relative to today
(2026-11-15). They must be re-checked against the live CFP before any plan depends on them; no
deadline in this document is verified and none is relied upon.

## 3. Sponsor / registration request packet (outline)

To be prepared by the human lead **only after paper acceptance** (per DIMVA SPEC section 9:
request student travel sponsorship through organizer/society and school/industry; the venue does
not appear travel-free by default). This packet is an outline; nothing has been sent, requested,
or committed.

1. **Cover request (1 page):** paper title, DIMVA 2027 acceptance status and paper ID, presenting
   author name and role, total requested amount, itemized budget (registration, travel, lodging),
   and explicit statement that amounts are estimates pending the official fee schedule.
2. **Fee evidence:** the official DIMVA 2027 registration page (URL + ISO capture date to be
   recorded at verification time; currently UNVERIFIED) and the author-registration requirement
   quote. The LNCS "no separate publication fee, registration applies" candidate statement must
   be replaced by a dated citation from the live page.
3. **Waiver / travel-support evidence:** the official DIMVA 2027 student travel support or waiver
   page (URL + ISO capture date to be recorded at verification time; currently UNVERIFIED —
   existence not established). If none exists, this section states "no venue waiver program
   located; not assured".
4. **Student status proof:** enrollment certificate or registrar letter for the presenting author,
   current within the registration period.
5. **Contribution statement:** per-author contribution block matching the manuscript.
6. **Conflict and overlap statement:** declared conflicts, plus the overlap-audit conclusion
   (IFIP SEC detection-vs-rejection firewall, study `dimva` in `publication_overlap_registry.yaml`).
7. **Budget cap acknowledgment:** infrastructure-agent cost caps apply; no nonrefundable
   registration is purchased before gate G9 (cost and presentation feasibility verified per DIMVA
   SPEC section 7).
8. **Sign-off line:** human authorization signature/date for any payment or submission action.

## 4. Action ledger

- No submission action was taken. No account was created, no PDF was uploaded, no deadline was
  exercised.
- No fee was paid and no registration was purchased.
- No waiver was requested; no waiver is claimed as granted, assured, or automatic.
- No email was sent to DIMVA organizers; the "ask about student travel support" step is a human
  task.
- **Human authorization is required** for every external action above; this document is an
  internal readiness artifact, not an authorization.

## 5. Re-verification checklist at submission time (human)

1. Fetch the live DIMVA 2027 CFP at the official URL above; record URL + ISO capture date next to
   each fact in section 2; promote rows to the verified state only when a URL and an ISO date are
   recorded on the same line.
2. Re-check template (Springer LNCS author instructions), page limit, anonymity (double-blind),
   and AI-use disclosure against the live author guide.
3. Re-check registration fees, the author-registration requirement, the LNCS proceedings-fee
   posture, and any waiver/travel-support program; update `fee_or_registration` and
   `waiver_path` with dated citations.
4. Re-run the overlap audit and re-read the official simultaneous-submission policy; record it.
5. Freeze the author list and contribution statement; collect conflict declarations.
6. Record the final go/no-go decision; flip `decision` away from HOLD only after steps 1–5 are
   complete and dependencies (released study evidence per the P09 gate in
   `research/venue2027/GATES/PHASE_GATE_MATRIX.md`) hold.

---

**Decision: HOLD** — submission readiness is unverified; no external submission or fee action was
taken and human authorization is required before any such action.
