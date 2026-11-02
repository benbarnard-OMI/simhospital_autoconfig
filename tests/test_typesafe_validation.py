"""TypeSafe AI validation tests for generated Simhospital configs.

Follows the Jev Evaluation SOP:
- Run deterministic checks first (local rules).
- Only escalate to Jev when the deterministic system cannot confidently answer.
- Ask narrow, typed questions with clear success criteria.
"""

import json
import os
from pathlib import Path

import pytest
import yaml

from simhospital_autoconfig.deterministic_checks import (
    get_deterministic_confidence,
    run_deterministic_checks,
)


def _load_dotenv() -> None:
    """Load KEY=VALUE pairs from the gitignored .env at the repo root.

    Existing environment variables win, so CI secrets are never overridden.
    """
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

try:
    from typesafe_sdk import Noul, Score, TypeSafeClient

    TYPESAFE_AVAILABLE = True
    TYPESAFE_SKIP_REASON = ""
except ImportError:
    TYPESAFE_AVAILABLE = False
    TYPESAFE_SKIP_REASON = "typesafe_sdk not installed; use pip install -e '.[typesafe]'"

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "1730209545"
API_KEY = os.environ.get("TYPESAFE_API_KEY", "")
MODEL = "jev-latest"

requires_typesafe = pytest.mark.skipif(
    not TYPESAFE_AVAILABLE or not API_KEY,
    reason=TYPESAFE_SKIP_REASON or "TYPESAFE_API_KEY not set; these tests call api.typesafe.ai",
)


def _get_client():
    return TypeSafeClient(api_key=API_KEY)


def _load_yaml(filename):
    with open(FIXTURE_DIR / filename) as f:
        return yaml.safe_load(f)


def _load_csv(filename):
    with open(FIXTURE_DIR / filename, newline="") as f:
        return f.read()


def _run_questions(state: str, questions: dict):
    """Run TypeSafe questions and return the response."""
    client = _get_client()
    return client.system_one(state=state, questions=questions, model=MODEL)


class TestDeterministicChecks:
    """Deterministic checks run locally before escalating to Jev."""

    def test_deterministic_checks_pass(self):
        results = run_deterministic_checks()
        failures = [name for name, (passed, _) in results.items() if not passed]
        assert not failures, f"Deterministic checks failed: {failures}"

    def test_deterministic_confidence_is_high(self):
        confidence = get_deterministic_confidence()
        assert confidence >= 0.9, f"Deterministic confidence too low: {confidence}"


@requires_typesafe
class TestTypeSafeConfigAudit:
    """Use TypeSafe for uncertainty classification only after deterministic checks pass."""

    def test_data_yml_placeholders_resolved(self):
        data = _load_yaml("data.yml")
        state = json.dumps(data, indent=2)
        response = _run_questions(
            state,
            {
                "has_placeholders": Noul(
                    instructions="Does this data.yml contain unresolved ${ORGANIZATION_NAME} or ${ORGANIZATION_ID} placeholders?"
                ),
            },
        )
        assert response.answers["has_placeholders"].noul < 0.3

    def test_locations_ed_and_numeric_floors(self):
        data = _load_yaml("locations.yml")
        state = json.dumps(data, indent=2)
        response = _run_questions(
            state,
            {
                "has_ed": Noul(
                    instructions="Does this locations.yml include a location with type ED?"
                ),
                "floors_numeric": Noul(
                    instructions="Are all floor values numeric integers (e.g. 1, 2, 3)?"
                ),
            },
        )
        assert response.answers["has_ed"].noul > 0.8
        assert response.answers["floors_numeric"].noul > 0.8

    def test_ethnicity_sentinel_present(self):
        csv_text = _load_csv("ethnicity.csv")
        response = _run_questions(
            csv_text,
            {
                "has_sentinel": Noul(
                    instructions="Does this CSV contain exactly one row where both ID and Text are 'nil'?"
                ),
            },
        )
        assert response.answers["has_sentinel"].noul > 0.8

    def test_doctors_required_fields(self):
        yml_path = FIXTURE_DIR / "doctors.yml"
        if not yml_path.exists():
            pytest.skip("doctors.yml not generated for this fixture")
        data = _load_yaml("doctors.yml")
        if not data:
            pytest.skip("doctors.yml is empty")
        state = json.dumps(data, indent=2)
        response = _run_questions(
            state,
            {
                "has_required_fields": Noul(
                    instructions="Does each doctor entry have a non-empty id, surname, firstname, prefix, and specialty?"
                ),
            },
        )
        assert response.answers["has_required_fields"].noul > 0.8

    def test_hl7_required_sections_and_resolved_placeholders(self):
        data = _load_yaml("hl7.yml")
        state = json.dumps(data, indent=2)
        response = _run_questions(
            state,
            {
                "has_required_sections": Noul(
                    instructions="Does this hl7.yml contain all required top-level sections: allergy, diagnosis, gender, patient_class, primary_facility?"
                ),
                "placeholders_resolved": Noul(
                    instructions="Are the primary_facility.organization_name and primary_facility.id_number values resolved (no ${...} remaining)?"
                ),
            },
        )
        assert response.answers["has_required_sections"].noul > 0.8
        assert response.answers["placeholders_resolved"].noul > 0.8

    def test_plan_completeness_is_high(self):
        plan_text = """
        Completed Plan: Prove the Generator Works with Real Simulator
        Status: All steps implemented and verified.

        Deliverables completed:
        - tests/cassettes/test_simulator_validation[1730209545].yaml (61KB recorded)
        - tests/fixtures/1730209545/ (hl7.yml, locations.yml, data.yml, ethnicity.csv, doctors.yml)
        - tests/test_schema_validation.py (5 tests)
        - scripts/validate_with_simulator.sh (Docker + local binary support)
        - scripts/generate_and_validate.sh
        - Makefile with validate-simulator target
        - .github/workflows/tests.yml with simulator-validation job
        - tests/test_e2e.py updated with vcrpy (2 tests)
        - test_locations_yml.py updated for floor type compatibility
        - Simulator binary built and validated against generated configs

        Test results: 82 passed and 7 skipped offline (89 collected); the 17
        deterministic checks pass on the regenerated fixtures.
        """
        response = _run_questions(
            plan_text,
            {
                "is_complete": Noul(
                    instructions="Does this implementation plan include all required Simhospital config files, CI, offline tests, and simulator validation?"
                ),
                "has_validation": Noul(
                    instructions="Does the plan include validation against the real Simhospital simulator?"
                ),
                "has_offline_tests": Noul(
                    instructions="Does the plan include offline test capability using recorded cassettes?"
                ),
            },
        )
        assert response.answers["is_complete"].noul > 0.75, (
            f"Plan completeness noul too low: {response.answers['is_complete'].noul}"
        )
        assert response.answers["has_validation"].noul > 0.8
        assert response.answers["has_offline_tests"].noul > 0.8

    def test_blind_spot_edge_cases(self):
        """Use TypeSafe to classify uncertainty about remaining blind spots."""
        state = json.dumps({
            "project": "simhospital_autoconfig",
            "deterministic_confidence": get_deterministic_confidence(),
            "configs": ["hl7.yml", "locations.yml", "data.yml", "ethnicity.csv", "doctors.yml"],
            "data_sources": ["NPPES", "Census ACS", "CMS"],
            "known_fixes_applied": [
                "country_code US -> USA normalization",
                "address.postal_code -> postalcodes list",
                "doctors default prefix to empty string",
                "ethnicity CSV comment preservation",
                "empty doctors list produces empty doctors.yml",
                "invalid NPI raises ValueError",
                "missing doctor fields default to empty strings",
                "organization ID excluded from YAML outputs",
                "special characters in hospital name preserved",
                "unicode hospital name handled",
                "empty demographics uses default ethnicity data",
                "empty hospital_data uses safe location defaults",
                "non-US country codes not normalized",
                "multiple taxonomies without primary handled",
                "empty string NPI rejected",
            ],
            "test_count": 89,
            "edge_case_tests": [
                "empty_demographics", "empty_doctors_list", "none_doctors",
                "special_characters_in_name", "unicode_name", "long_name",
                "missing_address_fields", "ethnicity_csv_comments", "doctors_sorted",
                "country_normalization", "locations_emergency_warning", "hl7_override",
                "all_five_files_generated", "ethnicity_sentinel_invariants",
                "doctors_empty_specialty", "doctors_missing_fields", "invalid_npi",
                "organization_id_exclusion_locations", "organization_id_exclusion_data",
                "empty_demographics_default_ethnicity", "hospital_data_missing_fields",
                "multiple_taxonomies_no_primary", "npi_empty_string_rejected",
                "non_us_country_code_preserved", "doctors_invalid_specialty_preserved",
                "empty_postalcodes_default_locations",
            ],
        }, indent=2)
        response = _run_questions(
            state,
            {
                "needs_more_tests": Noul(
                    instructions="Given the deterministic checks pass at high confidence and 27 edge case tests are implemented, does this project clearly need additional edge case tests before production?"
                ),
                "security_risk": Noul(
                    instructions="Is there a concrete security risk (injection, data exposure, hardcoded secrets) in the current implementation?"
                ),
                "error_handling": Score(
                    instructions="How robust is error handling in the generator? "
                    "0 = no error handling, 1 = some try/except blocks, 2 = comprehensive with fallbacks.",
                    criteria=["No error handling", "Some handling", "Comprehensive"],
                ),
            },
        )
        assert response.answers["needs_more_tests"].noul < 0.5, (
            f"TypeSafe suggests more tests are needed (noul={response.answers['needs_more_tests'].noul})"
        )
        assert response.answers["security_risk"].noul < 0.5, (
            f"TypeSafe detected security risk (noul={response.answers['security_risk'].noul})"
        )
        assert response.answers["error_handling"].score >= 1.5, (
            f"Error handling score too low: {response.answers['error_handling'].score}"
        )
