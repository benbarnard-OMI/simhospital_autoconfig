import os
import pytest
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


@pytest.fixture
def locations_yml():
    with open(LOCATIONS_YML_PATH, 'r') as f:
        return yaml.safe_load(f)


def test_locations_is_dict(locations_yml):
    """Verify that locations.yml root is a dict."""
    assert isinstance(locations_yml, dict)


def test_locations_not_empty(locations_yml):
    """Verify that locations.yml contains entries."""
    assert len(locations_yml) > 0


def test_location_required_keys(locations_yml):
    """Verify each location entry has required keys."""
    required_keys = {'poc', 'facility', 'floor', 'room'}
    for name, loc in locations_yml.items():
        missing_keys = required_keys - set(loc.keys())
        assert not missing_keys, f"Location '{name}' missing required keys: {missing_keys}"


def test_location_floor_is_int(locations_yml):
    """Verify that floor values are integers."""
    for name, loc in locations_yml.items():
        assert isinstance(loc['floor'], int), f"Location '{name}' floor must be an integer"


def test_locations_consistent_keys(locations_yml):
    """Verify all locations share the same set of optional keys."""
    # All locations should either all have 'building' or none should
    building_present = {name: 'building' in loc for name, loc in locations_yml.items()}
    if any(building_present.values()):
        assert all(building_present.values()), \
            "Not all locations have 'building' key - inconsistent structure"
