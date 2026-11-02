import os
import yaml
import pytest

HL7_PATH = os.path.join(os.path.dirname(__file__), 'hl7.yml')

REQUIRED_TOP_KEYS = {
    "allergy", "diagnosis", "document", "procedure", "order_control",
    "result_status", "document_status", "order_status", "patient_class",
    "patient_account_status", "gender", "abnormal_flags", "primary_facility",
    "hospital_service", "coding_system", "mapping"
}


def _is_list_of_strings(value):
    return isinstance(value, list) and len(value) > 0 and all(isinstance(item, str) for item in value)


def _is_string(value):
    return isinstance(value, str)


def _validate_leaf(key, value):
    if isinstance(value, dict):
        for sub_key, sub_value in value.items():
            _validate_leaf(f"{key}.{sub_key}", sub_value)
        return
    if _is_list_of_strings(value) or _is_string(value):
        return
    pytest.fail(f"Key '{key}' has invalid type: expected list of strings or string, got {type(value).__name__}")


def test_hl7_top_level_keys():
    with open(HL7_PATH, 'r') as f:
        data = yaml.safe_load(f)
    assert data is not None
    missing = REQUIRED_TOP_KEYS - set(data.keys())
    assert not missing, f"Missing required top-level keys: {missing}"


def test_hl7_leaf_values():
    with open(HL7_PATH, 'r') as f:
        data = yaml.safe_load(f)
    for key, value in data.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                _validate_leaf(f"{key}.{sub_key}", sub_value)
        else:
            _validate_leaf(key, value)


def test_hl7_primary_facility_placeholders():
    with open(HL7_PATH, 'r') as f:
        data = yaml.safe_load(f)
    pf = data["primary_facility"]
    assert "${ORGANIZATION_NAME}" in pf["organization_name"]
    assert "${ORGANIZATION_ID}" in pf["id_number"]
