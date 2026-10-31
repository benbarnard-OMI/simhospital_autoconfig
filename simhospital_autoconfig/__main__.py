"""
Command-line interface for simhospital_autoconfig.

Usage:
    python -m simhospital_autoconfig generate --npi 1730209545
    python -m simhospital_autoconfig generate --name "John H. Stroger Jr. Hospital" --state IL
    python -m simhospital_autoconfig generate --zip 60601
"""

from __future__ import annotations

import argparse
import logging
import sys

from .census import CensusClient
from .cms import COL_FACILITY_ID, CMSClient
from .generators import generate_all_configs
from .nppes import NPPESClient, NPPESResult
from .specialties import get_specialties_for_hospital

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# NPPES publishes "other identifier" type codes as numbers, so matching on the
# literal string "ccn" never fired. Code 02 is the Medicare OSCAR number, which is
# the CMS Certification Number; descriptions are matched too as a fallback.
CCN_IDENTIFIER_CODES = {"02"}
CCN_IDENTIFIER_DESC_HINTS = ("oscar", "ccn")


def _find_ccn(nppes_result: NPPESResult) -> str | None:
    """Return the CMS Certification Number from NPPES identifiers, if published."""
    for identifier in nppes_result.identifiers or []:
        code = (identifier.code or "").strip()
        desc = (identifier.desc or "").lower()
        if code in CCN_IDENTIFIER_CODES or any(h in desc for h in CCN_IDENTIFIER_DESC_HINTS):
            value = (identifier.identifier or "").strip()
            if value:
                return value
    return None


def _resolve_cms_hospital(
    cms_client: CMSClient, nppes_result: NPPESResult
) -> dict | None:
    """Resolve this hospital in the CMS catalog, or None if it cannot be matched.

    Returns None rather than a fabricated record when there is no match, so the
    generators fall back to their own defaults instead of consuming invented CMS
    facts. The previous fallback asserted ``emergency_services: "Y"`` for every
    hospital, which presented a guess as a CMS finding.

    The catalog has no NPI column, so the join is CCN first and facility
    name-plus-state second.
    """
    row = None
    ccn = _find_ccn(nppes_result)

    if ccn:
        try:
            row = cms_client.get_hospital_by_ccn(ccn)
            logger.info("Matched CMS hospital by CCN %s", ccn)
        except ValueError:
            logger.info("No CMS facility with CCN %s; trying name and state", ccn)

    if row is None:
        address = nppes_result.address
        state = address.state if address else None
        name = nppes_result.organization_name
        if name and state:
            hits = cms_client.search_hospitals(name=name, state=state)
            if len(hits) == 1:
                row = hits[0]
                logger.info(
                    "Matched CMS hospital by name and state: %s", row.get(COL_FACILITY_ID)
                )
            elif len(hits) > 1:
                logger.warning(
                    "CMS returned %d facilities matching %r in %s (%s); refusing to "
                    "guess. locations.yml will use built-in defaults.",
                    len(hits),
                    name,
                    state,
                    ", ".join(h.get(COL_FACILITY_ID, "?") for h in hits),
                )
                return None

    if row is None:
        logger.warning(
            "No CMS match for %r; hospital type and ED status are unknown and "
            "locations.yml will use built-in defaults.",
            nppes_result.organization_name,
        )
        return None

    return cms_client.map_to_simhospital_config(row)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        description="Automatically configure Google Simhospital to mirror real-world hospital traits.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    generate_parser = subparsers.add_parser("generate", help="Generate configuration files")
    generate_parser.add_argument("--npi", help="NPI number for the hospital")
    generate_parser.add_argument(
        "--name",
        help="Hospital name (used with --state for NPPES search)",
    )
    generate_parser.add_argument("--state", help="State abbreviation (used with --name)")
    generate_parser.add_argument(
        "--zip",
        help="ZIP code to resolve to ZCTA and fetch hospital via CMS",
    )
    generate_parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory to write configuration files (default: current directory)",
    )
    generate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions without writing files",
    )
    generate_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser


def run_generate(args: argparse.Namespace) -> int:
    """Execute the generate command."""
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    nppes_client = NPPESClient()
    cms_client = CMSClient()
    census_client = CensusClient()

    nppes_result = None
    hospital_data = None
    demographics = None
    doctors: list[dict] = []

    if args.npi:
        logger.info("Fetching hospital by NPI: %s", args.npi)
        try:
            nppes_result = nppes_client.get_organization_by_npi(args.npi)
            logger.info("Found organization: %s", nppes_result.organization_name)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to fetch NPPES data: %s", exc)
            return 1
    elif args.name and args.state:
        logger.info("Searching NPPES for %s in %s", args.name, args.state)
        # For simplicity, this CLI path requires manual NPI lookup or future NPPES search implementation
        logger.error("Name/state search not yet implemented; please use --npi")
        return 1
    elif args.zip:
        logger.info("Resolving ZIP %s to ZCTA and fetching CMS hospital", args.zip)
        # CMS does not directly support ZIP-to-CCN search in this client yet
        logger.error("ZIP-based resolution not yet implemented; please use --npi")
        return 1
    else:
        logger.error("Must specify --npi, or --name with --state, or --zip")
        return 1

    if nppes_result:
        logger.info("Fetching CMS data")
        try:
            hospital_data = _resolve_cms_hospital(cms_client, nppes_result)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "CMS lookup failed for %s (%s). locations.yml will use built-in "
                "defaults instead of this hospital's real type and ED status.",
                nppes_result.organization_name,
                exc,
            )

        logger.info("Fetching Census demographics")
        try:
            zcta = (
                nppes_result.address.postal_code[:5]
                if nppes_result.address and nppes_result.address.postal_code
                else "00000"
            )
            demographics = census_client.get_demographics(zcta)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Census fetch failed, continuing without demographics: %s", exc)

        logger.info("Fetching doctors by location")
        try:
            if nppes_result.address and nppes_result.address.postal_code:
                taxonomies = [
                    {"desc": t.desc} for t in (nppes_result.taxonomies or [])
                ]
                specialties = get_specialties_for_hospital(taxonomies) or ["MED"]
                doctors = nppes_client.fetch_doctors_by_location(
                    nppes_result.address.postal_code[:5],
                    specialties,
                )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("NPPES doctor fetch failed, continuing without doctors: %s", exc)

    if args.dry_run:
        logger.info("Dry run enabled; would generate:")
        logger.info("  hl7.yml")
        logger.info("  locations.yml")
        logger.info("  data.yml")
        logger.info("  ethnicity.csv")
        if doctors:
            logger.info("  doctors.yml")
        return 0

    logger.info("Generating configuration files to: %s", args.output_dir)
    generate_all_configs(
        nppes_result,
        output_dir=args.output_dir,
        demographics=demographics,
        hospital_data=hospital_data,
        doctors=doctors if doctors else None,
    )
    logger.info("Successfully generated configuration files")
    return 0


def main() -> int:
    """Main entry point for the CLI."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "generate":
        return run_generate(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
