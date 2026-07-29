#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
lock_file="${repo_dir}/docs/interoperability/fhir-toolchain.lock.json"
fixture_dir="${repo_dir}/services/api/tests/fixtures/fhir"

if [[ -z "${FHIR_VALIDATOR_JAR:-}" || ! -f "${FHIR_VALIDATOR_JAR}" ]]; then
  echo "FHIR_VALIDATOR_JAR must point to the pinned validator_cli.jar" >&2
  exit 2
fi

expected_sha="$(jq -r '.validator.sha256' "${lock_file}")"
actual_sha="$(sha256sum "${FHIR_VALIDATOR_JAR}" | awk '{print $1}')"
if [[ "${actual_sha}" != "${expected_sha}" ]]; then
  echo "FHIR validator checksum mismatch" >&2
  exit 3
fi

java -jar "${FHIR_VALIDATOR_JAR}" \
  "${fixture_dir}/lifemap-summary-r4.json" \
  -version 4.0.1 \
  -tx n/a \
  -output-style compact
