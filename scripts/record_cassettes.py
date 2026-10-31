"""Record vcrpy cassettes for NPI 1730209545 against the real NPPES, CMS, and Census APIs,
then generate the corresponding Simhospital configuration files.

Usage:
    python3 scripts/record_cassettes.py
"""

import logging
import os
import sys
from typing import Any, Dict, List, Optional

import requests
import vcr
import yaml

from simhospital_autoconfig.census import CensusClient, CENSUS_API_BASE, RACE_ETHNICITY_MAP
from simhospital_autoconfig.cms import CMSClient
from simhospital_autoconfig.generators import generate_all_configs
from simhospital_autoconfig.nppes import NPPESClient, NPPES_API_BASE

NPI = "1730209545"
ZCTA = "60601"
CASSETTE_NAME = f"test_simulator_validation[{NPI}]"
CASSETTE_DIR = "tests/cassettes"
OUTPUT_DIR = os.path.join("tests", "fixtures", NPI)
LOG_LEVEL = logging.INFO

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("record_cassettes")


def _strip_census_key(request: Any) -> Any:
    """Remove the Census API `key` parameter before the cassette is persisted."""
    try:
        from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
    except ImportError:
        return request
    parts = urlsplit(request.uri)
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    new_pairs = [(k, v) for (k, v) in pairs if k != "key"]
    new_query = urlencode(new_pairs, doseq=True)
    request.uri = urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))
    return request


def _record_cassette() -> Dict[str, Any]:
    """Use vcrpy to record live HTTP interactions and return the parsed data."""
    cassette_path = CASSETTE_NAME
    fixtures: Dict[str, Any] = {}

    nppes = NPPESClient()
    cms = CMSClient()
    census = CensusClient(api_key=os.environ.get("CENSUS_API_KEY") or "")

    nppes_vcr = vcr.VCR(
        cassette_library_dir=CASSETTE_DIR,
        record_mode="once",
        path_transformer=vcr.VCR.ensure_suffix(".yaml"),
        filter_query_parameters=["key"],
        before_record_request=_strip_census_key,
    )

    with nppes_vcr.use_cassette(cassette_path):
        nppes_result = nppes.get_organization_by_npi(NPI)
        fixtures["nppes"] = nppes_result
        logger.info("NPPES: %s", nppes_result.organization_name)

        hospital_data = None
        try:
            hospital_data = cms.get_hospital_by_npi(NPI)
            fixtures["cms"] = hospital_data
            logger.info("CMS: %s", hospital_data.get("hospital_name") if hospital_data else None)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("CMS request failed (continuing): %s", exc)
            hospital_data = None

        demographics: Optional[Dict[str, Any]] = None
        try:
            demographics = census.get_demographics(ZCTA)
            fixtures["census"] = demographics
            logger.info("Census demographics fetched.")
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Census request failed (likely no real key): %s", exc)
            logger.warning("Recording an empty Census response so the cassette stays valid.")
            census_url = f"{CENSUS_API_BASE}/2021/acs/acs5"
            params = {
                "get": ",".join(
                    ["NAME", "B01001_001E"] + list(RACE_ETHNICITY_MAP.keys())
                ),
                "for": f"zip code tabulation area:{ZCTA}",
                "key": os.environ.get("CENSUS_API_KEY", "") or "",
            }
            resp = requests.get(census_url, params=params, timeout=30)
            try:
                payload: Any = resp.json()
            except ValueError:
                payload = {"error": resp.text}
            fixtures["census_raw"] = payload
            demographics = None

    return {
        "nppes": fixtures.get("nppes"),
        "hospital_data": fixtures.get("cms"),
        "demographics": fixtures.get("census"),
        "census_raw": fixtures.get("census_raw"),
    }


def _build_demographics(raw: Any) -> Optional[Dict[str, Any]]:
    """Convert raw Census two-row JSON into a demographics dict, if possible."""
    if not raw or not isinstance(raw, list) or len(raw) < 2:
        return None
    headers = raw[0]
    values = raw[1]
    if not headers or not values:
        return None
    row = dict(zip(headers, values))

    ethnicity: Dict[str, int] = {}
    for var, code in RACE_ETHNICITY_MAP.items():
        val = row.get(var, 0)
        try:
            ethnicity[code] = int(val)
        except (TypeError, ValueError):
            ethnicity[code] = 0

    return {
        "total_population": int(row.get("B01001_001E", 0) or 0),
        "ethnicity": ethnicity,
        "sex_by_age": {
            var: int(row.get(var, 0) or 0)
            for var in headers
            if var.startswith("B01001_")
        },
        "zcta": row.get("zip code tabulation area", ZCTA),
    }


def _generate_configs(
    nppes_result: Any,
    hospital_data: Optional[Dict[str, Any]],
    demographics: Optional[Dict[str, Any]],
) -> List[str]:
    """Run generate_all_configs and return the list of files written."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    results = generate_all_configs(
        nppes_result,
        output_dir=OUTPUT_DIR,
        demographics=demographics,
        hospital_data=hospital_data,
    )
    for filename, content in results.items():
        path = os.path.join(OUTPUT_DIR, filename)
        with open(path, "w") as fh:
            fh.write(content)
        logger.info("Wrote %s (%d bytes)", path, len(content))
    return list(results.keys())


def main() -> int:
    os.makedirs(CASSETTE_DIR, exist_ok=True)
    cassette_path = os.path.join(CASSETTE_DIR, f"{CASSETTE_NAME}.yaml")

    if os.path.exists(cassette_path):
        logger.info("Cassette %s already exists; delete it to re-record.", cassette_path)
    else:
        logger.info("Recording cassette to %s ...", cassette_path)

    recorded = _record_cassette()
    nppes_result = recorded["nppes"]
    hospital_data = recorded["hospital_data"]
    demographics = recorded["demographics"]

    if demographics is None and recorded.get("census_raw") is not None:
        demographics = _build_demographics(recorded["census_raw"])

    if nppes_result is None:
        logger.error("NPPES lookup failed; aborting.")
        return 1

    files = _generate_configs(nppes_result, hospital_data, demographics)
    logger.info("Generated %d config files in %s", len(files), OUTPUT_DIR)

    if os.path.exists(cassette_path):
        size = os.path.getsize(cassette_path)
        logger.info("Cassette ready: %s (%d bytes)", cassette_path, size)
    else:
        logger.warning("Cassette file not found at %s", cassette_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())