"""Unit tests for the deterministic checks.

Each test here corresponds to a defect that the original ten checks passed while
the generated output was wrong, so the failure cases matter as much as the
success cases.
"""

from __future__ import annotations

import textwrap

import pytest

from simhospital_autoconfig.deterministic_checks import (
    check_data_streets_not_uk_default,
    check_doctor_ids_unique,
    check_doctors_not_placeholder,
    check_doctors_specialties_allowed,
    check_ethnicity_frequencies_positive,
    check_ethnicity_no_duplicate_ids,
    check_ethnicity_not_uk_default,
    check_ethnicity_sentinel_invariants,
    check_hl7_hospital_service_allowed,
    format_check_report,
    get_deterministic_confidence,
    run_deterministic_checks,
)
from simhospital_autoconfig.specialties import ALLOWED_SPECIALTIES

GOOD_ETHNICITY_CSV = textwrap.dedent(
    """\
    # In HL7, ethnicities are represented as Coded Elements (type CE).
    # Frequencies derived from US Census ACS 2023 5-year estimates for ZCTA 60612.
    2135-2,Hispanic or Latino,161
    2106-3,White,221
    2054-5,Black or African American,540
    # This "nil,nil" row is interpreted as an absent ethnicity.
    nil,nil,2
    """
)

UK_ETHNICITY_CSV = textwrap.dedent(
    """\
    # The frequencies have been derived from https://en.wikipedia.org/wiki/Ethnic_groups_in_London
    A,White - British,449
    B,White - Irish,22
    # This "nil,nil" row is interpreted as an absent ethnicity.
    nil,nil,2
    """
)


def write_configs(tmp_path, ethnicity=GOOD_ETHNICITY_CSV, doctors=None, hl7_service="MED", streets=None):
    """Write a minimal but complete config directory and return its path."""
    (tmp_path / "ethnicity.csv").write_text(ethnicity)
    (tmp_path / "locations.yml").write_text(
        "ED:\n  poc: ED\n  facility: TEST\n  floor: 1\n  room: ED\n  type: ED\n"
    )
    street_block = "\n".join(f"  - {s}" for s in (streets or ["Street", "Avenue", "Drive"]))
    (tmp_path / "data.yml").write_text(
        f"address:\n  country: USA\n  cities:\n  - CHICAGO\n  streets:\n{street_block}\n"
    )
    (tmp_path / "hl7.yml").write_text(
        f"allergy: {{}}\ndiagnosis: {{}}\ngender: {{}}\npatient_class: {{}}\n"
        f"hospital_service: {hl7_service}\n"
        "primary_facility:\n  organization_name: TEST\n  id_number: '12345'\n"
    )
    if doctors is not None:
        import yaml

        (tmp_path / "doctors.yml").write_text(yaml.dump(doctors))
    return tmp_path


class TestEthnicityChecks:
    def test_no_duplicate_ids_passes(self):
        assert check_ethnicity_no_duplicate_ids(GOOD_ETHNICITY_CSV)

    def test_no_duplicate_ids_catches_collision(self):
        """Appending Census rows to the UK defaults collided on A, B and H."""
        collided = UK_ETHNICITY_CSV + "A,Asian,300\n"
        assert not check_ethnicity_no_duplicate_ids(collided)

    def test_comments_are_not_treated_as_data_rows(self):
        assert check_ethnicity_no_duplicate_ids("# nil,nil,2\n2106-3,White,10\nnil,nil,2\n")

    @pytest.mark.parametrize("frequency", ["0", "-5"])
    def test_non_positive_frequency_rejected(self, frequency):
        assert not check_ethnicity_frequencies_positive(f"2106-3,White,{frequency}\nnil,nil,2\n")

    def test_non_numeric_frequency_rejected(self):
        assert not check_ethnicity_frequencies_positive("2106-3,White,many\n")

    def test_positive_frequencies_pass(self):
        assert check_ethnicity_frequencies_positive(GOOD_ETHNICITY_CSV)

    def test_uk_default_detected(self):
        assert not check_ethnicity_not_uk_default(UK_ETHNICITY_CSV)

    def test_us_data_passes(self):
        assert check_ethnicity_not_uk_default(GOOD_ETHNICITY_CSV)

    def test_sentinel_invariants(self):
        assert check_ethnicity_sentinel_invariants(GOOD_ETHNICITY_CSV)
        assert not check_ethnicity_sentinel_invariants("2106-3,White,10\n")
        assert not check_ethnicity_sentinel_invariants("nil,nil,2\nnil,nil,3\n")


class TestDataChecks:
    UK_STREETS = ["Road", "Street", "Lane", "Avenue", "Place", "Square"]

    def test_uk_street_list_detected(self):
        data = {"address": {"country": "USA", "streets": self.UK_STREETS}}
        assert not check_data_streets_not_uk_default(data)

    def test_us_suffixes_pass(self):
        data = {"address": {"country": "USA", "streets": ["Street", "Avenue", "Boulevard", "Parkway"]}}
        assert check_data_streets_not_uk_default(data)

    def test_shared_subset_is_not_a_false_positive(self):
        """US suffixes overlap the UK ones; only an exact match counts as unconverted."""
        data = {"address": {"country": "USA", "streets": ["Street", "Avenue"]}}
        assert check_data_streets_not_uk_default(data)

    def test_missing_address_passes(self):
        assert check_data_streets_not_uk_default({})


class TestDoctorChecks:
    def test_placeholder_names_detected(self):
        """The committed fixture once held invented John Smith / Jane Doe records."""
        doctors = [{"id": "1", "surname": "Smith", "firstname": "John", "prefix": "Dr", "specialty": "MED"}]
        assert not check_doctors_not_placeholder(doctors)

    def test_real_names_pass(self):
        doctors = [
            {
                "id": "1306422589",
                "surname": "ABI-YOUNES",
                "firstname": "NADINE",
                "prefix": "Dr",
                "specialty": "ANESTH",
            }
        ]
        assert check_doctors_not_placeholder(doctors)

    def test_duplicate_ids_detected(self):
        doctors = [
            {"id": "1", "surname": "A", "firstname": "B", "prefix": "Dr", "specialty": "MED"},
            {"id": "1", "surname": "C", "firstname": "D", "prefix": "Dr", "specialty": "SUR"},
        ]
        assert not check_doctor_ids_unique(doctors)

    def test_specialty_outside_allowed_set_detected(self):
        """NUCC_TO_HL7_MAP once emitted 570 codes outside the allowed 14."""
        doctors = [{"id": "1", "surname": "A", "firstname": "B", "prefix": "Dr", "specialty": "NEURORAD"}]
        assert not check_doctors_specialties_allowed(doctors)
        assert "NEURORAD" not in ALLOWED_SPECIALTIES


class TestHl7Checks:
    def test_nucc_code_rejected(self):
        """generate_all_configs once wrote taxonomy.code straight through."""
        assert not check_hl7_hospital_service_allowed({"hospital_service": "282N00000X"})

    def test_hl7_code_accepted(self):
        assert check_hl7_hospital_service_allowed({"hospital_service": "MED"})


class TestRunDeterministicChecks:
    def test_accepts_an_arbitrary_directory(self, tmp_path):
        """The whole point of parameterizing: validate generated output, not a fixture."""
        write_configs(tmp_path)
        results = run_deterministic_checks(tmp_path)
        failures = [name for name, (passed, _) in results.items() if not passed]
        assert not failures, f"unexpected failures: {failures}"
        assert get_deterministic_confidence(tmp_path) == 1.0

    def test_catches_stale_uk_output(self, tmp_path):
        write_configs(
            tmp_path,
            ethnicity=UK_ETHNICITY_CSV,
            doctors=[{"id": "1", "surname": "Smith", "firstname": "John", "prefix": "Dr", "specialty": "MED"}],
            hl7_service="282N00000X",
            streets=["Road", "Street", "Lane", "Avenue", "Place", "Square"],
        )
        results = run_deterministic_checks(tmp_path)
        failed = {name for name, (passed, _) in results.items() if not passed}
        assert {
            "ethnicity_not_uk_default",
            "data_streets_not_uk_default",
            "doctors_not_placeholder",
            "hl7_hospital_service_allowed",
        } <= failed
        assert get_deterministic_confidence(tmp_path) < 0.9

    def test_missing_directory_reports_failures_instead_of_raising(self, tmp_path):
        results = run_deterministic_checks(tmp_path / "does-not-exist")
        assert results, "a missing directory must still produce a report"
        assert all(not passed for passed, _ in results.values())
        assert get_deterministic_confidence(tmp_path / "does-not-exist") == 0.0
        # The exception is captured as detail, not propagated.
        assert any("FileNotFoundError" in detail for _, detail in results.values())

    def test_doctor_checks_skipped_when_file_absent(self, tmp_path):
        write_configs(tmp_path)  # no doctors.yml
        results = run_deterministic_checks(tmp_path)
        assert "doctors_not_placeholder" not in results

    def test_report_lists_failures(self, tmp_path):
        write_configs(tmp_path, ethnicity=UK_ETHNICITY_CSV)
        report = format_check_report(run_deterministic_checks(tmp_path))
        assert "FAILED ethnicity_not_uk_default" in report
        assert "deterministic checks passed" in report
