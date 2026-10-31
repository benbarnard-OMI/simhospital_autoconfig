"""Integration tests for CensusClient."""

import pytest
import requests_mock

from simhospital_autoconfig.census import (
    RACE_ETHNICITY_MAP,
    TOTAL_POPULATION_VARIABLE,
    CensusClient,
)

TEST_KEY = "TEST_KEY"

# Mirrors the real api.census.gov response shape: a header row, one value row, and a
# trailing geography column. Values are synthetic but sum to a consistent total.
CENSUS_RESPONSE = [
    [
        "NAME",
        "B03002_012E",  # Hispanic or Latino
        "B03002_003E",  # White alone, not Hispanic
        "B03002_004E",  # Black or African American alone, not Hispanic
        "B03002_005E",  # American Indian and Alaska Native alone, not Hispanic
        "B03002_006E",  # Asian alone, not Hispanic
        "B03002_007E",  # Native Hawaiian and Other Pacific Islander alone, not Hispanic
        "B03002_008E",  # Some other race alone, not Hispanic
        "B03002_009E",  # Two or more races, not Hispanic
        "B01001_001E",  # Total
        "zip code tabulation area",
    ],
    [
        "ZCTA5 60612",
        "5577",
        "7683",
        "18753",
        "25",
        "1527",
        "13",
        "700",
        "421",
        "34699",
        "60612",
    ],
]


@pytest.fixture
def census_client():
    return CensusClient(api_key=TEST_KEY)


def test_request_asks_for_every_variable_it_reads(census_client):
    """Regression guard for the defect that made ethnicity always zero.

    get_demographics() once read B03002_* out of a response that had only asked for
    B01001_*, so every count came back 0. A mock that returned B03002 columns anyway
    hid it. Asserting on the outgoing query is what keeps the mock honest.
    """
    with requests_mock.Mocker() as m:
        m.get(requests_mock.ANY, json=CENSUS_RESPONSE)
        census_client.get_demographics("60612")

    # requests_mock lowercases query values, so compare case-insensitively.
    requested = [v.upper() for v in m.request_history[0].qs["get"][0].split(",")]
    for var in RACE_ETHNICITY_MAP:
        assert var in requested, f"{var} is read from the response but never requested"
    assert TOTAL_POPULATION_VARIABLE in requested
    # api.census.gov rejects a request with more than 50 variables with HTTP 400.
    assert len(requested) <= 50, f"requested {len(requested)} variables, API cap is 50"


def test_get_demographics_maps_to_hl7_codes(census_client):
    with requests_mock.Mocker() as m:
        m.get(requests_mock.ANY, json=CENSUS_RESPONSE)
        result = census_client.get_demographics("60612")

    assert result["total_population"] == 34699
    assert result["zcta"] == "60612"
    assert result["ethnicity"] == {
        "2135-2": 5577,
        "2106-3": 7683,
        "2054-5": 18753,
        "1002-5": 25,
        "2028-9": 1527,
        "2076-8": 13,
        # B03002_008E and _009E both map to 2131-1 and must be summed, not overwritten.
        "2131-1": 1121,
    }
    assert set(result["ethnicity_labels"]) == set(result["ethnicity"])


def test_categories_partition_the_total_exactly(census_client):
    """The eight B03002 variables are mutually exclusive and exhaustive."""
    with requests_mock.Mocker() as m:
        m.get(requests_mock.ANY, json=CENSUS_RESPONSE)
        result = census_client.get_demographics("60612")

    assert sum(result["ethnicity"].values()) == result["total_population"]


def test_hispanic_and_non_hispanic_totals_are_not_swapped(census_client):
    """B03002_002E is the *not*-Hispanic total; B03002_012E is the Hispanic total.

    The previous mapping read 002 as Hispanic, which inverted the demographics: a
    ~93% non-Hispanic ZCTA was reported as ~93% Hispanic.
    """
    assert RACE_ETHNICITY_MAP["B03002_012E"] == "2135-2"
    assert "B03002_002E" not in RACE_ETHNICITY_MAP, "002 is the non-Hispanic total, not a race"

    with requests_mock.Mocker() as m:
        m.get(requests_mock.ANY, json=CENSUS_RESPONSE)
        result = census_client.get_demographics("60612")
    assert result["ethnicity_labels"]["2135-2"] == "Hispanic or Latino"


def test_negative_acs_sentinel_clamps_to_zero(census_client):
    """ACS reports unavailable estimates as large negative numbers."""
    response = [CENSUS_RESPONSE[0], list(CENSUS_RESPONSE[1])]
    response[1][1] = "-666666666"  # B03002_012E

    with requests_mock.Mocker() as m:
        m.get(requests_mock.ANY, json=response)
        result = census_client.get_demographics("60612")

    assert result["ethnicity"]["2135-2"] == 0


def test_missing_api_key_fails_fast(monkeypatch):
    """api.census.gov answers a keyless request with an HTTP 200 HTML 'Missing Key' page.

    That used to surface as an opaque JSON decode error after three retries, which the
    caller's broad except turned into a silent fallback to UK default demographics.
    """
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    with pytest.raises(ValueError, match="CENSUS_API_KEY is not set"):
        CensusClient().get_demographics("60612")


def test_acs_year_is_configurable(census_client):
    with requests_mock.Mocker() as m:
        m.get(requests_mock.ANY, json=CENSUS_RESPONSE)
        result = census_client.get_demographics("60612", year=2021)

    assert result["acs_year"] == 2021
    assert "/2021/acs/acs5" in m.request_history[0].url
