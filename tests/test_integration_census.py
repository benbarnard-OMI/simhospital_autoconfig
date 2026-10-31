"""Integration tests for CensusClient."""

import os

import pytest
import requests_mock

from simhospital_autoconfig.census import CensusClient


CENSUS_RESPONSE = [
    [
        "NAME",
        "B01001_001E",
        "B03002_002E",
        "B03002_008E",
        "B03002_009E",
        "B03002_011E",
    ],
    [
        "ZCTA5 60601",
        "50000",
        "15000",
        "25000",
        "5000",
        "3000",
    ],
]


@pytest.fixture
def census_client():
    return CensusClient(api_key="TEST_KEY")


def test_get_demographics_returns_expected_keys(census_client):
    with requests_mock.Mocker() as m:
        m.get(requests_mock.ANY, json=CENSUS_RESPONSE)
        result = census_client.get_demographics("60601")
    assert "total_population" in result
    assert "ethnicity" in result
    assert "sex_by_age" in result
    assert result["total_population"] == 50000
    assert result["ethnicity"]["H"] == 15000
    assert result["ethnicity"]["W"] == 25000


def test_get_demographics_without_api_key(monkeypatch):
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    client = CensusClient()
    with requests_mock.Mocker() as m:
        m.get(requests_mock.ANY, json=CENSUS_RESPONSE)
        result = client.get_demographics("60601")
    assert result["total_population"] == 50000
