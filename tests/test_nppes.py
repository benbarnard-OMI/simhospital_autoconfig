"""Tests for the NPPES API client."""

import pytest
from unittest.mock import patch, MagicMock
import requests

from simhospital_autoconfig.nppes import (
    NPPESClient,
    NPPESResult,
    NPPESAddress,
    NPPESTaxonomy,
    NPPESIdentifier,
    get_hospital_data,
)


@pytest.fixture
def mock_nppes_response():
    """Sample NPPES API response for testing."""
    return {
        "result_count": 1,
        "results": [
            {
                "basic": {
                    "organization_name": "TEST HOSPITAL INC",
                },
                "addresses": [
                    {
                        "address_1": "123 HOSPITAL WAY",
                        "address_2": "SUITE 100",
                        "city": "SPRINGFIELD",
                        "state": "IL",
                        "postal_code": "62701",
                        "country_code": "US",
                        "address_purpose": "LOCATION",
                        "address_type": "PRIMARY",
                    }
                ],
                "taxonomies": [
                    {
                        "code": "282N00000X",
                        "desc": "General Acute Care Hospital",
                        "primary": True,
                        "state": "IL",
                        "license": "0005272",
                    }
                ],
                "identifiers": [
                    {
                        "code": "05",
                        "desc": "MEDICAID",
                        "identifier": "123456789",
                        "state": "IL",
                        "issuer": None,
                    }
                ],
                "other_names": [
                    {
                        "organization_name": "SPRINGFIELD GENERAL",
                        "type": "Doing Business As",
                        "code": "3",
                    }
                ],
            }
        ],
    }


@pytest.fixture
def mock_empty_response():
    """Empty NPPES API response for testing."""
    return {"result_count": 0, "results": []}


class TestNPPESClient:
    """Tests for NPPESClient class."""

    def test_get_organization_by_npi_success(self, mock_nppes_response):
        """Test successful fetch of organization data."""
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_nppes_response
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            client = NPPESClient()
            result = client.get_organization_by_npi("1234567890")

            assert isinstance(result, NPPESResult)
            assert result.npi == "1234567890"
            assert result.organization_name == "TEST HOSPITAL INC"
            assert result.enumeration_type == "NPI-2"

    def test_get_organization_by_npi_with_address(self, mock_nppes_response):
        """Test that address is parsed correctly."""
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_nppes_response
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            client = NPPESClient()
            result = client.get_organization_by_npi("1234567890")

            assert result.address is not None
            assert result.address.city == "SPRINGFIELD"
            assert result.address.state == "IL"
            assert result.address.postal_code == "62701"
            assert result.address.country_code == "US"

    def test_get_organization_by_npi_with_taxonomies(self, mock_nppes_response):
        """Test that taxonomies are parsed correctly."""
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_nppes_response
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            client = NPPESClient()
            result = client.get_organization_by_npi("1234567890")

            assert result.taxonomies is not None
            assert len(result.taxonomies) == 1
            assert result.taxonomies[0].code == "282N00000X"
            assert result.taxonomies[0].desc == "General Acute Care Hospital"
            assert result.taxonomies[0].primary is True

    def test_get_organization_by_npi_with_identifiers(self, mock_nppes_response):
        """Test that identifiers are parsed correctly."""
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_nppes_response
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            client = NPPESClient()
            result = client.get_organization_by_npi("1234567890")

            assert result.identifiers is not None
            assert len(result.identifiers) == 1
            assert result.identifiers[0].code == "05"
            assert result.identifiers[0].desc == "MEDICAID"

    def test_get_organization_by_npi_no_results(self, mock_empty_response):
        """Test that ValueError is raised when no results are found."""
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_empty_response
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            client = NPPESClient()
            
            with pytest.raises(ValueError, match="No NPPES result found"):
                client.get_organization_by_npi("0000000000")

    def test_get_organization_by_npi_http_error(self):
        """Test that HTTPError is raised when API request fails."""
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = requests.HTTPError("API Error")
            mock_get.return_value = mock_response

            client = NPPESClient()
            
            with pytest.raises(requests.HTTPError):
                client.get_organization_by_npi("1234567890")


class TestGetHospitalData:
    """Tests for the get_hospital_data convenience function."""

    def test_get_hospital_data(self, mock_nppes_response):
        """Test the convenience function."""
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_nppes_response
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            result = get_hospital_data("1234567890")

            assert isinstance(result, NPPESResult)
            assert result.organization_name == "TEST HOSPITAL INC"


class TestDataClasses:
    """Tests for dataclasses."""

    def test_nppes_address_defaults(self):
        """Test NPPESAddress default values."""
        address = NPPESAddress()
        assert address.address_1 is None
        assert address.city is None
        assert address.state is None

    def test_nppes_address_with_values(self):
        """Test NPPESAddress with values."""
        address = NPPESAddress(
            address_1="123 Main St",
            city="Springfield",
            state="IL",
        )
        assert address.address_1 == "123 Main St"
        assert address.city == "Springfield"
        assert address.state == "IL"

    def test_nppes_taxonomy_defaults(self):
        """Test NPPESTaxonomy default values."""
        taxonomy = NPPESTaxonomy(code="282N00000X", desc="Hospital", primary=True)
        assert taxonomy.code == "282N00000X"
        assert taxonomy.desc == "Hospital"
        assert taxonomy.primary is True
        assert taxonomy.state is None
        assert taxonomy.license is None

    def test_nppes_identifier_defaults(self):
        """Test NPPESIdentifier default values."""
        identifier = NPPESIdentifier(
            code="05",
            desc="MEDICAID",
            identifier="12345",
        )
        assert identifier.code == "05"
        assert identifier.desc == "MEDICAID"
        assert identifier.identifier == "12345"
        assert identifier.state is None
        assert identifier.issuer is None
