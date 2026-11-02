# Project Progress — simhospital_autoconfig

_Last updated: 2026-11-02. PR #33 is merged in `b1fc054310a8a5637f442a90fc61e95bf54d57a4`. CMS primary-NPI ZIP work is in a new follow-up branch._

## Current state

- PR #33 merged the 1.0 generator and validation baseline into `main`.
- The PR checks passed on `5ba93c7`: test, simulator-validation, and Kilo Code Review ([Actions run 41372270369](https://github.com/benbarnard-OMI/simhospital_autoconfig/actions/runs/41372270369)).
- Post-merge CI passed on `b1fc054`: test and simulator-validation ([Actions run 41378658377](https://github.com/benbarnard-OMI/simhospital_autoconfig/actions/runs/41378658377)).
- The manual simulator E2E workflow passed on `main` at `b1fc054`. It built the pinned simulator and validated the four HL7 messages and required segments ([Actions run 41379786588](https://github.com/benbarnard-OMI/simhospital_autoconfig/actions/runs/41379786588)).
- The initial clean-worktree baseline check passed: pytest reported 174 passed and 7 skipped live TypeSafe checks; Ruff and shell syntax checks passed; `make validate-simulator` passed all 17 deterministic checks and Simhospital loaded the generated configs.
- Follow-up checks on 2026-11-02 passed: pytest reported 174 passed and 7 skipped; Ruff and shell syntax checks passed. The local `make validate-simulator` attempt stopped during NPPES lookup because this environment could not resolve `npiregistry.cms.hhs.gov`. This clean worktree also has no Simhospital checkout or binary. The PR simulator-validation job checks the updated branch in CI.
- The original checkout has no unique changes that need to be carried forward. It was left unchanged.
- D13 remains deferred. CMS links CCN `140124` to primary NPI `1588612832`, and does not link NPI `1730209545` to that enrollment. The feature branch below uses the CMS primary NPI for ZIP lookup. The current `main` branch still uses its earlier CMS-only fallback when it cannot verify one NPPES match. That fallback can write the CCN as `hl7.yml`'s `id_number` and default `hospital_service` to `MED`.
- D13 research now has a current CMS baseline. The September 29, 2026 [Hospital Enrollments snapshot CSV](https://data.cms.gov/sites/default/files/2026-10/961708ac-2136-43cb-9587-ac64af23b6ab/Hospital_Enrollments_2026.09.29.csv) lists CCN `140124` and enrollment `O20101228000196` with NPI `1588612832`, `COOK COUNTY`, DBA `JOHN H. STROGER, JR HOSPITAL OF COOK COUNTY`, and `MULTIPLE NPI FLAG=Y`. The [interactive CMS table](https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities/hospital-enrollments/data) labels this release October 2026. The matching September 29, 2026 Hospital Additional NPIs file lists 26 more NPIs for this enrollment: `1023137528`, `1043238298`, `1053942045`, `1093283533`, `1295366466`, `1336269133`, `1366073256`, `1366073355`, `1386110674`, `1396865077`, `1427689413`, `1457385775`, `1457982340`, `1457982449`, `1568093557`, `1609407691`, `1649390022`, `1649551938`, `1740811736`, `1750912648`, `1760502439`, `1790316784`, `1891329488`, `1922127844`, `1922639913`, and `1942508460` ([additional NPIs CSV](https://data.cms.gov/sites/default/files/2026-10/Hospital_Additional_NPIs_2026.09.29.csv), [CMS file guidance](https://data.cms.gov/sites/default/files/2026-07/Hospital_Data_Guidance.pdf)). NPI `1730209545` is not in the main row or this additional-NPI list. Current NPPES API queries mark both `1588612832` and `1730209545` as active Type 2 NPIs. Both list `COOK COUNTY`, address `1901 W HARRISON ST, CHICAGO, IL 60612-3714`, and taxonomy `282N00000X`; their DBA names differ ([NPI 1588612832](https://npiregistry.cms.hhs.gov/api/?number=1588612832&version=2.1), [NPI 1730209545](https://npiregistry.cms.hhs.gov/api/?number=1730209545&version=2.1)). This confirms that NPI `1730209545` remains active in NPPES. It does not link that NPI to CMS enrollment `O20101228000196`, and it does not make NPI `1588612832` a replacement for every Cook County NPI. D13 remains deferred. No matching behavior has changed.

## Active follow-up: CMS primary NPI for ZIP lookup

- The prior PR #35 was closed without merge. Its branch remains available. A new branch, `codex/cms-primary-npi-followup`, now contains the same focused feature on top of current `main` (`7828b43`, PR #34 merge).
- ZIP lookup resolves one CMS Hospital General Information facility, joins its exact CCN to the primary NPI in the latest CMS Hospital Enrollments release, then fetches that NPI from NPPES.
- For Stroger, the expected join is CCN `140124` to NPI `1588612832`. The ZIP path fails if the enrollment row is missing, duplicated, or has no valid NPI. It also fails if NPPES cannot return that NPI. It does not write a CCN as an NPI.
- Use `--npi 1730209545` to select that NPI directly. The ZIP path does not use HRSA 340B data. CMS and NPPES can use different names for the same facility; the README explains the source fields.
- On the rebased branch, pytest passed: 179 passed and 7 skipped. Ruff and shell syntax checks passed. The 7 skips are live TypeSafe checks.
- GitHub checks passed on commit `d7b5dea`: pytest and Ruff, simulator build and generated-config validation, and Kilo review ([PR checks](https://github.com/benbarnard-OMI/simhospital_autoconfig/actions/runs/41448325032), [review](https://github.com/benbarnard-OMI/simhospital_autoconfig/runs/125286924460)).
- The manual simulator HL7 workflow passed on `d7b5dea`. It built the pinned simulator and completed the four-message workflow ([run 41448507169](https://github.com/benbarnard-OMI/simhospital_autoconfig/actions/runs/41448507169)).
- Local `make validate-simulator` stopped during NPPES lookup because this environment could not resolve `npiregistry.cms.hhs.gov`. No local Simhospital binary is available. CI passed the same simulator validation with network access.
- Do not add catalog or CSV-header fallback logic unless current CMS data shows that the existing lookup fails. Keep the fresh PR unmerged. Do not change D13 matching behavior in this work.

## Remaining D13 actions

1. Decide which identifiers the generator needs. The CMS enrollment files link the CCN to 27 NPIs, while NPPES also lists active NPI `1730209545` at the same organization location. Test any proposed choice against all 27 CMS NPIs, the `1730209545` NPPES record, and the current CCN. Do not treat NPI `1588612832` as a replacement for `1730209545` without a clear rule and test evidence.
2. Compare two D13 options before implementation:
   - **CMS enrollment crosswalk:** Join by exact CCN and enrollment ID, then validate each listed NPI against NPPES. This avoids name-only matches. The evidence shows one CMS enrollment with 27 associated NPIs, so choosing one NPI for the hospital config has a high false-match risk until the project defines which NPI the config needs. The crosswalk itself needs monthly refreshes and checks for inactive or conflicting records. Test CCN `140124`, all 27 associated NPIs, one-to-many CCN/NPI cases, missing rows, inactive NPIs, and conflicting NPPES addresses.
   - **Maintained alias map:** Store reviewed CCN-to-NPI links for known hospitals. An exact CCN key has low false-match risk when a person verifies each mapping and the map records the intended NPI use. A wrong or stale entry can persist until review. The initial code cost is low; staff must review and update entries when identifiers change. Test all 27 CMS NPIs, the active `1730209545` record, duplicate names at different CCNs, multiple NPIs, and a stale mapping.
3. Do not use fuzzy name matching to choose a facility. Its false-match risk is unmeasured. Keep D13 in a separate follow-up, and get approval before adding matching behavior.

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
- Rotate the TypeSafe and Census keys when convenient. Both live only in the gitignored `.env`
  now, but the TypeSafe key was pasted into the session transcript.
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
