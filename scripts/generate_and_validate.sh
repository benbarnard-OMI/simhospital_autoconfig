#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
NPI="${1:-1730209545}"
OUTPUT_DIR="${2:-$PROJECT_ROOT/tmp-config-$NPI}"
VALIDATOR="$SCRIPT_DIR/validate_with_simulator.sh"

echo "=== Generating configs for NPI $NPI ==="
cd "$PROJECT_ROOT"

python3 -m simhospital_autoconfig generate \
    --npi "$NPI" \
    --output-dir "$OUTPUT_DIR"

echo ""
echo "=== Validating configs with simulator ==="
bash "$VALIDATOR" "$OUTPUT_DIR"
VALIDATOR_EXIT=$?

echo ""
echo "=== Cleaning up ==="
rm -rf "$OUTPUT_DIR"

exit $VALIDATOR_EXIT
