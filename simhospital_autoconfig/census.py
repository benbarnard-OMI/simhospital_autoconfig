"""
Census ACS fetcher for US demographics data.

API Documentation: https://www.census.gov/data/developers/guidance/api-user-guide.html
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

CENSUS_API_BASE = "https://api.census.gov/data"
logger = logging.getLogger(__name__)

# ACS table B03002, "Hispanic or Latino Origin by Race".
# Variable -> HL7 v2 Table 0005 / CDC race-ethnicity code.
#
# Labels verified against https://api.census.gov/data/2023/acs/acs5/groups/B03002.json.
# B03002_002E is the *not*-Hispanic total and B03002_012E is the Hispanic total; the
# previous mapping had these inverted and misassigned every other variable, which would
# have reported a ~93% non-Hispanic ZCTA as ~93% Hispanic.
#
# These eight variables partition B03002_001E (total population) exactly: 012 is the
# Hispanic-or-Latino total, 003-009 are the not-Hispanic race categories. 008 and 009
# both map to 2131-1 ("other"), so counts are summed per code, not overwritten.
#
# Codes are the dashed CDC/HL7 form rather than the single letters A-Z used by the
# upstream UK ethnicity.csv, so US-derived rows cannot collide with those CE IDs.
RACE_ETHNICITY_MAP = {
    "B03002_012E": "2135-2",  # Hispanic or Latino
    "B03002_003E": "2106-3",  # White alone, not Hispanic
    "B03002_004E": "2054-5",  # Black or African American alone, not Hispanic
    "B03002_005E": "1002-5",  # American Indian and Alaska Native alone, not Hispanic
    "B03002_006E": "2028-9",  # Asian alone, not Hispanic
    "B03002_007E": "2076-8",  # Native Hawaiian and Other Pacific Islander alone, not Hispanic
    "B03002_008E": "2131-1",  # Some other race alone, not Hispanic
    "B03002_009E": "2131-1",  # Two or more races, not Hispanic
}

ETHNICITY_LABELS = {
    "2135-2": "Hispanic or Latino",
    "2106-3": "White",
    "2054-5": "Black or African American",
    "1002-5": "American Indian or Alaska Native",
    "2028-9": "Asian",
    "2076-8": "Native Hawaiian or Other Pacific Islander",
    "2131-1": "Some other race or two or more races",
}

# Most recent ACS 5-year release verified to serve ZCTA data as of 2026-10.
DEFAULT_ACS_YEAR = 2023

# B01001_001E is the only sex-by-age variable any generator consumes (total
# population). The full 49-variable age breakdown was fetched but never read, and
# requesting it alongside B03002 exceeded the Census API's 50-variable cap per
# request, which made every call fail with HTTP 400.
TOTAL_POPULATION_VARIABLE = "B01001_001E"


def _as_count(value: Any) -> int:
    """Coerce an ACS estimate to a non-negative int.

    ACS uses large negative sentinels (e.g. -666666666) for estimates that are not
    available, and a missing variable comes back as None. Either would otherwise
    produce a negative or crashing frequency downstream.
    """
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


class CensusClient:
    """Client for interacting with the US Census Bureau ACS API."""

    def __init__(self, api_key: str | None = None, timeout: int = 30):
        self.api_key = api_key or os.environ.get("CENSUS_API_KEY")
        self.timeout = timeout

    def _request(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        """Make an API request with retry logic."""
        max_attempts = 3
        base_delay = 1.0
        last_exception: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                last_exception = exc
                if attempt < max_attempts:
                    wait = base_delay * attempt
                    logger.warning(
                        "Census API request failed (attempt %d/%d). Retrying in %.1fs.",
                        attempt,
                        max_attempts,
                        wait,
                    )
                    time.sleep(wait)
        raise last_exception  # type: ignore[misc]

    def _build_acs_url(self, year: int = DEFAULT_ACS_YEAR) -> str:
        return f"{CENSUS_API_BASE}/{year}/acs/acs5"

    def get_demographics(self, zcta: str, year: int = DEFAULT_ACS_YEAR) -> dict[str, Any]:
        """
        Fetch demographics for a ZIP Code Tabulation Area.

        Args:
            zcta: ZIP Code Tabulation Area (e.g., "60612")
            year: ACS 5-year release to query

        Returns:
            Dictionary with total_population, ethnicity (HL7/CDC code -> count),
            ethnicity_labels (code -> label), zcta and acs_year.

        Raises:
            ValueError: If no API key is configured, or the API returns no row
                for the given ZCTA.
        """
        if not self.api_key:
            # Without a key api.census.gov answers with an HTTP 200 HTML "Missing Key"
            # page. That previously surfaced as an opaque JSON decode error after three
            # retries, and the caller's broad except turned it into a silent fallback to
            # UK default demographics.
            raise ValueError(
                "CENSUS_API_KEY is not set. api.census.gov requires a key and returns an "
                "HTML 'Missing Key' page without one. Get a free key at "
                "https://api.census.gov/data/key_signup.html and add it to .env."
            )

        url = self._build_acs_url(year)
        params = {
            # B03002 must be requested explicitly; reading it from a response that only
            # asked for B01001 silently yielded zeros for every ethnicity count.
            "get": ",".join(["NAME", *RACE_ETHNICITY_MAP, TOTAL_POPULATION_VARIABLE]),
            "for": f"zip code tabulation area:{zcta}",
            "key": self.api_key,
        }

        data = self._request(url, params)
        if not data or len(data) < 2:
            raise ValueError(f"No Census data returned for ZCTA: {zcta}")

        headers, values = data[0], data[1]
        row = dict(zip(headers, values))

        ethnicity: dict[str, int] = {}
        for var, code in RACE_ETHNICITY_MAP.items():
            # B03002_008E and _009E share code 2131-1, so accumulate rather than overwrite.
            ethnicity[code] = ethnicity.get(code, 0) + _as_count(row.get(var))

        return {
            "total_population": _as_count(row.get(TOTAL_POPULATION_VARIABLE)),
            "ethnicity": ethnicity,
            "ethnicity_labels": dict(ETHNICITY_LABELS),
            "zcta": zcta,
            "acs_year": year,
        }
