# GLHS revision-ready patch set — unit of analysis

Status: **draft for editorial review; not applied to the submitted manuscript**.

Source audited: `CLARA_All_Manuscript_Drafts_2026_LiteratureHardened_v2/01_GLHS_Journal_Revision/main.tex`.
The companion `unit_of_analysis_audit.csv` records the Results/Methods audit. These proposals clarify units and estimands only; they do not add a new experiment or alter a reported result.

| Location | Exact old sentence | Proposed replacement | Evidence / reason | Changes reported result? |
| --- | --- | --- | --- | --- |
| `main.tex:190` | “A second grid used 1, 2, 4, 8, and 16 writers, with five independent profile races per level, for 50 races and 310 writer attempts.” | “A second grid used 1, 2, 4, 8, and 16 writers, with five repeated profile-race schedules per level (50 schedules and 310 writer attempts); these schedules are benchmark repetitions, not independent clinical or model subjects.” | `unit_of_analysis_audit.csv` identifies the absent estimand/aggregation qualification. | No |
| `main.tex:208` | “In the $N=4$ PostgreSQL test, both same-slot and unrelated-slot races produced one atomic winner and three stale rejections with no database error.” | “In the four-writer PostgreSQL race schedule, both same-slot and unrelated-slot races produced one atomic winner and three stale rejections with no database error.” | Avoids a participant-like `N` notation for a writer-count configuration. | No |
| `main.tex:208` | “The contention grid reproduced the expected consequence of one winner per simultaneous profile race: unrelated-slot false-stale rejection was 0 with one writer, 0.50 with two, 0.75 with four, 0.875 with eight, and 0.9375 with sixteen.” | “Across the five repeated schedules at each writer-count configuration, the contention grid reproduced the expected one-winner-per-simultaneous-profile-race consequence: unrelated-slot false-stale rejection was 0 with one writer, 0.50 with two, 0.75 with four, 0.875 with eight, and 0.9375 with sixteen.” | Makes the schedule-level denominator/aggregation visible while retaining each reported value. | No |
| `main.tex:238` table heading | “Effect (pp)” | “Paired-subject risk difference (pp)” | The protocol and Methods use paired subject-level contrasts; this labels the displayed estimand without changing its values. | No |
| `main.tex:194` | “Paired subject-level differences were bootstrapped 1,000 times with seed 20260811; exact two-sided sign tests used only discordant subjects and were Holm-adjusted across all ten tests.” | “Paired subject-level risk differences (Strict THSS minus comparator) were bootstrapped 1,000 times with seed 20260811; exact two-sided sign tests used only discordant subject pairs and were Holm-adjusted across all ten tests.” | Defines the risk-difference direction and the exact-test unit. | No |

No proposed text may be inserted until the journal revision process permits a manuscript update. This patch set intentionally does not address open blockers for mandatory binding on every model-derived path, real governance-writer TOCTOU atomicity, full literature review, or independent adjudication.
