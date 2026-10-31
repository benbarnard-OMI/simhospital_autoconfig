"""Edge case tests for simhospital_autoconfig generators.

These tests cover boundary conditions and failure modes that TypeSafe
identified as potential blind spots.
"""

import csv
import io

import pytest
import yaml

from simhospital_autoconfig.generators import (
    generate_all_configs,
    generate_data_yml,
    generate_doctors_yml,
    generate_ethnicity_csv,
    generate_hl7_yml,
    generate_locations_yml,
)
from simhospital_autoconfig.nppes import NPPESAddress, NPPESResult, NPPESTaxonomy


@pytest.fixture
def minimal_nppes_result():
    return NPPESResult(
        npi="1730209545",
        enumeration_type="NPI-2",
        organization_name="Test Hospital",
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


class TestEdgeCases:
    """Edge case tests identified by TypeSafe blind-spot analysis."""

    def test_empty_demographics_still_generates_valid_config(self, minimal_nppes_result, tmp_path):
        results = generate_all_configs(
            minimal_nppes_result,
            output_dir=str(tmp_path),
            demographics=None,
            hospital_data=None,
            doctors=None,
        )
        assert "data.yml" in results
        assert "ethnicity.csv" in results
        assert "hl7.yml" in results
        assert "locations.yml" in results

        with open(tmp_path / "data.yml") as f:
            data = yaml.safe_load(f)
        assert data["address"]["country"] == "USA"

    def test_empty_doctors_list_produces_empty_doctors_yml(self, minimal_nppes_result, tmp_path):
        results = generate_all_configs(
            minimal_nppes_result,
            output_dir=str(tmp_path),
            doctors=[],
        )
        assert "doctors.yml" in results
        with open(tmp_path / "doctors.yml") as f:
            docs = yaml.safe_load(f)
        assert docs == []

    def test_none_doctors_produces_no_doctors_yml(self, minimal_nppes_result, tmp_path):
        results = generate_all_configs(
            minimal_nppes_result,
            output_dir=str(tmp_path),
            doctors=None,
        )
        assert "doctors.yml" not in results

    def test_special_characters_in_hospital_name(self, minimal_nppes_result, tmp_path):
        minimal_nppes_result.organization_name = 'O"Brien & Associates <Test>'
        generate_all_configs(
            minimal_nppes_result,
            output_dir=str(tmp_path),
        )
        with open(tmp_path / "hl7.yml") as f:
            hl7 = yaml.safe_load(f)
        assert hl7["primary_facility"]["organization_name"] == 'O"Brien & Associates <Test>'

    def test_unicode_hospital_name(self, minimal_nppes_result, tmp_path):
        minimal_nppes_result.organization_name = "München Klinik"
        generate_all_configs(
            minimal_nppes_result,
            output_dir=str(tmp_path),
        )
        with open(tmp_path / "hl7.yml") as f:
            hl7 = yaml.safe_load(f)
        assert hl7["primary_facility"]["organization_name"] == "München Klinik"

    def test_very_long_hospital_name(self, minimal_nppes_result, tmp_path):
        minimal_nppes_result.organization_name = "A" * 500
        generate_all_configs(
            minimal_nppes_result,
            output_dir=str(tmp_path),
        )
        with open(tmp_path / "hl7.yml") as f:
            hl7 = yaml.safe_load(f)
        assert hl7["primary_facility"]["organization_name"] == "A" * 500

    def test_missing_address_fields_use_defaults(self, tmp_path):
        nppes_result = NPPESResult(
            npi="1730209545",
            enumeration_type="NPI-2",
            organization_name="Test Hospital",
            address=None,
            taxonomies=[],
            identifiers=[],
        )
        generate_all_configs(
            nppes_result,
            output_dir=str(tmp_path),
        )
        with open(tmp_path / "data.yml") as f:
            data = yaml.safe_load(f)
        assert data["address"]["country"] == "USA"

    def test_ethnicity_csv_preserves_comments_with_census_data(self, tmp_path):
        demographics = {
            "ethnicity": {"H": 100, "W": 200},
        }
        content = generate_ethnicity_csv(
            "Test Hospital",
            "1730209545",
            demographics=demographics,
            output_path=str(tmp_path / "ethnicity.csv"),
        )
        lines = content.strip().split("\n")
        comment_lines = [line for line in lines if line.startswith("#")]
        assert len(comment_lines) >= 4
        data_lines = [line for line in lines if not line.startswith("#") and line.strip()]
        assert len(data_lines) == 20

    def test_doctors_yml_sorted_by_specialty(self):
        doctors = [
            {"id": "3", "surname": "C", "firstname": "C", "prefix": "", "specialty": "SUR"},
            {"id": "1", "surname": "A", "firstname": "A", "prefix": "", "specialty": "INTMED"},
            {"id": "2", "surname": "B", "firstname": "B", "prefix": "", "specialty": "INTMED"},
        ]
        content = generate_doctors_yml(doctors)
        docs = yaml.safe_load(content)
        assert docs[0]["specialty"] == "INTMED"
        assert docs[1]["specialty"] == "INTMED"
        assert docs[2]["specialty"] == "SUR"

    def test_data_yml_normalizes_us_country_code(self):
        content = generate_data_yml(
            "Test Hospital",
            "1730209545",
            address=NPPESAddress(city="Chicago", state="IL", postal_code="60601", country_code="US"),
        )
        data = yaml.safe_load(content)
        assert data["address"]["country"] == "USA"

    def test_locations_yml_warns_on_no_emergency_services(self, minimal_nppes_result, tmp_path, caplog):
        generate_locations_yml(
            minimal_nppes_result.organization_name,
            minimal_nppes_result.npi,
            hospital_data={"emergency_services": False},
            output_path=str(tmp_path / "locations.yml"),
        )
        assert "ED will still be included" in caplog.text

    def test_hl7_yml_overrides_hospital_service(self, minimal_nppes_result, tmp_path):
        generate_hl7_yml(
            minimal_nppes_result.organization_name,
            minimal_nppes_result.npi,
            hospital_service="EMER",
            output_path=str(tmp_path / "hl7.yml"),
        )
        with open(tmp_path / "hl7.yml") as f:
            hl7 = yaml.safe_load(f)
        assert hl7["hospital_service"] == "EMER"

    def test_generate_all_configs_returns_all_five_files(self, minimal_nppes_result, tmp_path):
        results = generate_all_configs(
            minimal_nppes_result,
            output_dir=str(tmp_path),
            demographics={"total_population": 1000, "ethnicity": {"W": 100}},
            hospital_data={"hospital_type": "Acute Care", "emergency_services": True},
            doctors=[{"id": "1", "surname": "Smith", "firstname": "John", "prefix": "Dr", "specialty": "INTMED"}],
        )
        expected = ["hl7.yml", "locations.yml", "data.yml", "ethnicity.csv", "doctors.yml"]
        for filename in expected:
            assert filename in results
            assert (tmp_path / filename).exists()

    def test_ethnicity_csv_sentinel_invariants_after_census_append(self, tmp_path):
        demographics = {
            "ethnicity": {"H": 100, "W": 200, "B": 50},
        }
        content = generate_ethnicity_csv(
            "Test Hospital",
            "1730209545",
            demographics=demographics,
            output_path=str(tmp_path / "ethnicity.csv"),
        )
        reader = csv.reader(io.StringIO(content))
        rows = [row for row in reader if row and not row[0].startswith("#")]
        sentinel_rows = [row for row in rows if row[0] == "nil" and row[1] == "nil"]
        assert len(sentinel_rows) == 1
        nil_rows = [row for row in rows if row[0] == "nil" or row[1] == "nil"]
        assert len(nil_rows) == 1
        for row in rows:
            assert int(row[2]) > 0

    def test_doctors_yml_empty_specialty_defaults_to_med(self):
        content = generate_doctors_yml([
            {"id": "1", "surname": "Smith", "firstname": "John", "prefix": "", "specialty": ""},
        ])
        docs = yaml.safe_load(content)
        assert docs[0]["specialty"] == "MED"

    def test_doctors_yml_missing_fields_get_defaults(self):
        content = generate_doctors_yml([
            {"id": "1"},
        ])
        docs = yaml.safe_load(content)
        assert docs[0]["surname"] == ""
        assert docs[0]["firstname"] == ""
        assert docs[0]["prefix"] == ""
        assert docs[0]["specialty"] == "MED"

    def test_invalid_npi_raises_error(self):
        from simhospital_autoconfig.nppes import NPPESClient
        client = NPPESClient()
        with pytest.raises(ValueError, match="Invalid NPI format"):
            client.validate_npi("not-a-npi")

    def test_generate_locations_yml_does_not_include_organization_id(self):
        from simhospital_autoconfig.generators import generate_locations_yml
        content = generate_locations_yml("Test Hospital", "1234567890")
        assert "${ORGANIZATION_ID}" not in content
        assert "1234567890" not in content

    def test_generate_data_yml_does_not_include_organization_id(self):
        from simhospital_autoconfig.generators import generate_data_yml
        from simhospital_autoconfig.nppes import NPPESAddress
        content = generate_data_yml(
            "Test Hospital",
            "1234567890",
            address=NPPESAddress(city="Chicago", state="IL", postal_code="60601", country_code="USA"),
        )
        assert "${ORGANIZATION_ID}" not in content
        assert "1234567890" not in content

    def test_empty_demographics_produces_default_ethnicity_csv(self, minimal_nppes_result, tmp_path):
        results = generate_all_configs(
            minimal_nppes_result,
            output_dir=str(tmp_path),
            demographics={},
        )
        assert "ethnicity.csv" in results
        with open(tmp_path / "ethnicity.csv") as f:
            content = f.read()
        assert "# This \"nil,nil\" row is interpreted as an absent ethnicity." in content
        assert "nil,nil,2" in content

    def test_hospital_data_missing_fields_uses_default_locations(self, minimal_nppes_result, tmp_path):
        results = generate_all_configs(
            minimal_nppes_result,
            output_dir=str(tmp_path),
            hospital_data={},
        )
        assert "locations.yml" in results
        with open(tmp_path / "locations.yml") as f:
            loc = yaml.safe_load(f)
        assert "ED" in loc
        assert loc["ED"]["facility"] == "Test Hospital"

    def test_multiple_taxonomies_no_primary_defaults(self, tmp_path):
        nppes_result = NPPESResult(
            npi="1730209545",
            enumeration_type="NPI-2",
            organization_name="Test Hospital",
            address=NPPESAddress(city="Chicago", state="IL", postal_code="60601", country_code="USA"),
            taxonomies=[
                NPPESTaxonomy(code="INTMED", desc="Internal Medicine", primary=False),
                NPPESTaxonomy(code="SUR", desc="Surgery", primary=False),
            ],
            identifiers=[],
        )
        generate_all_configs(
            nppes_result,
            output_dir=str(tmp_path),
        )
        with open(tmp_path / "data.yml") as f:
            data = yaml.safe_load(f)
        assert data["address"]["country"] == "USA"

    def test_npi_validation_rejects_empty_string(self):
        from simhospital_autoconfig.nppes import NPPESClient
        client = NPPESClient()
        with pytest.raises(ValueError, match="Invalid NPI format"):
            client.validate_npi("")

    def test_non_us_country_code_not_normalized(self):
        from simhospital_autoconfig.nppes import NPPESAddress
        content = generate_data_yml(
            "Test Hospital",
            "1730209545",
            address=NPPESAddress(city="Toronto", state="ON", postal_code="M5V", country_code="CAN"),
        )
        data = yaml.safe_load(content)
        assert data["address"]["country"] == "CAN"

    def test_doctors_yml_invalid_specialty_preserved(self):
        content = generate_doctors_yml([
            {"id": "1", "surname": "Smith", "firstname": "John", "prefix": "Dr", "specialty": "INVALID"},
        ])
        docs = yaml.safe_load(content)
        assert docs[0]["specialty"] == "INVALID"

    def test_generate_locations_yml_with_empty_postalcodes(self, tmp_path):
        from simhospital_autoconfig.generators import generate_locations_yml
        generate_locations_yml(
            "Test Hospital",
            "1730209545",
            hospital_data={"postalcodes": []},
            output_path=str(tmp_path / "locations.yml"),
        )
        with open(tmp_path / "locations.yml") as f:
            loc = yaml.safe_load(f)
        assert "ED" in loc
