# Canonical Simhospital fixture

These files are a checked-in snapshot of the configs generated for NPI
`1730209545` (Cook County/Stroger Hospital). They provide stable inputs for the
manual Simhospital end-to-end smoke run and do not require API access at runtime.

The snapshot was regenerated on 2026-10-31 by
[`scripts/record_cassettes.py`](../../../scripts/record_cassettes.py). The NPPES
facility and practitioner responses and Census ACS 2023 demographics for ZCTA
60612 were recorded in the corresponding VCR cassette. CMS Provider Data Catalog
bulk data is intentionally not included in the cassette. The script resolves the
facility through CMS live; it can cache the resolved facility record in
`cms_hospital.json` for subsequent refreshes. That cache is not part of this fixture.

To refresh the snapshot deliberately:

1. Set `CENSUS_API_KEY` in `.env`.
2. Review whether the recorded NPPES and Census responses should also be refreshed.
   To record fresh responses, remove the relevant cassette first.
3. Ensure the CMS Provider Data Catalog is reachable; its source data is not in the cassette.
4. Run `python scripts/record_cassettes.py`.
5. Review the config diff and run `python -m pytest -q` before committing changes.

The simulator end-to-end check uses the upstream `test_pathway_four_messages`
pathway. It checks the four ordered HL7 message types and required segments,
including an `OBX` in both `ORU^R01` messages. Dynamic patient details and
timestamps are not compared byte-for-byte.
