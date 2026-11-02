"""End-to-end integration test for configuration generation."""

import os

import pytest
import vcr
import yaml

from simhospital_autoconfig.generators import generate_all_configs
from simhospital_autoconfig.nppes import NPPESAddress, NPPESResult, NPPESTaxonomy

NPI = "1730209545"
CASSETTE_PATH = f"test_simulator_validation[{NPI}]"

# record_mode="none" keeps the suite offline: a request missing from the cassette
# raises instead of silently hitting the network.
CASSETTE_VCR = vcr.VCR(
    cassette_library_dir="tests/cassettes",
    record_mode="none",
    path_transformer=vcr.VCR.ensure_suffix(".yaml"),
)


@pytest.fixture
def nppes_result():
    with CASSETTE_VCR.use_cassette(CASSETTE_PATH):
        from simhospital_autoconfig.nppes import NPPESClient
        return NPPESClient().get_organization_by_npi(NPI)


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


def test_e2e_generates_all_files(tmp_path, sample_nppes_result):
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

    expected_files = ["hl7.yml", "locations.yml", "data.yml", "ethnicity.csv", "doctors.yml"]
    for filename in expected_files:
        assert filename in results
        filepath = os.path.join(str(tmp_path), filename)
        assert os.path.exists(filepath)

    with open(os.path.join(str(tmp_path), "data.yml")) as f:
        data = yaml.safe_load(f)
    assert data["address"]["country"] == "USA"

    with open(os.path.join(str(tmp_path), "hl7.yml")) as f:
        hl7 = yaml.safe_load(f)
    assert "${ORGANIZATION_NAME}" not in yaml.dump(hl7)

    with open(os.path.join(str(tmp_path), "doctors.yml")) as f:
        docs = yaml.safe_load(f)
    assert isinstance(docs, list)
    assert len(docs) == 1
    assert docs[0]["specialty"] == "INTMED"


def test_e2e_with_recorded_cassettes(tmp_path, nppes_result):
    # CMS is deliberately not replayed here. The Provider Data Catalog offers no
    # working server-side filter, so the client downloads a 1.4 MB bulk CSV; putting
    # that in the cassette would dwarf everything else in it. The catalog contract is
    # covered against mocks in tests/test_integration_cms.py instead.
    hospital_data = None

    demographics = {
        "total_population": 34699,
        "ethnicity": {"2135-2": 5577, "2106-3": 7683, "2054-5": 18753},
        "ethnicity_labels": {
            "2135-2": "Hispanic or Latino",
            "2106-3": "White",
            "2054-5": "Black or African American",
        },
        "zcta": "60612",
        "acs_year": 2023,
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
        nppes_result,
        output_dir=str(tmp_path),
        demographics=demographics,
        hospital_data=hospital_data,
        doctors=doctors,
    )

    expected_files = ["hl7.yml", "locations.yml", "data.yml", "ethnicity.csv", "doctors.yml"]
    for filename in expected_files:
        assert filename in results
        assert os.path.exists(os.path.join(str(tmp_path), filename))

    with open(os.path.join(str(tmp_path), "data.yml")) as f:
        data = yaml.safe_load(f)
    assert data["address"]["country"] == "USA"
    assert data["address"]["cities"] == ["CHICAGO"]
