#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
NPI="${1:-1730209545}"
if [ "$#" -ge 2 ]; then
    OUTPUT_DIR="$2"
    CLEANUP_OUTPUT=false
else
    OUTPUT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/simhospital-config-${NPI}.XXXXXX")"
    CLEANUP_OUTPUT=true
fi
VALIDATOR="$SCRIPT_DIR/validate_with_simulator.sh"

if [ "$CLEANUP_OUTPUT" = true ]; then
    trap 'rm -rf -- "$OUTPUT_DIR"' EXIT
fi

echo "=== Generating configs for NPI $NPI ==="
cd "$PROJECT_ROOT"

# Prefer the project venv; bare python3 only works if the system interpreter
# happens to have pyyaml and requests installed.
PYTHON="$PROJECT_ROOT/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
    PYTHON="python3"
fi
echo "Using interpreter: $PYTHON"

"$PYTHON" -m simhospital_autoconfig generate \
    --npi "$NPI" \
    --strict \
    --output-dir "$OUTPUT_DIR"

echo ""
echo "=== Validating configs with simulator ==="
# `|| VALIDATOR_EXIT=$?` rather than a bare call: under `set -e` a non-zero exit
# would abort here, skipping the cleanup below and leaking the temp directory.
VALIDATOR_EXIT=0
bash "$VALIDATOR" "$OUTPUT_DIR" || VALIDATOR_EXIT=$?

echo ""
if [ "$CLEANUP_OUTPUT" = true ]; then
    echo "=== Cleaning up temporary output ==="
else
    echo "Keeping caller-provided output directory: $OUTPUT_DIR"
fi

exit $VALIDATOR_EXIT
