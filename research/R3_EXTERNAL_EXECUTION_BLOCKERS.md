# R3 External Execution Blockers

**Checked:** 2026-08-19  
**Branch:** `codex/commitloop-phase-a`

This file records execution prerequisites that cannot be manufactured by the
repository. It does not promote any pending protocol to evidence.

| Workstream | Missing prerequisite | Current safe disposition |
|---|---|---|
| GLHS TOCTOU rerun/repetitions | No local Docker or `psql`; no isolated PostgreSQL endpoint/credential in the environment | Protocols remain frozen and unexecuted; no result or seal fabricated |
| GLHS 384-subject malformed audit | The v5-batch5 raw bytes and checksum seal are absent; only a descriptive generated 384-subject record and a separate 2-subject/360-cell artifact are present | Preserve the primary historical claim as unresolved; do not reconstruct or infer the 220 outputs |
| v7 rerun | The previous `/tmp` run was lost at reboot; current `CLARA_ROUTER_API_KEY` is absent | Persistent-storage restart procedure exists in `research/evidence_upgrade/v7_final_status/DEVELOPMENT_RUN_STATUS.md`; no accuracy claim |
| GovRed holdout | Independent human authorship and outcome-blinded expected labels are not available | 39-schedule skeleton remains unexecuted/manual-gated |
| GovMut W9 | Independent human non-equivalence reviewer(s) and signed/blinded dispositions are not available | W9 denominator cannot be promoted; no model review is substituted for human review |
| CareGuard | Existing restricted DAV files do not include an authorized current identity-frame manifest or rights/access approval; the source checklist explicitly rejects them as a source frame | Keep `RESULT-INCOMPLETE`; no DAV crawl, mapping review, or benchmark run |
| PDFs | No `latexmk`, `pdflatex`, `xelatex`, `pandoc`, or equivalent tool is installed; manuscript TeX files are untracked user documents | Source/build/render preflight remains open; no PDF is claimed as rebuilt |

## Required Inputs To Continue

1. A reachable isolated PostgreSQL service and connection details for the GLHS
   rerun/repetition runners, or an authorized VPS session with those services.
2. The v5-batch5 raw output directory plus its original checksum/seal, if the
   384-subject/220-malformed decomposition is to be verified rather than
   permanently reported as unavailable.
3. `CLARA_ROUTER_API_KEY` exported in the execution shell for a fresh persistent
   v7 run. The key must not be committed or pasted into research artifacts.
4. Outcome-blinded, independently human-authored GovRed holdout schedules and
   human W9 non-equivalence review packets/dispositions.
5. Authorized DAV identity-frame delivery with official access terms, release
   identity, record-ID field, and redistribution status; restricted files alone
   do not satisfy that gate.
6. A pinned PDF build toolchain or permission to install one, plus authorized
   tracked manuscript source inputs.

Until these prerequisites exist, changing a status to `DONE`, rerunning with a
different denominator, using restricted DAV data as an identity frame, or
substituting LLM output for human review would violate the R3 rules.
