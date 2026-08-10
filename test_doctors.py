import yaml
import pytest

import os

def test_doctors_yaml_structure():
    # Resolve the path relative to the test file to handle execution from other directories
    file_path = os.path.join(os.path.dirname(__file__), "doctors.yml")
    with open(file_path, "r") as f:
        data = yaml.safe_load(f)

    assert isinstance(data, list), "Root element should be a list"
    assert len(data) > 0, "List should not be empty"

    required_keys = {"id", "surname", "firstname", "prefix", "specialty"}
    seen_ids = set()

    for doctor in data:
        # Check required keys
        missing_keys = required_keys - set(doctor.keys())
        assert not missing_keys, f"Doctor entry missing required keys: {missing_keys}"

        # Check all values are strings
        for key in required_keys:
            assert isinstance(doctor[key], str), f"Value for '{key}' must be a string"

        # Check for duplicate ids
        doctor_id = doctor["id"]
        assert doctor_id not in seen_ids, f"Duplicate doctor id found: {doctor_id}"
        seen_ids.add(doctor_id)
