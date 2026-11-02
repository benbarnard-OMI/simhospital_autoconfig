# Plan: Full Adversarial Analysis Remediation

## Step 1: Add Missing Test Files for `hl7.yml` and `locations.yml`

**Problem:** Git history shows tests were added for `hl7.yml` and `locations.yml` but no corresponding test files exist in the workspace. These files have complex structures that are currently untested.

**Actions:**
1. Create `test_hl7_yml.py` that validates:
   - Top-level keys exist: `allergy`, `diagnosis`, `document`, `procedure`, `order_control`, `result_status`, `document_status`, `order_status`, `patient_class`, `patient_account_status`, `gender`, `abnormal_flags`, `primary_facility`, `hospital_service`, `coding_system`, `mapping`.
   - List-valued keys are non-empty lists of strings.
   - Scalar values are strings.
   - `primary_facility` contains `${ORGANIZATION_NAME}` and `${ORGANIZATION_ID}` placeholders.
2. Create `test_locations_yml.py` that validates:
   - Top-level keys exist: `ED`, `Renal`, `Non-renal`.
   - Each location has required sub-keys: `poc`, `facility`, `floor`, `room`.
   - `floor` is an integer.
   - `facility` contains `${ORGANIZATION_NAME}` placeholder.
   - `ED` has `type: "ED"`.
   - `Renal` and `Non-renal` have `building` (non-empty string).

**Deliverable / Exit Criteria:**
- Both new test files exist.
- Running `pytest -v` shows all tests passing (existing + new).
- A deliberately malformed `hl7.yml` (missing required key) or `locations.yml` (non-integer floor) causes a test failure.

---

## Step 2: Enforce `ethnicity.csv` Sentinel Row Invariants

**Problem:** The `nil,nil` sentinel row is documented but not validated. A consumer breaks if the sentinel is missing, duplicated, or if rogue `nil` rows appear elsewhere.

**Actions:**
1. Update `test_ethnicity_csv.py` to add assertions:
   - Exactly one row has `id == "nil"` and `text == "nil"`.
   - No other row has `id == "nil"` or `text == "nil"`.
   - All frequency values (including sentinel) are positive integers.
   - The sentinel row's frequency is a positive integer.

**Deliverable / Exit Criteria:**
- `test_ethnicity_csv.py` contains the new sentinel-invariant tests.
- Running `pytest -v` passes on the current `ethnicity.csv`.
- Removing the sentinel row, duplicating it, or adding a rogue `nil` row causes a test failure.

---

## Step 3: Harden CI Workflow Permissions and Pinning

**Problem:** `.github/workflows/tests.yml` uses unpinned actions and default `GITHUB_TOKEN` permissions (write-all).

**Actions:**
1. Add a `permissions:` block to `.github/workflows/tests.yml` restricting `GITHUB_TOKEN` to `contents: read`.
2. Pin `actions/checkout@v4` and `actions/setup-python@v5` to their current SHA256 hashes.

**Deliverable / Exit Criteria:**
- `.github/workflows/tests.yml` contains `permissions: contents: read`.
- Action references include `@sha256:<hash>`.
- Workflow still runs successfully after changes.

---

## Step 4: Add Upper Bounds to `requirements.txt`

**Problem:** Floating minimum versions (`>=7.0`, `>=6.0`) allow major version upgrades that could break tests.

**Actions:**
1. Update `requirements.txt` to pin upper bounds: `pytest>=7.0,<8.0` and `pyyaml>=6.0,<7.0`.

**Deliverable / Exit Criteria:**
- `requirements.txt` contains upper bounds.
- `pip install -r requirements.txt` installs compatible versions.

---

## Step 5: Add Range Validation to `test_data_yml.py`

**Problem:** Percentage values (`percentage`, `degree_percentage`, `suffix_percentage`, `middlename_percentage`) are not validated to be within `[0, 100]`.

**Actions:**
1. Add a helper `assert_in_range(parent_dict, key, min_val, max_val)`.
2. Add assertions in `test_allergy_section`, `test_patient_name_section` to validate:
   - `allergy.percentage` is in `[0, 100]`.
   - `allergy.maximum_allergies` is a positive integer.
   - `patient_name.degree_percentage` is in `[0, 100]`.
   - `patient_name.suffix_percentage` is in `[0, 100]`.
   - `patient_name.middlename_percentage` is in `[0, 100]`.

**Deliverable / Exit Criteria:**
- `test_data_yml.py` contains range checks.
- Current `data.yml` passes.
- Setting a percentage to `-1` or `101` causes a test failure.

---

## Step 6: Validate Doctor Specialty Codes Against HL7 Table 0069

**Problem:** `test_doctors.py` does not validate that `specialty` values are from the HL7 Table 0069 set.

**Actions:**
1. Define the allowed HL7 Table 0069 specialty codes in `test_doctors.py` (based on `https://hl7-definition.caristix.com/v2/HL7v2.5.1/Tables/0069`): at minimum `MED`, `SUR`, `URO`, `PUL`, `CAR` (the codes used in the file), plus any others deemed relevant.
2. Add an assertion that each doctor's `specialty` is in the allowed set.

**Deliverable / Exit Criteria:**
- `test_doctors.py` contains the allowed specialty set and validation.
- Current `doctors.yml` passes.
- Changing a specialty to an invalid code (e.g., `"INVALID"`) causes a test failure.

---

## Step 7: Make README `sed` Examples Robust and Document Placeholder Consequences

**Problem:** The `sed` examples use `/` as delimiter, which breaks if the substitution value contains `/`. Also, the consequence of not substituting placeholders is not documented.

**Actions:**
1. Update the `sed` examples in `README.md` to use `|` as delimiter (or another safe delimiter).
2. Add a note explaining that if placeholders are not substituted, generated HL7 messages will contain the literal strings `${ORGANIZATION_NAME}` and `${ORGANIZATION_ID}`, which will cause downstream validation failures.

**Deliverable / Exit Criteria:**
- `README.md` uses a safe delimiter in `sed` examples.
- README documents the consequence of skipping substitution.

---

## Step 8: Add Pip Caching to CI Workflow

**Problem:** CI runs `pip install -r requirements.txt` on every run with no cache, slowing down feedback.

**Actions:**
1. Update `.github/workflows/tests.yml` to add a `cache: pip` step before `Install dependencies`.

**Deliverable / Exit Criteria:**
- `.github/workflows/tests.yml` includes pip caching.
- CI workflow still runs successfully.
