import os
import pytest
import yaml

DOCTORS_YML_PATH = os.path.join(os.path.dirname(__file__), 'doctors.yml')


def test_doctors_yml_exists():
    """Verify that doctors.yml exists."""
    assert os.path.exists(DOCTORS_YML_PATH)


def test_doctors_yml_is_valid_yaml():
    """Verify that doctors.yml is valid YAML."""
    with open(DOCTORS_YML_PATH, 'r') as f:
        data = yaml.safe_load(f)
    assert data is not None


@pytest.fixture
def doctors_yml():
    with open(DOCTORS_YML_PATH, 'r') as f:
        return yaml.safe_load(f)


def test_doctors_yml_is_list(doctors_yml):
    """Verify that doctors.yml root is a list."""
    assert isinstance(doctors_yml, list)


def test_doctors_yml_not_empty(doctors_yml):
    """Verify that doctors.yml contains entries."""
    assert len(doctors_yml) > 0


def test_doctor_required_keys(doctors_yml):
    """Verify each doctor entry has all required keys."""
    required_keys = {'id', 'surname', 'firstname', 'prefix', 'specialty'}
    for doctor in doctors_yml:
        missing_keys = required_keys - set(doctor.keys())
        assert not missing_keys, f"Doctor entry missing required keys: {missing_keys}"


def test_doctor_values_are_strings(doctors_yml):
    """Verify all doctor values are strings."""
    required_keys = {'id', 'surname', 'firstname', 'prefix', 'specialty'}
    for doctor in doctors_yml:
        for key in required_keys:
            assert isinstance(doctor[key], str), f"Value for '{key}' must be a string"


def test_doctor_ids_unique(doctors_yml):
    """Verify that all doctor IDs are unique."""
    seen_ids = set()
    for doctor in doctors_yml:
        doctor_id = doctor['id']
        assert doctor_id not in seen_ids, f"Duplicate doctor id found: {doctor_id}"
        seen_ids.add(doctor_id)
