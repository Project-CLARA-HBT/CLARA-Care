# Encounter identity and medication projection identity on UCI 296

## Development study

How often do two distinct encounters for the same person have identical values on the medication projection? A content digest can identify identical content across encounters. A receipt that must distinguish disclosure *instances* therefore needs an instance identifier in addition to content identity. The empirical endpoint is the frequency of this distinction in one external dataset.

Use the source ZIP bound by the tracked diabetes_130_us_hospitals source manifest. Include all encounters. For each person with at least two distinct encounters select the first two in source-file order. File order is only a reproducible sampling rule. Neither event time nor knowledge time is inferred. Count each eligible person once. Retain singleton counts and report the number of rows beyond the first pair. Duplicate encounter IDs, absent required columns, or missing subject or encounter keys invalidate the run.

Project the 23 named medication-status columns from the Diabetes-130 adapter with their original categorical values, preserving explicit missingness. Exclude demographics, encounter and subject identifiers, utilization, diagnoses and outcomes from this projection. Compute the production GLHS projection digest on both dictionaries. Compare digest equality against direct equality of all 23 source strings. As a sensitivity analysis, reduce each vector to drug presence (No = absent, Down/Steady/Up = present, missing = unknown). Reject unexpected categories. Count pairs equal on the full projection, pairs equal only on presence, and pairs different on presence. Report any digest disagreement, including a nonzero result.

Report only aggregate finite-cohort counts and denominators. This describes content repetition and loss of distinctions under a coarser representation. It estimates neither clinical appropriateness nor a stale-write or disclosure failure rate. No classifier, causal treatment effect, tuning, or test-set claim is involved. This study is separate from sealed GLHS experiments and the FMC preprint.

Source attribution: John Clore, Krzysztof Cios, Jon DeShazo and Beata Strack, *Diabetes 130-US Hospitals for Years 1999–2008*, UCI Machine Learning Repository, CC BY 4.0. [Dataset and citation](https://archive.ics.uci.edu/dataset/296/diabetes+130-us+hospitals+for+years+1999-2008).
