"""
CMS Hospital Data Fetcher for hospital type, departments, and location data.

API Documentation: https://data.cms.gov/
Dataset: Hospital General Information (xubh-q36u)
"""

import logging
import os
from typing import Any, Dict, List, Optional

import requests

CMS_HOSPITAL_INFO_URL = "https://data.cms.gov/resource/xubh-q36u.json"
logger = logging.getLogger(__name__)


class CMSClient:
    """Client for interacting with CMS public datasets."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def get_hospital_by_ccn(self, ccn: str) -> Dict[str, Any]:
        """
        Fetch hospital data from CMS Hospital General Information by CCN.

        Args:
            ccn: CMS Certification Number

        Returns:
            Dictionary with hospital details
        """
        params = {
            "ccn": ccn,
            "$limit": 1,
        }
        response = requests.get(
            CMS_HOSPITAL_INFO_URL,
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        results = response.json()
        if not results:
            raise ValueError(f"No CMS hospital found for CCN: {ccn}")
        return results[0]

    def get_hospital_by_npi(self, npi: str) -> Optional[Dict[str, Any]]:
        """
        Search Hospital General Info by NPI/provider_id.

        Note: Most CMS datasets use CCN, but NPPES identifiers may include CCN.
        This method searches by provider_id when available.

        Args:
            npi: NPI number

        Returns:
            Hospital data dictionary or None if not found
        """
        params = {
            "provider_id": npi,
            "$limit": 1,
        }
        response = requests.get(
            CMS_HOSPITAL_INFO_URL,
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        results = response.json()
        return results[0] if results else None

    def get_hospital_services(self, zcta: str) -> List[str]:
        """
        Query for department presence in a ZCTA (optional).

        Args:
            zcta: ZIP Code Tabulation Area

        Returns:
            List of service codes present in the area
        """
        url = "https://data.cms.gov/resource/enh3-zyvv.json"
        params = {
            "zip_code": zcta,
            "$select": "service_code",
            "$group": "service_code",
        }
        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return [row.get("service_code") for row in response.json() if row.get("service_code")]

    def map_to_simhospital_config(self, hospital: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map CMS fields to Simhospital configuration.

        Args:
            hospital: Raw CMS hospital data

        Returns:
            Dictionary suitable for use with Simhospital generators
        """
        hospital_type = hospital.get("hospital_type", "")
        emergency_services = hospital.get("emergency_services", "").lower() == "y"

        return {
            "hospital_type": hospital_type,
            "emergency_services": emergency_services,
            "hospital_name": hospital.get("hospital_name"),
            "address": {
                "city": hospital.get("city"),
                "state": hospital.get("state"),
                "postal_code": hospital.get("zip_code"),
            },
        }
