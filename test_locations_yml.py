import os
import yaml

LOCATIONS_YML_PATH = os.path.join(os.path.dirname(__file__), 'locations.yml')

def test_locations_yml_exists():
    """Verify that locations.yml exists."""
    assert os.path.exists(LOCATIONS_YML_PATH)

def test_locations_yml_is_valid_yaml():
    """Verify that locations.yml is valid YAML."""
    with open(LOCATIONS_YML_PATH, 'r') as f:
        data = yaml.safe_load(f)
    assert data is not None
