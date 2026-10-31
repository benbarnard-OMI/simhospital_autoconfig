"""Schema validation tests for generated Simhospital configs.

These tests validate that generated configs match the implicit schema
enforced by Simhospital's Go loader.
"""

import csv
import os
import re

import pytest
import yaml

from simhospital_autoconfig.generators import generate_all_configs
from simhospital_autoconfig.nppes import NPPESAddress, NPPESResult, NPPESTaxonomy

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "1730209545")
ALLOWED_SPECIALTIES = {
    "MED", "SUR", "URO", "PUL", "CAR",
    "ANESTH", "EMER", "FAMP", "INTMED", "OBG", "PEDS", "PSY", "RAD", "TRAUM"
}


@pytest.fixture
def sample_nppes_result():
    return NPPESResult(
        npi="1730209545",
        enumeration_type="NPI-2",
        organization_name="Stroger Hospital",
        address=NPPESAddress(
            city="Chicago",
            state="IL",
            postal_code="60601",
            country_code="USA",
        ),
        taxonomies=[
            NPPESTaxonomy(code="INTMED", desc="Internal Medicine", primary=True),
        ],
        identifiers=[],
    )


def _load_yaml(filename):
    path = os.path.join(FIXTURE_DIR, filename)
    with open(path) as f:
        return yaml.safe_load(f)


def test_locations_floor_is_numeric_int_or_str():
    data = _load_yaml("locations.yml")
    for loc_name, loc_data in data.items():
        floor = loc_data["floor"]
        assert isinstance(floor, (int, str)), (
            f"Location '{loc_name}' floor must be int or numeric str, got {type(floor).__name__}: {floor}"
        )
        if isinstance(floor, str):
            assert re.fullmatch(r"\d+", floor), (
                f"Location '{loc_name}' floor string is not numeric: {floor}"
            )


def test_data_yml_country_is_usa_for_us_hospital():
    data = _load_yaml("data.yml")
    assert data["address"]["country"] == "USA", (
        f"US hospitals must have country='USA', got {data['address']['country']!r}"
    )


def test_ethnicity_csv_has_exactly_one_nil_sentinel():
    csv_path = os.path.join(FIXTURE_DIR, "ethnicity.csv")
    rows = []
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            rows.append(row)

    sentinel_rows = [row for row in rows if row[0] == "nil" and row[1] == "nil"]
    assert len(sentinel_rows) == 1, (
        f"Expected exactly one nil,nil sentinel, found {len(sentinel_rows)}: {sentinel_rows}"
    )

    nil_rows = [row for row in rows if row[0] == "nil" or row[1] == "nil"]
    assert len(nil_rows) == 1, (
        f"Expected exactly one row with nil values, found {len(nil_rows)}: {nil_rows}"
    )

    for row in rows:
        freq = int(row[2])
        assert freq > 0, f"Frequency must be positive, got {freq} in row {row}"


def test_doctors_yml_specialties_in_allowed_set():
    yml_path = os.path.join(FIXTURE_DIR, "doctors.yml")
    if not os.path.exists(yml_path):
        pytest.skip("doctors.yml not generated for this fixture")
    with open(yml_path) as f:
        doctors = yaml.safe_load(f)
    assert isinstance(doctors, list)
    for doc in doctors:
        assert doc["specialty"] in ALLOWED_SPECIALTIES, (
            f"Doctor {doc['id']} has invalid specialty: {doc['specialty']}"
        )


def test_generated_configs_pass_schema_validation(tmp_path, sample_nppes_result):
    demographics = {
        "total_population": 50000,
        "ethnicity": {"H": 15000, "W": 25000, "B": 5000, "A": 3000},
        "sex_by_age": {"B01001_001E": 50000},
        "zcta": "60601",
    }
    hospital_data = {
        "hospital_type": "Acute Care",
        "emergency_services": True,
        "hospital_name": "Stroger Hospital",
    }
    doctors = [
        {
            "id": "1",
            "surname": "Smith",
            "firstname": "John",
            "prefix": "A",
            "specialty": "INTMED",
        },
    ]

    results = generate_all_configs(
        sample_nppes_result,
        output_dir=str(tmp_path),
        demographics=demographics,
        hospital_data=hospital_data,
        doctors=doctors,
    )

    expected_files = ["hl7.yml", "locations.yml", "data.yml", "ethnicity.csv"]
    for filename in expected_files:
        assert filename in results
        assert os.path.exists(os.path.join(str(tmp_path), filename))

    with open(os.path.join(str(tmp_path), "data.yml")) as f:
        data = yaml.safe_load(f)
    assert data["address"]["country"] == "USA"

    with open(os.path.join(str(tmp_path), "hl7.yml")) as f:
        hl7 = yaml.safe_load(f)
    assert "${ORGANIZATION_NAME}" not in yaml.dump(hl7)
    assert hl7["hospital_service"] == "INTMED"

    with open(os.path.join(str(tmp_path), "doctors.yml")) as f:
        docs = yaml.safe_load(f)
    assert isinstance(docs, list)
    assert len(docs) == 1
    assert docs[0]["specialty"] == "INTMED"
