#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: $0 --release-tag <vX.Y.Z> --commit-sha <sha> --registry <registry>/<owner>/<repo>

Builds and pushes api/ml/web images to GHCR (or compatible OCI registry).
Tags pushed per service:
- sha-<shortsha>
- <release-tag>
- v<major>.<minor>
- v<major>

Outputs manifest JSON path to stdout.
USAGE
}

release_tag=""
commit_sha=""
registry_repo=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --release-tag)
      release_tag="${2:-}"
      shift 2
      ;;
    --commit-sha)
      commit_sha="${2:-}"
      shift 2
      ;;
    --registry)
      registry_repo="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[error] unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$release_tag" || -z "$commit_sha" || -z "$registry_repo" ]]; then
  echo "[error] missing required arguments" >&2
  usage >&2
  exit 1
fi

if [[ ! "$release_tag" =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
  echo "[error] release tag must match vX.Y.Z, got: $release_tag" >&2
  exit 1
fi

major="${BASH_REMATCH[1]}"
minor="${BASH_REMATCH[2]}"
short_sha="${commit_sha:0:7}"

if ! command -v docker >/dev/null 2>&1; then
  echo "[error] docker is required" >&2
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "[error] jq is required" >&2
  exit 1
fi

manifest_dir="release-artifacts"
mkdir -p "$manifest_dir"
manifest_path="$manifest_dir/image-manifest-${release_tag}.json"

services=("api" "ml" "web")
dockerfiles=(
  "services/api/Dockerfile"
  "services/ml/Dockerfile"
  "apps/web/Dockerfile"
)
contexts=(
  "."
  "."
  "."
)

entries_json="[]"

for i in "${!services[@]}"; do
  service="${services[$i]}"
  dockerfile="${dockerfiles[$i]}"
  context="${contexts[$i]}"

  image_base="${registry_repo}/clara-${service}"
  tag_sha="sha-${short_sha}"
  tag_full="${release_tag}"
  tag_minor="v${major}.${minor}"
  tag_major="v${major}"

  full_sha_ref="${image_base}:${tag_sha}"

  metadata_file="/tmp/metadata-${service}.json"
  rm -f "$metadata_file"

  build_args=()
  if [[ "$service" == "web" ]]; then
    build_args+=(--build-arg "NEXT_PUBLIC_API_URL=/api/v1")
    build_args+=(--build-arg "NEXT_PUBLIC_GRAFANA_URL=/grafana")
  fi

  docker buildx build \
    --platform linux/amd64 \
    --file "$dockerfile" \
    --push \
    --provenance=false \
    --metadata-file "$metadata_file" \
    -t "${image_base}:${tag_sha}" \
    -t "${image_base}:${tag_full}" \
    -t "${image_base}:${tag_minor}" \
    -t "${image_base}:${tag_major}" \
    "${build_args[@]}" \
    "$context"

  digest="$(jq -r '."containerimage.digest" // empty' "$metadata_file")"
  if [[ -z "$digest" || "$digest" == "null" ]]; then
    echo "[error] missing image digest for service $service" >&2
    exit 1
  fi

  entries_json="$(jq -c --arg service "$service" \
    --arg image "$full_sha_ref" \
    --arg digest "$digest" \
    --arg release_tag "$release_tag" \
    --arg commit_sha "$commit_sha" \
    --arg tag_sha "$tag_sha" \
    --arg tag_full "$tag_full" \
    --arg tag_minor "$tag_minor" \
    --arg tag_major "$tag_major" \
    '. + [{
      service: $service,
      image: $image,
      digest: $digest,
      release_tag: $release_tag,
      commit_sha: $commit_sha,
      pushed_tags: [$tag_sha, $tag_full, $tag_minor, $tag_major]
    }]' <<< "$entries_json")"
done

jq -n \
  --arg release_tag "$release_tag" \
  --arg commit_sha "$commit_sha" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg registry_repo "$registry_repo" \
  --argjson images "$entries_json" \
  '{
    release_tag: $release_tag,
    commit_sha: $commit_sha,
    registry_repo: $registry_repo,
    generated_at: $generated_at,
    images: $images
  }' > "$manifest_path"

printf '%s\n' "$manifest_path"
