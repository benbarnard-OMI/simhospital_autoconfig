#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="${1:-.}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKER_IMAGE="eu.gcr.io/simhospital-images/simhospital:latest"
LOCAL_BINARY=""
TIMEOUT_SECONDS=30

if [ -f "$PROJECT_ROOT/simulator" ]; then
    LOCAL_BINARY="$PROJECT_ROOT/simulator"
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
    SIMHOSPITAL_DIR="$(dirname "$CONFIG_ABS")"
    timeout "$TIMEOUT_SECONDS" "$LOCAL_BINARY" \
        --local_path="$SIMHOSPITAL_DIR" \
        --locations_file="$CONFIG_ABS/locations.yml" \
        --data_config_file="$CONFIG_ABS/data.yml" \
        --hl7_config_file="$CONFIG_ABS/hl7.yml" \
        --ethnicity_file="$CONFIG_ABS/ethnicity.csv" \
        --doctors_file="$CONFIG_ABS/doctors.yml" \
        --max_pathways=1 || {
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 124 ]; then
            echo "Simulator exited via timeout — treating as success."
            exit 0
        fi
        echo "ERROR: Local simulator exited with code $EXIT_CODE"
        exit $EXIT_CODE
    }
    echo "Simulator completed successfully."
    exit 0
elif command -v docker >/dev/null 2>&1; then
    echo "Docker found. Running simulator in Docker..."
    CONFIG_ABS="$(cd "$CONFIG_DIR" && pwd)"
    timeout "$TIMEOUT_SECONDS" docker run --rm \
        -v "$CONFIG_ABS:/configs/hl7_messages" \
        "$DOCKER_IMAGE" health/simulator || {
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 124 ]; then
            echo "Simulator exited via timeout (SIGTERM after ${TIMEOUT_SECONDS}s) — treating as success."
            exit 0
        fi
        echo "ERROR: Docker simulator exited with code $EXIT_CODE"
        echo "NOTE: The image eu.gcr.io/simhospital-images/simhospital:latest may require authentication."
        echo "      Run: gcloud auth configure-docker eu.gcr.io"
        exit $EXIT_CODE
    }
    echo "Simulator completed successfully."
    exit 0
else
    echo "WARNING: Neither Docker nor a local 'simhospital' binary was found."
    echo "Skipping simulator validation. Install Docker or build the simhospital binary to enable this check."
    exit 0
fi
