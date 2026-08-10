import os
import yaml

HL7_YML_PATH = os.path.join(os.path.dirname(__file__), 'hl7.yml')

def test_hl7_yml_exists():
    """Verify that hl7.yml exists."""
    assert os.path.exists(HL7_YML_PATH)

def test_hl7_yml_is_valid_yaml():
    """Verify that hl7.yml is valid YAML."""
    with open(HL7_YML_PATH, 'r') as f:
        data = yaml.safe_load(f)
    assert data is not None
