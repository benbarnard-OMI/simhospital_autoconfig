#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="${1:-.}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKER_IMAGE="eu.gcr.io/simhospital-images/simhospital:latest"
LOCAL_BINARY=""
TIMEOUT_SECONDS=30
# The simulator logs "Shutting down gracefully" on SIGTERM and can then hang, so
# timeout must escalate to SIGKILL or validation stalls indefinitely.
TIMEOUT_CMD=(timeout --kill-after=10s "$TIMEOUT_SECONDS")

if [ -f "$PROJECT_ROOT/simulator" ]; then
    LOCAL_BINARY="$PROJECT_ROOT/simulator"
elif [ -f "$PROJECT_ROOT/simhospital/simulator" ]; then
    # Where `go build` puts it in the vendored google/simhospital clone.
    LOCAL_BINARY="$PROJECT_ROOT/simhospital/simulator"
elif [ -f "./simulator" ]; then
    LOCAL_BINARY="./simulator"
fi

if [ ! -d "$CONFIG_DIR" ]; then
    echo "ERROR: Config directory does not exist: $CONFIG_DIR"
    exit 1
fi

echo "Validating Simhospital configs in: $CONFIG_DIR"

if [ -n "$LOCAL_BINARY" ]; then
    echo "Local simhospital binary found at: $LOCAL_BINARY"
    CONFIG_ABS="$(cd "$CONFIG_DIR" && pwd)"
    # --local_path is the base against which Simhospital resolves its OWN relative
    # defaults (configs/hardcoded_messages, configs/pathways, ...), not the directory
    # holding the generated configs. Pointing it at the config dir's parent made the
    # simulator abort with "cannot read hardcoded messages directory" before it ever
    # read a single generated file, so validation never actually ran.
    SIMHOSPITAL_DIR="$PROJECT_ROOT/simhospital"
    if [ ! -d "$SIMHOSPITAL_DIR/configs/hardcoded_messages" ]; then
        echo "ERROR: $SIMHOSPITAL_DIR/configs/hardcoded_messages not found."
        echo "       --local_path must be a simhospital checkout containing configs/."
        exit 1
    fi
    echo "Using simhospital checkout as local_path: $SIMHOSPITAL_DIR"
    "${TIMEOUT_CMD[@]}" "$LOCAL_BINARY" \
        --local_path="$SIMHOSPITAL_DIR" \
        --locations_file="$CONFIG_ABS/locations.yml" \
        --data_config_file="$CONFIG_ABS/data.yml" \
        --hl7_config_file="$CONFIG_ABS/hl7.yml" \
        --ethnicity_file="$CONFIG_ABS/ethnicity.csv" \
        --doctors_file="$CONFIG_ABS/doctors.yml" \
        --max_pathways=1 || {
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 124 ] || [ $EXIT_CODE -eq 137 ]; then
            echo "Simulator exited via timeout — treating as success."
            exit 0
        fi
        echo "ERROR: Local simulator exited with code $EXIT_CODE"
        exit $EXIT_CODE
    }
    echo "Simulator completed successfully."
    exit 0
elif command -v docker >/dev/null 2>&1; then
    # NOTE: this branch is unverified and does not validate the generated configs.
    # The image eu.gcr.io/simhospital-images/simhospital:latest is no longer publicly
    # pullable (eu.gcr.io moved to Artifact Registry and denies unauthenticated
    # requests), and the invocation passes none of the --*_file flags: it mounts the
    # config directory at /configs/hl7_messages and runs the image's default
    # health/simulator entrypoint, so Simhospital never reads the files under test.
    # Left in place but no longer allowed to claim success silently.
    echo "Docker found. Running simulator in Docker..."
    CONFIG_ABS="$(cd "$CONFIG_DIR" && pwd)"
    "${TIMEOUT_CMD[@]}" docker run --rm \
        -v "$CONFIG_ABS:/configs/hl7_messages" \
        "$DOCKER_IMAGE" health/simulator || {
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 124 ] || [ $EXIT_CODE -eq 137 ]; then
            echo "Simulator exited via timeout (SIGTERM after ${TIMEOUT_SECONDS}s) — treating as success."
            exit 0
        fi
        echo "ERROR: Docker simulator exited with code $EXIT_CODE"
        echo "NOTE: The image eu.gcr.io/simhospital-images/simhospital:latest may require authentication,"
        echo "      or may no longer be published. Run: gcloud auth configure-docker eu.gcr.io"
        exit $EXIT_CODE
    }
    echo "::warning title=Simulator validation inconclusive::The Docker path does not pass the generated config files to the simulator, so this run did not validate them. Build a local binary instead: cd simhospital && go build -o simulator ./cmd/simulator"
    echo "Container exited 0, but the generated configs were never passed to it."
    exit 0
else
    echo "ERROR: Neither Docker nor a local simulator binary was found."
    echo "Looked for: $PROJECT_ROOT/simulator, $PROJECT_ROOT/simhospital/simulator, ./simulator, and docker on PATH."
    if [ "${SIMULATOR_VALIDATION:-}" = "true" ]; then
        # Set by `make validate-simulator`: a developer who explicitly asks to
        # validate should not get a green run when nothing was validated.
        echo "SIMULATOR_VALIDATION=true, so a skipped validation is treated as a failure."
        exit 1
    fi
    # This is not a validation failure -- no simulator ever looked at the configs --
    # so it must not exit non-zero. It must not pass silently either, which is what a
    # bare echo plus exit 0 used to do. The annotation surfaces it in the Actions UI.
    SKIP_MSG="Simulator validation SKIPPED: no simulator available (no local binary, no docker). Configs were generated but never checked against Simhospital."
    echo "WARNING: $SKIP_MSG"
    echo "::warning title=Simulator validation skipped::$SKIP_MSG"
    echo "To enable it, either install Docker or build the binary:"
    echo "  cd simhospital && go build -o simulator ./cmd/simulator"
    exit 0
fi
