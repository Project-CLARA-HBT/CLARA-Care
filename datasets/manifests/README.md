# Dataset manifests

Only metadata, checksums, source/license records, and aggregate inspection
results belong here. Raw or normalized patient-level records, archive content,
token salts, credentials, and reviewer identities must remain outside git.

A manifest is evidence only when `scripts/data/freeze_manifest.py` produced it
from a locally present source and the verifier subsequently passed. A registry
entry or an operator report alone is not proof that a dataset was acquired.
