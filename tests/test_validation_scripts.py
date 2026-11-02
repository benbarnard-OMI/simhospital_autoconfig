"""Offline contract tests for the simulator validation shell scripts."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o755)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Create an isolated project copy with deterministic command stubs."""
    root = tmp_path / "project"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    for name in ("generate_and_validate.sh", "validate_with_simulator.sh"):
        shutil.copy2(REPO_ROOT / "scripts" / name, scripts / name)

    (root / "simhospital/configs/hardcoded_messages").mkdir(parents=True)
    _write_executable(
        root / "simulator",
        """#!/usr/bin/env bash
if [ "${SIMULATOR_BEHAVIOR:-ready}" = "hang" ]; then exec sleep 60; fi
if [ "${SIMULATOR_BEHAVIOR:-ready}" = "error" ]; then
    echo "Simulated Hospital exited with errors"
    exit 2
fi
echo "Starting dashboard on address :8000"
echo "Starting metrics server on address :9095"
if [ "${SIMULATOR_BEHAVIOR:-ready}" = "ready-error" ]; then
    sleep 0.1
    echo "Simulated Hospital exited with errors"
    exit 0
fi
exec sleep 60
""",
    )

    bin_dir = root / "bin"
    bin_dir.mkdir()
    _write_executable(
        bin_dir / "python3",
        """#!/usr/bin/env bash
output_dir=""
want_output=false
for arg in "$@"; do
    if [ "$want_output" = true ]; then
        output_dir="$arg"
        want_output=false
    elif [ "$arg" = "--output-dir" ]; then
        want_output=true
    fi
done
if [ -n "$output_dir" ]; then mkdir -p "$output_dir"; fi
exit "${GENERATOR_EXIT:-0}"
""",
    )

    return root


def _run(project: Path, script: str, *args: str, **extra_env: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.update(extra_env)
    env["PATH"] = f"{project / 'bin'}:{env['PATH']}"
    return subprocess.run(
        ["bash", str(project / "scripts" / script), *args],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_simulator_startup_timeout_fails_validation(project: Path, tmp_path: Path) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()

    result = _run(
        project,
        "validate_with_simulator.sh",
        str(config_dir),
        SIMULATOR_BEHAVIOR="hang",
        SIMULATOR_VALIDATION_STARTUP_TIMEOUT="1",
        SIMULATOR_VALIDATION_STOP_GRACE="0",
    )

    assert result.returncode == 124
    assert "did not reach config acceptance" in result.stderr + result.stdout


def test_simulator_config_errors_fail_validation(project: Path, tmp_path: Path) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()

    result = _run(
        project,
        "validate_with_simulator.sh",
        str(config_dir),
        SIMULATOR_BEHAVIOR="error",
        SIMULATOR_VALIDATION_STOP_GRACE="0",
    )

    assert result.returncode == 2
    assert "exited before config acceptance" in result.stderr + result.stdout


def test_simulator_runtime_error_with_zero_exit_fails_validation(project: Path, tmp_path: Path) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()

    result = _run(
        project,
        "validate_with_simulator.sh",
        str(config_dir),
        SIMULATOR_BEHAVIOR="ready-error",
        SIMULATOR_VALIDATION_STOP_GRACE="0",
    )

    assert result.returncode == 1
    assert "failed during startup" in result.stdout


def test_successful_simulator_passes_validation(project: Path, tmp_path: Path) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()

    result = _run(
        project,
        "validate_with_simulator.sh",
        str(config_dir),
        SIMULATOR_VALIDATION_STOP_GRACE="0",
    )

    assert result.returncode == 0
    assert "loaded the generated configs successfully" in result.stdout


def test_missing_simulator_fails_validation(project: Path, tmp_path: Path) -> None:
    (project / "simulator").unlink()
    config_dir = tmp_path / "configs"
    config_dir.mkdir()

    result = _run(project, "validate_with_simulator.sh", str(config_dir))

    assert result.returncode != 0
    assert "binary not found" in result.stdout


def test_generate_wrapper_cleans_only_its_temporary_output(project: Path, tmp_path: Path) -> None:
    temp_root = tmp_path / "temporary"
    temp_root.mkdir()

    result = _run(
        project,
        "generate_and_validate.sh",
        "1730209545",
        TMPDIR=str(temp_root),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert list(temp_root.iterdir()) == []


def test_generate_wrapper_preserves_caller_output(project: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "keep-me"
    output_dir.mkdir()
    sentinel = output_dir / "sentinel.txt"
    sentinel.write_text("preserve")

    result = _run(project, "generate_and_validate.sh", "1730209545", str(output_dir))

    assert result.returncode == 0, result.stdout + result.stderr
    assert sentinel.read_text() == "preserve"
    assert output_dir.is_dir()


def test_generate_wrapper_cleans_temporary_output_after_generation_failure(
    project: Path, tmp_path: Path
) -> None:
    temp_root = tmp_path / "temporary"
    temp_root.mkdir()

    result = _run(
        project,
        "generate_and_validate.sh",
        "1730209545",
        TMPDIR=str(temp_root),
        GENERATOR_EXIT="7",
    )

    assert result.returncode == 7
    assert list(temp_root.iterdir()) == []


def test_generate_wrapper_cleans_temporary_output_after_validation_failure(
    project: Path, tmp_path: Path
) -> None:
    temp_root = tmp_path / "temporary"
    temp_root.mkdir()

    result = _run(
        project,
        "generate_and_validate.sh",
        "1730209545",
        TMPDIR=str(temp_root),
        SIMULATOR_BEHAVIOR="error",
        SIMULATOR_VALIDATION_STOP_GRACE="0",
    )

    assert result.returncode == 2
    assert list(temp_root.iterdir()) == []


def test_make_target_fails_without_local_simulator(project: Path) -> None:
    (project / "simulator").unlink()
    shutil.copy2(REPO_ROOT / "Makefile", project / "Makefile")
    env = os.environ.copy()
    env["PATH"] = f"{project / 'bin'}:{env['PATH']}"

    result = subprocess.run(
        ["make", "validate-simulator"],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "binary not found" in result.stdout + result.stderr
