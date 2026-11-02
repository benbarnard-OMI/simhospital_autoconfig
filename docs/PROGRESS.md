# Project Progress — simhospital_autoconfig

_Last updated: 2026-11-02. `main` is at `b959e3d7e8a1e253ae33b0d9b0da053058882bb4`._

## Current state

- PRs #33, #34, and #36 are merged. PR #35 closed without merge and was superseded.
- PR #36 merged as `b959e3d`. Its post-merge CI passed: the test and lint job, and simulator validation ([run 41543962954](https://github.com/benbarnard-OMI/simhospital_autoconfig/actions/runs/41543962954)).
- The manual simulator E2E workflow passed on current `main` at `b959e3d`. It built the pinned simulator and checked four HL7 messages and required segments ([run 41548506599](https://github.com/benbarnard-OMI/simhospital_autoconfig/actions/runs/41548506599)).
- PR #36 local checks passed: pytest reported 182 passed and 7 skipped; Ruff, shell syntax, and `git diff --check` passed. The skipped tests require live TypeSafe access.
- In this fresh worktree, `make validate-simulator` failed because `CENSUS_API_KEY` is not set. The generator used its UK ethnicity fallback, and strict validation failed the `ethnicity_not_uk_default` check. Post-merge CI simulator validation passed with the repository secret.
- No other open PRs or issues were found before this status-only PR was opened.

## Completed work

- The 1.0 generator and validation baseline is on `main` through PR #33.
- ZIP lookup now resolves a CMS hospital by CCN, finds its primary NPI in CMS Hospital Enrollments, and fetches organization details from NPPES. It does not write a CCN as an NPI.
- For Stroger, CMS CCN `140124` maps to primary NPI `1588612832`. Use `--npi` to select a specific NPI, including `1730209545`.
- PR #36 updated ZIP identity lookup and its tests and documentation. This work is complete on `main`.
- The original detached workspace remains clean at `b1fc054`. The status work uses a separate worktree at `b959e3d`.

## Deferred work and limits

- D13, the CMS-to-NPPES identity mismatch, remains deferred. Do not add automatic matching for NPI `1730209545`.
- CMS Hospital Enrollments lists NPI `1588612832` as the primary NPI for CCN `140124`; the associated additional-NPI file does not list `1730209545`. NPPES lists both NPIs as active at the same Cook County address. This does not establish that `1730209545` belongs to CCN `140124`.
- ZIP lookup uses the CMS primary NPI. Use `--npi` when a specific NPI is required. No matching behavior changes are planned until a separate, evidence-based decision.

## Credential status

- The user confirmed that the Census API key was rotated.
- Rotation of the TypeSafe API key cannot be confirmed from the available project or GitHub records. Treat it as an outstanding security action. Do not store key values in the repository, progress record, or PR.

## Current validation record

- PR #36 checks passed before merge. Post-merge CI passed on `b959e3d` in run [41543962954](https://github.com/benbarnard-OMI/simhospital_autoconfig/actions/runs/41543962954).
- Manual simulator E2E passed on current `main` at `b959e3d`. Run [41548506599](https://github.com/benbarnard-OMI/simhospital_autoconfig/actions/runs/41548506599) built the pinned simulator and passed the four-message pathway and required HL7 segments. The earlier run [41536400519](https://github.com/benbarnard-OMI/simhospital_autoconfig/actions/runs/41536400519) also passed on feature commit `f7a9e82`.
- Fresh local checks passed: pytest reported 182 passed and 7 skipped; Ruff, shell syntax, and `git diff --check` passed. Local simulator validation failed because this worktree has no `CENSUS_API_KEY`; strict validation caught the UK fallback. The manual simulator E2E workflow passed on current `main` at `b959e3d` (run [41548506599](https://github.com/benbarnard-OMI/simhospital_autoconfig/actions/runs/41548506599)).

> **Historical record:** The sections below describe project state before PR #33. Old Docker fallback, skip behavior, and local-only simulator claims are historical. PR #33 replaces them with required local simulator validation and a pinned simulator build in CI. Use the current state above for active work and validation results.

---

## What changed in session 2

### Environment and CI (was: unusable)

| Problem | Fix |
|---|---|
| `.venv` built for 3.12 but `.venv/bin/python` resolved to 3.14 → every package invisible | recreated on CPython 3.12.12 via `uv` |
| pytest aborted with **51 collection errors** from `simhospital/bazel-*` symlinks | `norecursedirs` in pyproject |
| `vcrpy<6` incompatible with urllib3 2.x → `test_e2e` errored | pin relaxed to `>=6.0` |
| CI installed deps the tests don't have (`vcr`, `requests_mock`, `typesafe_sdk`) | CI installs `.[dev]`; new `typesafe` extra; `requirements.txt` synced |
| ruff unpinned with no declared rule set → 201 findings, results drift with ruff version | `ruff==0.17.3` pinned, rule set declared explicitly |
| 9 TypeSafe tests made live API calls with no guard | `importorskip` + key check → suite passes offline |
| API key literal committed in a test file | moved to gitignored `.env`; `.env.example` committed; scan confirms no key in any git-visible file |

**The test suite had never been runnable as configured.** The "46 passed, 0 skipped" figure
quoted in session 1 was a literal string inside `test_plan_completeness_is_high`, not a
measurement. The first real run gave 76 passed + 1 error.

### Data sources (was: 1 of 3 working)

**Census — three independent defects, all fixed.**
1. `get_demographics()` requested only `NAME,B01001_*` but then read `B03002_*`, so every
   ethnicity count was always `0`. The mock returned those columns anyway, hiding it.
2. `RACE_ETHNICITY_MAP` misassigned **every** variable. Checked against the authoritative ACS
   labels: `B03002_002E` is the *not*-Hispanic total but was mapped to `H` (Hispanic), which
   would have reported a 93%-non-Hispanic ZCTA as 93% Hispanic. Rewritten to HL7 Table 0005 /
   CDC codes that partition the total exactly.
3. Adding B03002 took the request to 58 variables against a **50-variable API cap** (the old
   request was already at exactly 50) → HTTP 400. The 49 age-band variables were never read by
   any generator, so they were dropped rather than split into a second request.

Also: fails fast with an actionable message when the key is missing (previously three retries
against an HTML error page, then a silent UK fallback); clamps ACS negative sentinels; ACS year
parameterized, default 2023.

Verified live — and the two candidate ZCTAs disagree sharply:

| ZCTA | Profile |
|---|---|
| **60612** (the hospital) | 54.0% Black, 22.1% White, 16.1% Hispanic, 4.4% Asian |
| **60601** (what the fixtures used) | 54.1% White, 28.1% Asian, 6.5% Hispanic |

**CMS — endpoint was retired, not the dataset.** `xubh-q36u` is alive in the Provider Data
Catalog; only the Socrata `/resource/*.json` API was decommissioned. Now resolved through two
metastore hops to a versioned bulk CSV (the URL's version token changes on every refresh, so it
cannot be hardcoded), downloaded once and filtered locally because **the catalog's server-side
filtering does not work** (`filter[...]` silently ignored, `conditions[...]` fails schema
validation). Verified against all 5,419 rows.

`Emergency Services` is `"Yes"`/`"No"`, and the old comparison was `.lower() == "y"` — false for
`"yes"`, so ED was reported absent for all **4,495** hospitals that have one. Now normalizes
correctly (4,495 `Yes` → 4,495 `True`).

**Doctors — could never have been populated.** `fetch_doctors_by_location` was documented as
taking taxonomy *descriptions* but was passed HL7 *codes*, so NPPES was queried with
`taxonomy_description=MED`. Individual records carry `name_prefix`, not `middle_name`, so
`prefix` was always empty; and there was no `enumeration_type` filter, so an organizational NPI
could be written in as a person. Now searches a fixed clinical roster (a hospital's own NPPES
taxonomies are organizational — Stroger's sole entry is "General Acute Care Hospital", which
matches no individual practitioners) and derives each practitioner's HL7 code from their own
taxonomy. Verified live: **138 real practitioners** for ZIP 60612.

**Specialty codes.** `NUCC_TO_HL7_MAP` spans 688 descriptions and 584 distinct codes, but
`ALLOWED_SPECIALTIES` admits 14 — so 88% of the mapping produced codes the validators reject.
`get_hl7_code` now coerces into the allowed set. Verified: all 688 descriptions resolve to
exactly the 14 allowed codes. Caveat: 587 land on `MED`, expected since most of those 584 codes
are dental, DME and non-clinical services with no hospital-service counterpart.

**`hospital_service` was a NUCC code.** Generated `hl7.yml` carried `282N00000X` where HL7 Table
0069 expects `MED`. Now mapped through `get_hl7_code`.

### Generated output

`ethnicity.csv` **replaces** the UK defaults rather than appending to them — the two ID spaces
collided on `A`, `B` and `H`, and Simhospital's loader accepts duplicate CE IDs silently, so
the corruption never surfaced. Zero-count rows dropped, frequencies scaled to ~1000, header
cites the ACS release and ZCTA instead of the Wikipedia London article. New `addresses.py`
supplies USPS street suffixes (confirmed against the Go generator that `streets` holds
*suffixes*, not full names) replacing the UK list.

### Deterministic checks (the session goal)

Were fixture-scoped and structural: they reported confidence **1.0** on output that was London
ethnicity data with invented doctors. Now parameterized by `config_dir`, with seven new checks
targeting exactly those blind spots — duplicate CE IDs, non-positive frequencies, unconverted UK
ethnicity, unconverted UK street suffixes, placeholder doctors, duplicate doctor NPIs, and a
`hospital_service` outside Table 0069. 25 dedicated unit tests cover both directions.

Proof they earn their keep, same code run against both directories:

```
stale session-1 fixtures    13/16   confidence 0.812   (names UK streets, UK ethnicity,
                                                        placeholder doctors)
freshly generated output    17/17   confidence 1.000
```

Wired into `generate_all_configs(..., validate=True)` so it gates **generated output**, and into
the CLI with a new `--strict` flag (warn by default, since a degraded source still yields usable
configs; exit 1 under `--strict`).

### Simulator validation (was: never ran, could never fail)

Two defects made it inert. The script looked for the binary at `$PROJECT_ROOT/simulator` but
`go build` puts it at `simhospital/simulator`, so it fell through to Docker and — with Docker
absent — printed a warning and **exited 0**, which CI then also swallowed via
`continue-on-error`. And `--local_path` was the config dir's *parent*; that flag is the base for
Simhospital's own relative defaults (`configs/hardcoded_messages`), so the simulator aborted
before reading a single generated file.

Now real: parses all five generated files, loads 3 locations and 138 doctors, runs pathways,
shuts down on the timeout. Also `timeout --kill-after=10s`, because the simulator logs
"Shutting down gracefully" on SIGTERM and then hangs; and `generate_and_validate.sh` no longer
leaks its temp directory on failure (a bare call under `set -e` aborted before cleanup).

**Scope of this evidence:** it proves the configs are *accepted and loaded*. It does not verify
HL7 message content — the simulator writes to an HL7 sink, not stdout, so nothing asserts on
generated messages.

**Update — the Docker path is dead and never validated anything.** Verified after the push:
`docker manifest inspect eu.gcr.io/simhospital-images/simhospital:latest` is denied
(`eu.gcr.io` moved to Artifact Registry and rejects unauthenticated pulls), so the image the CI
job falls back to cannot be fetched. Worse, that branch passes **none** of the `--*_file` flags —
it mounts the config directory at `/configs/hl7_messages` and runs the image's default
`health/simulator` entrypoint, so Simhospital would not have read the generated files even with a
working image. An earlier note in this document guessed the mount shadowed `configs/hardcoded_messages`;
that was wrong, and the real defect is that the invocation never points at the configs.

At that historical point, CI no longer set `SIMULATOR_VALIDATION`, so a missing simulator produced
a warning and exit 0. `make validate-simulator` set the flag and failed. PR #33 later replaced this
skip behavior with a pinned simulator build and strict validation job. The three earlier outcomes
were measured:

```
no simulator, env unset   -> ::warning annotation, exit 0     (CI)
no simulator, env=true    -> exit 1                           (local make)
local binary present      -> loads 3 locations, exit 0        (verified)
```

At that historical point, real simulator validation happened **locally only**, against
`simhospital/simulator`. PR #33 later added simulator validation in CI.

---

## Test results

```
$ pytest -q                                  # offline / CI equivalent
141 passed, 7 skipped in 3.4s

$ pytest -q                                  # CENSUS_API_KEY + TYPESAFE_API_KEY set
148 passed

$ ruff check simhospital_autoconfig tests
All checks passed!

$ make validate-simulator
exit 0 in ~48s; "All 17 deterministic checks passed"
```

The 7 skipped are `TestTypeSafeConfigAudit`, which call `api.typesafe.ai` live — confirmed real
by running them against an invalid key: all 7 fail with `TypeSafeAuthenticationError: 401`.

Growth: 68 test functions at session start (never runnable) → 148 passing. The additions are
`test_integration_census.py` (2→7), `test_integration_cms.py` (4→10), `test_edge_cases.py`
(+2), `test_deterministic_checks.py` (new, 25), `test_integration_nppes.py` (new, 8) and
`test_cli.py` (new, 26 — `__main__` had no coverage at all before this).

---

## Remaining work

**Features (D10) — done.** All three input paths work: `--npi`, `--zip [--name] [--state]`, and
`--name --state`. `nppes.search_organizations()` drives the name search; `--zip` resolves through
the existing `cms.search_hospitals()`. Every path refuses to guess when the match is not unique —
it lists candidates with their identifiers and exits non-zero.

Two facts established by live testing shape how usable each path is:

- NPPES matches the **legal business name**, fuzzily. `--name "John H. Stroger Jr. Hospital"
  --state IL` returns nothing (the facility is registered as `COOK COUNTY`), while `--name "RUSH
  UNIVERSITY MEDICAL CENTER" --state IL` returns **73 exact matches**, because large systems
  register many NPIs under one legal name across campuses and departments. So `--name` alone is
  rarely decisive; `--npi` or `--zip --name` is the practical route.
- `--zip` composes with `--name`/`--state` because `search_hospitals` accepts all three, and CMS
  holds one row per facility. `--zip 60612 --name stroger` resolves cleanly to CCN 140124, and its
  output passes 17/17 deterministic checks under `--strict` and is accepted by the real simulator
  (3 locations, 138 doctors loaded).

**Known limitation (D13), narrowed but not closed.** The CMS↔NPPES join still fails for the
canonical hospital: NPPES names NPI `1730209545` **"COOK COUNTY"** while the catalog says **"JOHN
H STROGER JR HOSPITAL"**, and NPPES publishes no CCN for it — only a Medicaid identifier. When
`--zip` resolves a facility but cannot join it to exactly one NPPES record, it now synthesizes an
`NPPESResult` from the CMS row: `hl7.yml`'s `id_number` becomes the CCN and `hospital_service`
defaults to `MED` because there are no taxonomies to derive it from. That substitution is logged
as a warning, and the ambiguous-join case gets its own message — an earlier version emitted both
warnings at once, telling the user the record was absent when the real problem was that 73
matched. Closing D13 properly needs an alias/fuzzy join or another CCN source.

**Housekeeping.**
- The Census API key was rotated, as confirmed by the user. TypeSafe key rotation is not confirmed;
  see the current credential status above. Do not place key values in project files.
- `roan-stranger` branch and `.kilo/worktrees/roan-stranger` are stale and prunable (needs
  explicit approval — pruning deletes a branch).
- `dist/` holds a 0.1.0 wheel+sdist predating all of this. Gitignored, harmless.
- The Ruff target covers `scripts/run_simulator_e2e.py`. It does not cover the older helper scripts.
  Their current lint status is unknown.

---

## Historical session 2 commit list

| SHA | Summary |
|---|---|
| `860929b` | chore: ignore vendored simulator clone, agent tooling, scratch output |
| `91d74db` | build: packaging, CI, dev tooling (+ pytest collection, vcrpy pin) |
| `f9a5559` | feat: US hospital config generator package (as-is restore point) |
| `2288ae7` | test: generator, schema, edge-case, e2e suites |
| `8b74760` | feat: simulator validation and cassette recording scripts |
| `3b4d306` | test: hl7/locations validators + ethnicity sentinel enforcement |
| `be3ea7d` | docs: progress report, archived session plans, README |
| `0f0991b` | style: declare lint rule set; fix 84 duplicate mapping keys |
| `e7e4dc1` | fix(census): correct B03002 mapping and request the variables |
| `1020404` | fix(generators): US ethnicity and address data instead of UK defaults |
| `1659654` | fix(cms): Provider Data Catalog; stop reporting ED as absent |
| `7d49690` | fix(specialties,nppes): constrain HL7 codes; search doctors by taxonomy |
| `6d5a540` | feat(checks): gate generated output; regenerate fixtures from real data |
| `9128f27` | fix(scripts): make simulator validation actually run and actually fail |
| _(this)_ | test + docs for the deterministic checks |

The package was committed **as-is, bugs included**, at `f9a5559` to create a restore point
before any behaviour changed. Every fix after that is its own commit with the evidence in the
message.

---

## Reference: verified external facts

Recorded here because they were expensive to discover and are not obvious from the code.

**Census ACS** (`api.census.gov`)
- Requires a key. Keyless calls return HTTP 200 with an HTML "Missing Key" page, not an error.
- Max **50 variables** per `get`; exceeding it returns HTTP 400.
- B03002 structure: `002` = *not*-Hispanic total, `003`–`009` = non-Hispanic races,
  `012` = Hispanic total, `013`–`021` = Hispanic sub-breakdowns.
- ACS 2021 and 2023 both serve ZCTA data as of 2026-10.
- Unavailable estimates come back as large negative sentinels (e.g. `-666666666`).

**CMS Provider Data Catalog** (`data.cms.gov/provider-data`)
- Dataset `xubh-q36u` "Hospital General Information", 5,419 rows, 38 columns, 1.4 MB CSV.
- Metadata: `GET /api/1/metastore/schemas/dataset/items/xubh-q36u?show-reference-ids=true`
  → `distribution[0].identifier` → `GET /api/1/metastore/schemas/distribution/items/{id}`
  → `data.downloadURL`.
- **Akamai returns 403 for browser-like User-Agents**; `curl/8.5.0` and `python-requests` work.
- **Server-side filtering does not work.** `filter[field][value]=` is ignored; `conditions[...]`
  fails JSON-schema validation. Both return all 5,419 rows.
- Columns are human-readable (`Facility ID`, `Facility Name`, `City/Town`, `ZIP Code`,
  `Hospital Type`, `Emergency Services`). No NPI column exists.
- `Emergency Services` ∈ {`Yes`, `No`}; 4,495 / 924 across the catalog.
- Stroger: `Facility ID 140124`, 1901 W Harrison St, Chicago IL **60612**, Acute Care Hospitals,
  Government - Local, Emergency Services = Yes.

**NPPES** (`npiregistry.cms.hhs.gov/api/`)
- Individual (NPI-1) `basic` carries `name_prefix`, `credential`, `first_name`, `last_name`,
  `sex`. There is **no** `middle_name` on individuals.
- NPI `1730209545` → organization_name **"COOK COUNTY"**, MAILING 1110 S Oakley Blvd 60612-4218,
  LOCATION 1901 W Harrison St 60612-3714, one taxonomy `282N00000X` "General Acute Care
  Hospital", one identifier (`05`/MEDICAID). No CCN.

**Simhospital** (vendored at `simhospital/`, upstream `e69eef7`)
- `pkg/config/csv.go`: `reader.Comment = '#'`, so comment lines are skipped; rows whose
  non-frequency columns are all `nil` become a nil value (the `nil,nil` sentinel); duplicate CE
  IDs are **accepted silently** into the weighted distribution.
- `pkg/generator/address/address.go`: the `streets` config key holds *street suffixes*
  ("Road", "Street", "Place"), sampled directly; addresses render as `<number> <noun> <suffix>`.
- `ir.Ethnicity{ID, Text}` are free-form strings, so dashed CDC codes like `2106-3` are valid.
- `--local_path` is the base for the simulator's own relative defaults, not the config directory.

---

## Archive

Session-1 plans, copied out of `.kilo/` before it was gitignored:

- `docs/plans/01-adversarial-remediation.md` — 3 steps, all completed in session 1.
- `docs/plans/02-build-us-hospital-config-generator.md` — 14 steps; all now done except step 10's
  two CLI branches and step 12's optional pre-commit/tox. Step 6's `addresses.py` landed in
  session 2.
- `docs/plans/03-prove-generator-with-real-simulator.md` — 6 steps. Its exit criteria were only
  genuinely met in session 2: the suite did not pass offline, and simulator validation had never
  run.
- `docs/typesafe_plan.md` — four-layer Jev strategy. Layer 1 is now a real gate on generated
  output; Layer 3 remains test-only and requires network plus a key.
