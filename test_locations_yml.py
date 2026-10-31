import os
import yaml
import pytest

LOCATIONS_PATH = os.path.join(os.path.dirname(__file__), 'locations.yml')
REQUIRED_LOCATIONS = {"ED", "Renal", "Non-renal"}
REQUIRED_SUB_KEYS = {"poc", "facility", "floor", "room"}


def test_locations_top_level_keys():
    with open(LOCATIONS_PATH, 'r') as f:
        data = yaml.safe_load(f)
    assert data is not None
    missing = REQUIRED_LOCATIONS - set(data.keys())
    assert not missing, f"Missing required location keys: {missing}"


def test_locations_required_sub_keys():
    with open(LOCATIONS_PATH, 'r') as f:
        data = yaml.safe_load(f)
    for loc_name, loc_data in data.items():
        missing = REQUIRED_SUB_KEYS - set(loc_data.keys())
        assert not missing, f"Location '{loc_name}' missing required sub-keys: {missing}"


@pytest.mark.parametrize("floor_value", [1, "1", 5, "5"])
def test_locations_floor_is_int_or_numeric_str(floor_value):
    assert isinstance(floor_value, (int, str))
    if isinstance(floor_value, str):
        assert floor_value.isdigit()


def test_locations_floor_values_are_numeric():
    with open(LOCATIONS_PATH, 'r') as f:
        data = yaml.safe_load(f)
    for loc_name, loc_data in data.items():
        floor = loc_data["floor"]
        assert isinstance(floor, (int, str)), f"Location '{loc_name}' floor is not int or str: {floor}"
        if isinstance(floor, str):
            assert floor.isdigit(), f"Location '{loc_name}' floor is not a numeric string: {floor}"


def test_locations_facility_placeholder():
    with open(LOCATIONS_PATH, 'r') as f:
        data = yaml.safe_load(f)
    for loc_name, loc_data in data.items():
        facility = loc_data["facility"]
        assert isinstance(facility, str), f"Location '{loc_name}' facility is not a string"
        assert "${ORGANIZATION_NAME}" in facility, f"Location '{loc_name}' facility missing placeholder"


def test_ed_has_type():
    with open(LOCATIONS_PATH, 'r') as f:
        data = yaml.safe_load(f)
    ed = data["ED"]
    assert ed.get("type") == "ED", f"ED type should be 'ED', got {ed.get('type')}"


def test_renal_and_nonrenal_have_building():
    with open(LOCATIONS_PATH, 'r') as f:
        data = yaml.safe_load(f)
    for loc_name in ["Renal", "Non-renal"]:
        loc_data = data[loc_name]
        assert "building" in loc_data, f"Location '{loc_name}' missing 'building' key"
        building = loc_data["building"]
        assert isinstance(building, str) and len(building) > 0, f"Location '{loc_name}' building must be a non-empty string"
