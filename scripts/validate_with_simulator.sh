#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="${1:-.}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOCAL_BINARY=""
STARTUP_TIMEOUT_SECONDS="${SIMULATOR_VALIDATION_STARTUP_TIMEOUT:-30}"
STOP_GRACE_SECONDS="${SIMULATOR_VALIDATION_STOP_GRACE:-2}"

if [ -f "$PROJECT_ROOT/simulator" ]; then
    LOCAL_BINARY="$PROJECT_ROOT/simulator"
elif [ -f "$PROJECT_ROOT/simhospital/simulator" ]; then
    LOCAL_BINARY="$PROJECT_ROOT/simhospital/simulator"
elif [ -f "./simulator" ]; then
    LOCAL_BINARY="./simulator"
fi

if [ ! -d "$CONFIG_DIR" ]; then
    echo "ERROR: Config directory does not exist: $CONFIG_DIR"
    exit 1
fi

if [ -z "$LOCAL_BINARY" ]; then
    echo "ERROR: Local Simhospital binary not found."
    echo "Looked for: $PROJECT_ROOT/simulator, $PROJECT_ROOT/simhospital/simulator, and ./simulator."
    echo "See README.md for the pinned Bazel build command."
    exit 1
fi

CONFIG_ABS="$(cd "$CONFIG_DIR" && pwd)"
SIMHOSPITAL_DIR="$PROJECT_ROOT/simhospital"
if [ ! -d "$SIMHOSPITAL_DIR/configs/hardcoded_messages" ]; then
    echo "ERROR: $SIMHOSPITAL_DIR/configs/hardcoded_messages not found."
    echo "       --local_path must be a Simhospital checkout containing configs/."
    exit 1
fi

SIM_LOG="$(mktemp)"
SIMULATOR_PID=""
cleanup() {
    if [ -n "$SIMULATOR_PID" ]; then
        kill -KILL "$SIMULATOR_PID" 2>/dev/null || true
        wait "$SIMULATOR_PID" 2>/dev/null || true
    fi
    rm -f -- "$SIM_LOG"
}
trap cleanup EXIT

echo "Validating Simhospital configs in: $CONFIG_ABS"
echo "Using simulator binary: $LOCAL_BINARY"
echo "Using Simhospital checkout as local_path: $SIMHOSPITAL_DIR"

"$LOCAL_BINARY" \
    --local_path="$SIMHOSPITAL_DIR" \
    --locations_file="$CONFIG_ABS/locations.yml" \
    --data_config_file="$CONFIG_ABS/data.yml" \
    --hl7_config_file="$CONFIG_ABS/hl7.yml" \
    --ethnicity_file="$CONFIG_ABS/ethnicity.csv" \
    --doctors_file="$CONFIG_ABS/doctors.yml" \
    --max_pathways=1 >"$SIM_LOG" 2>&1 &
SIMULATOR_PID=$!

# Starting both servers is logged only after the generated config files, doctors,
# locations, demographics, and pathways have loaded. Once that acceptance point is
# reached, stop the long-running simulator intentionally. A startup timeout or early
# simulator exit remains a failure.
STARTUP_TICKS=$((STARTUP_TIMEOUT_SECONDS * 10))
READY=false
for ((tick = 0; tick < STARTUP_TICKS; tick++)); do
    if grep -q "Starting dashboard on address" "$SIM_LOG" && \
       grep -q "Starting metrics server on address" "$SIM_LOG"; then
        READY=true
        break
    fi
    if ! kill -0 "$SIMULATOR_PID" 2>/dev/null; then
        EXIT_CODE=0
        wait "$SIMULATOR_PID" || EXIT_CODE=$?
        cat "$SIM_LOG"
        echo "ERROR: Simulator exited before config acceptance (exit $EXIT_CODE)."
        if [ "$EXIT_CODE" -eq 0 ]; then EXIT_CODE=1; fi
        exit "$EXIT_CODE"
    fi
    sleep 0.1
done

if [ "$READY" != true ]; then
    kill -TERM "$SIMULATOR_PID" 2>/dev/null || true
    sleep "$STOP_GRACE_SECONDS"
    kill -KILL "$SIMULATOR_PID" 2>/dev/null || true
    wait "$SIMULATOR_PID" 2>/dev/null || true
    SIMULATOR_PID=""
    cat "$SIM_LOG"
    echo "ERROR: Simulator did not reach config acceptance within ${STARTUP_TIMEOUT_SECONDS}s."
    exit 124
fi

# Give the server startup a moment to surface bind or initialization errors before
# considering the generated files accepted.
sleep 1
if grep -q "Simulated Hospital exited with errors" "$SIM_LOG" || \
   ! kill -0 "$SIMULATOR_PID" 2>/dev/null; then
    EXIT_CODE=0
    wait "$SIMULATOR_PID" || EXIT_CODE=$?
    cat "$SIM_LOG"
    echo "ERROR: Simulator failed during startup (exit ${EXIT_CODE:-0})."
    if [ "$EXIT_CODE" -eq 0 ]; then EXIT_CODE=1; fi
    exit "$EXIT_CODE"
fi

kill -TERM "$SIMULATOR_PID" 2>/dev/null || true
sleep "$STOP_GRACE_SECONDS"
kill -KILL "$SIMULATOR_PID" 2>/dev/null || true
wait "$SIMULATOR_PID" 2>/dev/null || true
SIMULATOR_PID=""

if grep -q "Simulated Hospital exited with errors" "$SIM_LOG"; then
    cat "$SIM_LOG"
    echo "ERROR: Simulator reported an error after loading the configs."
    exit 1
fi

cat "$SIM_LOG"
echo "Simulator loaded the generated configs successfully."
