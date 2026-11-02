# simhospital_autoconfig

Resources to automatically configure Google Simhospital to reflect the traits of a specific real-world hospital.

Google Simhospital (https://github.com/google/simhospital) can be configured to look like any hospital, real or fictional. These are the files that I'm interested in:

- [data.yml](https://github.com/google/simhospital/blob/master/configs/hl7_messages/data.yml): This file includes the data that creates random patients.
- [doctors.yml](https://github.com/google/simhospital/blob/master/configs/hl7_messages/doctors.yml): Same thing but for doctors.
- [ethnicity.csv](https://github.com/google/simhospital/blob/master/configs/hl7_messages/ethnicity.csv): Ethnic breakdown of the population serviced by the hospital.
- [hl7.yml](https://github.com/google/simhospital/blob/master/configs/hl7_messages/hl7.yml): Significant number of attributes relevant to all HL7 messages being generated.
- [locations.yml](https://github.com/google/simhospital/blob/master/configs/hl7_messages/locations.yml): Locations that the hospital includes.

The idea is to create a simple script for a user to provide some kind of identifying information (like an NPI) and then have the script pull public information and generate the configuration files to mirror the real-world traits of the facility.

No claim is being made about how realistic these messages will be, but the effort will be to do the most possible with public information.

## Usage

Install the package:

```bash
pip install -e .
```

Generate configuration files for a hospital using its NPI:

```bash
simhospital-autoconfig generate --npi 1730209545 --output-dir ./config
```

Supported input types:

- `--npi <NPI>` — Primary workflow and the most reliable. Fetches the hospital from NPPES by NPI.
- `--zip <ZIP> [--name <fragment>] [--state <XX>]` — Resolves one hospital through CMS Hospital General Information, then joins its exact CCN to the primary NPI in CMS Hospital Enrollments. It fetches the organization details from NPPES. A ZIP often holds several hospitals (60612 holds four), so narrow it with `--name`.
- `--name "<Hospital Name>" --state <XX>` — Searches NPPES by legal business name. Works, but see the caveats below.

```bash
# Several hospitals share this ZIP, so narrow it:
simhospital-autoconfig generate --zip 60612 --name stroger --output-dir ./config
```

### Ambiguity is never guessed at

Every path refuses to pick a facility when the match is not unique. Candidates are listed
with their identifiers and the command exits non-zero, so you can re-run with `--npi`:

```
ERROR - 4 CMS facilities are in ZIP 60612:
ERROR -   CCN 14003F  JESSE BROWN VA MEDICAL CENTER - VA CHICAGO HEALTHCARE SYSTEM  (Acute Care - Veterans Administration, ED: Yes)
ERROR -   CCN 140119  RUSH UNIVERSITY MEDICAL CENTER  (Acute Care Hospitals, ED: Yes)
ERROR -   CCN 140124  JOHN H STROGER JR HOSPITAL  (Acute Care Hospitals, ED: Yes)
ERROR -   CCN 140150  UNIVERSITY OF ILLINOIS HOSPITAL AND CLINICS  (Acute Care Hospitals, ED: Yes)
ERROR - Narrow it with --name, or re-run with --npi <NPI>; this tool will not guess.
```

### Why `--name` is the weakest of the three

NPPES matches on the **legal business name**, not the name a hospital is known by, and the
match is fuzzy:

- `--name "John H. Stroger Jr. Hospital" --state IL` finds **nothing** — that facility is
  registered as `COOK COUNTY`. The error message says so and suggests the legal entity.
- `--name "RUSH UNIVERSITY MEDICAL CENTER" --state IL` finds **73** exact matches; large
  health systems register many NPIs under one legal name, across campuses and departments.

Prefer `--npi`, or `--zip --name`. The ZIP path uses the primary NPI in the CMS enrollment row.
For example, CMS links Stroger CCN `140124` to primary NPI `1588612832`.

The ZIP path exits with an error if CMS does not return exactly one enrollment row with a
valid primary NPI, or if NPPES cannot return that NPI. It never writes a CCN into
`hl7.yml`'s `id_number`. Use `--npi` to select a specific NPI directly. CMS does not link
NPI `1730209545` to CCN `140124`; CMS lists NPI `1588612832` as that enrollment's primary NPI.

The generated config uses the NPPES record for the CMS primary NPI for the organization name,
identifier, address, and taxonomy. CMS provides the matched facility's type and emergency-services
details. The current generator uses the emergency-services value to report when a facility has no
emergency services. It does not write the hospital type to a config file. These sources can use
different names for the same enrolled facility. For example, NPPES names the primary NPI
`COOK COUNTY`, while CMS names CCN `140124` `JOHN H STROGER JR HOSPITAL`.

For `--zip`, Census demographics and practitioner searches use the CMS facility ZIP. Other input
paths use the NPPES location ZIP. The generated organization address remains the NPPES address.

Additional options:

- `--output-dir` — Directory to write configuration files (default: current directory).
- `--dry-run` — Print planned actions without writing files.
- `--verbose` — Enable verbose logging.
- `--strict` — Exit non-zero if any deterministic check fails on the generated configs. Without it, failures are logged as warnings, since a degraded data source still produces usable configs.

Generation always runs the deterministic checks over what it wrote and logs the report, for example:

```
INFO - Census ZCTA 60612: population 34699, 7 ethnicity categories
INFO - Fetched 138 practitioners
INFO - All 17 deterministic checks passed
```

## Placeholder Substitution

The generated files include placeholders that are automatically replaced:

- `${ORGANIZATION_NAME}` — The legal name of the hospital.
- `${ORGANIZATION_ID}` — The facility identifier (e.g., NPI).

If you need to substitute manually, use `sed`:

```bash
sed -i 's|${ORGANIZATION_NAME}|Stroger Hospital|g' hl7.yml locations.yml
sed -i 's|${ORGANIZATION_ID}|1730209545|g' hl7.yml locations.yml
```

> **Warning:** If placeholders are not substituted, generated HL7 messages will contain the literal strings `${ORGANIZATION_NAME}` and `${ORGANIZATION_ID}`, which will cause downstream validation failures.

## Simulator Validation

You can validate that generated configs are accepted by the real Google Simhospital simulator:

```bash
make validate-simulator
```

This command requires `CENSUS_API_KEY` in the process environment. If you store the
key in `.env`, load it into your shell before you run the command:

```bash
set -a; . ./.env; set +a
make validate-simulator
```

The command generates configs with `--strict` before it starts the local simulator.
CI uses the same check and reads the key from the repository secret named
`CENSUS_API_KEY`.

This command:
1. Generates configs for the canonical test hospital (NPI `1730209545` — Cook County/Stroger Hospital).
2. Starts the local Simhospital binary and confirms it loads the generated configs.
3. Cleans up temporary files.

Prerequisites:
- A Simhospital checkout at `simhospital/` and a built binary at `simhospital/simulator`. The checkout is required as `--local_path`, since the simulator resolves its own `configs/hardcoded_messages` and `configs/pathways` relative to it. Build the simulator with Bazel 5.4.1:

  ```bash
  cd simhospital
  echo 5.4.1 > .bazelversion
  bazel build //cmd/simulator:simulator
  simulator_target="$(bazel cquery --output=files //cmd/simulator:simulator | head -n 1)"
  cp "$(readlink -f "$simulator_target")" simulator
  cd ..
  ```

If the binary is missing, the script exits non-zero. Timeouts and simulator errors also
fail validation; a timeout does not prove that the configs were accepted. The CI job
checks out a pinned Simhospital revision, builds the binary, and validates generated
configs with it.

This validates **config acceptance**: the simulator parses the generated files and loads the
locations and doctors. The wrapper then stops it intentionally after startup, before waiting
for a pathway to finish. It does not assert on HL7 message content, which the simulator writes
to an HL7 sink rather than stdout. A startup timeout or early simulator exit is a failure.

By default, the wrapper uses a unique temporary output directory and removes it on exit.
If you pass an output directory as the second argument, that directory is retained for
inspection after validation.

### Manual end-to-end smoke run

The config-acceptance check above stops after Simhospital loads its configuration. To
exercise message generation as well, run the deterministic smoke pathway against the
checked-in config fixture:

```bash
make test-simulator-e2e
```

This runs the upstream `test_pathway_four_messages` pathway to completion and checks for
four HL7 messages in order: `ORU^R01`, `ADT^A01`, `ORU^R01`, and `ADT^A03`. It also checks
the required segments for each type and an `OBX` in both result messages. Timestamps and
generated patient details are allowed to vary. The run uses the local simulator binary and
the same Simhospital checkout required by `make validate-simulator`.

The end-to-end run is available through the local Make target and the manually triggered
`Simulator end-to-end` GitHub Actions workflow. It does not run as a PR check. On success,
local temporary output is removed. On failure, the simulator log and HL7 output are retained
in a temporary directory whose path is printed. GitHub Actions uploads those diagnostics only
on failure and retains them for seven days.

The fixture provenance and intentional refresh procedure are documented in
[`tests/fixtures/1730209545/README.md`](tests/fixtures/1730209545/README.md).

## Data Sources

- [NPPES](https://npiregistry.cms.hhs.gov/api-page) — National Plan and Provider Enumeration System. Provides hospital name, address, taxonomies, and identifiers, and is the source for practitioner records in `doctors.yml`.
- [Census ACS](https://www.census.gov/data/developers/guidance/api-user-guide.html) — American Community Survey 5-Year estimates (default release: 2023). Table `B03002` provides the race/ethnicity distribution used for `ethnicity.csv`, mapped to HL7 v2 Table 0005 / CDC codes. **Requires an API key** — see Limitations.
- [CMS Provider Data Catalog](https://data.cms.gov/provider-data/dataset/xubh-q36u) — Hospital General Information. Provides hospital type, emergency services status, and the facility address. Resolved through the catalog's metastore to a versioned bulk CSV, then filtered locally.
- [CMS Hospital Enrollments](https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities/hospital-enrollments) — Provides the primary NPI for each enrolled hospital CCN. CMS lists additional NPIs in a separate file ([Hospital Data Guidance](https://data.cms.gov/sites/default/files/2026-02/Hospital_Data_Guidance.pdf)). The ZIP workflow resolves the latest CSV through the [CMS data catalog](https://data.cms.gov/data.json) and uses the primary NPI only.

## Limitations

- **Census API key is required, not optional.** Without `CENSUS_API_KEY`, `api.census.gov` returns an HTTP 200 HTML "Missing Key" page rather than an error. The client now raises immediately with a remediation message. Get a free key at <https://api.census.gov/data/key_signup.html> and put it in `.env` (see `.env.example`).
- **CMS and NPPES can list different NPIs for one organization.** ZIP lookup uses the primary NPI in CMS Hospital Enrollments. CMS links CCN `140124` to primary NPI `1588612832`; it does not link NPI `1730209545` to that CCN. Use `--npi` to select a specific NPI. The ZIP path stops if CMS cannot provide one primary NPI or NPPES cannot return it.
- **Rate limits:** NPPES has undocumented rate limits (~2-3 requests/second). The client implements exponential backoff on HTTP 429 responses and sleeps between practitioner searches.
- **CMS server-side filtering does not work.** The catalog ignores `filter[...]` parameters and rejects `conditions[...]`, so the full 1.4 MB CSV is downloaded once per run and filtered in memory.
- **ZCTA vs ZIP mismatch:** ZIP codes and ZCTAs are not always identical. ZIP lookup uses the first five digits of the CMS facility ZIP for Census data and practitioner searches. Other input paths use the first five digits of the NPPES **LOCATION** address. NPPES mailing addresses can be administrative offices in a different ZCTA.
- **Missing data fallbacks:** If a data source fails, the generator warns and continues with default values. For `ethnicity.csv` that default is the upstream UK distribution, which does not describe a US hospital — the warning says so explicitly, and the `ethnicity_not_uk_default` deterministic check fails on it.
- **Doctor search:** practitioners are found by searching a fixed clinical roster near the hospital ZIP, because a hospital's own NPPES taxonomies are organizational and match almost no individuals. NPPES taxonomy search is fuzzy, so results may include providers with similar but not exact specialties.
- **Specialty granularity:** NUCC taxonomies are mapped onto the 14 HL7 Table 0069 codes Simhospital's own `doctors.yml` uses. Most NUCC descriptions (dental, durable medical equipment, non-clinical services) have no counterpart there and fall back to `MED`.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup instructions.

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
