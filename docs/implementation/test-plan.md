# Master implementation test plan

For every checkpoint, run format/lint/type checks, focused unit tests and the
boundary-specific integration/contract/invariant tests. Run service/web builds
where tooling is present. Record unavailable tooling or dependencies as
`not run` with the command, never as pass.

Required release evidence includes the normal service suites, web lint/type/
test/build, migration upgrade/downgrade checks when migrations change, i18n
catalog parity/scanner checks, secret/PII-log review, `make eval-smoke`, and
`make eval-judge-report`. `make eval-release` must fail closed if its locked
inputs are unmeasured.
