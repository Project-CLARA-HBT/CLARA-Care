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

On pull requests and main-branch changes that affect `apps/web` (or CI), the
required CI gate runs Vitest and Playwright's `core-experience` suite. The E2E
job installs Chromium plus its system dependencies and uses the Playwright
configuration's standalone production-artifact server; it is not a dev-server
smoke test. Upload its `test-results` and `playwright-report` artifacts on
failure so a startup timeout or browser assertion is diagnosable.
