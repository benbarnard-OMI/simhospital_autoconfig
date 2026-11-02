"""CLI tests for the `generate` command.

`__main__` previously had no coverage at all: `--name/--state` and `--zip` were stubs
that logged "not yet implemented" and returned 1, and nothing asserted on argument
dispatch, ambiguity handling, or exit codes.

The fakes subclass the real clients and override only the network calls, so argument
parsing, name normalization, CMS field mapping and config generation stay under test.
"""

from __future__ import annotations

import argparse
import logging
from types import SimpleNamespace

import pytest

from simhospital_autoconfig import __main__ as cli
from simhospital_autoconfig.cms import CMSClient
from simhospital_autoconfig.nppes import (
    NPPESAddress,
    NPPESClient,
    NPPESearchResults,
    NPPESResult,
    NPPESTaxonomy,
)

RUSH_NPI = "1699921007"
STROGER_CCN = "140124"
STROGER_NPI = "1588612832"

CMS_ROW = {
    "Facility ID": STROGER_CCN,
    "Facility Name": "JOHN H STROGER JR HOSPITAL",
    "Address": "1901 W HARRISON ST",
    "City/Town": "CHICAGO",
    "State": "IL",
    "ZIP Code": "60612",
    "County/Parish": "COOK",
    "Telephone Number": "(312) 864-6000",
    "Hospital Type": "Acute Care Hospitals",
    "Hospital Ownership": "Government - Local",
    "Emergency Services": "Yes",
}


def nppes_org(npi, name, zip4="606123833"):
    return NPPESResult(
        npi=npi,
        enumeration_type="NPI-2",
        organization_name=name,
        address=NPPESAddress(
            address_1="100 MAIN ST", city="CHICAGO", state="IL", postal_code=zip4, country_code="US"
        ),
        taxonomies=[NPPESTaxonomy(code="282N00000X", desc="General Acute Care Hospital", primary=True)],
    )


class FakeNPPES(NPPESClient):
    def __init__(self, search=None, by_npi=None, doctors=None):
        super().__init__()
        self.search = search if search is not None else NPPESearchResults([], 0)
        self.by_npi = by_npi
        self.doctors = doctors or []
        self.search_calls = []
        self.doctor_calls = []
        self.npi_calls = []

    def search_organizations(self, organization_name, state, **kwargs):
        self.search_calls.append((organization_name, state))
        return self.search

    def get_organization_by_npi(self, npi, **kwargs):
        self.npi_calls.append(npi)
        if self.by_npi is None:
            raise ValueError(f"No NPPES result found for NPI: {npi}")
        return self.by_npi

    def fetch_doctors_by_location(self, zip_code, **kwargs):
        self.doctor_calls.append(zip_code)
        return list(self.doctors)


class FakeCMS(CMSClient):
    """Keeps the real map_to_simhospital_config; only the download is faked."""

    def __init__(self, rows=None, enrollment_npi=STROGER_NPI):
        super().__init__()
        self.rows = rows or []
        self.enrollment_npi = enrollment_npi
        self.search_calls = []
        self.enrollment_calls = []

    def search_hospitals(self, **kwargs):
        self.search_calls.append(kwargs)
        return list(self.rows)

    def load_rows(self):
        return list(self.rows)

    def get_primary_npi_by_ccn(self, ccn):
        self.enrollment_calls.append(ccn)
        if isinstance(self.enrollment_npi, Exception):
            raise self.enrollment_npi
        return self.enrollment_npi


class FakeCensus:
    def __init__(self):
        self.zctas = []

    def get_demographics(self, zcta, **kwargs):
        self.zctas.append(zcta)
        return {
            "total_population": 34699,
            "ethnicity": {"2106-3": 7683, "2054-5": 18753},
            "ethnicity_labels": {"2106-3": "White", "2054-5": "Black or African American"},
            "zcta": zcta,
            "acs_year": 2023,
        }


@pytest.fixture
def env(monkeypatch):
    """Install fakes and capture what generation was asked to do."""
    state = SimpleNamespace(
        nppes=FakeNPPES(),
        cms=FakeCMS(),
        census=FakeCensus(),
        generated=[],
        checks={"sample_check": (True, "")},
    )
    monkeypatch.setattr(cli, "NPPESClient", lambda *a, **k: state.nppes)
    monkeypatch.setattr(cli, "CMSClient", lambda *a, **k: state.cms)
    monkeypatch.setattr(cli, "CensusClient", lambda *a, **k: state.census)
    monkeypatch.setattr(cli, "_resolve_cms_hospital", lambda cms, nppes: None)

    def fake_generate(nppes_result, **kwargs):
        state.generated.append((nppes_result, kwargs))
        return {"hl7.yml": ""}

    monkeypatch.setattr(cli, "generate_all_configs", fake_generate)
    monkeypatch.setattr(cli, "run_deterministic_checks", lambda d: state.checks)
    return state


def make_args(**overrides):
    base = {
        "npi": None,
        "name": None,
        "state": None,
        "zip": None,
        "output_dir": ".",
        "dry_run": True,  # stops before generate_all_configs, which most tests don't need
        "verbose": False,
        "strict": False,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


class TestArgumentDispatch:
    def test_no_selector_errors(self, env):
        assert cli.run_generate(make_args()) == 1
        assert not env.generated

    def test_name_without_state_errors(self, env):
        assert cli.run_generate(make_args(name="Rush")) == 1

    def test_npi_lookup_failure_errors(self, env):
        assert cli.run_generate(make_args(npi="1730209545")) == 1
        assert not env.generated

    def test_invalid_state_errors(self, env):
        env.nppes.search = NPPESearchResults([nppes_org(RUSH_NPI, "RUSH")], 1)
        assert cli.run_generate(make_args(name="Rush", state="ILL")) == 1
        assert not env.nppes.search_calls, "should reject before calling the API"

    @pytest.mark.parametrize("bad_zip", ["abc", "606", "606123456", ""])
    def test_invalid_zip_errors(self, env, bad_zip):
        assert cli.run_generate(make_args(zip=bad_zip)) == 1
        assert not env.cms.search_calls

    def test_zip_plus_four_is_accepted_and_truncated(self, env):
        env.cms.rows = [CMS_ROW]
        env.nppes.by_npi = nppes_org(STROGER_NPI, "COOK COUNTY")
        assert cli.run_generate(make_args(zip="60612-3714")) == 0
        assert env.cms.search_calls[0]["zip_code"] == "60612"


class TestNameStateBranch:
    def test_single_exact_match_proceeds(self, env):
        env.nppes.search = NPPESearchResults(
            [
                nppes_org(RUSH_NPI, "RUSH UNIVERSITY MEDICAL CENTER"),
                # Fuzzy noise the API also returns; must not be treated as a match.
                nppes_org("1487103644", "DEPARTMENT OF PSYCHIATRY AT RUSH"),
            ],
            2,
        )
        assert cli.run_generate(make_args(name="Rush University Medical Center", state="IL")) == 0
        assert env.nppes.search_calls == [("Rush University Medical Center", "IL")]
        assert env.census.zctas == ["60612"]

    def test_truncated_results_do_not_resolve_one_exact_match(self, env, caplog):
        env.nppes.search = NPPESearchResults(
            [nppes_org(RUSH_NPI, "RUSH UNIVERSITY MEDICAL CENTER")],
            500,
        )
        with caplog.at_level(logging.ERROR):
            assert cli.run_generate(
                make_args(name="Rush University Medical Center", state="IL")
            ) == 1

        assert "could not be verified as complete" in caplog.text
        assert "matched 500 organizations" in caplog.text
        assert "returned 1 result on this page" in caplog.text
        assert "--npi" in caplog.text
        assert not env.generated

    def test_unknown_result_count_fails_closed_without_logging_error(self, env, caplog):
        env.nppes.search = NPPESearchResults(
            [nppes_org(RUSH_NPI, "RUSH UNIVERSITY MEDICAL CENTER")], None
        )

        with caplog.at_level(logging.ERROR):
            assert cli.run_generate(
                make_args(name="Rush University Medical Center", state="IL")
            ) == 1

        assert "could not be verified as complete" in caplog.text
        assert "did not report the total match count" in caplog.text
        assert "--npi" in caplog.text
        assert "Logging error" not in caplog.text
        assert "None" not in caplog.text
        assert not env.generated

    def test_no_results_hints_at_the_legal_entity_name(self, env, caplog):
        env.nppes.search = NPPESearchResults([], 0)
        with caplog.at_level(logging.ERROR):
            assert cli.run_generate(make_args(name="Stroger", state="IL")) == 1
        # NPPES registers that hospital as its legal entity, so the public name finds nothing.
        assert "COOK COUNTY" in caplog.text
        assert not env.generated

    def test_multiple_exact_matches_are_listed_not_guessed(self, env, caplog):
        """Rush holds three NPIs across Skokie and two Chicago campuses."""
        env.nppes.search = NPPESearchResults(
            [
                nppes_org("1699921007", "RUSH UNIVERSITY MEDICAL CENTER", "606123833"),
                nppes_org("1396184669", "RUSH UNIVERSITY MEDICAL CENTER", "606123841"),
                nppes_org("1316067994", "RUSH UNIVERSITY MEDICAL CENTER", "600761224"),
            ],
            3,
        )
        with caplog.at_level(logging.ERROR):
            assert cli.run_generate(make_args(name="Rush University Medical Center", state="IL")) == 1
        for npi in ("1699921007", "1396184669", "1316067994"):
            assert npi in caplog.text
        assert "will not guess" in caplog.text
        assert not env.generated

    def test_fuzzy_only_matches_are_listed(self, env, caplog):
        env.nppes.search = NPPESearchResults(
            [nppes_org("1487103644", "DEPARTMENT OF PSYCHIATRY AT RUSH")], 1
        )
        with caplog.at_level(logging.ERROR):
            assert cli.run_generate(make_args(name="Rush University Medical Center", state="IL")) == 1
        assert "partially match" in caplog.text
        assert not env.generated

    def test_search_exception_errors(self, env, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("connection reset")

        monkeypatch.setattr(env.nppes, "search_organizations", boom)
        assert cli.run_generate(make_args(name="Rush", state="IL")) == 1


class TestZipBranch:
    def test_no_facility_errors(self, env):
        env.cms.rows = []
        assert cli.run_generate(make_args(zip="60612")) == 1
        assert not env.generated

    def test_multiple_facilities_are_listed_not_guessed(self, env, caplog):
        """ZIP 60612 really does hold four hospitals."""
        env.cms.rows = [
            CMS_ROW,
            {**CMS_ROW, "Facility ID": "140119", "Facility Name": "RUSH UNIVERSITY MEDICAL CENTER"},
        ]
        with caplog.at_level(logging.ERROR):
            assert cli.run_generate(make_args(zip="60612")) == 1
        assert "140124" in caplog.text and "140119" in caplog.text
        assert "--name" in caplog.text
        assert not env.generated

    def test_name_filter_narrows_a_dense_zip(self, env):
        env.cms.rows = [
            {**CMS_ROW, "Facility ID": "140119", "Facility Name": "RUSH UNIVERSITY MEDICAL CENTER"}
        ]
        env.nppes.by_npi = nppes_org(STROGER_NPI, "RUSH UNIVERSITY MEDICAL CENTER")
        assert cli.run_generate(make_args(zip="60612", name="rush")) == 0
        assert env.cms.search_calls[0]["name"] == "rush"
        assert env.cms.search_calls[0]["zip_code"] == "60612"

    def test_zip_uses_cms_primary_npi_for_nppes_and_hl7_config(
        self, env, tmp_path, monkeypatch
    ):
        env.cms.rows = [CMS_ROW]
        env.nppes.by_npi = nppes_org(STROGER_NPI, "COOK COUNTY")
        env.nppes.doctors = [{"id": "1", "surname": "A", "firstname": "B", "prefix": "Dr", "specialty": "MED"}]

        from simhospital_autoconfig.generators import generate_all_configs as real_generate

        monkeypatch.setattr(cli, "generate_all_configs", real_generate)
        assert cli.run_generate(
            make_args(zip="60612", name="stroger", dry_run=False, output_dir=str(tmp_path))
        ) == 0

        assert env.cms.search_calls[0]["name"] == "stroger"
        assert env.cms.enrollment_calls == [STROGER_CCN]
        assert env.nppes.npi_calls == [STROGER_NPI]
        assert not env.nppes.search_calls
        assert "id_number: '1588612832'" in (tmp_path / "hl7.yml").read_text()
        assert STROGER_CCN not in (tmp_path / "hl7.yml").read_text()

    def test_catalog_is_queried_only_once(self, env):
        """The --zip path already has the row; the shared tail must not re-join."""
        env.cms.rows = [CMS_ROW]
        env.nppes.by_npi = nppes_org(STROGER_NPI, "COOK COUNTY")
        assert cli.run_generate(make_args(zip="60612", dry_run=False)) == 0
        assert len(env.cms.search_calls) == 1

    def test_missing_enrollment_npi_fails_and_never_generates(self, env, caplog):
        env.cms.rows = [CMS_ROW]
        env.cms.enrollment_npi = ValueError("duplicate CCN rows; use --npi")

        with caplog.at_level(logging.WARNING):
            assert cli.run_generate(make_args(zip="60612", dry_run=False)) == 1
        assert "duplicate CCN rows" in caplog.text
        assert "--npi" in caplog.text
        assert not env.generated

    def test_nppes_failure_fails_and_never_generates(self, env, caplog):
        env.cms.rows = [CMS_ROW]
        env.cms.enrollment_npi = STROGER_NPI

        with caplog.at_level(logging.WARNING):
            assert cli.run_generate(make_args(zip="60612", dry_run=False)) == 1
        assert "Use --npi" in caplog.text
        assert not env.generated

    def test_census_uses_the_cms_zip(self, env):
        env.cms.rows = [CMS_ROW]
        env.nppes.by_npi = nppes_org(STROGER_NPI, "COOK COUNTY")
        assert cli.run_generate(make_args(zip="60612")) == 0
        assert env.census.zctas == ["60612"]


class TestValidationExitCodes:
    def test_strict_exits_nonzero_when_a_check_fails(self, env):
        env.nppes.by_npi = nppes_org("1730209545", "COOK COUNTY")
        env.checks = {"ethnicity_not_uk_default": (False, "")}
        assert cli.run_generate(make_args(npi="1730209545", dry_run=False, strict=True)) == 1

    def test_without_strict_a_failed_check_only_warns(self, env, caplog):
        env.nppes.by_npi = nppes_org("1730209545", "COOK COUNTY")
        env.checks = {"ethnicity_not_uk_default": (False, "")}
        with caplog.at_level(logging.WARNING):
            assert cli.run_generate(make_args(npi="1730209545", dry_run=False)) == 0
        assert "FAILED ethnicity_not_uk_default" in caplog.text

    def test_all_checks_passing_exits_zero(self, env):
        env.nppes.by_npi = nppes_org("1730209545", "COOK COUNTY")
        assert cli.run_generate(make_args(npi="1730209545", dry_run=False, strict=True)) == 0
        assert env.nppes.npi_calls == ["1730209545"]

    def test_dry_run_does_not_generate(self, env):
        env.nppes.by_npi = nppes_org("1730209545", "COOK COUNTY")
        assert cli.run_generate(make_args(npi="1730209545", dry_run=True)) == 0
        assert not env.generated
