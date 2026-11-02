"""Deterministic validation rules for Simhospital configs.

These rules are checked locally before escalating to Jev, following the Jev
Evaluation SOP principle: ask Jev only when the deterministic system cannot
confidently answer a specific question.

Every check here exists because something real went wrong. The UK-default and
placeholder-doctor checks in particular were added after generated output for a
Chicago hospital was found to contain London ethnicity data and invented
practitioners -- defects that passed every earlier check because the checks only
looked at structure, not at whether the data actually described the hospital.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import yaml

from .specialties import ALLOWED_SPECIALTIES

# Default target: the checked-in fixture for the canonical test hospital. Callers
# should pass the directory they actually generated into -- validating a fixture
# proves nothing about freshly generated output.
DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "1730209545"

# Markers of the upstream UK ethnicity table, which is what a generated US config
# falls back to when Census data never arrives.
UK_ETHNICITY_MARKERS = ("White - British", "Ethnic_groups_in_London")

# The exact street-suffix list shipped in the upstream UK data.yml. US suffixes
# overlap with these, so only an exact match is treated as unconverted.
UK_STREET_SUFFIXES = {"Road", "Street", "Lane", "Avenue", "Place", "Square"}

# Names that appeared in a hand-written fixture doctors.yml and were validated as
# if they were real NPPES practitioners.
PLACEHOLDER_DOCTOR_NAMES = {("John", "Smith"), ("Jane", "Doe")}

DOCTOR_REQUIRED_FIELDS = ("id", "surname", "firstname", "prefix", "specialty")


def _csv_data_rows(csv_text: str) -> list[list[str]]:
    """Parse a config CSV, dropping comment lines.

    Simhospital's loader sets csv.Reader.Comment = '#', so comments never reach the
    distribution and must not be validated as data rows.
    """
    return [
        row
        for row in csv.reader(io.StringIO(csv_text))
        if row and not row[0].startswith("#")
    ]


def check_no_placeholders(content: str) -> bool:
    """No unresolved ${ORGANIZATION_*} placeholders remain."""
    return "${ORGANIZATION_NAME}" not in content and "${ORGANIZATION_ID}" not in content


def check_ed_present(data: dict) -> bool:
    """locations.yml contains an ED location, which Simhospital requires."""
    return "ED" in data


def check_floors_numeric(data: dict) -> bool:
    """All floor values parse as integers, matching Go's strconv.Atoi."""
    for loc in data.values():
        floor = (loc or {}).get("floor")
        if floor is None:
            return False
        try:
            int(floor)
        except (ValueError, TypeError):
            return False
    return True


def check_csv_has_sentinel(csv_text: str) -> bool:
    """ethnicity.csv contains a nil,nil sentinel for absent ethnicity."""
    return any(len(row) >= 2 and row[0] == "nil" and row[1] == "nil" for row in _csv_data_rows(csv_text))


def check_ethnicity_sentinel_invariants(csv_text: str) -> bool:
    """Exactly one nil,nil sentinel, and no other row mentions nil."""
    rows = _csv_data_rows(csv_text)
    sentinel = sum(1 for r in rows if len(r) >= 2 and r[0] == "nil" and r[1] == "nil")
    any_nil = sum(1 for r in rows if len(r) >= 2 and ("nil" in (r[0], r[1])))
    return sentinel == 1 and any_nil == 1


def check_ethnicity_no_duplicate_ids(csv_text: str) -> bool:
    """Each CE ID appears at most once.

    Simhospital's loader (pkg/config/csv.go) accepts duplicate IDs silently and just
    builds a weighted distribution, so a collision corrupts patient ethnicity
    instead of raising. Appending Census codes to the UK defaults used to collide on
    A, B and H.
    """
    ids = [row[0] for row in _csv_data_rows(csv_text)]
    return len(ids) == len(set(ids))


def check_ethnicity_frequencies_positive(csv_text: str) -> bool:
    """Every frequency is a positive integer; a zero row can never be sampled."""
    for row in _csv_data_rows(csv_text):
        if len(row) < 3:
            return False
        try:
            if int(row[2]) <= 0:
                return False
        except ValueError:
            return False
    return True


def check_ethnicity_not_uk_default(csv_text: str) -> bool:
    """Generated output for a US hospital is not still the upstream UK table."""
    return not any(marker in csv_text for marker in UK_ETHNICITY_MARKERS)


def check_data_streets_not_uk_default(data: dict) -> bool:
    """data.yml street suffixes are not the unconverted upstream UK list."""
    streets = (data.get("address") or {}).get("streets") or []
    return set(streets) != UK_STREET_SUFFIXES


def check_doctors_required_fields(doctors: list) -> bool:
    """Every doctor entry has all required fields, non-empty."""
    for doc in doctors:
        for field in DOCTOR_REQUIRED_FIELDS:
            if field not in doc or not str(doc[field]).strip():
                return False
    return True


def check_doctors_specialties_allowed(doctors: list) -> bool:
    """Every specialty is one Simhospital and the schema tests recognize."""
    return all(doc.get("specialty") in ALLOWED_SPECIALTIES for doc in doctors)


def check_doctor_ids_unique(doctors: list) -> bool:
    """No two doctors share an NPI."""
    ids = [str(doc.get("id")) for doc in doctors]
    return len(ids) == len(set(ids))


def check_doctors_not_placeholder(doctors: list) -> bool:
    """Doctors are real practitioners, not invented fixture rows."""
    for doc in doctors:
        name = (str(doc.get("firstname", "")).strip(), str(doc.get("surname", "")).strip())
        if name in PLACEHOLDER_DOCTOR_NAMES:
            return False
    return True


def check_hl7_required_sections(data: dict) -> bool:
    """hl7.yml contains the sections the generators are responsible for."""
    required = {"allergy", "diagnosis", "gender", "patient_class", "primary_facility"}
    return required.issubset(data.keys())


def check_hl7_placeholders_resolved(data: dict) -> bool:
    """hl7.yml primary_facility carries resolved values."""
    primary = data.get("primary_facility") or {}
    org_name = primary.get("organization_name", "")
    org_id = primary.get("id_number", "")
    return "${" not in org_name and "${" not in org_id


def check_hl7_hospital_service_allowed(data: dict) -> bool:
    """hospital_service is an HL7 Table 0069 code, not a raw NUCC taxonomy code.

    generate_all_configs once wrote NPPES's ``taxonomy.code`` straight through, so
    generated hl7.yml carried values like 282N00000X where Simhospital expects MED.
    """
    return data.get("hospital_service") in ALLOWED_SPECIALTIES


def check_country_is_usa_or_iso(data: dict) -> bool:
    """Country is a recognized code or a well-formed three-letter ISO code."""
    country = (data.get("address") or {}).get("country", "")
    return country in {"USA", "US", "GBR", "CAN"} or bool(re.match(r"^[A-Z]{3}$", country))


def run_deterministic_checks(config_dir: str | Path | None = None) -> dict[str, tuple[bool, str]]:
    """Run every deterministic check against a directory of generated configs.

    Args:
        config_dir: Directory holding the five config files. Defaults to the
            checked-in fixture for NPI 1730209545 so existing callers keep working,
            but callers should pass the directory they actually generated into.

    Returns:
        Mapping of check name to (passed, detail). A check that raises is recorded
        as failed with the exception as its detail rather than propagating, so one
        unreadable file does not abort the whole audit.
    """
    root = Path(config_dir) if config_dir is not None else DEFAULT_CONFIG_DIR
    results: dict[str, tuple[bool, str]] = {}

    def record(name: str, fn) -> None:
        try:
            results[name] = (bool(fn()), "")
        except Exception as exc:  # pylint: disable=broad-except
            results[name] = (False, f"{type(exc).__name__}: {exc}")

    data_yml = root / "data.yml"
    locations_yml = root / "locations.yml"
    ethnicity_csv = root / "ethnicity.csv"
    doctors_yml = root / "doctors.yml"
    hl7_yml = root / "hl7.yml"

    record("country_code_valid", lambda: check_country_is_usa_or_iso(_load_yaml(data_yml)))
    record(
        "data_streets_not_uk_default",
        lambda: check_data_streets_not_uk_default(_load_yaml(data_yml)),
    )

    record("ed_present", lambda: check_ed_present(_load_yaml(locations_yml)))
    record("floors_numeric", lambda: check_floors_numeric(_load_yaml(locations_yml)))

    record("sentinel_present", lambda: check_csv_has_sentinel(_load_text(ethnicity_csv)))
    record(
        "sentinel_invariants",
        lambda: check_ethnicity_sentinel_invariants(_load_text(ethnicity_csv)),
    )
    record(
        "ethnicity_no_duplicate_ids",
        lambda: check_ethnicity_no_duplicate_ids(_load_text(ethnicity_csv)),
    )
    record(
        "ethnicity_frequencies_positive",
        lambda: check_ethnicity_frequencies_positive(_load_text(ethnicity_csv)),
    )
    record(
        "ethnicity_not_uk_default",
        lambda: check_ethnicity_not_uk_default(_load_text(ethnicity_csv)),
    )

    if doctors_yml.exists():
        record("doctors_required_fields", lambda: check_doctors_required_fields(_load_yaml(doctors_yml) or []))
        record("doctors_specialties_allowed", lambda: check_doctors_specialties_allowed(_load_yaml(doctors_yml) or []))
        record("doctor_ids_unique", lambda: check_doctor_ids_unique(_load_yaml(doctors_yml) or []))
        record("doctors_not_placeholder", lambda: check_doctors_not_placeholder(_load_yaml(doctors_yml) or []))

    record("hl7_required_sections", lambda: check_hl7_required_sections(_load_yaml(hl7_yml)))
    record("hl7_placeholders_resolved", lambda: check_hl7_placeholders_resolved(_load_yaml(hl7_yml)))
    record("hl7_hospital_service_allowed", lambda: check_hl7_hospital_service_allowed(_load_yaml(hl7_yml)))
    record("no_placeholders_in_content", lambda: check_no_placeholders(_load_text(hl7_yml)))

    return results


def _load_yaml(path: Path):
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _load_text(path: Path) -> str:
    with open(path) as f:
        return f.read()


def get_deterministic_confidence(config_dir: str | Path | None = None) -> float:
    """Fraction of deterministic checks that pass, as a 0.0-1.0 confidence score."""
    results = run_deterministic_checks(config_dir)
    if not results:
        return 0.0
    return sum(1 for passed, _ in results.values() if passed) / len(results)


def format_check_report(results: dict[str, tuple[bool, str]]) -> str:
    """Render check results for logging, listing failures first."""
    failed = [(name, detail) for name, (passed, detail) in results.items() if not passed]
    lines = [f"{len(results) - len(failed)}/{len(results)} deterministic checks passed"]
    for name, detail in sorted(failed):
        lines.append(f"  FAILED {name}" + (f": {detail}" if detail else ""))
    return "\n".join(lines)
