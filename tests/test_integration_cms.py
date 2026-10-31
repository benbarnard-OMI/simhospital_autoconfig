"""Integration tests for CMSClient."""

import pytest
import requests_mock

from simhospital_autoconfig.cms import CMSClient


CMS_RESPONSE = [
    {
        "ccn": "140001",
        "hospital_name": "Test Hospital",
        "hospital_type": "Acute Care",
        "emergency_services": "Y",
        "city": "Chicago",
        "state": "IL",
        "zip_code": "60601",
    }
]


def test_get_hospital_by_ccn():
    client = CMSClient()
    with requests_mock.Mocker() as m:
        m.get("https://data.cms.gov/resource/xubh-q36u.json", json=CMS_RESPONSE)
        result = client.get_hospital_by_ccn("140001")
    assert result["hospital_name"] == "Test Hospital"
    assert result["emergency_services"] == "Y"


def test_get_hospital_by_npi_found():
    client = CMSClient()
    with requests_mock.Mocker() as m:
        m.get("https://data.cms.gov/resource/xubh-q36u.json", json=CMS_RESPONSE)
        result = client.get_hospital_by_npi("1730209545")
    assert result is not None
    assert result["ccn"] == "140001"


def test_get_hospital_by_npi_not_found():
    client = CMSClient()
    with requests_mock.Mocker() as m:
        m.get("https://data.cms.gov/resource/xubh-q36u.json", json=[])
        result = client.get_hospital_by_npi("0000000000")
    assert result is None


def test_map_to_simhospital_config():
    client = CMSClient()
    hospital = {
        "hospital_name": "Test Hospital",
        "hospital_type": "Critical Access",
        "emergency_services": "N",
        "city": "Springfield",
        "state": "IL",
        "zip_code": "62701",
    }
    mapped = client.map_to_simhospital_config(hospital)
    assert mapped["emergency_services"] is False
    assert mapped["hospital_name"] == "Test Hospital"
