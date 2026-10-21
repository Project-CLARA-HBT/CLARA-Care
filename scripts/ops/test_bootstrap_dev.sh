#!/usr/bin/env bash
# ==============================================================================
# Test Suite for scripts/ops/bootstrap_dev.sh
# Phase: PH01 / Subagent: A09
#
# Validates:
#   1. --help displays usage and returns 0
#   2. --check runs preflight inspection and returns 0 on supported environment
#   3. --verify-research runs hermetic offline runners and returns 0
#   4. Unknown arguments return exit code 2
#   5. Missing or unsupported toolchains return exit code 1
#   6. Non-destructive safety invariant (does not overwrite existing .env)
# ==============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"

PASS_COUNT=0
FAIL_COUNT=0

assert_eq() {
  local test_name="$1"
  local expected="$2"
  local actual="$3"
  if [[ "${expected}" == "${actual}" ]]; then
    echo "  [PASS] ${test_name} (exit=${actual})"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "  [FAIL] ${test_name} (expected ${expected}, got ${actual})"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
}

echo "=== Running test suite for scripts/ops/bootstrap_dev.sh ==="

# Test 1: --help
set +e
bash scripts/ops/bootstrap_dev.sh --help >/dev/null 2>&1
status=$?
set -e
assert_eq "Test 1: --help returns 0" "0" "${status}"

# Test 2: --check (Positive: all core toolchains present)
set +e
check_out="$(bash scripts/ops/bootstrap_dev.sh --check 2>&1)"
status=$?
set -e
assert_eq "Test 2: --check returns 0 on valid toolchains" "0" "${status}"

# Test 2b: verify check output contains key toolchains
if echo "${check_out}" | grep -q "Python 3.12 detected" && \
   echo "${check_out}" | grep -q "Node.js 20 detected" && \
   echo "${check_out}" | grep -q "uv package manager detected"; then
  echo "  [PASS] Test 2b: --check output contains Python 3.12, Node 20, and uv verifications"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "  [FAIL] Test 2b: --check output missing expected toolchain assertions"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi

# Test 3: --verify-research
set +e
research_out="$(bash scripts/ops/bootstrap_dev.sh --verify-research 2>&1)"
status=$?
set -e
assert_eq "Test 3: --verify-research returns 0" "0" "${status}"

# Test 4: Unknown option returns 2
set +e
bash scripts/ops/bootstrap_dev.sh --unknown-flag-for-testing >/dev/null 2>&1
status=$?
set -e
assert_eq "Test 4: Unknown option returns 2" "2" "${status}"

# Test 5: Negative check: Incompatible Node version returns 1
set +e
# Use system node (18.x) by masking nvm node in PATH
fail_out="$(PATH="/usr/bin:/bin" bash scripts/ops/bootstrap_dev.sh --check 2>&1)"
status=$?
set -e
assert_eq "Test 5: Non-Node 20 environment returns 1" "1" "${status}"

# Test 6: Non-destructive invariant: setup-env preserves existing .env
tmp_env="$(mktemp)"
echo "TEST_VARIABLE_PH01_A09=preserved" > "${tmp_env}"

# Run setup-env against existing custom file simulation
set +e
test_env_target=".env.test_mock"
cp "${tmp_env}" "${test_env_target}"
# bootstrap_dev.sh tests .env, so let's verify if .env exists it preserves it
if [[ -f .env ]]; then
  existing_env_checksum="$(sha256sum .env | cut -d' ' -f1)"
  bash scripts/ops/bootstrap_dev.sh --setup-env >/dev/null 2>&1
  new_env_checksum="$(sha256sum .env | cut -d' ' -f1)"
  assert_eq "Test 6: Existing .env is preserved without modification" "${existing_env_checksum}" "${new_env_checksum}"
else
  # If .env does not exist, run setup-env, verify created, and verify second run preserves
  bash scripts/ops/bootstrap_dev.sh --setup-env >/dev/null 2>&1
  env_sha1="$(sha256sum .env | cut -d' ' -f1)"
  bash scripts/ops/bootstrap_dev.sh --setup-env >/dev/null 2>&1
  env_sha2="$(sha256sum .env | cut -d' ' -f1)"
  assert_eq "Test 6: .env idempotently preserved on repeated run" "${env_sha1}" "${env_sha2}"
  rm -f .env
fi
rm -f "${tmp_env}" "${test_env_target}"

echo "=== Test Summary: ${PASS_COUNT} passed, ${FAIL_COUNT} failed ==="
if [[ ${FAIL_COUNT} -gt 0 ]]; then
  exit 1
fi
exit 0
