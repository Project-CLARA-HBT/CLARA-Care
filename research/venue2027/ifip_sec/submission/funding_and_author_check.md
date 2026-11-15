# IFIP SEC 2027 · Funding, registration and author check (IFIP_SEC-funding, phase P09)

> **Task:** `IFIP_SEC-funding` · **Venue:** `ifip_sec` · **Phase:** `P09` · **Contract version:** `1.0.0`
>
> **Paper:** *Cross-Purpose Replay Resistance for Governed AI Context Receipts*
> **Dependencies satisfied:** `IFIP_SEC-scope` PASS, `SH-venue_formats` PASS (proof reports and logs
> under `research/venue2027/proof/`).
> **Base SHA of this worktree:** `573d5369abd2e9d35f8039a99cf647e6ba9b3f32`.
>
> **Honesty rule (binding):** facts marked verified below each carry a verification URL and an ISO
> capture date on the same line (live fetch performed by this agent on 2026-11-15). Facts marked
> UNVERIFIED were not established from an official source on a recorded date — notably the numeric
> fee schedule, which the official registration page states as "Registration fees TBC". No waiver
> entitlement is claimed. Nothing in this document authorizes a submission or a payment.

## 1. Machine-readable check block

The labeled lines below are the contract surface consumed by
`research/venue2027/_shared/tools/submission_contract.py` (all fields REQUIRED).

- cfp_url: CONFIRMED — https://ifipsec.org/cfp.html (42nd IFIP TC-11 International Conference on Information Security and Privacy Protection, SEC 2027, 14–16 June 2027, Linköping University, Sweden); fetched live 2026-11-15
- template: CONFIRMED — Springer proceedings (IFIP AICT series published by Springer), authors must follow Springer's AI guidance for researchers; source https://ifipsec.org/cfp.html fetched live 2026-11-15; the exact Springer author-kit version must be re-checked at the author instructions immediately before submission
- page_limit: CONFIRMED — at most 14 pages including references and appendices, submissions NOT anonymised, PC members are not required to read the appendices so the paper must be intelligible without them; source https://ifipsec.org/cfp.html fetched live 2026-11-15
- fee_or_registration: UNVERIFIED (numeric) — registration page https://ifipsec.org/registration fetched live 2026-11-15 states "Registration fees TBC"; the CFP (https://ifipsec.org/cfp.html, fetched live 2026-11-15) requires at least one author of each accepted paper to register by the author registration date, present in person, and at least one FULL registration per accepted paper; camera-ready 2027-03-15 is due "including registration and payment"; budget MUST be planned as nonzero and amounts remain UNVERIFIED until the official fee schedule is published
- waiver_path: UNVERIFIED — no fee-waiver or registration-waiver program for IFIP SEC 2027 has been located by this agent on https://ifipsec.org/cfp.html or https://ifipsec.org/registration (both fetched live 2026-11-15); the Yves Deswarte Best Student Paper Award (€1,000) and the Computers & Security Best Paper Award ($1,000) are competition prizes per https://ifipsec.org/cfp.html (fetched live 2026-11-15), NOT guaranteed sponsorship and NOT a waiver; the funding plan (apply for a school/industry grant only after acceptance) is a *plan*, not an entitlement, and no waiver may be presented as assured or automatic
- authorship_and_contribution: UNVERIFIED (format) — papers must be original, unpublished, and not under consideration elsewhere, at least one author must register and present in person, and Springer's AI guidance for researchers applies (AI cannot be an author) per https://ifipsec.org/cfp.html fetched live 2026-11-15; the exact contribution-statement format for the IFIP AICT volume is not yet verified; the author list and order are frozen by the human lead before submission, not by this agent
- conflicts_policy: all author conflicts of interest must be declared per the official form at submission time; the ACNS SoK distinction per `research/venue2027/_shared/PREVIOUS_ANTI_OVERLAP_MATRIX.md` and the overlap firewall in `research/venue2027/ifip_sec/overlap_audit.md` apply (novelty vs GLHS R4 / HEALTHINF #97 / GovRed-RIVF / GovMut-SOICT); the overlap audit must be re-run before any submission decision
- simultaneous_submission_policy: CONFIRMED — simultaneous submission and double submission are prohibited: the CFP requires papers to be original, unpublished, and "not submitted to another conference or journal for consideration"; source https://ifipsec.org/cfp.html fetched live 2026-11-15; the same manuscript must therefore not be under review at IFIP SEC 2027 and any other venue (including sibling 2027 studies subject to the anti-overlap matrix)
- verification_status: UNVERIFIED overall — fee amounts, waiver existence, and contribution-statement format remain UNVERIFIED despite the 2026-11-15 live CFP fetch; re-verify at submission
- decision: HOLD — fee amounts are "TBC" on the official registration page and the release gates (G0–G9 in `research/venue2027/CONTEXT/PAPERS/ifip_sec/SPEC.md`) are not yet satisfied; do not submit, do not pay, do not register until a human re-checks the live CFP and records a dated verification

## 2. Verification status detail (per fact)

Facts below were fetched from the live official CFP and registration pages on **2026-11-15**.

| Fact | Value | Status |
|---|---|---|
| Conference identity | 42nd IFIP TC-11 SEC 2027, 14–16 June 2027, Linköping University, Sweden | CONFIRMED — https://ifipsec.org/cfp.html, fetched live 2026-11-15 |
| Proceedings | IFIP AICT series, Springer | CONFIRMED — https://ifipsec.org/cfp.html, fetched live 2026-11-15 |
| Submission deadline | 2026-12-15 (AoE) | CONFIRMED — https://ifipsec.org/cfp.html, fetched live 2026-11-15 |
| Notification | 2027-02-18 | CONFIRMED — https://ifipsec.org/cfp.html, fetched live 2026-11-15 |
| Camera-ready incl. registration and payment | 2027-03-15 | CONFIRMED — https://ifipsec.org/cfp.html, fetched live 2026-11-15 |
| Conference dates | 2027-06-14 → 2027-06-16 | CONFIRMED — https://ifipsec.org/cfp.html, fetched live 2026-11-15 |
| Template | Springer proceedings instructions (IFIP AICT / Springer); Springer AI guidance applies | CONFIRMED — https://ifipsec.org/cfp.html, fetched live 2026-11-15 |
| Page limit | max 14 pages incl. references and appendices; NOT anonymised; intelligible without appendices | CONFIRMED — https://ifipsec.org/cfp.html, fetched live 2026-11-15 |
| Originality / double submission | original, unpublished, not submitted to another conference or journal | CONFIRMED — https://ifipsec.org/cfp.html, fetched live 2026-11-15 |
| Presentation | in-person presentation required; at least one FULL registration per accepted paper; author registration by the author-registration date | CONFIRMED — https://ifipsec.org/cfp.html, fetched live 2026-11-15 |
| Registration fee amounts | official page states "Registration fees TBC" | UNVERIFIED — https://ifipsec.org/registration fetched live 2026-11-15; amounts not yet published |
| Fee waiver / registration waiver | none located | UNVERIFIED — https://ifipsec.org/cfp.html and https://ifipsec.org/registration fetched live 2026-11-15; no waiver program found; existence not established |
| Best Paper Award | Computers & Security (Elsevier) sponsored, $1,000 USD prize + invited extended version | CONFIRMED — https://ifipsec.org/cfp.html, fetched live 2026-11-15; a prize, NOT sponsorship or a waiver |
| Best Student Paper Award | Yves Deswarte Best Student Paper Award, €1,000 EUR prize | CONFIRMED — https://ifipsec.org/cfp.html, fetched live 2026-11-15; a prize, NOT guaranteed sponsorship or a waiver |
| Extended versions | selected papers considered for Elsevier Computers & Security after further review | CONFIRMED — https://ifipsec.org/cfp.html, fetched live 2026-11-15 |
| Author contribution-statement format | not stated on the fetched pages | UNVERIFIED — https://ifipsec.org/cfp.html fetched live 2026-11-15; re-check the Springer IFIP AICT author instructions at submission |

## 3. Funding plan and sponsor / registration request packet (outline)

To be prepared by the human lead **only after paper acceptance** (per IFIP SEC SPEC section 0 and
section 9: apply for a school/industry grant; the best-student-paper prize is not sponsorship).
This packet is an outline; nothing has been sent, requested, or committed. Because registration
fees are "TBC", every amount in the packet is an estimate.

1. **Cover request (1 page):** paper title, IFIP SEC 2027 acceptance status and paper ID, presenting
   author name and role, total requested amount, itemized budget (registration, travel, lodging),
   and explicit statement that amounts are estimates pending the official fee schedule ("TBC" per
   https://ifipsec.org/registration, captured 2026-11-15).
2. **Fee evidence:** the official IFIP SEC 2027 registration page (https://ifipsec.org/registration,
   captured 2026-11-15, fees "TBC") plus the published fee schedule with URL and capture date
   recorded as soon as it is published; currently UNVERIFIED.
3. **Waiver / sponsorship evidence:** no venue waiver program was found on the official CFP or
   registration page (both fetched 2026-11-15); the packet must state "no venue waiver program
   located; not assured" and rely on external (school/industry) grants, not on any venue guarantee.
4. **Student status proof:** enrollment certificate or registrar letter for the presenting author,
   current within the registration period (relevant for any student-rate fee once published and for
   Yves Deswarte Best Student Paper Award eligibility if pursued).
5. **Contribution statement:** per-author contribution block matching the manuscript, in the format
   required by the Springer IFIP AICT author instructions (format UNVERIFIED; re-check at
   submission).
6. **Conflict and overlap statement:** declared conflicts, plus the overlap-audit conclusion (ACNS
   SoK distinction and the GLHS R4 / HEALTHINF #97 / GovRed-RIVF / GovMut-SOICT firewall per
   `research/venue2027/ifip_sec/overlap_audit.md`).
7. **Budget cap acknowledgment:** infrastructure-agent cost caps apply; no nonrefundable
   registration is purchased before gate G9 (cost and presentation feasibility verified; note the
   2027-03-15 camera-ready deadline includes registration and payment).
8. **Sign-off line:** human authorization signature/date for any payment or submission action.

## 4. Action ledger

- No submission action was taken. No account was created, no PDF was uploaded, no deadline was
  exercised.
- No fee was paid and no registration was purchased.
- No waiver was requested; no waiver is claimed as granted, assured, or automatic.
- No email was sent to IFIP SEC 2027 organizers; the funding-grant application step is a human task.
- **Human authorization is required** for every external action above; this document is an internal
  readiness artifact, not an authorization.
- **Action taken by this agent: none** beyond read-only live fetches of
  https://ifipsec.org/cfp.html and https://ifipsec.org/registration on 2026-11-15 and writing this
  internal artifact.

## 5. Re-verification checklist at submission time (human)

1. Re-fetch the live CFP (https://ifipsec.org/cfp.html) and registration page
   (https://ifipsec.org/registration); record URL + ISO capture date next to each fact in section 2;
   promote rows to the verified state only when a URL and an ISO date are recorded on the same line.
2. Re-check the published registration fee schedule when "TBC" is resolved; update
   `fee_or_registration` with dated citations; confirm the full-registration requirement and any
   student rate.
3. Re-check the Springer IFIP AICT author instructions for the exact template/author kit, AI-use
   disclosure wording, and contribution-statement format.
4. Re-run the overlap audit and re-read the official originality/double-submission wording; record
   it.
5. Freeze the author list and contribution statement; collect conflict declarations.
6. Record the final go/no-go decision; flip `decision` away from HOLD only after steps 1–5 are
   complete and the release gates (G0–G9, including G8 venue policy and G9 funding) hold.

---

**Decision: HOLD** — registration fee amounts are unpublished ("TBC") and submission readiness is
unverified; no external submission or fee action was taken and human authorization is required
before any such action.
