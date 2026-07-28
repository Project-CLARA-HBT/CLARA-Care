#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
export LC_ALL=C
export LANG=C

if ! command -v perl >/dev/null 2>&1; then
  echo "[docs-check] perl is required but not found."
  exit 2
fi

echo "[docs-check] scanning docs/*.md (excluding docs/archive)..."

errors=0

is_external_link() {
  local t="$1"
  [[ "$t" =~ ^(https?:|mailto:|tel:|#) ]]
}

normalize_target() {
  local t="$1"
  t="${t#<}"
  t="${t%>}"
  t="${t%\"}"
  t="${t#\"}"
  t="${t%\'}"
  t="${t#\'}"
  t="${t%%#*}"
  t="${t%%\?*}"
  printf "%s" "$t"
}

check_target() {
  local src_file="$1"
  local src_line="$2"
  local kind="$3"
  local raw_target="$4"

  local target
  target="$(normalize_target "$raw_target")"

  [[ -z "$target" ]] && return 0
  is_external_link "$target" && return 0

  if [[ "$target" == /Users/* || "$target" == /home/* || "$target" == /private/* ]]; then
    echo "[docs-check][ERROR] $src_file:$src_line [$kind] absolute local path is forbidden: $target"
    errors=$((errors + 1))
    return 0
  fi

  if [[ "$target" == /* ]]; then
    echo "[docs-check][ERROR] $src_file:$src_line [$kind] absolute path is forbidden: $target"
    errors=$((errors + 1))
    return 0
  fi

  local candidate
  if [[ "$target" == docs/* ]]; then
    candidate="$REPO_ROOT/$target"
  else
    candidate="$(dirname "$src_file")/$target"
  fi

  if [[ ! -e "$candidate" ]]; then
    echo "[docs-check][ERROR] $src_file:$src_line [$kind] missing path: $target"
    errors=$((errors + 1))
  fi
}

while IFS= read -r file; do
  # 1) Markdown links: [text](target)
  while IFS='|' read -r line kind target; do
    check_target "$file" "$line" "$kind" "$target"
  done < <(
    perl -ne '
      while (/\[[^\]]+\]\(([^)]+)\)/g) {
        print "$.:|md-link|$1\n";
      }
    ' "$file"
  )

  # 2) Inline docs path refs in plain text/code blocks/backticks, exclude URL paths.
  while IFS='|' read -r line kind target; do
    check_target "$file" "$line" "$kind" "$target"
  done < <(
    perl -ne '
      while (/(?<![A-Za-z0-9_\/\.-])(docs\/[A-Za-z0-9._\/-]+)/g) {
        print "$.:|inline-docs-ref|$1\n";
      }
    ' "$file" | sort -u
  )

done < <(find docs -type f -name '*.md' ! -path 'docs/archive/*' | sort)

# 3) Explicit ban on machine-specific absolute references in active docs.
while IFS= read -r hit; do
  echo "[docs-check][ERROR] absolute machine path found: $hit"
  errors=$((errors + 1))
done < <(
  if command -v rg >/dev/null 2>&1; then
    # Ignore URL path segments such as https://example.org/home/... while still
    # rejecting machine-specific absolute filesystem paths.
    rg -n -P '(?<![A-Za-z0-9.:])/(Users|home|private)/' \
      docs --glob '!docs/archive/**' || true
  else
    grep -R -nE '/Users/|/home/|/private/' docs --include='*.md' --exclude-dir='archive' || true
  fi
)

if (( errors > 0 )); then
  echo "[docs-check] FAILED with $errors issue(s)."
  exit 1
fi

echo "[docs-check] OK - no broken docs links detected."
