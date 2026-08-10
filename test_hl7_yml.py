import os
import yaml
import pytest

@pytest.mark.parametrize("filename", [
    "hl7.yml",
    "locations.yml",
    "doctors.yml",
    "data.yml",
    "ethnicity.csv"
])
def test_file_exists(filename):
    """Verify that essential configuration files exist."""
    filepath = os.path.join(os.path.dirname(__file__), filename)
    assert os.path.exists(filepath)

def test_hl7_yml_is_valid_yaml():
    """Verify that hl7.yml is valid YAML."""
    filepath = os.path.join(os.path.dirname(__file__), 'hl7.yml')
    with open(filepath, 'r') as f:
        data = yaml.safe_load(f)
    assert data is not None
