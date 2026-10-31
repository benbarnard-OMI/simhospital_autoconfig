# Project Progress — simhospital_autoconfig

_Last updated: 2026-10-31, end of session 2. Supersedes the session-1 snapshot._

## TL;DR

Session 1 (2026-09-18) built a ~3,700 LOC generator package and left **all of it
uncommitted**. Session 2 (2026-10-31) committed it on branch `chore/stabilize`, fixed the
environment and CI so the suite actually runs, and established a measured baseline:
**77 passed** (with API keys present) / **70 passed, 7 skipped** (offline).

Session 2 also found that the project's central claim does not yet hold: **only one of the
three advertised data sources has ever worked.** Census and CMS both fail silently, so every
"generated" fixture is really NPPES data wrapped in UK defaults. Details in
[Data source status](#data-source-status) — this is the main outstanding work.

Nothing has been pushed. No PR has been opened.

---

## Current state

```
Branch    chore/stabilize  (7 commits ahead of main; NOT pushed)
Base      main == origin/main @ 8a82936
Tests     77 passed (keys present) · 70 passed + 7 skipped (offline) · ~3s
Python    .venv recreated on CPython 3.12.12 via uv
Working tree  clean except README.md (modified) and docs/ (this file)
```

Commits on `chore/stabilize`:

| SHA | Chunk |
|---|---|
| `860929b` | chore: ignore vendored simulator clone, agent tooling, scratch output |
| `91d74db` | build: packaging, CI, dev tooling (+ pytest collection and vcrpy fixes) |
| `f9a5559` | feat: US hospital config generator package |
| `2288ae7` | test: generator, schema, edge-case, e2e suites |
| `8b74760` | feat: simulator validation and cassette recording scripts |
| `3b4d306` | test: hl7/locations validators + ethnicity sentinel enforcement |
| _(pending)_ | docs: progress report, archived session plans, README |

The package was committed **as-is, bugs included**, to create a restore point before any
behaviour changes. Data-correctness fixes belong in follow-up commits.

---

## What exists

### Package — `simhospital_autoconfig/` (2,430 LOC)

| Module | LOC | Role | Status |
|---|---|---|---|
| `specialties.py` | 808 | NUCC taxonomy → HL7 Table 0069 | works |
| `generators.py` | 716 | five per-file generators + `generate_all_configs()` | emits UK defaults, see defects |
| `nppes.py` | 259 | NPI org lookup, practitioner search, 429 backoff | **works** |
| `__main__.py` | 184 | `generate` CLI | only `--npi` implemented |
| `deterministic_checks.py` | 181 | 10 local validation rules | fixture-scoped, not a generator gate |
| `census.py` | 162 | ACS 5-year demographics by ZCTA | **broken** (3 defects) |
| `cms.py` | 117 | CMS Hospital General Information | **broken** (dead endpoint) |

### Tests — 77 test functions across 12 files

Root level (318 LOC) validates the **checked-in upstream** config files:
`test_locations_yml` 7, `test_data_yml` 4, `test_hl7_yml` 3, `test_doctors` 2,
`test_ethnicity_csv` 2, `test_yaml_files` 2 (parametrized ×5).

`tests/` (985 LOC) exercises the **generator**: `test_edge_cases` 26,
`test_typesafe_validation` 9, `test_schema_validation` 5, `test_integration_cms` 4,
`test_e2e` 2, `test_integration_census` 2.

Offline data: `tests/fixtures/1730209545/` (five generated configs) and
`tests/cassettes/test_simulator_validation[1730209545].yaml` (61 KB, replayed with
`record_mode="none"`).

### Tooling

`scripts/{validate_with_simulator.sh, generate_and_validate.sh, record_cassettes.py}`,
`Makefile` (`test`, `lint`, `validate-simulator`), hardened GitHub Actions workflow,
`pyproject.toml` with `dev` and `typesafe` extras, `MANIFEST.in`, `CONTRIBUTING.md`.

Vendored reference: `simhospital/` — google/simhospital @ `e69eef7` with a built 89 MB
`simulator` binary. Now gitignored.

---

## Verified test results (2026-10-31)

```
$ pytest -q                                   # CENSUS/TYPESAFE keys present via .env
77 passed in 3.05s

$ TYPESAFE_API_KEY= pytest -q                 # offline / CI equivalent
70 passed, 7 skipped in 1.41s
```

The session-1 claim of "46 passed, 0 skipped" — which was a literal string inside
`test_plan_completeness_is_high`, not a measured result — is superseded by the above.

The 7 skipped tests are `TestTypeSafeConfigAudit`, which make **live calls to
`api.typesafe.ai`**. This was confirmed by running them against an invalid key: all 7 fail
with `TypeSafeAuthenticationError: 401`. They are now behind `pytest.importorskip` plus a
key check, restoring plan 3's "suite passes offline" criterion.

`run_deterministic_checks()` also verified directly: 10/10 PASS, confidence 1.0 — but only
against the checked-in fixtures, which is itself the problem (see defect D8).

---

## Data source status

Decoded the recorded cassette interaction-by-interaction. Of three sources, one works:

| Source | Recorded result | Effect |
|---|---|---|
| **NPPES** | `200 OK`, real Stroger data (1110 S Oakley Blvd) | ✓ working |
| **CMS** | **`410 Gone`** | `hospital_data = None` → locations.yml uses hardcoded defaults |
| **Census** | `302` → "Missing Key" HTML, ×4 | `demographics = None` → ethnicity.csv and streets stay UK defaults |

Both failures were swallowed by `try/except` in `__main__.py` and `record_cassettes.py`, so
generation "succeeded" while producing London-derived data for a Chicago hospital.

### CMS — diagnosed and solved

`xubh-q36u` was never retired; the **Socrata `/resource/*.json` API** was decommissioned.
The dataset is alive in the Provider Data Catalog. Verified live on 2026-10-31:

```
Catalog metadata   GET  https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/xubh-q36u
Rows (unfiltered)  GET  https://data.cms.gov/provider-data/api/1/datastore/query/xubh-q36u/0?limit=1
Bulk CSV (1.4 MB)  resolved via  /metastore/schemas/distribution/items/<distribution-id>
                   → data.downloadURL
```

Gotchas found by probing:
- **Akamai returns 403 for browser-like User-Agents.** `curl/8.5.0` works; `Mozilla/5.0`
  does not. Any client must not send a browser UA.
- **Server-side filtering does not work.** `filter[field][value]=` is silently ignored and
  `conditions[...]` fails JSON-schema validation — both return the full unfiltered 5,419
  rows. Plan on downloading the bulk CSV and filtering locally.
- The bulk CSV `downloadURL` embeds a version token (`..._1785189955`) that changes on each
  data refresh, so it must be **resolved via the metastore at runtime**, never hardcoded.
- CSV headers are human-readable (`Facility ID`, `Facility Name`, `City/Town`, `ZIP Code`,
  `Hospital Type`, `Emergency Services`), not the old Socrata snake_case names.
- `Emergency Services` is **`"Yes"` / `"No"`**, not `"Y"` / `"N"`.

Real row for the canonical hospital: **`Facility ID 140124`, JOHN H STROGER JR HOSPITAL,
1901 W HARRISON ST, CHICAGO, IL, ZIP 60612**, Cook County, Acute Care Hospitals.

### Census — key obtained, three code defects remain

A working key is now in the gitignored `.env`. Verified live: ACS 2021 **and** 2023 both
return data for ZCTA 60601.

For ZCTA 60601 (ACS 2023): total 16,292; `B03002_002E` 15,227; `B03002_008E` 56;
`B03002_009E` 805; `B03002_011E` 417.

Checked against the authoritative ACS group labels
(`https://api.census.gov/data/2021/acs/acs5/groups/B03002.json`), `B03002_002E` is
**"Not Hispanic or Latino"**, so 15,227/16,292 ≈ 93% non-Hispanic is correct for the Loop.
`RACE_ETHNICITY_MAP` labels that variable `"H"` (Hispanic) — the mapping would report 93%
Hispanic. See defect D2.

---

## Outstanding defects

Ordered by how much they undermine the project's premise.

**D1 — `census.py` never requests the variables it reads.** `get_demographics()` builds
`get=NAME,B01001_*` only, then reads `B03002_*` from the response, so every ethnicity count
is always `0`.

**D2 — `RACE_ETHNICITY_MAP` is wrong on every entry.** Verified against ACS labels:
`002`=NH-total (mapped to `H`), `003`=NH-White (mapped to `HM`), `004`=NH-Black (mapped to
`HP`), `005`=NH-AIAN (mapped to `HL`), `006`=NH-Asian (mapped to `HO`), `008`=NH-SomeOther
(mapped to `W`), `009`=NH-TwoOrMore (mapped to `B`), `011`=NH-TwoRacesExcl (mapped to `A`),
`012`=Hispanic-total (mapped to `NH`), `013`=Hispanic-White (mapped to `SR`),
`014`=Hispanic-Black (mapped to `TM`). `007` (NH-Native Hawaiian) is absent entirely.
Fixing D1 without D2 would start producing confidently inverted demographics.

**D3 — `cms.py` points at a dead endpoint.** `data.cms.gov/resource/xubh-q36u.json` returns
410. Needs the PDC endpoint, the field renames above, and `emergency_services == "Yes"`
(currently `.lower() == "y"`, which is always False — so ED is always treated as absent).

**D4 — Duplicate CE codes in generated `ethnicity.csv`.** `generate_ethnicity_csv()` appends
Census rows to the UK defaults, and the code spaces collide: UK `A` = "White - British" vs
Census `A` = Asian; `B`, `H` likewise. Simhospital's loader accepts duplicates without error
(`pkg/config/csv.go` builds a weighted distribution, `ir.Ethnicity{ID,Text}` are free-form
strings), so this silently corrupts patient ethnicity rather than failing.

**D5 — Wrong ZCTA.** The CLI derives the ZCTA from the NPPES postal code, which for Stroger
is the **administrative** address 1110 S Oakley Blvd → `60601`. The hospital itself is at
1901 W Harrison St → **`60612`**. Demographics would be pulled for the wrong neighbourhood
even after D1–D3 are fixed. Prefer the CMS facility ZIP when available.

**D6 — `data.yml` still emits London data.** `streets` is the upstream UK list
(Road/Street/Lane/Avenue/Place/Square) and the header comment still cites
`en.wikipedia.org/wiki/Ethnic_groups_in_London`. `addresses.py` (plan 2 step 6) was never
created.

**D7 — Fixture `doctors.yml` is fabricated.** It contains two invented records
(`John Smith`, `Jane Doe`, ids `1730209545-1/-2`) that no code path produces:
`record_cassettes.py` calls `generate_all_configs()` **without** `doctors=`, so it never
writes that file. Three tests validate this fake data as if it were real.

**D8 — Deterministic checks are fixture-scoped.** `FIXTURE_DIR` is hardcoded to
`tests/fixtures/1730209545`, so the "confidence 1.0" result audits checked-in files, not
generated output. None of D1–D7 would be caught by the current 10 checks — they all pass on
data that is London-derived and partly fabricated.

**D9 — Simulator validation can silently pass.** `validate_with_simulator.sh` looks for
`$PROJECT_ROOT/simulator`, but the binary is at `simhospital/simulator`, so it falls through
to Docker and `exit 0` when Docker is absent. Combined with `continue-on-error: true` in CI,
the job proves nothing.

**D10 — CLI gaps.** `--name/--state` and `--zip` log an error and `return 1`. `--zip` also
depends on D3.

---

## Resolved this session

| Was | Now |
|---|---|
| ~3,700 LOC uncommitted, one `git clean -fdx` from loss | 7 commits on `chore/stabilize` |
| API key literal in `tests/test_typesafe_validation.py` | moved to gitignored `.env`; `.env.example` committed; scan confirms no key in any git-visible file |
| `.venv` unusable (3.12 site-packages, 3.14 interpreter) | recreated on CPython 3.12.12 via `uv` |
| pytest aborted with 51 collection errors from `simhospital/bazel-*` | `norecursedirs` added |
| `test_e2e` errored: vcrpy 5.x vs urllib3 2.x | pin relaxed to `vcrpy>=6.0` (9.2.0 installed) |
| CI installed deps the tests don't have | CI installs `.[dev]`; `requirements.txt` synced; `typesafe` extra added |
| TypeSafe tests required network with no guard | `importorskip` + key check → 70 passed, 7 skipped offline |
| `simhospital/`, `.kilo/` untracked and not ignored | both gitignored; session plans archived to `docs/plans/` |
| CMS replacement unknown | endpoint, field names, and gotchas verified live |

---

## Next steps

**Data correctness (the real work):**
1. `census.py` — request the `B03002_*` variables (D1) **and** rewrite the mapping against
   the verified ACS labels (D2); parameterize the ACS year (2021 and 2023 both live, default
   2023); raise a clear error when the key is missing instead of retrying an HTML error page.
2. `cms.py` — PDC endpoint, metastore-resolved bulk CSV, local filtering, field renames,
   `emergency_services == "Yes"` (D3).
3. `generate_ethnicity_csv()` — replace rather than append to the UK defaults; use HL7
   Table 0005 / CDC race codes (`2106-3`, `2054-5`, `2028-9`, `1002-5`, `2076-8`, `2135-2`,
   `2186-5`) so they cannot collide with `A`–`Z`; drop zero rows; normalize to 1000; cite ACS
   in the header (D4).
4. `addresses.py` — extract ~20 US street names + city patterns; use in `generate_data_yml` (D6).
5. Prefer the CMS facility ZIP over the NPPES administrative ZIP for the ZCTA (D5).
6. `record_cassettes.py` — pass `doctors=` from `fetch_doctors_by_location()` so fixtures are
   real; re-record the cassette and regenerate `tests/fixtures/` (D7). **Grep the new cassette
   for the Census key before committing.**

**Then:**
7. Deterministic checks (D8) — parameterize `run_deterministic_checks(config_dir=None)`; add
   checks that would have caught the above: duplicate CE IDs, non-positive frequencies,
   London-default ethnicity/streets despite available Census data, placeholder doctors.
   Wire into `generate_all_configs(..., validate=True)` so it gates generated output; CLI
   reports results and gains `--strict`.
8. Simulator validation (D9) — point the script at `simhospital/simulator`, fail loudly when
   `SIMULATOR_VALIDATION=true` and neither Docker nor the binary is present, drop
   `continue-on-error`, and actually run `make validate-simulator`.
9. Features (D10) — `search_organizations_by_name()` in `nppes.py` (error listing candidates
   on multiple matches, never silently pick), `get_hospital_by_zip()` in `cms.py`, implement
   both CLI branches.

**Housekeeping:** update the README's Data Sources section to name the PDC endpoint and note
that Census requires a key; the stale `roan-stranger` branch and
`.kilo/worktrees/roan-stranger` worktree are prunable with explicit approval; `dist/` holds a
stale 0.1.0 wheel predating all of this.

---

## Archive

Session-1 plans that drove the original build, copied out of `.kilo/plans/` before it was
gitignored:

- `docs/plans/01-adversarial-remediation.md` — 3 steps, all completed in session 1.
- `docs/plans/02-build-us-hospital-config-generator.md` — 14 steps; 1–5, 7–9, 11, 13, 14
  done. Gaps: step 6 (`addresses.py`), step 10 (two CLI branches), step 12 (pre-commit/tox).
- `docs/plans/03-prove-generator-with-real-simulator.md` — 6 steps, all nominally done, but
  its exit criterion "all tests pass offline" was not met until this session, and its
  "simulator validated" claim rests on D9.
- `docs/typesafe_plan.md` — four-layer Jev strategy; deliverables exist, Layer 3 runs only
  inside tests (D8).
