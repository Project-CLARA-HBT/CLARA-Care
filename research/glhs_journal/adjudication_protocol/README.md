# GLHS independent adjudication protocol

Status: **READY_FOR_EXTERNAL_ADJUDICATION, NOT RUN**.

Use `evaluation/clinical_adjudication/ANNOTATION_GUIDE.md` and its packet
tooling. A qualified independent curator must supply deidentified records; two
independent qualified reviewers and a distinct adjudicator are mandatory.

Required external controlled artifacts (never fabricate or commit identities):

- reviewer qualification metadata using role codes only;
- blinded packet map and reviewer packet hashes;
- two-reviewer labels preserving original values;
- disagreement log and adjudicator decisions;
- frozen annotation manifest and agreement/kappa output.

`qualification_metadata_schema.json` is a non-attesting pseudonymous template.
The import validator requires a role code plus eligibility and independence
attestations for both reviewers and the distinct adjudicator. It cannot verify
those claims; verification remains the responsibility of the external study
governance process. Before it imports an adjudication, the tooling also requires
the exactly-two reviewer codes and annotation-guide hash to match the blinded
packet manifest that was issued to reviewers.

Until all are collected and validated, no RQ2 clinical-correctness claim is
admissible.
