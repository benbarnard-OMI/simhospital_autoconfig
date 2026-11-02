#!/usr/bin/env python3
"""Run one deterministic Simhospital pathway against the checked-in config fixture."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_TYPES = ["ORU^R01", "ADT^A01", "ORU^R01", "ADT^A03"]
REQUIRED_SEGMENTS = {
    "ORU^R01": {"MSH", "PID", "PV1", "ORC", "OBR", "OBX"},
    "ADT^A01": {"MSH", "EVN", "PID", "PD1", "PV1", "PV2"},
    "ADT^A03": {"MSH", "EVN", "PID", "PD1", "PV1"},
}
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _message_type(msh: str) -> str:
    fields = msh.split("|")
    if len(fields) < 9 or fields[0] != "MSH":
        raise ValueError("message does not start with a valid MSH segment")
    # MSH-9 may include the optional message structure in component 3.
    return "^".join(fields[8].split("^")[:2])


def validate_hl7_messages(contents: str) -> list[str]:
    """Check the bounded pathway's message order and required HL7 segments."""
    blocks = [block.strip() for block in re.split(r"\n\s*\n", contents.strip()) if block.strip()]
    if len(blocks) != len(EXPECTED_TYPES):
        raise ValueError(f"expected 4 HL7 messages, found {len(blocks)}")

    actual_types: list[str] = []
    for index, block in enumerate(blocks, start=1):
        segments = [line for line in re.split(r"\r\n|\n|\r", block) if line]
        if not segments:
            raise ValueError(f"message {index} is empty")
        message_type = _message_type(segments[0])
        actual_types.append(message_type)
        expected_type = EXPECTED_TYPES[index - 1]
        if message_type != expected_type:
            raise ValueError(
                f"message {index} has type {message_type!r}; expected {expected_type!r}"
            )

        segment_names = {segment[:3] for segment in segments if len(segment) >= 3}
        missing = REQUIRED_SEGMENTS[message_type] - segment_names
        if missing:
            raise ValueError(
                f"message {index} ({message_type}) is missing segments: {', '.join(sorted(missing))}"
            )

    return actual_types


def _find_simulator(project_root: Path) -> Path | None:
    candidates = (
        project_root / "simulator",
        project_root / "simhospital" / "simulator",
        Path.cwd() / "simulator",
    )
    return next((path for path in candidates if path.is_file() and os.access(path, os.X_OK)), None)


def _run_dir() -> Path:
    parent = os.environ.get("SIMULATOR_E2E_ARTIFACT_PARENT")
    return Path(tempfile.mkdtemp(prefix="simhospital-e2e-", dir=parent))


def _cleanup_run_dir(run_dir: Path) -> None:
    try:
        shutil.rmtree(run_dir)
    except OSError as exc:
        print(
            f"WARNING: validation passed, but artifacts remain in {run_dir}: {exc}",
            file=sys.stderr,
        )


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    simhospital_dir = project_root / "simhospital"
    fixture_dir = project_root / "tests" / "fixtures" / "1730209545"
    run_dir: Path | None = None
    process: subprocess.Popen[bytes] | None = None

    try:
        run_dir = _run_dir()
        log_path = run_dir / "simulator.log"
        output_path = run_dir / "messages.hl7"
        simulator = _find_simulator(project_root)
        if simulator is None:
            raise RuntimeError("local Simhospital binary not found; see README.md for the build command")
        if not (simhospital_dir / "configs" / "pathways").is_dir():
            raise RuntimeError(f"Simhospital checkout not found at {simhospital_dir}")
        required_files = ("locations.yml", "data.yml", "hl7.yml", "ethnicity.csv", "doctors.yml")
        missing = [name for name in required_files if not (fixture_dir / name).is_file()]
        if missing:
            raise RuntimeError(f"fixture {fixture_dir} is missing: {', '.join(missing)}")

        command = [
            str(simulator),
            f"--local_path={simhospital_dir}",
            f"--locations_file={fixture_dir / 'locations.yml'}",
            f"--data_config_file={fixture_dir / 'data.yml'}",
            f"--hl7_config_file={fixture_dir / 'hl7.yml'}",
            f"--ethnicity_file={fixture_dir / 'ethnicity.csv'}",
            f"--doctors_file={fixture_dir / 'doctors.yml'}",
            f"--pathways_dir={simhospital_dir / 'configs' / 'pathways'}",
            "--pathway_manager_type=deterministic",
            "--pathway_names=test_pathway_four_messages",
            "--pathways_per_hour=3600",
            "--sleep_for=100ms",
            "--max_pathways=1",
            "--output=file",
            f"--output_file={output_path}",
        ]
        timeout_seconds = int(os.environ.get("SIMULATOR_E2E_TIMEOUT_SECONDS", "45"))
        if timeout_seconds <= 0:
            raise RuntimeError("SIMULATOR_E2E_TIMEOUT_SECONDS must be greater than zero")

        print(f"Running {simulator} with fixture {fixture_dir}")
        with log_path.open("wb") as log_file:
            process = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT)
            try:
                exit_code = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                _stop_process(process)
                process = None
                raise RuntimeError(f"simulator did not finish within {timeout_seconds}s") from exc
        process = None

        log_text = ANSI_ESCAPE.sub("", log_path.read_text(errors="replace"))
        if exit_code != 0:
            raise RuntimeError(f"simulator failed with exit code {exit_code}; see simulator.log")
        # This Simhospital revision logs its normal dashboard shutdown as an
        # error after max_pathways is reached. Accept that one known shutdown
        # message; other simulator errors remain failures.
        errors = [
            line
            for line in log_text.splitlines()
            if "ERRO" in line or "FATA" in line
        ]
        unexpected_errors = [
            line
            for line in errors
            if not (
                "Simulated Hospital exited with errors" in line
                and "http: Server closed" in line
            )
        ]
        if unexpected_errors:
            raise RuntimeError(f"simulator reported an error; see simulator.log: {unexpected_errors[-1]}")
        if "Pathway finished!" not in log_text:
            raise RuntimeError("simulator exited before the selected pathway finished")
        if "Messages successfully sent by the fileSender: 4" not in log_text:
            raise RuntimeError("simulator did not report sending exactly four HL7 messages")
        if not output_path.is_file():
            raise RuntimeError("simulator exited without creating the HL7 output file")

        message_types = validate_hl7_messages(output_path.read_text(errors="replace"))
        print(f"End-to-end validation passed: {', '.join(message_types)}")
        _cleanup_run_dir(run_dir)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        if process is not None:
            _stop_process(process)
        print(f"ERROR: {exc}", file=sys.stderr)
        if run_dir is not None:
            log_path = run_dir / "simulator.log"
            if not log_path.exists():
                try:
                    log_path.write_text(
                        f"E2E validation failed before simulator startup: {exc}\n"
                    )
                except OSError as write_exc:
                    print(f"WARNING: could not write failure log: {write_exc}", file=sys.stderr)
            print(f"Failure artifacts retained in: {run_dir}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
