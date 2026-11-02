# Plan: Prove the Generator Works with Real Simulator

## Context
We have a working generator that produces structurally valid config files, but we have not yet proven that Google Simhospital accepts and uses those configs at runtime. This plan adds runtime validation against the actual simulator binary.

---

## Step 1: Record Deterministic API Cassettes

**Goal:** Make the full generator pipeline runnable offline with real API shapes.

**Actions:**
1. Pick a small, well-known hospital (e.g., NPI `1730209545` — Cook County/Stroger Hospital, Chicago, IL) as the canonical test fixture.
2. Use `vcrpy` to record NPPES, Census, and CMS responses for that NPI and its associated ZCTA.
3. Store cassettes in `tests/cassettes/`.
4. Add a fixture in `tests/test_simulator_validation.py` that generates configs from recorded data without hitting the network.

**Deliverables:**
- `tests/cassettes/test_simulator_validation[<npi>].yaml` containing recorded interactions.
- Generated configs for the fixture hospital checked into `tests/fixtures/<npi>/` so tests can validate them even if APIs change.

---

## Step 2: Add Config Schema Validation

**Goal:** Validate generated configs against the implicit schema enforced by Simhospital's Go loader.

**Actions:**
1. Inspect `pkg/config/data.go` (and related loaders) from the `google/simhospital` repo to extract type constraints:
   - `locations.yml`: `floor` is parsed with `strconv.Atoi` — verify if it accepts strings like `"1"` or requires integers. The current test asserts `int`; reconcile.
   - `data.yml`: verify expected types for `percentage`, `country`, `cities`, etc.
   - `ethnicity.csv`: verify column count, header expectations, sentinel handling.
   - `doctors.yml`: verify required keys and types.
   - `hl7.yml`: verify placeholder replacement expectations.
2. Add a `tests/test_schema_validation.py` that loads generated configs and asserts:
   - `floor` in `locations.yml` is either `int` or a numeric string (matching Go's `Atoi` behavior).
   - `data.yml` `address.country` is `"USA"` for US hospitals.
   - `ethnicity.csv` has exactly one `nil,nil` sentinel.
   - `doctors.yml` specialties are in `ALLOWED_SPECIALTIES`.
3. Update `test_locations_floor_is_int` to parameterize against both `int` and `str` if Go accepts both, or lock it to `int` if that's confirmed.

**Deliverables:**
- `tests/test_schema_validation.py`.
- Updated `test_locations_yml.py` if needed.

---

## Step 3: Build a Simulator Validation Script

**Goal:** Create a script that runs the actual Simhospital binary against generated configs and reports success/failure.

**Actions:**
1. Create `scripts/validate_with_simulator.sh` (and `.bat` if needed) that:
   - Accepts an input config directory.
   - Checks for `docker` (preferred) or a local `simhospital` binary.
   - If using Docker: runs `docker run --rm -v "$(pwd)/config:/app/config" eu.gcr.io/simhospital-images/simhospital:latest` with a 30-second timeout.
   - Captures exit code, stdout, and stderr.
   - Treats exit code 0 or a graceful SIGTERM after timeout as "configs accepted".
   - Treats config parse errors in stderr as failure.
2. Create `scripts/generate_and_validate.sh` that:
   - Runs `simhospital-autoconfig generate --npi <NPI> --output-dir ./tmp-config`.
   - Runs `validate_with_simulator.sh ./tmp-config`.
   - Cleans up.
3. Add a `Makefile` target:
   ```make
   validate-simulator:
       bash scripts/generate_and_validate.sh 1730209545
   ```

**Deliverables:**
- `scripts/validate_with_simulator.sh`.
- `scripts/generate_and_validate.sh`.
- `Makefile` with `validate-simulator` target.

---

## Step 4: Add CI Step for Simulator Validation

**Goal:** Run the simulator in CI to prove generated configs work in a clean environment.

**Actions:**
1. Update `.github/workflows/tests.yml`:
   - Add a job `simulator-validation` that runs on Ubuntu with Docker enabled.
   - Steps: checkout, set up Python, install deps, install package, run `make validate-simulator`.
   - Use `docker.io` login if the image is private (the plan image `eu.gcr.io/simhospital-images/simhospital:latest` is public; if not, use `gcloud auth configure-docker` with a service account).
   - Cache pip deps.
   - Note: This job can be optional/skipped on PRs if Docker is unavailable, but should run on main.
2. Add a `SIMULATOR_VALIDATION` env flag to allow skipping the step.

**Deliverables:**
- Updated `.github/workflows/tests.yml` with `simulator-validation` job.
- Documentation in `README.md` about running validation locally.

---

## Step 5: Add E2E Test with Recorded Responses

**Goal:** Prove the end-to-end pipeline works offline.

**Actions:**
1. Update `tests/test_e2e.py` to use `vcrpy` with the recorded cassettes from Step 1.
2. Run `generate_all_configs` with mocked fetchers.
3. Assert all 5 files exist and pass schema validation.
4. Optionally, assert that `simhospital-autoconfig generate --npi <NPI> --dry-run` exits 0.

**Deliverables:**
- `tests/test_e2e.py` uses `vcrpy`.
- All tests pass offline.

---

## Step 6: Reconcile `floor` Type with Go Loader

**Goal:** Ensure `floor` values in generated configs match what Simhospital actually accepts.

**Actions:**
1. Read `pkg/config/data.go` from the `google/simhospital` repo to confirm whether `floor` is parsed as `int` or `string`.
2. If Go uses `strconv.Atoi`, it accepts both `int` and numeric strings in YAML (PyYAML parses unquoted `1` as `int`, quoted `"1"` as `str`).
3. Update `generate_locations_yml` to emit `floor` as `int` (current behavior) if that's confirmed correct.
4. Update `test_locations_floor_is_int` to match reality.

**Deliverables:**
- Confirmed `floor` type.
- Generator and test aligned.

---

## Exit Criteria
- `make validate-simulator` runs successfully against the real Simhospital Docker image.
- `pytest -v` passes, including the new schema validation and e2e tests with recorded cassettes.
- CI runs `simulator-validation` job on the main branch and it passes.
- A developer can run `make validate-simulator` locally and see the simulator start without config errors.
