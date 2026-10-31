"""
Generators for Simhospital configuration files.

These functions take hospital data and generate the appropriate config files.
"""

import csv
import io
import logging
import os
from typing import Any, Dict, List, Optional

import yaml

from .nppes import NPPESAddress, NPPESResult

logger = logging.getLogger(__name__)


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
    output_path: Optional[str] = None,
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
    hospital_data: Optional[Dict[str, Any]] = None,
    output_path: Optional[str] = None,
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
    address: Optional[NPPESAddress] = None,
    demographics: Optional[Dict[str, Any]] = None,
    output_path: Optional[str] = None,
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

    if address:
        if address.city:
            data["address"]["cities"] = [address.city]
        if address.postal_code:
            data["address"]["postalcodes"] = [address.postal_code]
        if address.country_code:
            data["address"]["country"] = "USA" if address.country_code == "US" else address.country_code
        else:
            data["address"]["country"] = "USA"
    else:
        data["address"]["country"] = "USA"

    if demographics:
        data.setdefault("allergy", {})
        data["allergy"]["percentage"] = demographics.get("allergy_percentage", data["allergy"]["percentage"])

    content = yaml.dump(data, default_flow_style=False, sort_keys=False)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(content)

    return content


def generate_ethnicity_csv(
    organization_name: str,
    organization_id: str,
    demographics: Optional[Dict[str, Any]] = None,
    output_path: Optional[str] = None,
) -> str:
    """
    Generate ethnicity.csv configuration file.

    Args:
        organization_name: Name of the hospital/organization
        organization_id: ID number for the organization
        demographics: Optional Census demographics to populate ethnicity
        output_path: If provided, write to this file path

    Returns:
        The generated CSV content as a string
    """
    output = io.StringIO()
    writer = csv.writer(output)

    if demographics and demographics.get("ethnicity"):
        rows = list(DEFAULT_ETHNICITY_CSV)
        ethnicity_labels = {
            "H": "Hispanic or Latino",
            "W": "White",
            "B": "Black or African American",
            "A": "Asian",
            "HL": "Hispanic - Mexican",
            "HP": "Hispanic - Puerto Rican",
            "HM": "Hispanic - Cuban",
            "AI": "American Indian and Alaska Native",
            "NH": "Native Hawaiian and Other Pacific Islander",
            "HO": "Hispanic - Other",
            "SR": "Some Other Race",
            "TM": "Two or More Races",
        }
        rows.extend(
            (code, ethnicity_labels.get(code, code), str(count))
            for code, count in demographics["ethnicity"].items()
        )
    else:
        rows = DEFAULT_ETHNICITY_CSV

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
    doctors: List[Dict[str, Any]],
    output_path: Optional[str] = None,
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
    demographics: Optional[Dict[str, Any]] = None,
    hospital_data: Optional[Dict[str, Any]] = None,
    doctors: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, str]:
    """
    Generate all Simhospital configuration files from NPPES data.

    Args:
        nppes_result: NPPESResult from the API
        output_dir: Directory to write the config files to
        demographics: Optional Census demographics data
        hospital_data: Optional CMS hospital data
        doctors: Optional list of doctor records

    Returns:
        Dictionary mapping filename to the generated content
    """
    org_name = nppes_result.organization_name or "Unknown Hospital"
    org_id = nppes_result.npi
    hospital_service = "MED"
    if nppes_result.taxonomies:
        primary = next((t for t in nppes_result.taxonomies if t.primary), nppes_result.taxonomies[0])
        hospital_service = primary.code or hospital_service

    results: Dict[str, str] = {}

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

    return results
