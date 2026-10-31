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

- `--npi <NPI>` — Primary workflow. Fetches hospital data from NPPES by NPI number.
- `--name "<Hospital Name>" --state <XX>` — Fallback search via NPPES (name/state search not yet implemented).
- `--zip <ZIP>` — Resolve ZIP to ZCTA, then fetch hospital via CMS (not yet implemented).

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

This command:
1. Generates configs for the canonical test hospital (NPI `1730209545` — Cook County/Stroger Hospital).
2. Runs the Simhospital Docker image against the generated configs.
3. Cleans up temporary files.

Prerequisites:
- Docker installed and running locally, **or** a built simulator binary at `simhospital/simulator` (`cd simhospital && go build -o simulator ./cmd/simulator`). The vendored `simhospital/` checkout is also required as `--local_path`, since the simulator resolves its own `configs/hardcoded_messages` and `configs/pathways` relative to it.
- Network access to pull `eu.gcr.io/simhospital-images/simhospital:latest` when using Docker.

If neither Docker nor a local binary is available, the script exits non-zero when
`SIMULATOR_VALIDATION=true` (which CI and the Makefile set) and exits 0 with a warning
otherwise. It used to exit 0 unconditionally, which let CI report success without ever
starting the simulator.

Note that this validates **config acceptance**: the simulator parses the generated files,
loads the locations and doctors, and runs pathways. It does not assert on HL7 message content,
which the simulator writes to an HL7 sink rather than stdout.

## Data Sources

- [NPPES](https://npiregistry.cms.hhs.gov/api-page) — National Plan and Provider Enumeration System. Provides hospital name, address, taxonomies, and identifiers, and is the source for practitioner records in `doctors.yml`.
- [Census ACS](https://www.census.gov/data/developers/guidance/api-user-guide.html) — American Community Survey 5-Year estimates (default release: 2023). Table `B03002` provides the race/ethnicity distribution used for `ethnicity.csv`, mapped to HL7 v2 Table 0005 / CDC codes. **Requires an API key** — see Limitations.
- [CMS Provider Data Catalog](https://data.cms.gov/provider-data/dataset/xubh-q36u) — Hospital General Information. Provides hospital type, emergency services status, and the facility address. Resolved through the catalog's metastore to a versioned bulk CSV, then filtered locally.

## Limitations

- **Census API key is required, not optional.** Without `CENSUS_API_KEY`, `api.census.gov` returns an HTTP 200 HTML "Missing Key" page rather than an error. The client now raises immediately with a remediation message. Get a free key at <https://api.census.gov/data/key_signup.html> and put it in `.env` (see `.env.example`).
- **CMS cannot always be joined to NPPES.** The catalog has no NPI column, so the join is CCN first and facility-name-plus-state second. NPPES often publishes the legal entity rather than the hospital — NPI `1730209545` is named "COOK COUNTY" while CMS calls it "JOHN H STROGER JR HOSPITAL", and NPPES publishes no CCN for it. When there is no match the CLI warns and `locations.yml` uses built-in defaults rather than guessing.
- **Rate limits:** NPPES has undocumented rate limits (~2-3 requests/second). The client implements exponential backoff on HTTP 429 responses and sleeps between practitioner searches.
- **CMS server-side filtering does not work.** The catalog ignores `filter[...]` parameters and rejects `conditions[...]`, so the full 1.4 MB CSV is downloaded once per run and filtered in memory.
- **ZCTA vs ZIP mismatch:** ZIP codes and ZCTAs are not always identical. The generator uses the first five digits of the NPPES **LOCATION** address, which is the facility; the MAILING address is frequently an administrative office in a different ZCTA with a different population.
- **Missing data fallbacks:** If a data source fails, the generator warns and continues with default values. For `ethnicity.csv` that default is the upstream UK distribution, which does not describe a US hospital — the warning says so explicitly, and the `ethnicity_not_uk_default` deterministic check fails on it.
- **Doctor search:** practitioners are found by searching a fixed clinical roster near the hospital ZIP, because a hospital's own NPPES taxonomies are organizational and match almost no individuals. NPPES taxonomy search is fuzzy, so results may include providers with similar but not exact specialties.
- **Specialty granularity:** NUCC taxonomies are mapped onto the 14 HL7 Table 0069 codes Simhospital's own `doctors.yml` uses. Most NUCC descriptions (dental, durable medical equipment, non-clinical services) have no counterpart there and fall back to `MED`.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup instructions.

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
