import pytest

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
