import os
import yaml
import pytest

DATA_YML_PATH = os.path.join(os.path.dirname(__file__), 'data.yml')

def assert_non_empty_list(parent_dict, key):
    assert key in parent_dict
    assert isinstance(parent_dict[key], list)
    assert len(parent_dict[key]) > 0

def assert_has_type(parent_dict, key, expected_type):
    assert key in parent_dict
    assert isinstance(parent_dict[key], expected_type)

def test_data_yml_exists():
    """Verify that data.yml exists."""
    assert os.path.exists(DATA_YML_PATH)

def test_data_yml_is_valid_yaml():
    """Verify that data.yml is valid YAML."""
    with open(DATA_YML_PATH, 'r') as f:
        data = yaml.safe_load(f)
    assert data is not None

@pytest.fixture
def data_yml():
    with open(DATA_YML_PATH, 'r') as f:
        return yaml.safe_load(f)

def test_allergy_section(data_yml):
    """Verify the allergy section in data.yml."""
    assert 'allergy' in data_yml
    allergy = data_yml['allergy']

    assert_non_empty_list(allergy, 'reactions')
    assert_has_type(allergy, 'percentage', int)
    assert_has_type(allergy, 'maximum_allergies', int)

def test_patient_name_section(data_yml):
    """Verify the patient_name section in data.yml."""
    assert 'patient_name' in data_yml
    patient_name = data_yml['patient_name']

    assert_non_empty_list(patient_name, 'degrees')
    assert_has_type(patient_name, 'degree_percentage', int)
    assert_non_empty_list(patient_name, 'suffixes')
    assert_has_type(patient_name, 'suffix_percentage', int)
    assert_non_empty_list(patient_name, 'female_prefixes')
    assert_non_empty_list(patient_name, 'male_prefixes')
    assert_has_type(patient_name, 'middlename_percentage', int)

def test_address_section(data_yml):
    """Verify the address section in data.yml."""
    assert 'address' in data_yml
    address = data_yml['address']

    assert_non_empty_list(address, 'cities')
    assert_non_empty_list(address, 'streets')
    assert_has_type(address, 'country', str)
    assert_non_empty_list(address, 'types')
