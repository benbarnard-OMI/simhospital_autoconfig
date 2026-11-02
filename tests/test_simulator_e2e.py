import pytest

from scripts import record_cassettes, run_simulator_e2e
from scripts.run_simulator_e2e import validate_hl7_messages


def _message(message_type: str, segments: tuple[str, ...]) -> str:
    return "\r".join(
        (f"MSH|^~\\&|APP|FAC|APP|FAC|202610310000||{message_type}|1|P|2.3", *segments)
    )


def _valid_output() -> str:
    messages = (
        _message("ORU^R01", ("PID|1", "PV1|1", "ORC|RE", "OBR|1", "OBX|1|NM")),
        _message("ADT^A01", ("EVN|A01", "PID|1", "PD1", "PV1|1", "PV2")),
        _message("ORU^R01", ("PID|1", "PV1|1", "ORC|RE", "OBR|1", "OBX|1|NM")),
        _message("ADT^A03", ("EVN|A03", "PID|1", "PD1", "PV1|1")),
    )
    return "\n\n".join(messages) + "\n\n"


def test_validate_hl7_messages_accepts_expected_sequence_and_segments():
    assert validate_hl7_messages(_valid_output()) == [
        "ORU^R01",
        "ADT^A01",
        "ORU^R01",
        "ADT^A03",
    ]


def test_validate_hl7_messages_rejects_wrong_order():
    messages = _valid_output().split("\n\n")
    messages[1], messages[2] = messages[2], messages[1]

    with pytest.raises(ValueError, match="message 2 has type"):
        validate_hl7_messages("\n\n".join(messages))


def test_validate_hl7_messages_rejects_missing_required_segment():
    output = _valid_output().replace("OBX|1|NM", "NTE|no result", 1)

    with pytest.raises(ValueError, match="missing segments: OBX"):
        validate_hl7_messages(output)


def test_validate_hl7_messages_rejects_missing_message():
    output = "\n\n".join(_valid_output().split("\n\n")[:3])

    with pytest.raises(ValueError, match="expected 4 HL7 messages, found 3"):
        validate_hl7_messages(output)


def test_main_reports_temporary_directory_creation_error_without_traceback(monkeypatch, capsys):
    def fail_run_dir():
        raise OSError("temporary storage is unavailable")

    monkeypatch.setattr(run_simulator_e2e, "_run_dir", fail_run_dir)

    assert run_simulator_e2e.main() == 1
    captured = capsys.readouterr()
    assert "ERROR: temporary storage is unavailable" in captured.err
    assert "Traceback" not in captured.err
    assert "Failure artifacts retained" not in captured.err


def test_cleanup_failure_warns_without_raising(monkeypatch, capsys, tmp_path):
    def fail_remove(path):
        raise OSError("permission denied")

    monkeypatch.setattr(run_simulator_e2e.shutil, "rmtree", fail_remove)

    run_simulator_e2e._cleanup_run_dir(tmp_path / "artifacts")

    assert "validation passed, but artifacts remain" in capsys.readouterr().err


def test_cassette_and_fixture_paths_are_independent_of_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    project_root = run_simulator_e2e.Path(__file__).resolve().parents[1]

    assert record_cassettes.PROJECT_ROOT == project_root
    assert record_cassettes.CASSETTE_DIR == project_root / "tests" / "cassettes"
    assert record_cassettes.OUTPUT_DIR == project_root / "tests" / "fixtures" / "1730209545"
    assert record_cassettes.CASSETTE_DIR.is_absolute()
    assert record_cassettes.OUTPUT_DIR.is_absolute()
