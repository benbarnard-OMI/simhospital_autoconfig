"""
Generators for Simhospital configuration files.

These functions take hospital data and generate the appropriate config files.
"""

import os
from typing import Optional, Dict, Any, List
from dataclasses import asdict
import yaml
import csv

from .nppes import NPPESResult, NPPESAddress


# Default templates for config files
DEFAULT_HL7_YML = """# Copyright 2020 Google LLC
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

DEFAULT_LOCATIONS_YML = """# Copyright 2020 Google LLC
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

DEFAULT_DATA_YML = """# Copyright 2020 Google LLC
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

# Default ethnicity data (London-based from Wikipedia)
# Format: ID, Text, Frequency
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
    return content.replace("${ORGANIZATION_NAME}", organization_name).replace("${ORGANIZATION_ID}", organization_id)


def generate_hl7_yml(
    organization_name: str,
    organization_id: str,
    output_path: Optional[str] = None
) -> str:
    """
    Generate hl7.yml configuration file with hospital-specific values.
    
    Args:
        organization_name: Name of the hospital/organization
        organization_id: ID number for the organization
        output_path: If provided, write to this file path
        
    Returns:
        The generated YAML content as a string
    """
    content = _replace_placeholders(
        DEFAULT_HL7_YML,
        organization_name=organization_name,
        organization_id=organization_id
    )
    
    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(content)
    
    return content


def generate_locations_yml(
    organization_name: str,
    organization_id: str,
    output_path: Optional[str] = None
) -> str:
    """
    Generate locations.yml configuration file with hospital-specific values.
    
    Args:
        organization_name: Name of the hospital/organization
        organization_id: ID number for the organization
        output_path: If provided, write to this file path
        
    Returns:
        The generated YAML content as a string
    """
    content = _replace_placeholders(
        DEFAULT_LOCATIONS_YML,
        organization_name=organization_name,
        organization_id=organization_id
    )
    
    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(content)
    
    return content


def generate_data_yml(
    organization_name: str,
    organization_id: str,
    address: Optional[NPPESAddress] = None,
    output_path: Optional[str] = None
) -> str:
    """
    Generate data.yml configuration file with hospital-specific values.
    
    Args:
        organization_name: Name of the hospital/organization
        organization_id: ID number for the organization
        address: Optional NPPES address to customize location data
        output_path: If provided, write to this file path
        
    Returns:
        The generated YAML content as a string
    """
    # Parse default YAML to modify it
    import io
    data = yaml.safe_load(DEFAULT_DATA_YML)
    
    # Update address section if we have address data
    if address and "address" in data:
        if address.city:
            # Replace the cities list with the hospital's city
            data["address"]["cities"] = [address.city]
        if address.state:
            data["address"]["state"] = address.state
        if address.postal_code:
            data["address"]["postal_code"] = address.postal_code
        if address.country_code:
            data["address"]["country"] = address.country_code
    
    content = yaml.dump(data, default_flow_style=False, sort_keys=False)
    
    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(content)
    
    return content


def generate_ethnicity_csv(
    organization_name: str,
    organization_id: str,
    output_path: Optional[str] = None
) -> str:
    """
    Generate ethnicity.csv configuration file.
    
    Note: This currently uses default London-based demographic data.
    In the future, this could be enhanced to fetch regional demographics
    based on the hospital's location.
    
    Args:
        organization_name: Name of the hospital/organization (currently unused)
        organization_id: ID number for the organization (currently unused)
        output_path: If provided, write to this file path
        
    Returns:
        The generated CSV content as a string
    """
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    
    for row in DEFAULT_ETHNICITY_CSV:
        writer.writerow(row)
    
    content = output.getvalue()
    output.close()
    
    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(content)
    
    return content


def generate_all_configs(
    nppes_result: NPPESResult,
    output_dir: str = "."
) -> Dict[str, str]:
    """
    Generate all Simhospital configuration files from NPPES data.
    
    Args:
        nppes_result: NPPESResult from the API
        output_dir: Directory to write the config files to
        
    Returns:
        Dictionary mapping filename to the generated content
    """
    org_name = nppes_result.organization_name or "Unknown Hospital"
    org_id = nppes_result.npi
    
    results = {}
    
    # Generate each config file
    results["hl7.yml"] = generate_hl7_yml(
        org_name, org_id,
        output_path=os.path.join(output_dir, "hl7.yml")
    )
    
    results["locations.yml"] = generate_locations_yml(
        org_name, org_id,
        output_path=os.path.join(output_dir, "locations.yml")
    )
    
    results["data.yml"] = generate_data_yml(
        org_name, org_id,
        address=nppes_result.address,
        output_path=os.path.join(output_dir, "data.yml")
    )
    
    results["ethnicity.csv"] = generate_ethnicity_csv(
        org_name, org_id,
        output_path=os.path.join(output_dir, "ethnicity.csv")
    )
    
    return results
