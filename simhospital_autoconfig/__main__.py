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
import re
import sys
from typing import Any

from .census import CensusClient
from .cms import (
    COL_EMERGENCY,
    COL_FACILITY_ID,
    COL_FACILITY_NAME,
    COL_HOSPITAL_TYPE,
    CMSClient,
    normalize_name,
)
from .deterministic_checks import format_check_report, run_deterministic_checks
from .generators import generate_all_configs
from .nppes import NPPESClient, NPPESResult

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
        # NPPES returns numeric identifier codes and can drop their leading zero.
        code = str(identifier.code or "").strip().zfill(2)
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
    generate_parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any deterministic check fails on the generated configs",
    )
    return parser


MAX_LISTED_CANDIDATES = 10


def _exact_name_matches(results: list[NPPESResult], name: str) -> list[NPPESResult]:
    """Keep only results whose organization name matches exactly once normalized.

    NPPES name search is fuzzy -- "Rush University Medical Center" also returns
    "Department of Psychiatry at Rush" -- so fuzzy hits are dropped before deciding
    whether the match is unambiguous.
    """
    wanted = normalize_name(name)
    return [r for r in results if normalize_name(r.organization_name or "") == wanted]


def _log_nppes_candidates(
    candidates: list[NPPESResult], name: str, state: str, reason: str
) -> None:
    """List ambiguous NPPES matches so the user can pick an NPI."""
    logger.error(
        "%d NPPES organization(s) %s %r in %s:", len(candidates), reason, name, state
    )
    for result in candidates[:MAX_LISTED_CANDIDATES]:
        address = result.address
        if address and address.postal_code:
            where = f"{address.city}, {address.state} {address.postal_code[:5]}"
        else:
            where = "no address on record"
        logger.error("  NPI %s  %s  (%s)", result.npi, result.organization_name, where)
    if len(candidates) > MAX_LISTED_CANDIDATES:
        logger.error("  ... and %d more", len(candidates) - MAX_LISTED_CANDIDATES)
    logger.error("Re-run with --npi <NPI> to select one; this tool will not guess.")


def _resolve_by_name(
    nppes_client: NPPESClient, name: str, state: str
) -> tuple[NPPESResult | None, int]:
    """Resolve --name/--state to a single NPPES organization.

    Returns (result, exit_code); a non-zero exit_code means the caller should stop.
    """
    if not re.fullmatch(r"[A-Za-z]{2}", state.strip()):
        logger.error("--state must be a two-letter abbreviation, got %r", state)
        return None, 1

    logger.info("Searching NPPES for %r in %s", name, state.upper())
    try:
        found = nppes_client.search_organizations(name, state.strip().upper())
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("NPPES search failed: %s", exc)
        return None, 1

    if not found.results:
        logger.error(
            "NPPES has no organization matching %r in %s. NPPES records the legal "
            "business name, which is often not the hospital's public name -- John H. "
            "Stroger Jr. Hospital is registered as 'COOK COUNTY'. Try the legal entity, "
            "or use --npi.",
            name,
            state,
        )
        return None, 1

    if found.truncated:
        page_count = len(found.results)
        page_noun = "result" if page_count == 1 else "results"
        if found.total is None:
            result_summary = (
                f"NPPES did not report the total match count and returned "
                f"{page_count} {page_noun} on this page."
            )
        else:
            result_summary = (
                f"NPPES matched {found.total} organizations and returned "
                f"{page_count} {page_noun} on this page."
            )
        logger.error(
            "NPPES results for %r in %s could not be verified as complete. %s "
            "This tool cannot select one safely. Use --npi to select the organization directly.",
            name,
            state.upper(),
            result_summary,
        )
        return None, 1

    exact = _exact_name_matches(found.results, name)
    if len(exact) == 1:
        chosen = exact[0]
        logger.info("Resolved to NPI %s (%s)", chosen.npi, chosen.organization_name)
        return chosen, 0

    if len(exact) > 1:
        _log_nppes_candidates(exact, name, state, "match exactly")
        return None, 1

    _log_nppes_candidates(found.results, name, state, "partially match")
    return None, 1


def _resolve_by_zip(
    cms_client: CMSClient, nppes_client: NPPESClient, args: argparse.Namespace
) -> tuple[NPPESResult | None, dict[str, Any] | None, int]:
    """Resolve --zip to one CMS facility, optionally narrowed by --name/--state.

    Returns (nppes_result, hospital_data, exit_code). hospital_data comes back
    already mapped so the shared tail does not repeat the catalog join.

    ZIP goes through CMS rather than NPPES because NPPES has no facility-type
    filter: postal_code + NPI-2 returns every organization in the ZIP, including
    therapy practices and transport companies.
    """
    zip_code = (args.zip or "").strip()
    # Hyphen required for ZIP+4: accepting "606123456" would silently truncate a
    # nine-digit typo to a valid-looking ZIP.
    if not re.fullmatch(r"\d{5}(-\d{4})?", zip_code):
        logger.error("--zip must be a 5-digit ZIP code, optionally ZIP+4, got %r", args.zip)
        return None, None, 1
    zip_code = zip_code[:5]

    logger.info("Looking up CMS hospitals in ZIP %s", zip_code)
    try:
        rows = cms_client.search_hospitals(
            name=args.name, state=args.state, zip_code=zip_code
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("CMS lookup failed: %s", exc)
        return None, None, 1

    if not rows:
        logger.error(
            "The CMS catalog has no hospital in ZIP %s%s. Narrow or drop the --name "
            "filter, or use --npi.",
            zip_code,
            f" matching {args.name!r}" if args.name else "",
        )
        return None, None, 1

    if len(rows) > 1:
        logger.error("%d CMS facilities are in ZIP %s:", len(rows), zip_code)
        for row in rows[:MAX_LISTED_CANDIDATES]:
            logger.error(
                "  CCN %s  %s  (%s, ED: %s)",
                row.get(COL_FACILITY_ID),
                row.get(COL_FACILITY_NAME),
                row.get(COL_HOSPITAL_TYPE),
                row.get(COL_EMERGENCY),
            )
        if len(rows) > MAX_LISTED_CANDIDATES:
            logger.error("  ... and %d more", len(rows) - MAX_LISTED_CANDIDATES)
        logger.error(
            "Narrow it with --name, or re-run with --npi <NPI>; this tool will not guess."
        )
        return None, None, 1

    hospital_data = cms_client.map_to_simhospital_config(rows[0])
    logger.info(
        "Resolved ZIP %s to %s (CCN %s)",
        zip_code,
        hospital_data.get("hospital_name"),
        hospital_data.get("ccn"),
    )

    ccn = str(hospital_data.get("ccn") or "").strip()
    try:
        primary_npi = cms_client.get_primary_npi_by_ccn(ccn)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Could not resolve a primary CMS NPI for CCN %s: %s", ccn, exc)
        return None, None, 1

    try:
        nppes_result = nppes_client.get_organization_by_npi(primary_npi)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error(
            "CMS primary NPI %s for CCN %s is not available in NPPES (%s). "
            "Use --npi <NPI> to select an organization directly.",
            primary_npi,
            ccn,
            exc,
        )
        return None, None, 1

    logger.info(
        "Resolved CMS CCN %s to primary NPI %s (%s)",
        ccn,
        primary_npi,
        nppes_result.organization_name,
    )
    return nppes_result, hospital_data, 0


def run_generate(args: argparse.Namespace) -> int:
    """Execute the generate command."""
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    nppes_client = NPPESClient()
    cms_client = CMSClient()
    census_client = CensusClient()

    nppes_result: NPPESResult | None = None
    # Pre-populated when --zip already resolved the facility in the CMS catalog, so
    # the shared tail below does not have to join it a second time.
    hospital_data: dict | None = None
    demographics = None
    doctors: list[dict] = []

    # --zip is tested before --name/--state so that --zip can be narrowed by them:
    # search_hospitals accepts all three filters, and a dense ZIP such as 60612 holds
    # four separate hospitals.
    if args.npi:
        logger.info("Fetching hospital by NPI: %s", args.npi)
        try:
            nppes_result = nppes_client.get_organization_by_npi(args.npi)
            logger.info("Found organization: %s", nppes_result.organization_name)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to fetch NPPES data: %s", exc)
            return 1
    elif args.zip:
        nppes_result, hospital_data, exit_code = _resolve_by_zip(cms_client, nppes_client, args)
        if exit_code:
            return exit_code
    elif args.name and args.state:
        nppes_result, exit_code = _resolve_by_name(nppes_client, args.name, args.state)
        if exit_code:
            return exit_code
    else:
        logger.error("Must specify --npi, or --name with --state, or --zip")
        return 1

    if nppes_result is None:
        logger.error("Could not resolve a single hospital from the given arguments")
        return 1

    if nppes_result:
        if hospital_data is not None:
            logger.info(
                "Reusing the CMS record resolved from --zip: %s",
                hospital_data.get("hospital_name"),
            )
        else:
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
            logger.info(
                "Census ZCTA %s: population %d, %d ethnicity categories",
                zcta,
                demographics["total_population"],
                len(demographics["ethnicity"]),
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "Census fetch failed for %s (%s). ethnicity.csv will fall back to the "
                "upstream UK distribution, which does not describe this hospital's "
                "population.",
                nppes_result.organization_name,
                exc,
            )

        logger.info("Fetching doctors by location")
        try:
            if nppes_result.address and nppes_result.address.postal_code:
                # A hospital's own NPPES taxonomies are organizational -- Stroger's sole
                # entry is "General Acute Care Hospital" -- which matches almost no
                # individual practitioners. Search the fixed clinical roster instead;
                # each practitioner's own taxonomy decides their HL7 code.
                doctors = nppes_client.fetch_doctors_by_location(
                    nppes_result.address.postal_code[:5],
                )
                logger.info("Fetched %d practitioners", len(doctors))
            else:
                logger.warning(
                    "No postal code in the NPPES address; doctors.yml will not be generated"
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
        # Reported once here rather than inside the generator, so the same results
        # can drive the exit code under --strict.
        validate=False,
    )
    logger.info("Successfully generated configuration files")

    report = run_deterministic_checks(args.output_dir)
    failures = [name for name, (passed, _) in report.items() if not passed]
    if failures:
        logger.warning("%s", format_check_report(report))
        if args.strict:
            logger.error("--strict set and %d deterministic checks failed", len(failures))
            return 1
    else:
        logger.info("All %d deterministic checks passed", len(report))

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
