# Plan: Build US Hospital Config Generator

## Context
The project goal is to auto-generate Google Simhospital configuration files from public US datasets. An initial implementation exists on `origin/vibe/feat-nppes-client-5aa6f0` (commit `461cbad`) but was never merged. It covers NPPES API integration and basic generators for `hl7.yml`, `locations.yml`, `data.yml`, and `ethnicity.csv`, but is missing `doctors.yml` generation, Census/CMS integration, and proper packaging.

---

## Step 1: Package Foundation

**Goal:** Create a proper Python package and port the existing NPPES implementation.

**Actions:**
1. Create `simhospital_autoconfig/` package directory with `__init__.py`, `nppes.py`, `generators.py`, `__main__.py`.
2. Add `pyproject.toml` with package metadata, dependencies (`requests`, `pyyaml`, `census`, `pytest`), and console script entry point `simhospital-autoconfig = "simhospital_autoconfig.__main__:main"`.
3. Add `.python-version` or note Python 3.9+ requirement in README.
4. Port the NPPES client from commit `461cbad` with fixes:
   - Validate NPI format (10 digits, numeric) before API call.
   - Handle rate-limit responses (HTTP 429) with exponential backoff.
   - Prefer `addresses[0]` where `address_purpose == "LOCATION"` over hardcoded index `[0]`.
   - Handle missing `basic.organization_name` by falling back to first `other_names[0].organization_name`.

**Deliverables / Exit Criteria:**
- `pip install -e .` succeeds.
- `simhospital-autoconfig --help` shows CLI usage.
- `python -m simhospital_autoconfig --help` works.

---

## Step 2: Census ACS Fetcher for Demographics

**Goal:** Fetch real ethnicity/race/age/sex distributions from US Census Bureau ACS 5-Year estimates.

**Actions:**
1. Create `simhospital_autoconfig/census.py`.
2. Implement `CensusClient` with method `get_demographics(zcta)` returning:
   - Total population
   - Race/ethnicity counts (B03002: Hispanic, White, Black, Asian, etc.)
   - Sex by age counts (B01001)
3. Map Census race categories to HL7 ethnicity codes. Use a configurable mapping dict; default to standard HL7 CE codes where available.
4. Add retry logic with 3 attempts and 1s backoff (Census API is generally stable but has occasional 5xx).
5. Add optional Census API key support via `CENSUS_API_KEY` env var (recommended by Census for higher quotas).

**Deliverables / Exit Criteria:**
- `CensusClient.get_demographics("60601")` returns population and ethnicity counts.
- Module imports cleanly without key; raises clear error if API key is needed and missing.
- Unit tests mock `requests.get` and verify parsing of real ACS JSON structure.

---

## Step 3: CMS Hospital Data Fetcher

**Goal:** Fetch hospital type, departments, and location data from CMS public datasets.

**Actions:**
1. Create `simhospital_autoconfig/cms.py`.
2. Implement `CMSClient` with:
   - `get_hospital_by_ccn(ccn)` — fetch from CMS Hospital General Information (`xubh-q36u`) SODA API.
   - `get_hospital_by_npi(npi)` — search Hospital General Info by `provider_id` (some datasets use NPI, but most use CCN; NPPES has `identifiers` with CCN).
   - `get_hospital_services(zcta)` — optional: query POS file or HCRIS for department presence (ED, Renal, etc.).
3. Map CMS fields to Simhospital config:
   - `hospital_type` → `location.type` (e.g., "Acute Care" → `ED` required, "Critical Access" may not have ED).
   - `emergency_services` flag → include/exclude `ED` in `locations.yml`.
   - `hospital_name` → fallback if NPPES `organization_name` missing.

**Deliverables / Exit Criteria:**
- `CMSClient.get_hospital_by_ccn("140001")` returns hospital details.
- Module handles missing/disabled emergency services gracefully.
- Unit tests mock SODA API responses.

---

## Step 4: NUCC to HL7 Table 0069 Mapper

**Goal:** Map NPPES/NUCC specialty taxonomy codes to HL7 Table 0069 codes for `doctors.yml` and `hl7.yml`.

**Actions:**
1. Create `simhospital_autoconfig/specialties.py`.
2. Build a static mapping dict from NUCC taxonomy descriptions to HL7 Table 0069 codes. At minimum cover codes used in the repo (`MED`, `SUR`, `URO`, `PUL`, `CAR`) plus common ones (`ANESTH`, `EMER`, `FAMP`, `INTMED`, `OBG`, `PEDS`, `PSY`, `RAD`, `TRAUM`).
3. Add fallback: if taxonomy description doesn't map, default to `MED`.
4. Add `get_specialties_for_hospital(taxonomies)` that returns a deduplicated list of HL7 codes from the hospital's provider taxonomies.

**Deliverables / Exit Criteria:**
- Mapping dict covers at least 15 common NUCC specialties.
- `get_specialties_for_hospital([{"desc": "Cardiology"}])` returns `{"CAR"}`.
- Tests verify mapping and fallback behavior.

---

## Step 5: Doctors Config Generator

**Goal:** Generate `doctors.yml` from NPPES practitioner data filtered by hospital location and specialty.

**Actions:**
1. Add `generate_doctors_yml` to `generators.py`.
2. Implement `fetch_doctors_by_location(zip_code, specialties)` in `nppes.py`:
   - Query NPPES API with `taxonomy_description` and `postal_code` (prefix).
   - Handle rate limits with `time.sleep(0.5)` between requests.
   - Limit to 20 doctors per specialty to avoid blowing rate limits.
   - Return structured list with `id`, `surname`, `firstname`, `prefix`, `specialty`.
3. Generator writes YAML list sorted by specialty then surname.
4. Add `doctors.yml` to `generate_all_configs`.

**Deliverables / Exit Criteria:**
- `generate_doctors_yml("12345", ["MED", "SUR"], output_path="./doctors.yml")` produces valid `doctors.yml`.
- Each doctor has required keys (`id`, `surname`, `firstname`, `prefix`, `specialty`).
- Specialty values are valid HL7 Table 0069 codes.
- Generated file passes existing `test_doctors.py` assertions.

---

## Step 6: Enhanced Data YAML Generator

**Goal:** Populate `data.yml` with realistic US demographics from Census data.

**Actions:**
1. Update `generate_data_yml` to accept `demographics` dict from `CensusClient`.
2. Map Census ethnicity fractions to `address` and `patient_name` percentages:
   - `allergy.percentage` — use national average (~20%) or regional if available.
   - `allergy.maximum_allergies` — fixed at 3 (no public source).
   - `patient_name.degree_percentage` / `suffix_percentage` / `middlename_percentage` — keep UK defaults or regionalize via Census name data if feasible; otherwise keep static defaults.
   - `address.country` → `"USA"` (not `"GBR"`).
   - `address.cities` → hospital city + nearest major city.
   - `address.streets` → US-common street names (replace UK-centric list).
3. Add `simhospital_autoconfig/addresses.py` with a static list of ~20 common US street names and ~10 city name patterns.

**Deliverables / Exit Criteria:**
- Generated `data.yml` has `country: "USA"`.
- `address.cities` contains the hospital's city.
- `address.streets` contains US-style names ("Main", "Oak", "Park", etc.).
- Generated file passes existing `test_data_yml.py` assertions.

---

## Step 7: Enhanced Ethnicity CSV Generator

**Goal:** Populate `ethnicity.csv` with real Census race/ethnicity data for the hospital's region.

**Actions:**
1. Update `generate_ethnicity_csv` to accept `demographics` dict from `CensusClient`.
2. Map Census race categories to HL7 CE codes using a priority order:
   - Hispanic/Latino → assign codes like `H` or create new ones if not present.
   - White, Black, Asian, etc. → map to existing or new CE codes.
   - Include `nil,nil` sentinel row with frequency derived from national average for "no ethnicity reported" (~5%).
3. Ensure all frequencies sum to a reasonable total (e.g., 1000 for 0.1% resolution).
4. Keep header comments from the original file.

**Deliverables / Exit Criteria:**
- Generated `ethnicity.csv` has exactly one `nil,nil` sentinel row.
- Frequencies are positive integers.
- File passes existing `test_ethnicity_csv.py` assertions.
- Removing sentinel or duplicating it causes test failure (already covered).

---

## Step 8: Enhanced Locations YAML Generator

**Goal:** Populate `locations.yml` with real hospital departments from CMS/POS data.

**Actions:**
1. Update `generate_locations_yml` to accept `hospital_data` from `CMSClient`.
2. Always include `ED` if `emergency_services == true` (CMS field).
3. Map CMS service flags to locations:
   - ` Renal ` or `ESRD` → add `Renal` location with `building` from CMS `hospital_name` or "Main Building".
   - Other departments → add generic `Non-renal` or department-specific location.
4. Set `facility` to `organization_name`.
5. Set `floor` and `room` to sensible defaults (`1`, `ED Room`, `MainRoom`).
6. Preserve `type: ED` for ED location; default other locations to `BED`.

**Deliverables / Exit Criteria:**
- If CMS reports no emergency services, `ED` is still included (Simhospital requires it) but with a warning log.
- `Renal` location is included if hospital has renal/dialysis services.
- Generated file passes existing `test_locations_yml.py` assertions.

---

## Step 9: HL7 YAML Generator Refinement

**Goal:** Ensure `hl7.yml` is correctly generated with hospital-specific values.

**Actions:**
1. Review and fix the existing `generate_hl7_yml`:
   - Ensure `${ORGANIZATION_NAME}` and `${ORGANIZATION_ID}` placeholders are fully replaced (no regex edge cases).
   - Set `hospital_service` based on the hospital's primary specialty from NPPES taxonomies (map NUCC desc → HL7 Table 0069).
   - Keep all HL7 table values static (they are standard codes).
2. Add validation: after generation, parse the YAML and assert all required keys exist before writing.

**Deliverables / Exit Criteria:**
- Generated `hl7.yml` contains no unresolved placeholders.
- `hospital_service` reflects the hospital's primary specialty.
- Generated file passes existing `test_hl7_yml.py` assertions.

---

## Step 10: CLI and Orchestration

**Goal:** Build a robust CLI that ties all fetchers and generators together.

**Actions:**
1. Rewrite `__main__.py` with `argparse` subcommands:
   - `generate --npi <NPI>` — primary workflow.
   - `generate --name "<Hospital Name>" --state <XX>` — fallback search via NPPES.
   - `generate --zip <ZIP>` — resolve ZIP to ZCTA, then fetch hospital via CMS.
2. Add pipeline:
   - Step 1: Resolve hospital identity (NPPES + CMS).
   - Step 2: Fetch demographics (Census).
   - Step 3: Fetch doctors (NPPES practitioner search).
   - Step 4: Generate all 5 config files.
   - Step 5: Validate generated files against existing test suite.
3. Add progress logging and error recovery (if one source fails, warn and continue with defaults).
4. Add `--dry-run` flag to print planned actions without writing files.

**Deliverables / Exit Criteria:**
- `simhospital-autoconfig generate --npi 1730209545 --output-dir ./config` creates all 5 files.
- CLI exits non-zero on unrecoverable errors (invalid NPI, no hospital found).
- CLI warns but does not crash on transient API failures.

---

## Step 11: Integration and Contract Tests

**Goal:** Ensure generated configs are valid and the end-to-end pipeline works.

**Actions:**
1. Create `tests/test_e2e.py`:
   - Use `vcrpy` or `requests-mock` to record/replay real API responses for a known hospital (e.g., NPI `1730209545` — Stroger Hospital, or a small critical-access hospital).
   - Run `generate_all_configs` with mocked data.
   - Assert all 5 output files exist and are valid YAML/CSV.
   - Assert generated files pass the existing root-level test suite (`pytest test_*.py`).
2. Create `tests/test_integration_census.py` and `tests/test_integration_cms.py` for each fetcher with recorded HTTP interactions.
3. Update existing root-level tests (`test_hl7_yml.py`, `test_locations_yml.py`, etc.) to also accept a `--generated` flag or parameterize against both default and generated files (optional; if too complex, keep existing tests as static-file validators and rely on e2e tests for generated output).

**Deliverables / Exit Criteria:**
- `pytest -v` runs all tests (root-level + `tests/`) and passes.
- E2E test records a full API interaction and replays it offline.
- Running the CLI with a recorded NPI produces passing tests.

---

## Step 12: CI/CD Hardening

**Goal:** Ensure the new package is tested in CI alongside existing static-file tests.

**Actions:**
1. Update `.github/workflows/tests.yml`:
   - Add a step "Install package" after "Install dependencies": `pip install -e .`.
   - Add a linting step (optional but recommended): `flake8 simhospital_autoconfig tests` or `ruff check`.
   - Ensure tests in both root `test_*.py` and `tests/test_*.py` are collected.
2. Add `tox.ini` or `noxfile.py` for local multi-environment testing (optional).
3. Add `pre-commit` config with `ruff`, `trailing-whitespace`, `end-of-file-fixer`.

**Deliverables / Exit Criteria:**
- GitHub Actions workflow passes with new package installed.
- Workflow caches pip dependencies (already implemented from prior plan).
- Workflow restricts `GITHUB_TOKEN` to `contents: read` (already implemented).

---

## Step 13: Documentation

**Goal:** Document how to use the generator and understand its data sources.

**Actions:**
1. Update `README.md`:
   - Add "Usage" section with CLI examples.
   - Document supported input types (NPI, hospital name, ZIP).
   - Document data sources (NPPES, Census ACS, CMS Hospital Compare) with links.
   - Document limitations: rate limits, ZCTA vs ZIP mismatch, missing data fallbacks.
   - Document that generated configs must still be reviewed and substituted with `${ORGANIZATION_NAME}` / `${ORGANIZATION_ID}` (or note that the generator does this automatically).
2. Add `CONTRIBUTING.md` with development setup instructions.
3. Add docstrings to all public functions and classes.

**Deliverables / Exit Criteria:**
- README explains the full workflow from input to generated configs.
- All public APIs have docstrings.
- Examples are copy-paste runnable.

---

## Step 14: PyPI Packaging (Optional)

**Goal:** Make the package installable via pip.

**Actions:**
1. Add `pyproject.toml` with `build-system`, `project`, and optional `[project.optional-dependencies]` for dev (`pytest`, `requests-mock`, `vcrpy`).
2. Add `MANIFEST.in` to include license, README, and any static data files (NUCC mapping).
3. Verify `python -m build` produces a valid wheel and sdist.

**Deliverables / Exit Criteria:**
- `python -m build` succeeds.
- Wheel installs in a clean venv and CLI works.
