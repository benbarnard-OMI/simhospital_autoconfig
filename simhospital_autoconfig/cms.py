"""
CMS Hospital Data Fetcher for hospital type, departments, and location data.

Dataset: Hospital General Information, served by the CMS Provider Data Catalog.
https://data.cms.gov/provider-data/dataset/xubh-q36u

The Socrata endpoint this module used to call
(https://data.cms.gov/resource/xubh-q36u.json) was decommissioned and now returns
HTTP 410 Gone. The dataset itself is alive in the Provider Data Catalog, but three
things differ from the old API:

* Server-side filtering does not work. ``filter[field][value]=`` is silently
  ignored and ``conditions[...]`` fails JSON-schema validation; both return the
  full unfiltered result set (5,419 rows). The bulk CSV is therefore downloaded
  once, cached, and filtered locally.
* The bulk CSV URL embeds a version token that changes on every data refresh, so
  it is resolved through the metastore at runtime rather than hardcoded.
* Column names are human-readable ("Facility ID", "City/Town") rather than
  Socrata snake_case, and ``Emergency Services`` is "Yes"/"No", not "Y"/"N".

The catalog has no NPI column, so an NPI cannot be resolved directly. The usable
join keys are the CCN (``Facility ID``), or facility name plus state. NPPES does
not always publish a CCN -- for NPI 1730209545 it exposes only a Medicaid
identifier -- so name-plus-state is the practical path.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from typing import Any

import requests

logger = logging.getLogger(__name__)

CMS_PDC_BASE = "https://data.cms.gov/provider-data/api/1"
HOSPITAL_GENERAL_INFO_DATASET = "xubh-q36u"

# Column names exactly as they appear in the Hospital General Information CSV.
COL_FACILITY_ID = "Facility ID"
COL_FACILITY_NAME = "Facility Name"
COL_ADDRESS = "Address"
COL_CITY = "City/Town"
COL_STATE = "State"
COL_ZIP = "ZIP Code"
COL_COUNTY = "County/Parish"
COL_PHONE = "Telephone Number"
COL_HOSPITAL_TYPE = "Hospital Type"
COL_OWNERSHIP = "Hospital Ownership"
COL_EMERGENCY = "Emergency Services"

TRUTHY = {"yes", "y", "true"}


def normalize_name(name: str) -> str:
    """Uppercase, strip punctuation and collapse whitespace for tolerant matching.

    Public because NPPES and CMS punctuate and capitalize facility names
    differently, and both the catalog filter and the CLI's exact-match check need
    the same folding to compare them.
    """
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]", "", (name or "").upper())).strip()


class CMSClient:
    """Client for the CMS Provider Data Catalog."""

    def __init__(self, timeout: int = 120):
        self.timeout = timeout
        self._rows: list[dict[str, str]] | None = None
        self._download_url: str | None = None

    def _get_json(self, url: str, params: dict[str, str] | None = None) -> Any:
        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def resolve_download_url(self) -> str:
        """Resolve the bulk CSV URL via the metastore.

        The URL contains a version token that changes whenever CMS refreshes the
        data, so it cannot be hardcoded.
        """
        if self._download_url:
            return self._download_url

        dataset = self._get_json(
            f"{CMS_PDC_BASE}/metastore/schemas/dataset/items/{HOSPITAL_GENERAL_INFO_DATASET}",
            {"show-reference-ids": "true"},
        )
        distributions = dataset.get("distribution") or []
        if not distributions:
            raise ValueError(f"CMS dataset {HOSPITAL_GENERAL_INFO_DATASET} exposes no distribution")
        distribution_id = distributions[0].get("identifier")

        distribution = self._get_json(
            f"{CMS_PDC_BASE}/metastore/schemas/distribution/items/{distribution_id}"
        )
        url = (distribution.get("data") or {}).get("downloadURL")
        if not url:
            raise ValueError(f"CMS distribution {distribution_id} has no downloadURL")

        self._download_url = url
        return url

    def load_rows(self) -> list[dict[str, str]]:
        """Download and cache the full Hospital General Information table."""
        if self._rows is not None:
            return self._rows

        url = self.resolve_download_url()
        logger.info("Downloading CMS Hospital General Information from %s", url)
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        # The file carries a UTF-8 BOM.
        text = response.content.decode("utf-8-sig")
        self._rows = list(csv.DictReader(io.StringIO(text)))
        logger.info("Loaded %d CMS hospital rows", len(self._rows))
        return self._rows

    def get_hospital_by_ccn(self, ccn: str) -> dict[str, str]:
        """
        Look up a hospital by its CMS Certification Number.

        Args:
            ccn: CMS Certification Number, the catalog's ``Facility ID``

        Returns:
            The raw catalog row

        Raises:
            ValueError: If no facility has that CCN
        """
        wanted = (ccn or "").strip()
        for row in self.load_rows():
            if (row.get(COL_FACILITY_ID) or "").strip() == wanted:
                return dict(row)
        raise ValueError(f"No CMS hospital found for CCN: {ccn}")

    def search_hospitals(
        self,
        name: str | None = None,
        state: str | None = None,
        zip_code: str | None = None,
    ) -> list[dict[str, str]]:
        """
        Filter the catalog locally by name, state and/or ZIP code.

        Filtering has to happen client-side: the catalog's query API ignores
        ``filter`` parameters and rejects ``conditions``.

        Args:
            name: Facility name, matched case- and punctuation-insensitively
            state: Two-letter state abbreviation, exact
            zip_code: ZIP code, compared on its first five digits

        Returns:
            Matching catalog rows, possibly empty
        """
        state_up = (state or "").strip().upper()
        zip_digits = (zip_code or "")[:5]
        needle = normalize_name(name) if name else None

        matches = []
        for row in self.load_rows():
            if state_up and (row.get(COL_STATE) or "").strip().upper() != state_up:
                continue
            if zip_digits and (row.get(COL_ZIP) or "").strip()[:5] != zip_digits:
                continue
            if needle:
                haystack = normalize_name(row.get(COL_FACILITY_NAME) or "")
                if needle != haystack and needle not in haystack:
                    continue
            matches.append(dict(row))
        return matches

    def get_hospital_by_zip(self, zip_code: str) -> list[dict[str, str]]:
        """
        Return every hospital in a ZIP code.

        A ZCTA can contain several facilities, so this returns a list and leaves
        the choice to the caller rather than silently picking one.

        Args:
            zip_code: Five-digit ZIP code

        Returns:
            Matching catalog rows, possibly empty
        """
        return self.search_hospitals(zip_code=zip_code)

    def map_to_simhospital_config(self, hospital: dict[str, Any]) -> dict[str, Any]:
        """
        Map a hospital record to the shape the generators consume.

        Accepts either a raw catalog row (human-readable column names) or an
        already-normalized dict, so NPPES-derived fallbacks keep working.

        Args:
            hospital: Raw CMS catalog row, or a normalized dict

        Returns:
            Dictionary with hospital_type, emergency_services (bool),
            hospital_name, ccn and address.
        """
        if COL_FACILITY_NAME in hospital:
            return {
                "hospital_type": hospital.get(COL_HOSPITAL_TYPE, ""),
                # The catalog uses "Yes"/"No". The previous comparison against "y"
                # evaluated False for every hospital, so ED was always reported absent.
                "emergency_services": str(hospital.get(COL_EMERGENCY, "")).strip().lower() in TRUTHY,
                "hospital_name": hospital.get(COL_FACILITY_NAME),
                "ccn": hospital.get(COL_FACILITY_ID),
                "address": {
                    "street": hospital.get(COL_ADDRESS),
                    "city": hospital.get(COL_CITY),
                    "state": hospital.get(COL_STATE),
                    "postal_code": hospital.get(COL_ZIP),
                    "county": hospital.get(COL_COUNTY),
                },
            }

        raw_emergency = hospital.get("emergency_services", "")
        if isinstance(raw_emergency, str):
            emergency = raw_emergency.strip().lower() in TRUTHY
        else:
            emergency = bool(raw_emergency)

        return {
            "hospital_type": hospital.get("hospital_type", ""),
            "emergency_services": emergency,
            "hospital_name": hospital.get("hospital_name"),
            "ccn": hospital.get("ccn"),
            "address": hospital.get("address") or {},
        }
