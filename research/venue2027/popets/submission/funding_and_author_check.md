# POPETS · Submission, Funding and Author Check

> **Task:** `POPETS-funding` (Phase `P09`, venue `popets`) · **Version:** `1.0.0` · **Decision date:** 2026-11-15
>
> **Base SHA:** `152c89116069072bcb82678702c7b0d70a0fccfb` · **Branch:** `research/venue2027/tasks/w2-popets-funding`
>
> **Paper:** *Revocation-Complete Future Disclosure for Cached Longitudinal AI Contexts* (scope: `research/venue2027/popets/novelty_contract.md`; threat model: `research/venue2027/popets/threat_model.md`).
>
> **Dependencies satisfied:** `POPETS-scope` (proof: `research/venue2027/proof/POPETS-scope.json`, status PASS) and `SH-venue_formats` (proof: `research/venue2027/proof/SH-venue_formats.json`, status PASS, recorded in `research/venue2027/STATE/completion.json`). No dependency was forged.
>
> **Verification method:** the official PoPETs/PETS pages listed below were fetched live over HTTPS on 2026-11-15 (ISO date) by this agent, e.g. https://petsymposium.org/authors-2027.php (fetched 2026-11-15). Each CONFIRMED row cites the exact URL and fetch date on the same line. Anything not on an official page fetched on that date is UNVERIFIED. This file makes **no** submission and **no** fee/payment action; all actions require explicit human authorization.

## 1. Verification status

- **verification_status: UNVERIFIED** at the registry level (`_shared/venue_checklist.json` popets row remains `UNVERIFIED` until a human re-checks at conversion time).
- This document upgrades individual facts from UNVERIFIED to CONFIRMED **only** where an official URL was fetched live on 2026-11-15, e.g. https://petsymposium.org/cfp27.php (fetched 2026-11-15); every such line carries URL + ISO date inline.
- The candidate SPEC (`research/venue2027/CONTEXT/PAPERS/popets/SPEC.md`) claimed "Verified $0 submission fees and $0 APC" without a URL; that claim was **not** accepted as evidence here — it was re-derived from official pages fetched on 2026-11-15 (see §4), and its exact wording is corrected: the official pages state PoPETs "does not have article processing charges (APCs) or article submission charges", which is a *no-fee policy statement*, not a signed cost schedule.

## 2. cfp_url

- **cfp_url: CONFIRMED** — https://petsymposium.org/cfp27.php (fetched 2026-11-15); author/submission instructions: https://petsymposium.org/authors-2027.php (fetched 2026-11-15); submission server: https://submit.petsymposium.org/ (stated on CFP page, fetched 2026-11-15).
- Target issue per candidate SPEC: Issue 3 (submission deadline 2026-11-30 AoE) or Issue 4 (submission deadline 2027-02-28 AoE). Deadlines CONFIRMED on https://petsymposium.org/cfp27.php (fetched 2026-11-15). As of 2026-11-15 the Issue 3 deadline (2026-11-30) is 15 days away — feasibility depends entirely on upstream scientific gates (P05–P08), which are not done.

## 3. template

- **template: CONFIRMED** — mandatory PoPETs 2027 LaTeX template (`\documentclass[sigconf]{acmart}` + `\usepackage{popets}`), mandatory-use-or-desk-reject, no alternative template offered: https://petsymposium.org/authors-2027.php (fetched 2026-11-15).
- **arXiv-preprint vs PoPETs-template separation (MANDATORY):** the arXiv-formatted working draft is a *draft-only* artifact and is **NOT** a submission format. The submission PDF must be rebuilt from the PoPETs 2027 `acmart`+`popets` template; arXiv style is desk-reject territory for submission. Conversely, posting a pre-print to arXiv is not forbidden by PoPETs ("Preliminary papers posted in arXiv, technical reports, etc. do not by themselves count against the originality of a submission", https://petsymposium.org/authors-2027.php, fetched 2026-11-15) but is *discouraged during review* on the same page (same URL, same date); any arXiv posting decision belongs to the human PI, not to this agent.
- New mandatory sections in the 2027 template (ethical considerations, open science, AI use; excluded from the page limit): https://petsymposium.org/authors-2027.php (fetched 2026-11-15). Camera-ready build environment: TeX Live 2026 (same page, same date).

## 4. fee_or_registration

- **fee_or_registration: CONFIRMED (submission/APC = none)** per https://petsymposium.org/ (fetched 2026-11-15) and https://petsymposium.org/cfp27.php (fetched 2026-11-15). Official statements:
  - "PoPETs does not have article processing charges (APCs) or article submission charges." — https://petsymposium.org/ (fetched 2026-11-15).
  - "PoPETs is self-published and does not have article processing charges or article submission charges." — https://petsymposium.org/cfp27.php (fetched 2026-11-15).
- **Exact APC amount: UNVERIFIED / NOT APPLICABLE as a number.** The task brief instructed marking the exact APC amount UNVERIFIED unless a cited URL+date exists. The official pages fetched 2026-11-15 (https://petsymposium.org/, https://petsymposium.org/cfp27.php, both fetched 2026-11-15) state a *no-APC policy* rather than an APC figure, so there is no amount to verify; the policy statement itself is cited inline, and the *absence of any numeric APC* is the honest reading. If a human later finds an APC figure on an official page, this row must be re-opened.
- **No guaranteed-waiver claim:** no waiver is needed under the no-APC policy above, and **no waiver approval is claimed or guaranteed by this document**. If any paid optional service or conference attendance is involved, standard waiver/bursary paths would go through the symposium's stipend/bursary chairs (Stipend Chairs listed as "TBD" on https://petsymposium.org/cfp27.php, fetched 2026-11-15) — route exists only when a human decides to attend, and nothing here presumes approval.
- **In-person attendance / PETS 2027 conference:** the symposium is PETS 2027, July 19–24, 2027, Delft, The Netherlands (https://petsymposium.org/, fetched 2026-11-15). In-person attendance "is not strictly required for publication in the proceedings" (https://petsymposium.org/cfp27.php, fetched 2026-11-15). Conference registration fees, student rates, stipends, and student-status proof requirements: **UNVERIFIED** — no fee schedule was published on the pages fetched 2026-11-15. Budget for attendance must therefore be modeled as a **nonzero unknown** until the human PI checks the registration page when it opens.

## 5. page_limit

- **page_limit: CONFIRMED** — submissions/resubmissions: at most **12 typeset pages main body**, excluding the three 2027-mandatory sections (ethics, open science, AI use), acknowledgements, bibliography, and clearly-marked appendices; exceeding 12 pages is automatic desk-reject. Revise-decision and camera-ready get 13 main-body pages. Max 4 concurrent submissions per author per issue (new for 2027, starting issue 3). Source: https://petsymposium.org/authors-2027.php (fetched 2026-11-15).

## 6. waiver_path

- **waiver_path: no APC waiver required under the confirmed no-fee policy (see §4; statements cited https://petsymposium.org/ and https://petsymposium.org/cfp27.php, both fetched 2026-11-15).** For optional PETS attendance costs, the symposium historically offers stipends/bursaries via the Stipend Chairs (listed "TBD" for 2027 on https://petsymposium.org/cfp27.php, fetched 2026-11-15); **this document does NOT guarantee any waiver, stipend, or bursary**. Any application is a separate human decision after publication is secured.

## 7. authorship_and_contribution

- **authorship_and_contribution: CONFIRMED (policy)** — generative AI tools **cannot be listed as authors**; human authors must have made substantial intellectual contributions (ACM-based authorship criteria); mandatory AI-use disclosure section; violations may lead to desk rejection or reporting to institutions. Source: https://petsymposium.org/authors-2027.php (fetched 2026-11-15).
- For this paper: the author list is **not decided by this agent**. Human authorization is required for author order, affiliation listing, and the CRediT-style contribution statement. The mandatory ethics / open-science / AI-use sections will be populated by humans; this agent's AI assistance must be disclosed there per policy (same URL, same date).

## 8. conflicts_policy

- **conflicts_policy: CONFIRMED (policy)** — authors declare conflicts with PC members during submission; clear cases: shared institutional affiliation at submission time, advisor/advisee ever, co-author within past two years or current collaborator; other forms must be raised with the chairs. Source: https://petsymposium.org/authors-2027.php (fetched 2026-11-15).
- Internal overlap firewall (repo-side, still binding): PoPETs↔PST cache-privacy distinction per `research/venue2027/_shared/publication_overlap_registry.yaml` and the anti-salami matrix; the E15–E22/GovRed/GovMut archive-reuse refusal from `research/venue2027/popets/novelty_contract.md` §5 carries into submission unchanged.

## 9. simultaneous_submission_policy

- **simultaneous_submission_policy: CONFIRMED (prohibited)** — "Submitted papers must not substantially overlap with papers that have been published or that are simultaneously submitted to a journal or a conference with proceedings. Simultaneous submission of the same work to multiple venues ... constitute[s] dishonesty or fraud. ... Double submissions are not permitted and will be desk rejected. PoPETs may share submission information with other venues to detect such cases." Papers stay under review until decision or approved withdrawal; revise-decision papers remain under review and must be formally withdrawn before going elsewhere. Source: https://petsymposium.org/authors-2027.php (fetched 2026-11-15).
- Therefore **no double submission**: while this paper is pending at PoPETs, it may not be simultaneously submitted to DSN, IFIP SEC, ACNS, COMPSAC, AIME, SACMAT, DIMVA, PST, or any other archival venue. If any sibling-venue submission of overlapping material exists, it must be withdrawn or the PoPETs submission blocked (human decision).
- Related confirmed policies: rejected papers must skip one full PoPETs issue before resubmission; resubmissions of papers rejected from *any* venue must include prior reviews plus a summary of changes: https://petsymposium.org/authors-2027.php (fetched 2026-11-15).

## 10. Decision

- **decision: HOLD**
- Rationale: (a) all submission-credential facts above are now cited with URL+date, but `SH-venue_formats`' registry row stays `UNVERIFIED` until a human re-checks the live CFP at conversion time; (b) the scientific pipeline (P05–P08: traces, freeze, confirmatory runs, reproduction) has not run, and Phase P09 requires released study evidence — submitting now would be an invented acceptance path; (c) author list, contribution statement, and any attendance/bursary choice require human authorization; (d) the 15-day runway to the Issue 3 deadline (2026-11-30) is insufficient for the full pipeline, making Issue 4 (2027-02-28) the realistic target.
- **HOLD flips to GO only when a human** (i) re-verifies the live CFP at conversion time, (ii) signs off on released study evidence passing gates G0–G9, (iii) fixes the author list and mandatory sections, and (iv) explicitly authorizes submission.
- **Action taken by this agent: NONE.** No submission was made, no account created on https://submit.petsymposium.org/, no fee paid (there is also nothing to pay under the cited no-fee policy), no waiver/bursary applied for, no pre-print posted. Human authorization is required for every one of these steps.

## 11. Evidence and log provenance

| Fact | Status | Source URL | Fetched (ISO) |
|---|---|---|---|
| CFP URL and issue deadlines (I3 2026-11-30, I4 2027-02-28, AoE) | CONFIRMED | https://petsymposium.org/cfp27.php | 2026-11-15 |
| PETS 2027 location/dates (Delft, July 19–24, 2027) | CONFIRMED | https://petsymposium.org/ | 2026-11-15 |
| No APCs, no submission charges (self-published) | CONFIRMED | https://petsymposium.org/ and https://petsymposium.org/cfp27.php | 2026-11-15 |
| Mandatory PoPETs 2027 acmart+popets LaTeX template; no alternative | CONFIRMED | https://petsymposium.org/authors-2027.php | 2026-11-15 |
| 12-page main-body limit (+1 revise/camera-ready); mandatory sections excluded | CONFIRMED | https://petsymposium.org/authors-2027.php | 2026-11-15 |
| Double/simultaneous submission prohibited; desk-reject; venue info sharing | CONFIRMED | https://petsymposium.org/authors-2027.php | 2026-11-15 |
| Max 4 concurrent submissions per author per issue (2027, from issue 3) | CONFIRMED | https://petsymposium.org/authors-2027.php | 2026-11-15 |
| AI tools cannot be authors; mandatory AI-use disclosure; substantial human contribution | CONFIRMED | https://petsymposium.org/authors-2027.php | 2026-11-15 |
| Conflict-of-interest definition (affiliation / advisor / co-author 2y) | CONFIRMED | https://petsymposium.org/authors-2027.php | 2026-11-15 |
| In-person attendance not strictly required for publication | CONFIRMED | https://petsymposium.org/cfp27.php | 2026-11-15 |
| arXiv pre-prints do not count against originality; posting discouraged during review | CONFIRMED | https://petsymposium.org/authors-2027.php | 2026-11-15 |
| Exact numeric APC amount | UNVERIFIED (no-APC policy statement is the cited fact; no numeric APC exists to verify) | — | — |
| Conference registration fee amounts / student rates / stipend amounts | UNVERIFIED | — | — |
| Stipend/bursary chairs and process for 2027 ("TBD") | UNVERIFIED | — | — |
| Artifact-review 2027 detailed requirements (exists per CFP page; details pending) | UNVERIFIED | — | — |

Fetched pages are archived as plain-text snapshots by the executing agent at `research/venue2027/proof/logs/POPETS-funding.livefetch.log` (raw fetch transcripts with dates, e.g. https://petsymposium.org/authors-2027.php fetched 2026-11-15), so that the rows marked as verified above remain auditable even if the live pages change.
