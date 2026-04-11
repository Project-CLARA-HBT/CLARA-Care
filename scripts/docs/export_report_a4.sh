#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

INPUT_MD="${1:-${ROOT_DIR}/bao-cao-thuyet-minh-clara-care-200-trang.md}"
OUT_DIR="${ROOT_DIR}/artifacts/report-export"
MERMAID_DIR="${OUT_DIR}/mermaid"
PREPARED_MD="${OUT_DIR}/bao-cao-thuyet-minh-clara-care-200-trang.rendered.md"
REFERENCE_DOCX="${OUT_DIR}/reference-a4.docx"
OUTPUT_DOCX="${OUT_DIR}/bao-cao-thuyet-minh-clara-care-200-trang-A4.docx"
OUTPUT_PDF="${OUT_DIR}/bao-cao-thuyet-minh-clara-care-200-trang-A4.pdf"
MMDC_PATH="${ROOT_DIR}/.build-tools/node_modules/.bin/mmdc"

if [[ ! -f "${INPUT_MD}" ]]; then
  echo "[error] Input markdown not found: ${INPUT_MD}" >&2
  exit 1
fi
if [[ ! -x "${MMDC_PATH}" ]]; then
  echo "[error] Mermaid CLI not found: ${MMDC_PATH}" >&2
  exit 1
fi

mkdir -p "${OUT_DIR}" "${MERMAID_DIR}"

python3 "${SCRIPT_DIR}/render_mermaid_and_prepare.py" \
  --input "${INPUT_MD}" \
  --output "${PREPARED_MD}" \
  --assets-dir "${MERMAID_DIR}" \
  --mmdc "${MMDC_PATH}"

python3 "${SCRIPT_DIR}/build_reference_docx.py" \
  --output "${REFERENCE_DOCX}"

pandoc "${PREPARED_MD}" \
  --from markdown \
  --to docx \
  --lua-filter "${SCRIPT_DIR}/caption_numbering.lua" \
  --reference-doc "${REFERENCE_DOCX}" \
  --resource-path "${OUT_DIR}:${ROOT_DIR}" \
  --toc \
  --toc-depth=3 \
  --number-sections \
  --standalone \
  --output "${OUTPUT_DOCX}"

libreoffice --headless --convert-to pdf --outdir "${OUT_DIR}" "${OUTPUT_DOCX}" >/dev/null

echo "[ok] DOCX: ${OUTPUT_DOCX}"
echo "[ok] PDF : ${OUTPUT_PDF}"
