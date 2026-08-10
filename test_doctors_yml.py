import os
import yaml

DOCTORS_YML_PATH = os.path.join(os.path.dirname(__file__), 'doctors.yml')

def test_doctors_yml_is_valid_yaml():
    """Verify that doctors.yml is valid YAML and parses as a list."""
    with open(DOCTORS_YML_PATH, 'r') as f:
        data = yaml.safe_load(f)
    assert data is not None
    assert isinstance(data, list)

    # Optional but good: check that the entries look like doctors
    assert len(data) > 0
    assert 'id' in data[0]
    assert 'surname' in data[0]
    assert 'firstname' in data[0]
    assert 'specialty' in data[0]
