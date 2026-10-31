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
- Docker installed and running locally, or a built `simhospital` binary in the project root.
- Network access to pull `eu.gcr.io/simhospital-images/simhospital:latest`.

If Docker is unavailable, the validation script prints a warning and exits successfully so CI can continue.

## Data Sources

- [NPPES](https://npiregistry.cms.hhs.gov/api-page) — National Plan and Provider Enumeration System. Provides hospital name, address, taxonomies, and identifiers.
- [Census ACS](https://www.census.gov/data/developers/guidance/api-user-guide.html) — American Community Survey 5-Year estimates. Provides race/ethnicity and sex/age demographics.
- [CMS Hospital Compare](https://data.cms.gov/) — Hospital General Information dataset. Provides hospital type, emergency services status, and department data.

## Limitations

- **Rate limits:** NPPES API has undocumented rate limits (~2-3 requests/second). The client implements exponential backoff on HTTP 429 responses.
- **ZCTA vs ZIP mismatch:** ZIP codes and ZCTAs are not always identical. The generator uses the first 5 digits of the postal code as the ZCTA.
- **Missing data fallbacks:** If a data source fails, the generator warns and continues with default values.
- **Doctor search noise:** NPPES taxonomy search is fuzzy/partial-match, which may include providers with similar but not exact specialties.
- **Census API key:** A free Census API key is recommended for higher quotas. Set via the `CENSUS_API_KEY` environment variable.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup instructions.

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
