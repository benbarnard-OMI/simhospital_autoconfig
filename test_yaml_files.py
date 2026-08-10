import os
import yaml
import pytest

YAML_FILES = ['hl7.yml', 'locations.yml', 'doctors.yml']

@pytest.mark.parametrize('filename', YAML_FILES)
def test_yaml_exists(filename):
    """Verify that the YAML file exists."""
    filepath = os.path.join(os.path.dirname(__file__), filename)
    assert os.path.exists(filepath)

@pytest.mark.parametrize('filename', YAML_FILES)
def test_yaml_is_valid_yaml(filename):
    """Verify that the YAML file is valid YAML."""
    filepath = os.path.join(os.path.dirname(__file__), filename)
    with open(filepath, 'r') as f:
        data = yaml.safe_load(f)
    assert data is not None

    if filename == 'doctors.yml':
        assert isinstance(data, list)
        assert len(data) > 0
        assert 'id' in data[0]
        assert 'surname' in data[0]
        assert 'firstname' in data[0]
        assert 'specialty' in data[0]
