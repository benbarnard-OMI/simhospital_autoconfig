"""
Generators for Simhospital configuration files.

These functions take hospital data and generate the appropriate config files.
"""
from __future__ import annotations

import csv
import io
import logging
import os
from typing import Any

import yaml

from .addresses import US_CITY_FALLBACK, US_STREET_SUFFIXES
from .census import ETHNICITY_LABELS
from .deterministic_checks import format_check_report, run_deterministic_checks
from .nppes import NPPESAddress, NPPESResult
from .specialties import DEFAULT_SPECIALTY, get_hl7_code

logger = logging.getLogger(__name__)

# Weight of the "nil,nil" absent-ethnicity sentinel relative to ~1000 total. Kept at
# the upstream file's value rather than inventing an unreported-rate figure; tune here
# if a deployment wants more patients with no ethnicity recorded.
NIL_ETHNICITY_FREQUENCY = 2

# Target total for scaled Census frequencies, giving 0.1% resolution.
ETHNICITY_FREQUENCY_TOTAL = 1000


DEFAULT_HL7_YML = """\
# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#
# Allergies.
#
allergy:
  # Reference:
  # https://hl7-definition.caristix.com/v2/HL7v2.3.1/Tables/0127
  types:
    - "DA"
    - "FA"
    - "MA"
    - "MC"
  # Reference:
  # https://hl7-definition.caristix.com/v2/HL7v2.3.1/Tables/0128
  severities:
    - "SV"
    - "MO"
    - "MI"
  # SNOMED International coding system. Reference:
  # https://hl7-definition.caristix.com/v2/HL7v2.5.1/Tables/0396
  coding_system: "SNM3"

#
# Diagnoses.
#
diagnosis:
  # Reference:
  # https://hl7-definition.caristix.com/v2/HL7v2.3.1/Tables/0052
  types:
    - "A"
    - "W"
    - "F"
  # SNOMED International coding system. Reference:
  # https://hl7-definition.caristix.com/v2/HL7v2.5.1/Tables/0396
  coding_system: "SNM3"

#
# Document type.
#
document:
  # Reference:
  # https://hl7-definition.caristix.com/v2/HL7v2.3.1/Tables/0270
  types:
    - "AR"
    - "CD"
    - "CN"
    - "DI"
    - "DS"
    - "ED"
    - "HP"
    - "OP"
    - "PC"
    - "PH"
    - "PN"
    - "SP"
    - "TS"

#
# Procedures.
#
procedure:
  # Reference:
  # https://hl7-definition.caristix.com/v2/HL7v2.3.1/Tables/0230
  types:
    - "A"
    - "P"
    - "I"
    - "D"
  # SNOMED International coding system. Reference:
  # https://hl7-definition.caristix.com/v2/HL7v2.5.1/Tables/0396
  coding_system: "SNM3"

#
# Order Control.
#
# Reference:
# https://hl7-definition.caristix.com/v2/HL7v2.3.1/Tables/0119
order_control:
  new: "NW"
  ok: "OK"
  with_observations: "RE"

#
# Result status.
#
# Reference:
# https://hl7-definition.caristix.com/v2/HL7v2.5.1/Tables/0123
result_status:
  final: "F"
  corrected: "C"

#
# Document status
#
# Reference
# https://hl7-definition.caristix.com/v2/HL7v2.5.1/Tables/0271
document_status:
  authenticated: "AU"

#
# Order status.
#
# Reference:
# https://hl7-definition.caristix.com/v2/HL7v2.5.1/Tables/0038
order_status:
  completed: "CM"
  in_process: "IP"

#
# Patient Class.
#
# Reference:
# https://hl7-definition.caristix.com/v2/HL7v2.5.1/Tables/0004
patient_class:
  outpatient: "O"
  inpatient: "I"

#
# Patient Account Status.
#
# There are no recommended values in HL7; these are user defined.
patient_account_status:
  arrived: "ARRIVED"
  cancelled: "CANCELLED"
  finished: "FINISHED"
  planned: "PLANNED"

#
# Gender.
#
# Reference:
# https://hl7-definition.caristix.com/v2/HL7v2.3.1/Tables/0001
gender:
  male: "M"
  female: "F"

#
# Abnormal Flags.
#
# Reference:
# https://hl7-definition.caristix.com/v2/HL7v2.2/Tables/0078
abnormal_flags:
  below_low_normal: "L"
  above_high_normal: "H"

primary_facility:
  organization_name: "${ORGANIZATION_NAME}"
  id_number: "${ORGANIZATION_ID}"

#
# Hospital Service (PV1.10 - Hospital Service).
#
# Reference:
# https://hl7-definition.caristix.com/v2/HL7v2.5.1/Tables/0069
#
# The hospital service value can be overridden by the doctor's specialty.
hospital_service: "MED"

#
# Coding System.
#
# WinPath is the UK's leading Laboratory Information Management System.
coding_system: "WinPath"

#
# Mapping from HL7 codes to other value sets.
#
mapping:
  fhir:
    coding_systems: { "SNM3": "https://snomed.info/sct" }
    # Reference:
    # https://www.hl7.org/fhir/valueset-reaction-event-severity.html
    allergy_severities:
      severe: ["SV", "SEVERE"]
      moderate: ["MO", "MODERATE"]
      mild: ["MI", "MILD"]
    # Reference:
    # https://www.hl7.org/fhir/valueset-allergy-intolerance-category.html
    allergy_types:
      food: ["FA", "FOOD"]
      medication: ["DA", "MEDICATION"]
      environment: ["EA", "ENVIRONMENTAL"]
      biologic: ["BIOLOGIC"]
"""

DEFAULT_LOCATIONS_YML = """\
# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

ED:
  poc: ED
  facility: "${ORGANIZATION_NAME}"
  floor: 1
  room: ED
  type: ED

Renal:
  poc: RenalWard
  facility: "${ORGANIZATION_NAME}"
  building: Main Building
  floor: 5
  room: MainRoom

Non-renal:
  poc: OtherWard
  facility: "${ORGANIZATION_NAME}"
  building: Main Building
  floor: 4
  room: MainRoom
"""

DEFAULT_DATA_YML = """\
# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#
# Allergies.
#
allergy:
  # Taken from https://www.nhs.uk/conditions/allergies/symptoms/
  reactions:
    - "Sneezing"
    - "Itchy nose"
    - "Runny nose"
    - "Blocked nose"
    - "Itchy, red, watering eyes"
    - "Wheezing"
    - "Chest tightness"
    - "Shortness of breath"
    - "Cough"
    - "Raised, itchy, red rash"
    - "Swollen lips"
    - "Swollen tongue"
    - "Swollen eyes"
    - "Swollen face"
    - "Tummy pain"
    - "Feeling sick"
    - "Vomiting"
    - "Diarrhoea"
    - "Dry, red and cracked skin"
  # percentage and maximum_allergies are taken from
  # https://www.allergyuk.org/information-and-advice/statistics
  percentage: 20
  maximum_allergies: 3

#
# Patient names.
#
patient_name:
  degrees:
    - "B.A."
    - "B.F.A."
    - "B.M."
    - "B.S."
    - "B.S.E.E."
    - "D.A."
    - "D.B.A."
    - "D.D.S."
    - "D.M.L."
    - "D.Min."
    - "Ed.D."
    - "Ed.M."
    - "J.D."
    - "M.A."
    - "M.B.A."
    - "M.F.A."
    - "M.D."
    - "M.M."
    - "M.P.A."
    - "M.Phil."
    - "M.S.A."
    - "M.S.E.E."
    - "M.S.L.I.S."
    - "M.S.P.T."
    - "M.Th."
    - "Ph.D."
    - "R.N."
    - "S.T.M."
    - "Th.D."
  # This is an arbitrary percentage.
  degree_percentage: 5
  suffixes:
    - "Sr"
    - "Snr"
    - "Jr"
    - "Jnr"
    - "II"
    - "III"
    - "B.Sc"
    - "M.A."
    - "CCNA"
    - "O.B.E"
    - "CPA"
    - "DDS"
    - "Esq"
    - "JD"
    - "LLD"
    - "MD"
    - "Ret"
    - "RN"
    - "DO"
  # This is an arbitrary percentage.
  suffix_percentage: 10
  female_prefixes:
    - "Mrs"
    - "Ms"
    - "Miss"
  male_prefixes:
    - "Mr"
  # In 1911 only 37% babies were given middle name, these days - 80%:
  # https://www.dailymail.co.uk/news/article-2515376/Middle-names-booming-80-children-given-parents-chosen-honour-lost-relatives.html
  # Assume an average of 55%.
  middlename_percentage: 55

#
# Patient addresses.
#
address:
  # Subset of London post towns from: https://en.wikipedia.org/wiki/List_of_areas_of_London
  cities:
    - "London"
    - "Croydon"
    - "Ilford"
    - "Wembley"
    - "Westerham"
  streets:
    - "Road"
    - "Street"
    - "Lane"
    - "Avenue"
    - "Place"
    - "Square"
  country: "GBR"
  types:
    - "HOME"
"""

DEFAULT_ETHNICITY_CSV = [
    ("# In HL7, ethnicities are represented as Coded Elements (type CE).",),
    ("# The format of this file is:",),
    ("# ID of the CE, Text of the CE, Frequency represented as int.",),
    ("# The frequencies have been derived from https://en.wikipedia.org/wiki/Ethnic_groups_in_London",),
    ("A", "White - British", "449"),
    ("B", "White - Irish", "22"),
    ("C", "White - Other", "127"),
    ("D", "Mixed - White and Black Caribbean", "15"),
    ("E", "Mixed - White and Black African", "8"),
    ("F", "Mixed - White and Asian", "12"),
    ("G", "Mixed - Other", "15"),
    ("H", "Asian or Asian British - Indian", "66"),
    ("J", "Asian or Asian British - Pakistani", "27"),
    ("K", "Asian or Asian British - Bangladeshi", "27"),
    ("L", "Asian or Asian British - Other", "49"),
    ("M", "Black or Black British - Caribbean", "42"),
    ("N", "Black or Black British - African", "70"),
    ("P", "Black or Black British - Other", "21"),
    ("R", "Other - Chinese", "15"),
    ("S", "Any other ethnic group", "34"),
    ("Z", "Not stated", "1"),
    ("# This \"nil,nil\" row is interpreted as an absent ethnicity.",),
    ("nil", "nil", "2"),
]


def _replace_placeholders(content: str, organization_name: str, organization_id: str) -> str:
    """Replace placeholder variables in config file content."""
    return (
        content.replace("${ORGANIZATION_NAME}", organization_name)
        .replace("${ORGANIZATION_ID}", organization_id)
    )


def generate_hl7_yml(
    organization_name: str,
    organization_id: str,
    hospital_service: str = "MED",
    output_path: str | None = None,
) -> str:
    """
    Generate hl7.yml configuration file with hospital-specific values.

    Args:
        organization_name: Name of the hospital/organization
        organization_id: ID number for the organization
        hospital_service: HL7 Table 0069 service code
        output_path: If provided, write to this file path

    Returns:
        The generated YAML content as a string
    """
    data = yaml.safe_load(DEFAULT_HL7_YML)
    data["primary_facility"]["organization_name"] = organization_name
    data["primary_facility"]["id_number"] = organization_id
    data["hospital_service"] = hospital_service
    content = yaml.dump(data, default_flow_style=False, sort_keys=False)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(content)

    return content


def generate_locations_yml(
    organization_name: str,
    organization_id: str,
    hospital_data: dict[str, Any] | None = None,
    output_path: str | None = None,
) -> str:
    """
    Generate locations.yml configuration file with hospital-specific values.

    Args:
        organization_name: Name of the hospital/organization
        organization_id: ID number for the organization
        hospital_data: Optional CMS hospital data to customize locations
        output_path: If provided, write to this file path

    Returns:
        The generated YAML content as a string
    """
    data = yaml.safe_load(DEFAULT_LOCATIONS_YML)
    for loc_data in data.values():
        loc_data["facility"] = organization_name

    if hospital_data and hospital_data.get("emergency_services") is False:
        logger.warning(
            "CMS reports no emergency services for %s; ED will still be included (Simhospital requires it).",
            organization_name,
        )

    content = yaml.dump(data, default_flow_style=False, sort_keys=False)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(content)

    return content


def generate_data_yml(
    organization_name: str,
    organization_id: str,
    address: NPPESAddress | None = None,
    demographics: dict[str, Any] | None = None,
    output_path: str | None = None,
) -> str:
    """
    Generate data.yml configuration file with hospital-specific values.

    Args:
        organization_name: Name of the hospital/organization
        organization_id: ID number for the organization
        address: Optional NPPES address to customize location data
        demographics: Optional Census demographics to customize data
        output_path: If provided, write to this file path

    Returns:
        The generated YAML content as a string
    """
    data = yaml.safe_load(DEFAULT_DATA_YML)

    country = "USA"
    if address and address.country_code:
        country = "USA" if address.country_code == "US" else address.country_code
    data["address"]["country"] = country

    if address and address.postal_code:
        data["address"]["postalcodes"] = [address.postal_code]

    if country == "USA":
        # The upstream template ships UK address data (London post towns and
        # Road/Street/Lane suffixes). A US hospital must not silently inherit it.
        data["address"]["streets"] = list(US_STREET_SUFFIXES)
        city = address.city if address else None
        if city:
            data["address"]["cities"] = [city]
        else:
            logger.warning(
                "No city in the NPPES address for %s; falling back to generic US city "
                "names. Generated patient addresses will not reflect the hospital's "
                "actual location.",
                organization_name,
            )
            data["address"]["cities"] = list(US_CITY_FALLBACK)

    if demographics:
        data.setdefault("allergy", {})
        data["allergy"]["percentage"] = demographics.get("allergy_percentage", data["allergy"]["percentage"])

    content = yaml.dump(data, default_flow_style=False, sort_keys=False)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(content)

    return content


def _scale_frequencies(counts: dict[str, int], target_total: int) -> dict[str, int]:
    """Scale counts to sum to roughly target_total, keeping every row at least 1.

    A frequency of 0 can never be sampled and breaks the positive-frequency invariant
    the schema tests enforce, so a tiny category rounds up to 1 rather than down to 0.
    """
    total = sum(counts.values())
    if total <= 0:
        return {}
    return {code: max(1, round(count * target_total / total)) for code, count in counts.items()}


def generate_ethnicity_csv(
    organization_name: str,
    organization_id: str,
    demographics: dict[str, Any] | None = None,
    output_path: str | None = None,
) -> str:
    """
    Generate ethnicity.csv configuration file.

    When Census demographics are supplied they *replace* the upstream UK defaults
    instead of being appended to them. The two share CE IDs -- the UK file uses single
    letters A-Z including A, B and H -- so appending emitted duplicate IDs with
    conflicting meanings (UK A = "White - British" alongside Census A = Asian).
    Simhospital's loader accepts duplicates silently and just builds a weighted
    distribution, so the corruption never surfaced as an error.

    Args:
        organization_name: Name of the hospital/organization
        organization_id: ID number for the organization
        demographics: Optional Census demographics to populate ethnicity
        output_path: If provided, write to this file path

    Returns:
        The generated CSV content as a string
    """
    demographics = demographics or {}
    # Drop zero counts: ACS returns 0 for categories absent from a ZCTA, and for
    # large negative sentinels that census._as_count has already clamped to 0.
    counts = {
        code: int(count)
        for code, count in (demographics.get("ethnicity") or {}).items()
        if int(count) > 0
    }

    rows: list[tuple[str, ...]]
    if counts:
        labels = demographics.get("ethnicity_labels") or ETHNICITY_LABELS
        year = demographics.get("acs_year")
        source = f"US Census ACS {year} 5-year estimates" if year else "US Census ACS 5-year estimates"
        zcta = demographics.get("zcta")
        if zcta:
            source += f" for ZCTA {zcta}"
        scaled = _scale_frequencies(counts, ETHNICITY_FREQUENCY_TOTAL)
        rows = [
            ("# In HL7, ethnicities are represented as Coded Elements (type CE).",),
            ("# The format of this file is:",),
            ("# ID of the CE, Text of the CE, Frequency represented as int.",),
            (f"# Frequencies derived from {source}.",),
        ]
        rows.extend((code, labels.get(code, code), str(scaled[code])) for code in counts)
        rows.append(('# This "nil,nil" row is interpreted as an absent ethnicity.',))
        rows.append(("nil", "nil", str(NIL_ETHNICITY_FREQUENCY)))
    else:
        logger.warning(
            "No Census ethnicity data for %s; falling back to the upstream UK "
            "distribution. Generated patient ethnicity will not reflect this "
            "hospital's actual population.",
            organization_name,
        )
        # DEFAULT_ETHNICITY_CSV already carries the sentinel comment and row.
        rows = list(DEFAULT_ETHNICITY_CSV)

    output = io.StringIO()
    writer = csv.writer(output)
    for row in rows:
        if len(row) == 1 and row[0].startswith("#"):
            output.write(row[0] + "\n")
        else:
            writer.writerow(row)

    content = output.getvalue()
    output.close()

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(content)

    return content


def generate_doctors_yml(
    doctors: list[dict[str, Any]],
    output_path: str | None = None,
) -> str:
    """
    Generate doctors.yml configuration file from a list of doctors.

    Args:
        doctors: List of doctor records with id, surname, firstname, prefix, specialty
        output_path: If provided, write to this file path

    Returns:
        The generated YAML content as a string
    """
    DEFAULT_DOCTOR = {
        "id": "",
        "surname": "",
        "firstname": "",
        "prefix": "",
        "specialty": "MED",
    }

    normalized = []
    for doctor in doctors:
        entry = dict(DEFAULT_DOCTOR)
        entry.update(doctor)
        for key in ["id", "surname", "firstname", "prefix", "specialty"]:
            if not entry.get(key):
                entry[key] = DEFAULT_DOCTOR[key]
        normalized.append(entry)

    sorted_doctors = sorted(
        normalized,
        key=lambda d: (d.get("specialty", ""), d.get("surname", ""), d.get("firstname", "")),
    )
    content = yaml.dump(sorted_doctors, default_flow_style=False, sort_keys=False)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(content)

    return content


def generate_all_configs(
    nppes_result: NPPESResult,
    output_dir: str = ".",
    demographics: dict[str, Any] | None = None,
    hospital_data: dict[str, Any] | None = None,
    doctors: list[dict[str, Any]] | None = None,
    validate: bool = True,
) -> dict[str, str]:
    """
    Generate all Simhospital configuration files from NPPES data.

    Args:
        nppes_result: NPPESResult from the API
        output_dir: Directory to write the config files to
        demographics: Optional Census demographics data
        hospital_data: Optional CMS hospital data
        doctors: Optional list of doctor records
        validate: Run the deterministic checks over the written files and log the
            report. Failures are logged, not raised, because a degraded data source
            still produces usable configs; callers that need a hard gate should
            inspect run_deterministic_checks(output_dir) themselves.

    Returns:
        Dictionary mapping filename to the generated content
    """
    org_name = nppes_result.organization_name or "Unknown Hospital"
    org_id = nppes_result.npi
    hospital_service = DEFAULT_SPECIALTY
    if nppes_result.taxonomies:
        primary = next((t for t in nppes_result.taxonomies if t.primary), nppes_result.taxonomies[0])
        # primary.code is a NUCC taxonomy code such as 282N00000X. hl7.yml's
        # hospital_service is an HL7 Table 0069 value, so map from the description;
        # writing the NUCC code through produced invalid HL7.
        hospital_service = get_hl7_code(primary.desc)

    results: dict[str, str] = {}

    results["hl7.yml"] = generate_hl7_yml(
        org_name,
        org_id,
        hospital_service=hospital_service,
        output_path=os.path.join(output_dir, "hl7.yml"),
    )

    results["locations.yml"] = generate_locations_yml(
        org_name,
        org_id,
        hospital_data=hospital_data,
        output_path=os.path.join(output_dir, "locations.yml"),
    )

    results["data.yml"] = generate_data_yml(
        org_name,
        org_id,
        address=nppes_result.address,
        demographics=demographics,
        output_path=os.path.join(output_dir, "data.yml"),
    )

    results["ethnicity.csv"] = generate_ethnicity_csv(
        org_name,
        org_id,
        demographics=demographics,
        output_path=os.path.join(output_dir, "ethnicity.csv"),
    )

    if doctors is not None:
        results["doctors.yml"] = generate_doctors_yml(
            doctors,
            output_path=os.path.join(output_dir, "doctors.yml"),
        )

    if validate:
        # Validate what was actually written, not a checked-in fixture: the previous
        # fixture-scoped checks reported confidence 1.0 on output that was still
        # London ethnicity data with placeholder doctors.
        report = run_deterministic_checks(output_dir)
        if any(not passed for passed, _ in report.values()):
            logger.warning(
                "Generated configs in %s failed deterministic checks:\n%s",
                output_dir,
                format_check_report(report),
            )
        else:
            logger.info("All %d deterministic checks passed for %s", len(report), output_dir)

    return results
