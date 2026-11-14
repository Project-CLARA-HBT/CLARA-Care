# Research and evidence control beyond unit-test green

1. Before collecting research data, sign `preregistration.yaml`: null, alternative, primary outcome, margin (if applicable), variance assumptions, unit, randomization, missingness, planned comparison count, superiority/noninferiority framework, confidence budget and candidate code SHA.
2. Independent oracle must not import any candidate code. For clinical vignettes, reviewers must be blinded to model arm. For security/concurrency, truth labels derive from event sequence and policy/DB ground truth, not candidate reason codes.
3. A single independent schedule or vignette is the unit only if truly sampled independently; repeated calls within one history are clustered. For systems measurements, benchmark runs/replicas are the unit for inferential CIs, not every operation from the same worker.
4. Keep mutually exclusive per-arm outcome counts: eligible, attempted, completed, rejected, abstained, indeterminate, timeout, environment failure, not-run-external. Report inclusion/exclusion causes and predeclared primary denominator.
5. For non-inferiority and benefit, require **two separate gates**: predeclared one-sided safety bound meets margin AND utility improvement meets its inference/decision criterion. A non-significant safety difference is not a certificate.
6. Zero observed forbidden commits yields a confidence bound, not logical proof of all settings. Under independent Bernoulli trials 0 failures in n has one-sided 95% upper bound `1 - 0.05**(1/n)`; correlated histories need adjusted design.
7. Do not optimize seed, subgroup, attack schedule or baseline configuration based on main results. Pilot and sensitivity analysis data belong to development; release manifest must disclose each prospective amendment.
8. Recalculate paired confidence intervals and whole-dataset endpoints from raw events, using independent baseline and candidate signatures. If any expected file is missing, results are incomplete.
9. Do not extrapolate synthetic security results to safe patient treatment. Clinician studies require independent assessment and authorizing ethics/data-use decisions.
10. Policy-changing migrations, immutable GLHS data or production flags require separate, reviewed code changes. Research defaults fail closed and avoid production access.
