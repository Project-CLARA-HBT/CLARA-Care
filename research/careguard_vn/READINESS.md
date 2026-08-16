# CareGuard-VN readiness

Status: **NOT RUN — external validation not started**.

No independent Vietnam product source, current frozen RxNorm release, locked split, or oracle-identity execution currently exists. A controlled DDInter 2.0 positive-reference snapshot and a five-record DailyMed current-SPL regulatory-confirmation subset are retained outside git with validated hash inventories, but they are two source roles only and cannot form a benchmark or negative set. The legacy DAVIDrug endpoint is currently unsuitable for acquisition (HTTP 404); the DAV public-service root later showed maintenance, and a separate official YDCT search portal is explicitly incomplete for current status. Although the NLM RxNorm files page labels the current prescribable release no-license-required, its exact 2026-07-06 URL redirected this program to UTS login, so no payload is available; `source_acquisition_status.md` records the access evidence. Historical DrugBank output remains stale same-source conformance only and is not evidence for this study.

No false-clear, automatic-coverage, accuracy, or clinical-coverage claim is permitted.

`evaluation/careguard_external/source_manifest.py` now rejects metadata probes,
unresolved terms, missing raw-retention locations, incomplete record-hash
inventories, a source set without all four independent roles, and duplicate
declared source identities, source URLs, or payload hashes across nominal
roles. It is an
acquisition gate only; the DDInter manifest passes individual-source validation,
but no complete four-role source set currently passes it.

The repository now has a fail-closed authorized-RxNorm acquisition path that
requires a real ZIP and published MD5 before emitting a source manifest with
full RRF-row inventory. It rejects the observed login HTML and has not acquired
any payload; the terminology and Vietnam identity blockers remain unchanged.

Literature lock: CrossDDI is the nearest DDI comparison point. CareGuard-VN
must not claim novelty for generic normalization, abstention, evidence-grounded
DDI reasoning, or standard DDI benchmark construction. Its only prospective
contribution is source-bound identity gating evaluated on independently frozen
Vietnam product identity and DDI oracle sources.
