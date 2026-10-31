"""
NPPES API client for fetching hospital/organization and practitioner data.

API Documentation: https://npiregistry.cms.hhs.gov/api-page
"""

import re
import time
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

import requests

NPPES_API_BASE = "https://npiregistry.cms.hhs.gov/api/"
logger = logging.getLogger(__name__)


@dataclass
class NPPESAddress:
    """Represents an address from NPPES."""
    address_1: Optional[str] = None
    address_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country_code: Optional[str] = None
    address_purpose: Optional[str] = None
    address_type: Optional[str] = None


@dataclass
class NPPESTaxonomy:
    """Represents a taxonomy from NPPES."""
    code: str
    desc: str
    primary: bool
    state: Optional[str] = None
    license: Optional[str] = None


@dataclass
class NPPESIdentifier:
    """Represents an identifier from NPPES."""
    code: str
    desc: str
    identifier: str
    state: Optional[str] = None
    issuer: Optional[str] = None


@dataclass
class NPPESResult:
    """Represents a parsed NPPES API result for an organization."""
    npi: str
    enumeration_type: str
    organization_name: Optional[str] = None
    other_names: Optional[List[Dict[str, str]]] = None
    address: Optional[NPPESAddress] = None
    taxonomies: Optional[List[NPPESTaxonomy]] = None
    identifiers: Optional[List[NPPESIdentifier]] = None
    raw_response: Optional[Dict[str, Any]] = None


class NPPESClient:
    """Client for interacting with the NPPES Registry API."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    @staticmethod
    def validate_npi(npi: str) -> None:
        """Validate that an NPI is a 10-digit numeric string."""
        if not re.fullmatch(r"\d{10}", npi):
            raise ValueError(f"Invalid NPI format: {npi}. Expected 10 digits.")

    def _request_with_backoff(self, params: Dict[str, str]) -> Dict[str, Any]:
        """Make an API request with exponential backoff on rate limits."""
        max_attempts = 5
        base_delay = 1.0
        last_response = None
        for attempt in range(1, max_attempts + 1):
            response = requests.get(
                NPPES_API_BASE,
                params=params,
                timeout=self.timeout,
            )
            last_response = response
            if response.status_code != 429:
                response.raise_for_status()
                return response.json()
            wait = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "Rate limited by NPPES (attempt %d/%d). Retrying in %.1fs.",
                attempt,
                max_attempts,
                wait,
            )
            time.sleep(wait)
        raise requests.HTTPError(
            f"NPPES rate-limit persisted after {max_attempts} attempts."
        )

    def get_organization_by_npi(self, npi: str, version: str = "2.1") -> NPPESResult:
        """
        Fetch organization data from NPPES by NPI number.

        Args:
            npi: The NPI number to look up
            version: API version (default: 2.1)

        Returns:
            NPPESResult with parsed organization data

        Raises:
            requests.HTTPError: If the API request fails
            ValueError: If no result is found or NPI is invalid
        """
        self.validate_npi(npi)
        params = {
            "number": npi,
            "enumeration_type": "NPI-2",
            "version": version,
        }
        data = self._request_with_backoff(params)
        if not data.get("result_count") or data.get("result_count") == 0:
            raise ValueError(f"No NPPES result found for NPI: {npi}")

        result = data.get("results", [{}])[0]
        org_name = result.get("basic", {}).get("organization_name")
        other_names = result.get("other_names") or []
        if not org_name and other_names:
            org_name = other_names[0].get("organization_name")

        address = None
        addresses = result.get("addresses") or []
        location_addr = next((a for a in addresses if a.get("address_purpose") == "LOCATION"), None)
        if location_addr:
            address = self._parse_address(location_addr)
        elif addresses:
            address = self._parse_address(addresses[0])

        nppes_result = NPPESResult(
            npi=npi,
            enumeration_type="NPI-2",
            organization_name=org_name,
            other_names=other_names if other_names else None,
            address=address,
            taxonomies=self._parse_taxonomies(result.get("taxonomies", [])),
            identifiers=self._parse_identifiers(result.get("identifiers", [])),
            raw_response=result,
        )
        return nppes_result

    def _parse_address(self, address_data: Dict[str, Any]) -> Optional[NPPESAddress]:
        """Parse address from NPPES response."""
        if not address_data:
            return None
        return NPPESAddress(
            address_1=address_data.get("address_1"),
            address_2=address_data.get("address_2"),
            city=address_data.get("city"),
            state=address_data.get("state"),
            postal_code=address_data.get("postal_code"),
            country_code=address_data.get("country_code"),
            address_purpose=address_data.get("address_purpose"),
            address_type=address_data.get("address_type"),
        )

    def _parse_taxonomies(self, taxonomy_data: List[Dict[str, Any]]) -> List[NPPESTaxonomy]:
        """Parse taxonomies from NPPES response."""
        taxonomies = []
        for t in taxonomy_data:
            taxonomies.append(
                NPPESTaxonomy(
                    code=t.get("code", ""),
                    desc=t.get("desc", ""),
                    primary=t.get("primary", False),
                    state=t.get("state"),
                    license=t.get("license"),
                )
            )
        return taxonomies

    def _parse_identifiers(self, identifier_data: List[Dict[str, Any]]) -> List[NPPESIdentifier]:
        """Parse identifiers from NPPES response."""
        identifiers = []
        for i in identifier_data:
            identifiers.append(
                NPPESIdentifier(
                    code=i.get("code", ""),
                    desc=i.get("desc", ""),
                    identifier=i.get("identifier", ""),
                    state=i.get("state"),
                    issuer=i.get("issuer"),
                )
            )
        return identifiers

    def fetch_doctors_by_location(
        self,
        zip_code: str,
        specialties: List[str],
        limit_per_specialty: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Query NPPES for practitioners by ZIP prefix and taxonomy description.

        Args:
            zip_code: Postal code prefix (e.g., "12345")
            specialties: List of taxonomy descriptions to search for
            limit_per_specialty: Max results per specialty

        Returns:
            Structured list of doctor records
        """
        doctors: List[Dict[str, Any]] = []
        seen = set()
        for specialty in specialties:
            params = {
                "taxonomy_description": specialty,
                "postal_code": zip_code,
                "limit": limit_per_specialty,
                "version": "2.1",
            }
            data = self._request_with_backoff(params)
            for result in data.get("results", []):
                basic = result.get("basic", {})
                first = basic.get("first_name", "")
                last = basic.get("last_name", "")
                doctor_id = result.get("number") or f"{last}-{first}-{specialty}"
                if doctor_id in seen:
                    continue
                seen.add(doctor_id)
                doctors.append(
                    {
                        "id": doctor_id,
                        "surname": last,
                        "firstname": first,
                        "prefix": basic.get("middle_name", ""),
                        "specialty": specialty,
                    }
                )
            time.sleep(0.5)
        return doctors


def get_hospital_data(npi: str) -> NPPESResult:
    """
    Convenience function to fetch hospital data from NPPES.

    Args:
        npi: The NPI number to look up

    Returns:
        NPPESResult with hospital data
    """
    client = NPPESClient()
    return client.get_organization_by_npi(npi)
