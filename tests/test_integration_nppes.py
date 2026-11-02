"""Tests for NPPESClient.search_organizations and the shared organization parser.

The outgoing query is asserted as well as the parsed response: a mock that returns
whatever the test author expected is how the Census ethnicity defect stayed hidden.
"""

from __future__ import annotations

import pytest
import requests_mock

from simhospital_autoconfig.nppes import NPPES_API_BASE, NPPESClient

VALID_NPI = "1730209545"


def org(number, name, city="CHICAGO", state="IL", zip4="606123833"):
    """Build an NPPES organization result with both a MAILING and a LOCATION address."""
    return {
        "number": number,
        "enumeration_type": "NPI-2",
        "basic": {"organization_name": name},
        "other_names": [],
        "identifiers": [],
        "taxonomies": [
            {
                "code": "282N00000X",
                "desc": "General Acute Care Hospital",
                "primary": True,
                "state": state,
                "license": "X1",
            }
        ],
        "addresses": [
            {
                "address_purpose": "MAILING",
                "address_1": "1 ADMIN PLZ",
                "city": city,
                "state": state,
                "postal_code": "999999999",
                "country_code": "US",
            },
            {
                "address_purpose": "LOCATION",
                "address_1": "100 MAIN ST",
                "city": city,
                "state": state,
                "postal_code": zip4,
                "country_code": "US",
            },
        ],
    }


def test_search_sends_the_documented_parameters():
    """Regression guard on the request itself, not just the parsed result."""
    with requests_mock.Mocker() as m:
        m.get(NPPES_API_BASE, json={"result_count": 0, "results": []})
        NPPESClient().search_organizations("Rush University Medical Center", "IL")

    qs = m.request_history[0].qs  # requests_mock lowercases keys and values
    assert qs["organization_name"] == ["rush university medical center"]
    assert qs["state"] == ["il"]
    assert qs["enumeration_type"] == ["npi-2"], "NPI-1 would return individual practitioners"
    assert qs["limit"] == ["200"]
    assert qs["version"] == ["2.1"]
    assert "number" not in qs, "a name search must not reuse the NPI lookup parameter"


def test_search_parses_results_and_prefers_the_location_address():
    payload = {
        "result_count": 2,
        "results": [
            org("1699921007", "RUSH UNIVERSITY MEDICAL CENTER"),
            org("1487103644", "DEPARTMENT OF PSYCHIATRY AT RUSH"),
        ],
    }
    with requests_mock.Mocker() as m:
        m.get(NPPES_API_BASE, json=payload)
        found = NPPESClient().search_organizations("Rush", "IL")

    assert found.total == 2
    assert not found.truncated
    assert [r.npi for r in found.results] == ["1699921007", "1487103644"]

    first = found.results[0]
    assert first.organization_name == "RUSH UNIVERSITY MEDICAL CENTER"
    assert first.enumeration_type == "NPI-2"
    # MAILING is an administrative office in a different ZIP with a different
    # population; LOCATION is the facility and is what the ZCTA must come from.
    assert first.address.address_1 == "100 MAIN ST"
    assert first.address.postal_code == "606123833"
    assert first.taxonomies[0].desc == "General Acute Care Hospital"


def test_truncation_is_distinguishable_from_a_single_match():
    """One exact match on a truncated page is not the same as one match overall."""
    payload = {"result_count": 500, "results": [org("1699921007", "RUSH UNIVERSITY MEDICAL CENTER")]}
    with requests_mock.Mocker() as m:
        m.get(NPPES_API_BASE, json=payload)
        found = NPPESClient().search_organizations("Rush", "IL")

    assert found.total == 500
    assert len(found.results) == 1
    assert found.truncated


def test_no_matches_is_not_an_error():
    """Unlike the NPI lookup, an empty name search is a normal outcome the CLI reports."""
    with requests_mock.Mocker() as m:
        m.get(NPPES_API_BASE, json={"result_count": 0, "results": []})
        found = NPPESClient().search_organizations("Stroger", "IL")

    assert found.results == []
    assert found.total == 0
    assert not found.truncated


def test_missing_result_count_is_tolerated():
    with requests_mock.Mocker() as m:
        m.get(NPPES_API_BASE, json={"results": [org("1699921007", "RUSH")]})
        found = NPPESClient().search_organizations("Rush", "IL")

    assert found.total is None
    assert len(found.results) == 1
    assert found.truncated


@pytest.mark.parametrize("result_count", ["many", None])
def test_unusable_result_count_fails_closed(result_count):
    payload = {"result_count": result_count, "results": [org("1699921007", "RUSH")]}
    with requests_mock.Mocker() as m:
        m.get(NPPES_API_BASE, json=payload)
        found = NPPESClient().search_organizations("Rush", "IL")

    assert found.total is None
    assert found.truncated


def test_npi_lookup_still_works_after_the_shared_parser_refactor():
    payload = {
        "result_count": 1,
        "results": [org(VALID_NPI, "COOK COUNTY", zip4="606123714")],
    }
    with requests_mock.Mocker() as m:
        m.get(NPPES_API_BASE, json=payload)
        result = NPPESClient().get_organization_by_npi(VALID_NPI)

    assert result.npi == VALID_NPI
    assert result.organization_name == "COOK COUNTY"
    assert result.address.postal_code == "606123714"
    assert result.taxonomies[0].primary is True


def test_npi_lookup_raises_when_absent():
    with requests_mock.Mocker() as m:
        m.get(NPPES_API_BASE, json={"result_count": 0, "results": []})
        with pytest.raises(ValueError, match="No NPPES result found"):
            NPPESClient().get_organization_by_npi(VALID_NPI)


@pytest.mark.parametrize("results", [None, [], "missing"])
def test_npi_lookup_raises_when_results_are_empty_or_null(results):
    payload = {"result_count": 1}
    if results != "missing":
        payload["results"] = results
    with requests_mock.Mocker() as m:
        m.get(NPPES_API_BASE, json=payload)
        with pytest.raises(ValueError, match="No NPPES result found"):
            NPPESClient().get_organization_by_npi(VALID_NPI)


def test_doctor_search_treats_null_results_as_empty():
    with requests_mock.Mocker() as m:
        m.get(NPPES_API_BASE, json={"result_count": 0, "results": None})
        doctors = NPPESClient().fetch_doctors_by_location(
            "60612", taxonomy_descriptions=("Internal Medicine",)
        )

    assert doctors == []


def test_organization_name_falls_back_to_other_names():
    result = org("1699921007", "IGNORED")
    result["basic"].pop("organization_name")
    result["other_names"] = [{"organization_name": "FORMER NAME LLC"}]
    with requests_mock.Mocker() as m:
        m.get(NPPES_API_BASE, json={"result_count": 1, "results": [result]})
        parsed = NPPESClient().get_organization_by_npi(VALID_NPI)

    assert parsed.organization_name == "FORMER NAME LLC"
