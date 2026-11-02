"""Integration tests for CMSClient.

The mocks reproduce the real Provider Data Catalog contract: two metastore hops to
resolve a versioned download URL, then a CSV whose columns are human-readable.
"""

import pytest
import requests_mock

from simhospital_autoconfig.__main__ import _find_ccn
from simhospital_autoconfig.cms import (
    CMS_OPEN_DATA_CATALOG,
    CMS_PDC_BASE,
    HOSPITAL_ENROLLMENTS_SERIES,
    HOSPITAL_GENERAL_INFO_DATASET,
    CMSClient,
)
from simhospital_autoconfig.nppes import NPPESClient, NPPESResult

DATASET_URL = (
    f"{CMS_PDC_BASE}/metastore/schemas/dataset/items/{HOSPITAL_GENERAL_INFO_DATASET}"
)
DISTRIBUTION_ID = "90fa4cdf-f49d-556d-8790-d32fbbec40c6"
DISTRIBUTION_URL = f"{CMS_PDC_BASE}/metastore/schemas/distribution/items/{DISTRIBUTION_ID}"
# The real URL embeds a version token that CMS changes on every data refresh.
CSV_URL = (
    "https://data.cms.gov/provider-data/sites/default/files/resources/"
    "TOKEN_1785189955/Hospital_General_Information.csv"
)
ENROLLMENT_RELEASE = "https://data.cms.gov/data-api/v1/dataset/latest-enrollments/data-viewer"
ENROLLMENT_CSV_URL = "https://data.cms.gov/sites/files/hospital-enrollments.csv"
ENROLLMENT_CSV = (
    "NPI,MULTIPLE NPI FLAG,CCN\n"
    "1588612832,Y,140124\n"
    "1699921007,N,140119\n"
)

CSV_BODY = (
    "Facility ID,Facility Name,Address,City/Town,State,ZIP Code,County/Parish,"
    "Telephone Number,Hospital Type,Hospital Ownership,Emergency Services\n"
    "140124,JOHN H STROGER JR HOSPITAL,1901 W HARRISON ST,CHICAGO,IL,60612,COOK,"
    "(312) 864-6000,Acute Care Hospitals,Government - Local,Yes\n"
    "140119,RUSH UNIVERSITY MEDICAL CENTER,1653 W CONGRESS PKWY,CHICAGO,IL,60612,COOK,"
    "(312) 942-5000,Acute Care Hospitals,Voluntary non-profit - Private,Yes\n"
    "130001,PIEDMONT HOSPITAL,1968 PEACHTREE RD NW,ATLANTA,GA,30309,FULTON,"
    "(404) 351-1151,Acute Care Hospitals,Voluntary non-profit - Other,No\n"
)


def _mock_catalog(m):
    m.get(DATASET_URL, json={"distribution": [{"identifier": DISTRIBUTION_ID}]})
    m.get(DISTRIBUTION_URL, json={"data": {"downloadURL": CSV_URL}})
    m.get(CSV_URL, text=CSV_BODY, headers={"Content-Type": "text/csv"})


def test_resolves_the_download_url_through_the_metastore():
    """The CSV URL carries a version token, so it cannot be hardcoded."""
    client = CMSClient()
    with requests_mock.Mocker() as m:
        _mock_catalog(m)
        assert client.resolve_download_url() == CSV_URL
        # Both metastore hops must be consulted, then cached.
        assert len(m.request_history) == 2
        assert client.resolve_download_url() == CSV_URL
        assert len(m.request_history) == 2


def test_missing_distribution_raises():
    client = CMSClient()
    with requests_mock.Mocker() as m:
        m.get(DATASET_URL, json={"distribution": []})
        with pytest.raises(ValueError, match="exposes no distribution"):
            client.resolve_download_url()


def _mock_enrollments(m, csv_text=ENROLLMENT_CSV):
    m.get(
        CMS_OPEN_DATA_CATALOG,
        json={
            "datasetSeries": [
                {
                    "title": HOSPITAL_ENROLLMENTS_SERIES,
                    "last": {"@id": ENROLLMENT_RELEASE},
                }
            ],
            "dataset": [
                {
                    "@id": ENROLLMENT_RELEASE,
                    "distribution": [
                        {"mediaType": "text/csv", "downloadURL": ENROLLMENT_CSV_URL}
                    ],
                }
            ],
        },
    )
    content = csv_text.encode("utf-8") if isinstance(csv_text, str) else csv_text
    m.get(ENROLLMENT_CSV_URL, content=content)


def test_enrollment_csv_comes_from_latest_catalog_release():
    client = CMSClient()
    with requests_mock.Mocker() as m:
        _mock_enrollments(m)
        assert client.resolve_enrollment_download_url() == ENROLLMENT_CSV_URL
        assert client.resolve_enrollment_download_url() == ENROLLMENT_CSV_URL
    assert sum(r.url == CMS_OPEN_DATA_CATALOG for r in m.request_history) == 1


def test_get_primary_npi_by_exact_ccn_uses_main_npi_even_when_multiple_flag_is_set():
    client = CMSClient()
    with requests_mock.Mocker() as m:
        _mock_enrollments(m)
        assert client.get_primary_npi_by_ccn("140124") == "1588612832"


def test_empty_ccn_fails_before_download():
    client = CMSClient()
    with pytest.raises(ValueError, match="No CCN was provided"):
        client.get_primary_npi_by_ccn("")


def test_enrollment_csv_with_windows_1252_text_still_resolves_primary_npi():
    client = CMSClient()
    csv_bytes = (
        "NPI,MULTIPLE NPI FLAG,CCN,ORGANIZATION NAME\n"
        "1588612832,Y,140124,COOK COUNTY – HOSPITAL\n"
    ).encode("cp1252")
    with requests_mock.Mocker() as m:
        _mock_enrollments(m, csv_bytes)
        assert client.get_primary_npi_by_ccn("140124") == "1588612832"


@pytest.mark.parametrize(
    ("csv_text", "message"),
    [
        (
            "NPI,MULTIPLE NPI FLAG,CCN\n1699921007,N,140119\n",
            "0 rows for CCN 140124",
        ),
        (
            "NPI,MULTIPLE NPI FLAG,CCN\n"
            "1588612832,Y,140124\n1234567890,Y,140124\n",
            "2 rows for CCN 140124",
        ),
        (
            "NPI,MULTIPLE NPI FLAG,CCN\n, N,140124\n",
            "no valid primary NPI",
        ),
        (
            "NPI,MULTIPLE NPI FLAG,CCN\n12345,N,140124\n",
            "no valid primary NPI",
        ),
    ],
)
def test_invalid_or_ambiguous_enrollment_rows_fail(csv_text, message):
    client = CMSClient()
    with requests_mock.Mocker() as m:
        _mock_enrollments(m, csv_text)
        with pytest.raises(ValueError, match=message):
            client.get_primary_npi_by_ccn("140124")


def test_get_hospital_by_ccn():
    client = CMSClient()
    with requests_mock.Mocker() as m:
        _mock_catalog(m)
        row = client.get_hospital_by_ccn("140124")
    assert row["Facility Name"] == "JOHN H STROGER JR HOSPITAL"
    assert row["Emergency Services"] == "Yes"


def test_get_hospital_by_ccn_unknown_raises():
    client = CMSClient()
    with requests_mock.Mocker() as m:
        _mock_catalog(m)
        with pytest.raises(ValueError, match="No CMS hospital found"):
            client.get_hospital_by_ccn("999999")


def test_search_by_name_and_state_tolerates_punctuation():
    """NPPES and CMS punctuate facility names differently."""
    client = CMSClient()
    with requests_mock.Mocker() as m:
        _mock_catalog(m)
        hits = client.search_hospitals(name="John H. Stroger Jr. Hospital", state="IL")
    assert [h["Facility ID"] for h in hits] == ["140124"]


def test_search_filters_by_state():
    client = CMSClient()
    with requests_mock.Mocker() as m:
        _mock_catalog(m)
        hits = client.search_hospitals(state="GA")
    assert [h["Facility ID"] for h in hits] == ["130001"]


def test_get_hospital_by_zip_returns_every_facility():
    """A ZCTA holds several hospitals; silently picking one would be wrong."""
    client = CMSClient()
    with requests_mock.Mocker() as m:
        _mock_catalog(m)
        hits = client.get_hospital_by_zip("60612")
    assert {h["Facility ID"] for h in hits} == {"140124", "140119"}


def test_rows_are_downloaded_once():
    """The catalog has no server-side filtering, so the whole CSV is cached."""
    client = CMSClient()
    with requests_mock.Mocker() as m:
        _mock_catalog(m)
        client.get_hospital_by_ccn("140124")
        client.get_hospital_by_ccn("140119")
        client.get_hospital_by_zip("60612")
    assert sum(1 for r in m.request_history if r.url == CSV_URL) == 1


def test_map_reads_yes_rather_than_y():
    """Regression: the catalog says "Yes"/"No".

    The old Socrata-oriented comparison was `.lower() == "y"`, which is False for
    "yes", so emergency_services evaluated False for all 4,495 hospitals that do
    have an ED and locations.yml always warned that ED was missing.
    """
    client = CMSClient()
    with requests_mock.Mocker() as m:
        _mock_catalog(m)
        yes_row = client.get_hospital_by_ccn("140124")
        no_row = client.get_hospital_by_ccn("130001")

    mapped = client.map_to_simhospital_config(yes_row)
    assert mapped["emergency_services"] is True
    assert mapped["hospital_name"] == "JOHN H STROGER JR HOSPITAL"
    assert mapped["hospital_type"] == "Acute Care Hospitals"
    assert mapped["ccn"] == "140124"
    assert mapped["address"] == {
        "street": "1901 W HARRISON ST",
        "city": "CHICAGO",
        "state": "IL",
        "postal_code": "60612",
        "county": "COOK",
    }

    assert client.map_to_simhospital_config(no_row)["emergency_services"] is False


def test_map_accepts_a_normalized_nppes_fallback():
    """__main__ builds this shape from NPPES when CMS has no match."""
    client = CMSClient()

    mapped = client.map_to_simhospital_config(
        {
            "hospital_name": "Test Hospital",
            "hospital_type": "Critical Access",
            "emergency_services": "Y",
        }
    )
    assert mapped["emergency_services"] is True
    assert mapped["hospital_name"] == "Test Hospital"

    assert client.map_to_simhospital_config({"emergency_services": "No"})[
        "emergency_services"
    ] is False
    assert client.map_to_simhospital_config({"emergency_services": False})[
        "emergency_services"
    ] is False
    assert client.map_to_simhospital_config({"emergency_services": True})[
        "emergency_services"
    ] is True


@pytest.mark.parametrize("identifier_code", [2, "02"])
def test_find_ccn_normalizes_numeric_and_string_identifier_codes(identifier_code):
    identifiers = NPPESClient()._parse_identifiers(
        [{"code": identifier_code, "desc": "Other", "identifier": "140124"}]
    )
    result = NPPESResult(
        npi="1730209545",
        enumeration_type="NPI-2",
        identifiers=identifiers,
    )

    assert _find_ccn(result) == "140124"


def test_find_ccn_does_not_match_a_different_numeric_identifier_code():
    identifiers = NPPESClient()._parse_identifiers(
        [{"code": 5, "desc": "Other", "identifier": "not-a-ccn"}]
    )
    result = NPPESResult(
        npi="1730209545",
        enumeration_type="NPI-2",
        identifiers=identifiers,
    )

    assert _find_ccn(result) is None
