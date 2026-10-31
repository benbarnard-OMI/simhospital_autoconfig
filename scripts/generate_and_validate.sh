#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
NPI="${1:-1730209545}"
OUTPUT_DIR="${2:-$PROJECT_ROOT/tmp-config-$NPI}"
VALIDATOR="$SCRIPT_DIR/validate_with_simulator.sh"

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
    --output-dir "$OUTPUT_DIR"

echo ""
echo "=== Validating configs with simulator ==="
# `|| VALIDATOR_EXIT=$?` rather than a bare call: under `set -e` a non-zero exit
# would abort here, skipping the cleanup below and leaking the temp directory.
VALIDATOR_EXIT=0
bash "$VALIDATOR" "$OUTPUT_DIR" || VALIDATOR_EXIT=$?

echo ""
echo "=== Cleaning up ==="
rm -rf "$OUTPUT_DIR"

exit $VALIDATOR_EXIT
