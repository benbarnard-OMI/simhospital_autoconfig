"""Tests for the config file generators."""

import pytest
import os
import tempfile
import yaml
import csv

from simhospital_autoconfig.generators import (
    generate_hl7_yml,
    generate_locations_yml,
    generate_data_yml,
    generate_ethnicity_csv,
    generate_all_configs,
)
from simhospital_autoconfig.nppes import NPPESResult, NPPESAddress


class TestGenerateHl7Yml:
    """Tests for generate_hl7_yml function."""

    def test_generate_hl7_yml_content(self):
        """Test that hl7.yml content is generated correctly."""
        content = generate_hl7_yml("Test Hospital", "12345")
        
        assert 'organization_name: "Test Hospital"' in content or "organization_name: Test Hospital" in content
        assert 'id_number: "12345"' in content or "id_number: 12345" in content
        assert "allergy:" in content
        assert "diagnosis:" in content

    def test_generate_hl7_yml_writes_file(self):
        """Test that hl7.yml is written to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "hl7.yml")
            content = generate_hl7_yml("Test Hospital", "12345", output_path)
            
            assert os.path.exists(output_path)
            with open(output_path, "r") as f:
                file_content = f.read()
            
            assert file_content == content
            assert 'organization_name: "Test Hospital"' in file_content or "organization_name: Test Hospital" in file_content


class TestGenerateLocationsYml:
    """Tests for generate_locations_yml function."""

    def test_generate_locations_yml_content(self):
        """Test that locations.yml content is generated correctly."""
        content = generate_locations_yml("Test Hospital", "12345")
        
        assert 'facility: "Test Hospital"' in content or "facility: Test Hospital" in content
        assert "ED:" in content
        assert "Renal:" in content

    def test_generate_locations_yml_writes_file(self):
        """Test that locations.yml is written to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "locations.yml")
            content = generate_locations_yml("Test Hospital", "12345", output_path)
            
            assert os.path.exists(output_path)
            with open(output_path, "r") as f:
                file_content = f.read()
            
            assert file_content == content


class TestGenerateDataYml:
    """Tests for generate_data_yml function."""

    def test_generate_data_yml_content(self):
        """Test that data.yml content is generated correctly."""
        content = generate_data_yml("Test Hospital", "12345")
        
        # Should be valid YAML
        data = yaml.safe_load(content)
        assert "allergy" in data
        assert "patient_name" in data
        assert "address" in data

    def test_generate_data_yml_with_address(self):
        """Test that data.yml is customized with address data."""
        address = NPPESAddress(
            city="Springfield",
            state="IL",
            postal_code="62701",
            country_code="US",
        )
        
        content = generate_data_yml("Test Hospital", "12345", address)
        data = yaml.safe_load(content)
        
        # City should be updated
        assert "Springfield" in data["address"]["cities"]
        assert data["address"]["country"] == "US"

    def test_generate_data_yml_writes_file(self):
        """Test that data.yml is written to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "data.yml")
            content = generate_data_yml("Test Hospital", "12345", output_path=output_path)
            
            assert os.path.exists(output_path)
            with open(output_path, "r") as f:
                file_content = f.read()
            
            assert file_content == content


class TestGenerateEthnicityCsv:
    """Tests for generate_ethnicity_csv function."""

    def test_generate_ethnicity_csv_content(self):
        """Test that ethnicity.csv content is generated correctly."""
        content = generate_ethnicity_csv("Test Hospital", "12345")
        
        # Should be valid CSV
        lines = content.strip().split("\n")
        assert len(lines) > 0
        
        # Parse CSV and check structure
        reader = csv.reader(lines)
        rows = list(reader)
        
        # Should have header comments and data rows
        assert any("ID of the CE" in row[0] for row in rows)
        assert any("A" in row[0] and "White - British" in row[1] for row in rows)

    def test_generate_ethnicity_csv_writes_file(self):
        """Test that ethnicity.csv is written to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "ethnicity.csv")
            content = generate_ethnicity_csv("Test Hospital", "12345", output_path)
            
            assert os.path.exists(output_path)
            with open(output_path, "r") as f:
                file_content = f.read()
            
            # Normalize line endings for comparison
            assert file_content.replace("\r\n", "\n") == content.replace("\r\n", "\n")


class TestGenerateAllConfigs:
    """Tests for generate_all_configs function."""

    @pytest.fixture
    def mock_nppes_result(self):
        """Create a mock NPPESResult for testing."""
        address = NPPESAddress(
            address_1="123 Hospital Way",
            city="Springfield",
            state="IL",
            postal_code="62701",
            country_code="US",
        )
        
        return NPPESResult(
            npi="1234567890",
            enumeration_type="NPI-2",
            organization_name="Springfield General Hospital",
            address=address,
        )

    def test_generate_all_configs_creates_files(self, mock_nppes_result):
        """Test that all config files are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = generate_all_configs(mock_nppes_result, tmpdir)
            
            # Check all expected files exist
            assert os.path.exists(os.path.join(tmpdir, "hl7.yml"))
            assert os.path.exists(os.path.join(tmpdir, "locations.yml"))
            assert os.path.exists(os.path.join(tmpdir, "data.yml"))
            assert os.path.exists(os.path.join(tmpdir, "ethnicity.csv"))
            
            # Check all expected keys in results
            assert "hl7.yml" in results
            assert "locations.yml" in results
            assert "data.yml" in results
            assert "ethnicity.csv" in results

    def test_generate_all_configs_content(self, mock_nppes_result):
        """Test that generated content includes organization data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = generate_all_configs(mock_nppes_result, tmpdir)
            
            # Check hl7.yml has organization name
            assert "Springfield General Hospital" in results["hl7.yml"]
            assert "1234567890" in results["hl7.yml"]
            
            # Check locations.yml has organization name
            assert "Springfield General Hospital" in results["locations.yml"]
            
            # Check data.yml has address data
            data = yaml.safe_load(results["data.yml"])
            assert "Springfield" in data["address"]["cities"]
            assert data["address"]["country"] == "US"
