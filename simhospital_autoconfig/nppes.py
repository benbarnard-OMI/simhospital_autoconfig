"""
NPPES API client for fetching hospital/organization and practitioner data.

API Documentation: https://npiregistry.cms.hhs.gov/api-page
"""
from __future__ import annotations

import logging
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import requests

from .specialties import CLINICAL_ROSTER, get_hl7_code

NPPES_API_BASE = "https://npiregistry.cms.hhs.gov/api/"
logger = logging.getLogger(__name__)


@dataclass
class NPPESAddress:
    """Represents an address from NPPES."""
    address_1: str | None = None
    address_2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country_code: str | None = None
    address_purpose: str | None = None
    address_type: str | None = None


@dataclass
class NPPESTaxonomy:
    """Represents a taxonomy from NPPES."""
    code: str
    desc: str
    primary: bool
    state: str | None = None
    license: str | None = None


@dataclass
class NPPESIdentifier:
    """Represents an identifier from NPPES."""
    code: str
    desc: str
    identifier: str
    state: str | None = None
    issuer: str | None = None


@dataclass
class NPPESResult:
    """Represents a parsed NPPES API result for an organization."""
    npi: str
    enumeration_type: str
    organization_name: str | None = None
    other_names: list[dict[str, str]] | None = None
    address: NPPESAddress | None = None
    taxonomies: list[NPPESTaxonomy] | None = None
    identifiers: list[NPPESIdentifier] | None = None
    raw_response: dict[str, Any] | None = None


@dataclass
class NPPESearchResults:
    """Outcome of an organization name search.

    ``total`` is the API's reported result_count, which can exceed ``len(results)``
    when the search matched more organizations than one page holds. Callers need
    that distinction: a single exact match among a truncated page is not the same
    as a single match overall.
    """

    results: list[NPPESResult]
    total: int = 0

    @property
    def truncated(self) -> bool:
        return self.total > len(self.results)


# NPPES caps a single response; ask for the maximum so an exact match is not missed.
DEFAULT_SEARCH_LIMIT = 200


class NPPESClient:
    """Client for interacting with the NPPES Registry API."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    @staticmethod
    def validate_npi(npi: str) -> None:
        """Validate that an NPI is a 10-digit numeric string."""
        if not re.fullmatch(r"\d{10}", npi):
            raise ValueError(f"Invalid NPI format: {npi}. Expected 10 digits.")

    def _request_with_backoff(self, params: dict[str, str]) -> dict[str, Any]:
        """Make an API request with exponential backoff on rate limits."""
        max_attempts = 5
        base_delay = 1.0
        for attempt in range(1, max_attempts + 1):
            response = requests.get(
                NPPES_API_BASE,
                params=params,
                timeout=self.timeout,
            )
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

        return self._parse_organization(data.get("results", [{}])[0], npi=npi)

    def _parse_organization(
        self, result: dict[str, Any], npi: str | None = None
    ) -> NPPESResult:
        """Parse one NPPES result into an NPPESResult.

        Shared by the NPI lookup and the name search so both interpret addresses,
        taxonomies and identifiers identically.
        """
        basic = result.get("basic", {})
        org_name = basic.get("organization_name")
        other_names = result.get("other_names") or []
        if not org_name and other_names:
            org_name = other_names[0].get("organization_name")

        # Prefer the LOCATION address: MAILING is frequently an administrative office
        # in a different ZIP with a different population, which would send the Census
        # lookup to the wrong ZCTA.
        address = None
        addresses = result.get("addresses") or []
        location_addr = next((a for a in addresses if a.get("address_purpose") == "LOCATION"), None)
        if location_addr:
            address = self._parse_address(location_addr)
        elif addresses:
            address = self._parse_address(addresses[0])

        return NPPESResult(
            npi=npi or result.get("number") or "",
            enumeration_type=result.get("enumeration_type") or "NPI-2",
            organization_name=org_name,
            other_names=other_names if other_names else None,
            address=address,
            taxonomies=self._parse_taxonomies(result.get("taxonomies", [])),
            identifiers=self._parse_identifiers(result.get("identifiers", [])),
            raw_response=result,
        )

    def search_organizations(
        self,
        organization_name: str,
        state: str,
        limit: int = DEFAULT_SEARCH_LIMIT,
        version: str = "2.1",
    ) -> NPPESearchResults:
        """
        Search NPPES for organizations by name and state.

        The match is fuzzy: searching "Rush University Medical Center" also returns
        "Department of Psychiatry at Rush", and a single facility can hold several
        NPIs across campuses. Callers are expected to filter to exact name matches
        and to refuse to guess when more than one remains.

        Args:
            organization_name: Full or partial legal business name
            state: Two-letter state abbreviation
            limit: Maximum results to return in one page
            version: API version (default: 2.1)

        Returns:
            NPPESearchResults with the parsed page and the API's total match count
        """
        params = {
            "organization_name": organization_name,
            "state": state,
            # Organizations only; NPI-1 would return individual practitioners.
            "enumeration_type": "NPI-2",
            "limit": limit,
            "version": version,
        }
        data = self._request_with_backoff(params)
        total = int(data.get("result_count") or 0)
        results = [
            self._parse_organization(result) for result in data.get("results", []) or []
        ]
        if total > len(results):
            logger.warning(
                "NPPES matched %d organizations for %r in %s but returned only %d; "
                "an exact match may be missing. Narrow the search or use --npi.",
                total,
                organization_name,
                state,
                len(results),
            )
        return NPPESearchResults(results=results, total=total)

    def _parse_address(self, address_data: dict[str, Any]) -> NPPESAddress | None:
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

    def _parse_taxonomies(self, taxonomy_data: list[dict[str, Any]]) -> list[NPPESTaxonomy]:
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

    def _parse_identifiers(self, identifier_data: list[dict[str, Any]]) -> list[NPPESIdentifier]:
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
        taxonomy_descriptions: Sequence[str] = CLINICAL_ROSTER,
        limit_per_specialty: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Query NPPES for individual practitioners near a ZIP code.

        Args:
            zip_code: Postal code; only the first five digits are used
            taxonomy_descriptions: NUCC taxonomy descriptions to search for. These are
                search terms, not HL7 codes -- each practitioner's specialty is derived
                from their own primary taxonomy. The previous signature was ambiguous
                and __main__ passed HL7 codes, so NPPES was queried with
                taxonomy_description=MED and matched nothing.
            limit_per_specialty: Max results per search term

        Returns:
            List of doctor records with id, surname, firstname, prefix and specialty
        """
        doctors: list[dict[str, Any]] = []
        seen: set[str] = set()
        for description in taxonomy_descriptions:
            params = {
                "taxonomy_description": description,
                "postal_code": zip_code[:5],
                # Individuals only; without this an organizational NPI can be returned
                # and written into doctors.yml as a person.
                "enumeration_type": "NPI-1",
                "limit": limit_per_specialty,
                "version": "2.1",
            }
            data = self._request_with_backoff(params)
            for result in data.get("results", []):
                basic = result.get("basic", {})
                npi = result.get("number")
                if not npi or npi in seen:
                    continue
                seen.add(npi)

                taxonomies = result.get("taxonomies") or []
                primary = next(
                    (t for t in taxonomies if t.get("primary")),
                    taxonomies[0] if taxonomies else None,
                )
                practitioner_desc = (primary or {}).get("desc") or description

                doctors.append(
                    {
                        "id": npi,
                        "surname": basic.get("last_name", ""),
                        "firstname": basic.get("first_name", ""),
                        # Individual records carry name_prefix, not middle_name; reading
                        # middle_name always yielded an empty prefix.
                        "prefix": basic.get("name_prefix") or "Dr",
                        "specialty": get_hl7_code(practitioner_desc),
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
