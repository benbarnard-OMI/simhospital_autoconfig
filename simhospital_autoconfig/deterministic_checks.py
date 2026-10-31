"""Deterministic validation rules for Simhospital configs.

These rules are checked locally before escalating to Jev, following the
Jev Evaluation SOP principle: ask Jev only when the deterministic system
cannot confidently answer a specific question.
"""

import csv
import io
import re
from pathlib import Path

import yaml

FIXTURE_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "1730209545"
ALLOWED_SPECIALTIES = {
    "MED", "SUR", "URO", "PUL", "CAR",
    "ANESTH", "EMER", "FAMP", "INTMED", "OBG", "PEDS", "PSY", "RAD", "TRAUM"
}


def check_no_placeholders(content: str) -> bool:
    """Deterministic check: no unresolved placeholders remain."""
    return "${ORGANIZATION_NAME}" not in content and "${ORGANIZATION_ID}" not in content


def check_ed_present(data: dict) -> bool:
    """Deterministic check: locations.yml contains ED location."""
    return "ED" in data


def check_floors_numeric(data: dict) -> bool:
    """Deterministic check: all floor values are numeric."""
    for loc in data.values():
        floor = loc.get("floor")
        if floor is None:
            return False
        try:
            int(floor)
        except (ValueError, TypeError):
            return False
    return True


def check_csv_has_sentinel(csv_text: str) -> bool:
    """Deterministic check: ethnicity.csv contains nil,nil sentinel."""
    reader = csv.reader(io.StringIO(csv_text))
    for row in reader:
        if len(row) >= 2 and row[0] == "nil" and row[1] == "nil":
            return True
    return False


def check_doctors_required_fields(data: list) -> bool:
    """Deterministic check: all doctor entries have required fields."""
    for doc in data:
        for field in ["id", "surname", "firstname", "prefix", "specialty"]:
            if field not in doc or not str(doc[field]).strip():
                return False
    return True


def check_hl7_required_sections(data: dict) -> bool:
    """Deterministic check: hl7.yml contains required top-level sections."""
    required = {"allergy", "diagnosis", "gender", "patient_class", "primary_facility"}
    return required.issubset(data.keys())


def check_hl7_placeholders_resolved(data: dict) -> bool:
    """Deterministic check: hl7.yml placeholders are resolved."""
    pf = data.get("primary_facility", {})
    org_name = pf.get("organization_name", "")
    org_id = pf.get("id_number", "")
    return "${" not in org_name and "${" not in org_id


def check_country_is_usa_or_iso(data: dict) -> bool:
    """Deterministic check: country code is valid."""
    country = data.get("address", {}).get("country", "")
    return country in {"USA", "US", "GBR", "CAN"} or bool(re.match(r"^[A-Z]{3}$", country))


def check_ethnicity_sentinel_invariants(csv_text: str) -> bool:
    """Deterministic check: exactly one nil,nil sentinel row."""
    reader = csv.reader(io.StringIO(csv_text))
    sentinel_count = 0
    nil_count = 0
    for row in reader:
        if not row or not row[0].strip() or row[0].startswith("#"):
            continue
        if len(row) >= 2 and row[0] == "nil" and row[1] == "nil":
            sentinel_count += 1
        if len(row) >= 2 and (row[0] == "nil" or row[1] == "nil"):
            nil_count += 1
    return sentinel_count == 1 and nil_count == 1


def check_doctors_specialties_allowed(data: list) -> bool:
    """Deterministic check: all doctor specialties are in the allowed set."""
    for doc in data:
        if doc.get("specialty") not in ALLOWED_SPECIALTIES:
            return False
    return True


def run_deterministic_checks() -> dict:
    """Run all deterministic checks on fixture configs.

    Returns a dict of check_name -> (passed, detail).
    """
    results = {}

    try:
        with open(FIXTURE_DIR / "data.yml") as f:
            data = yaml.safe_load(f)
        results["country_code_valid"] = (check_country_is_usa_or_iso(data), data.get("address", {}).get("country"))
    except Exception as e:
        results["country_code_valid"] = (False, str(e))

    try:
        with open(FIXTURE_DIR / "locations.yml") as f:
            loc = yaml.safe_load(f)
        results["ed_present"] = (check_ed_present(loc), "ED" in loc)
        results["floors_numeric"] = (check_floors_numeric(loc), "")
    except Exception as e:
        results["ed_present"] = (False, str(e))
        results["floors_numeric"] = (False, str(e))

    try:
        with open(FIXTURE_DIR / "ethnicity.csv") as f:
            csv_text = f.read()
        results["sentinel_present"] = (check_csv_has_sentinel(csv_text), "")
        results["sentinel_invariants"] = (check_ethnicity_sentinel_invariants(csv_text), "")
    except Exception as e:
        results["sentinel_present"] = (False, str(e))
        results["sentinel_invariants"] = (False, str(e))

    try:
        with open(FIXTURE_DIR / "doctors.yml") as f:
            docs = yaml.safe_load(f)
        if docs:
            results["doctors_required_fields"] = (check_doctors_required_fields(docs), "")
            results["doctors_specialties_allowed"] = (check_doctors_specialties_allowed(docs), "")
        else:
            results["doctors_required_fields"] = (True, "empty doctors list")
            results["doctors_specialties_allowed"] = (True, "empty doctors list")
    except Exception as e:
        results["doctors_required_fields"] = (False, str(e))
        results["doctors_specialties_allowed"] = (False, str(e))

    try:
        with open(FIXTURE_DIR / "hl7.yml") as f:
            hl7 = yaml.safe_load(f)
        results["hl7_required_sections"] = (check_hl7_required_sections(hl7), "")
        results["hl7_placeholders_resolved"] = (check_hl7_placeholders_resolved(hl7), "")
    except Exception as e:
        results["hl7_required_sections"] = (False, str(e))
        results["hl7_placeholders_resolved"] = (False, str(e))

    try:
        hl7_path = FIXTURE_DIR / "hl7.yml"
        if hl7_path.exists():
            with open(hl7_path) as f:
                content = f.read()
            results["no_placeholders_in_content"] = (check_no_placeholders(content), "")
    except Exception as e:
        results["no_placeholders_in_content"] = (False, str(e))

    return results


def get_deterministic_confidence() -> float:
    """Calculate how confident we are in the deterministic checks alone.

    Returns 0.0-1.0 based on how many checks pass.
    """
    results = run_deterministic_checks()
    if not results:
        return 0.0
    passed = sum(1 for passed, _ in results.values() if passed)
    return passed / len(results)
