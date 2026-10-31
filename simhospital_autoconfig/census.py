"""
Census ACS fetcher for US demographics data.

API Documentation: https://www.census.gov/data/developers/guidance/api-user-guide.html
"""

import logging
import os
import time
from typing import Any, Dict, Optional

import requests

CENSUS_API_BASE = "https://api.census.gov/data"
logger = logging.getLogger(__name__)

RACE_ETHNICITY_MAP = {
    "B03002_002E": "H",
    "B03002_008E": "W",
    "B03002_009E": "B",
    "B03002_011E": "A",
    "B03002_005E": "HL",
    "B03002_004E": "HP",
    "B03002_003E": "HM",
    "B03002_010E": "AI",
    "B03002_012E": "NH",
    "B03002_006E": "HO",
    "B03002_013E": "SR",
    "B03002_014E": "TM",
}

SEX_AGE_VARIABLES = [
    "B01001_001E",
    "B01001_002E",
    "B01001_003E",
    "B01001_004E",
    "B01001_005E",
    "B01001_006E",
    "B01001_007E",
    "B01001_008E",
    "B01001_009E",
    "B01001_010E",
    "B01001_011E",
    "B01001_012E",
    "B01001_013E",
    "B01001_014E",
    "B01001_015E",
    "B01001_016E",
    "B01001_017E",
    "B01001_018E",
    "B01001_019E",
    "B01001_020E",
    "B01001_021E",
    "B01001_022E",
    "B01001_023E",
    "B01001_024E",
    "B01001_025E",
    "B01001_026E",
    "B01001_027E",
    "B01001_028E",
    "B01001_029E",
    "B01001_030E",
    "B01001_031E",
    "B01001_032E",
    "B01001_033E",
    "B01001_034E",
    "B01001_035E",
    "B01001_036E",
    "B01001_037E",
    "B01001_038E",
    "B01001_039E",
    "B01001_040E",
    "B01001_041E",
    "B01001_042E",
    "B01001_043E",
    "B01001_044E",
    "B01001_045E",
    "B01001_046E",
    "B01001_047E",
    "B01001_048E",
    "B01001_049E",
]


class CensusClient:
    """Client for interacting with the US Census Bureau ACS API."""

    def __init__(self, api_key: Optional[str] = None, timeout: int = 30):
        self.api_key = api_key or os.environ.get("CENSUS_API_KEY")
        self.timeout = timeout

    def _request(self, url: str, params: Dict[str, str]) -> Dict[str, Any]:
        """Make an API request with retry logic."""
        max_attempts = 3
        base_delay = 1.0
        last_exception: Optional[Exception] = None
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

    def _build_acs_url(self, year: int = 2021) -> str:
        return f"{CENSUS_API_BASE}/{year}/acs/acs5"

    def get_demographics(self, zcta: str) -> Dict[str, Any]:
        """
        Fetch demographics for a ZIP Code Tabulation Area.

        Args:
            zcta: ZIP Code Tabulation Area (e.g., "60601")

        Returns:
            Dictionary with total population, ethnicity counts, and sex/age counts

        Raises:
            ValueError: If the API key is required but missing
        """
        if not self.api_key:
            logger.warning("Census API key not set. Requests may be throttled.")

        url = self._build_acs_url()
        params = {
            "get": ",".join(["NAME"] + SEX_AGE_VARIABLES),
            "for": f"zip code tabulation area:{zcta}",
            "key": self.api_key or "",
        }

        data = self._request(url, params)
        if not data or len(data) < 2:
            raise ValueError(f"No Census data returned for ZCTA: {zcta}")

        headers = data[0]
        values = data[1]
        row = dict(zip(headers, values))

        ethnicity: Dict[str, int] = {}
        for var, code in RACE_ETHNICITY_MAP.items():
            ethnicity[code] = int(row.get(var, 0))

        sex_by_age: Dict[str, int] = {}
        for var in SEX_AGE_VARIABLES:
            sex_by_age[var] = int(row.get(var, 0))

        return {
            "total_population": int(row.get("B01001_001E", 0)),
            "ethnicity": ethnicity,
            "sex_by_age": sex_by_age,
            "zcta": zcta,
        }
