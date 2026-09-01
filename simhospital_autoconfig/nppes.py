"""
NPPES API client for fetching hospital/organization data.

API Documentation: https://npiregistry.cms.hhs.gov/api-page
"""

import requests
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


NPPES_API_BASE = "https://npiregistry.cms.hhs.gov/api/"


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
        params = {
            "number": npi,
            "enumeration_type": "NPI-2",  # Organization NPI
            "version": version,
        }
        
        response = requests.get(
            NPPES_API_BASE,
            params=params,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Check if we got results
        if not data.get("result_count") or data.get("result_count") == 0:
            raise ValueError(f"No NPPES result found for NPI: {npi}")
        
        result = data.get("results", [{}])[0]
        
        # Parse the result
        nppes_result = NPPESResult(
            npi=npi,
            enumeration_type="NPI-2",
            organization_name=result.get("basic", {}).get("organization_name"),
            other_names=result.get("other_names"),
            address=self._parse_address(result.get("addresses", [{}])[0]) if result.get("addresses") else None,
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
            taxonomies.append(NPPESTaxonomy(
                code=t.get("code", ""),
                desc=t.get("desc", ""),
                primary=t.get("primary", False),
                state=t.get("state"),
                license=t.get("license"),
            ))
        return taxonomies

    def _parse_identifiers(self, identifier_data: List[Dict[str, Any]]) -> List[NPPESIdentifier]:
        """Parse identifiers from NPPES response."""
        identifiers = []
        for i in identifier_data:
            identifiers.append(NPPESIdentifier(
                code=i.get("code", ""),
                desc=i.get("desc", ""),
                identifier=i.get("identifier", ""),
                state=i.get("state"),
                issuer=i.get("issuer"),
            ))
        return identifiers


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
