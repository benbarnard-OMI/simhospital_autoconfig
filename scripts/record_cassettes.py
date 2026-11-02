"""Record vcrpy cassettes for a canonical NPI, then regenerate its config fixtures.

NPPES and Census are recorded through vcr so tests can replay them offline. CMS is
deliberately *not* recorded: the Provider Data Catalog has no working server-side
filter, so the client downloads a 1.4 MB bulk CSV, which would dwarf everything else
in the cassette. The resolved hospital record is persisted as JSON instead.

Usage:
    set -a; . ./.env; set +a          # loads CENSUS_API_KEY
    python3 scripts/record_cassettes.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import requests
import vcr

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from simhospital_autoconfig.census import CensusClient  # noqa: E402
from simhospital_autoconfig.cms import CMSClient  # noqa: E402
from simhospital_autoconfig.deterministic_checks import (  # noqa: E402
    format_check_report,
    run_deterministic_checks,
)
from simhospital_autoconfig.generators import generate_all_configs  # noqa: E402
from simhospital_autoconfig.nppes import NPPESClient  # noqa: E402

NPI = os.environ.get("FIXTURE_NPI", "1730209545")
CASSETTE_NAME = f"test_simulator_validation[{NPI}]"
CASSETTE_DIR = PROJECT_ROOT / "tests" / "cassettes"
OUTPUT_DIR = PROJECT_ROOT / "tests" / "fixtures" / NPI

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("record_cassettes")


def _strip_secrets(request: Any) -> Any:
    """Remove the Census API key from the URI before the cassette is persisted."""
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(request.uri)
    kept = [(k, v) for (k, v) in parse_qsl(parts.query, keep_blank_values=True) if k != "key"]
    request.uri = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment))
    return request


def _zcta_from_nppes(nppes_result: Any) -> str | None:
    """Derive the ZCTA from the NPPES LOCATION address.

    The LOCATION address is the facility; the MAILING address is often an
    administrative office in a different ZCTA with a different population.
    """
    address = nppes_result.address
    if address and address.postal_code:
        return address.postal_code[:5]
    return None


def record() -> dict[str, Any]:
    """Fetch NPPES and Census through vcr, and CMS live. Returns the generator inputs."""
    nppes = NPPESClient()
    recorded: dict[str, Any] = {}

    recorder = vcr.VCR(
        cassette_library_dir=CASSETTE_DIR,
        record_mode="once",
        path_transformer=vcr.VCR.ensure_suffix(".yaml"),
        filter_query_parameters=["key"],
        before_record_request=_strip_secrets,
    )

    with recorder.use_cassette(CASSETTE_NAME):
        nppes_result = nppes.get_organization_by_npi(NPI)
        recorded["nppes"] = nppes_result
        logger.info("NPPES: %s", nppes_result.organization_name)

        zcta = _zcta_from_nppes(nppes_result)
        logger.info("ZCTA from the LOCATION address: %s", zcta)

        demographics = None
        if zcta:
            try:
                demographics = CensusClient().get_demographics(zcta)
                logger.info(
                    "Census: population %d across %d categories",
                    demographics["total_population"],
                    len(demographics["ethnicity"]),
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Census fetch failed: %s", exc)
        recorded["demographics"] = demographics

        try:
            doctors = nppes.fetch_doctors_by_location(zcta or "")
            logger.info("NPPES practitioners: %d", len(doctors))
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Doctor fetch failed: %s", exc)
            doctors = []
        recorded["doctors"] = doctors

    # CMS is fetched outside the cassette; see the module docstring.
    hospital_data = None
    cms_json = OUTPUT_DIR / "cms_hospital.json"
    if cms_json.exists():
        hospital_data = json.loads(cms_json.read_text())
        logger.info("CMS: reusing cached %s", cms_json)
    else:
        try:
            from simhospital_autoconfig.__main__ import _resolve_cms_hospital

            hospital_data = _resolve_cms_hospital(CMSClient(), nppes_result)
            if hospital_data:
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                cms_json.write_text(json.dumps(hospital_data, indent=2) + "\n")
                logger.info("CMS: %s", hospital_data.get("hospital_name"))
            else:
                logger.warning("CMS: no match; locations.yml will use built-in defaults")
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("CMS lookup failed: %s", exc)
    recorded["hospital_data"] = hospital_data

    return recorded


def assert_cassette_has_no_secrets() -> None:
    """Fail loudly if an API key was written into the cassette."""
    path = Path(CASSETTE_DIR) / f"{CASSETTE_NAME}.yaml"
    if not path.exists():
        return
    text = path.read_text(errors="replace")
    leaked = [
        name
        for name in ("CENSUS_API_KEY", "TYPESAFE_API_KEY")
        if (value := os.environ.get(name)) and value in text
    ]
    if leaked:
        raise SystemExit(f"REFUSING TO CONTINUE: cassette contains secret(s): {leaked}")
    if "key=" in text:
        raise SystemExit("REFUSING TO CONTINUE: cassette still contains a 'key=' query parameter")
    logger.info("Cassette verified free of secrets (%d bytes)", path.stat().st_size)


def main() -> int:
    Path(CASSETTE_DIR).mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not os.environ.get("CENSUS_API_KEY"):
        logger.warning(
            "CENSUS_API_KEY is not set; ethnicity.csv will fall back to UK defaults. "
            "Load it with: set -a; . ./.env; set +a"
        )

    recorded = record()
    assert_cassette_has_no_secrets()

    nppes_result = recorded["nppes"]
    results = generate_all_configs(
        nppes_result,
        output_dir=str(OUTPUT_DIR),
        demographics=recorded["demographics"],
        hospital_data=recorded["hospital_data"],
        doctors=recorded["doctors"] or None,
        validate=False,
    )
    for filename, content in results.items():
        logger.info("Wrote %s (%d bytes)", OUTPUT_DIR / filename, len(content))

    report = run_deterministic_checks(OUTPUT_DIR)
    print()
    print(format_check_report(report))
    failures = [name for name, (passed, _) in report.items() if not passed]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
