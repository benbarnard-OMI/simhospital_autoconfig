import os
import yaml
import pytest

DATA_YML_PATH = os.path.join(os.path.dirname(__file__), 'data.yml')

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

    assert 'reactions' in allergy
    assert isinstance(allergy['reactions'], list)
    assert len(allergy['reactions']) > 0

    assert 'percentage' in allergy
    assert isinstance(allergy['percentage'], int)

    assert 'maximum_allergies' in allergy
    assert isinstance(allergy['maximum_allergies'], int)

def test_patient_name_section(data_yml):
    """Verify the patient_name section in data.yml."""
    assert 'patient_name' in data_yml
    patient_name = data_yml['patient_name']

    assert 'degrees' in patient_name
    assert isinstance(patient_name['degrees'], list)
    assert len(patient_name['degrees']) > 0

    assert 'degree_percentage' in patient_name
    assert isinstance(patient_name['degree_percentage'], int)

    assert 'suffixes' in patient_name
    assert isinstance(patient_name['suffixes'], list)
    assert len(patient_name['suffixes']) > 0

    assert 'suffix_percentage' in patient_name
    assert isinstance(patient_name['suffix_percentage'], int)

    assert 'female_prefixes' in patient_name
    assert isinstance(patient_name['female_prefixes'], list)
    assert len(patient_name['female_prefixes']) > 0

    assert 'male_prefixes' in patient_name
    assert isinstance(patient_name['male_prefixes'], list)
    assert len(patient_name['male_prefixes']) > 0

    assert 'middlename_percentage' in patient_name
    assert isinstance(patient_name['middlename_percentage'], int)

def test_address_section(data_yml):
    """Verify the address section in data.yml."""
    assert 'address' in data_yml
    address = data_yml['address']

    assert 'cities' in address
    assert isinstance(address['cities'], list)
    assert len(address['cities']) > 0

    assert 'streets' in address
    assert isinstance(address['streets'], list)
    assert len(address['streets']) > 0

    assert 'country' in address
    assert isinstance(address['country'], str)

    assert 'types' in address
    assert isinstance(address['types'], list)
    assert len(address['types']) > 0
