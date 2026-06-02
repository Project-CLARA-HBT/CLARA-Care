#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: $0 <patch|minor|major>

Computes next semantic version tag based on existing git tags matching vX.Y.Z.
Prints the next tag to stdout.
USAGE
}

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 1
fi

bump="$1"
case "$bump" in
  patch|minor|major) ;;
  *)
    echo "[error] bump must be one of: patch, minor, major" >&2
    usage >&2
    exit 1
    ;;
esac

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[error] this script must run inside a git repository" >&2
  exit 1
fi

latest_tag="$(git tag -l 'v[0-9]*.[0-9]*.[0-9]*' --sort=-v:refname | head -n 1 || true)"

if [[ -z "$latest_tag" ]]; then
  major=0
  minor=0
  patch=0
else
  if [[ ! "$latest_tag" =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
    echo "[error] latest semver tag '$latest_tag' is invalid" >&2
    exit 1
  fi
  major="${BASH_REMATCH[1]}"
  minor="${BASH_REMATCH[2]}"
  patch="${BASH_REMATCH[3]}"
fi

case "$bump" in
  patch)
    patch=$((patch + 1))
    ;;
  minor)
    minor=$((minor + 1))
    patch=0
    ;;
  major)
    major=$((major + 1))
    minor=0
    patch=0
    ;;
esac

printf 'v%s.%s.%s\n' "$major" "$minor" "$patch"
