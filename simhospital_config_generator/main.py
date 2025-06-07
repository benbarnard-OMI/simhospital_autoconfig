import requests
import os
import sys
import argparse

# Conditional imports based on how the script is run
if __package__ is None or __package__ == '':
    # Running as a script
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))) # Prepend current dir to path
    from process_data import (
        extract_hospital_details,
        map_to_simhospital_locations,
        map_to_simhospital_doctors,
        map_to_simhospital_patient_address_data
    )
    from config_generator import (
        generate_locations_yaml,
        generate_doctors_yaml,
        update_data_yaml
    )
else:
    # Running as a module
    from .process_data import (
        extract_hospital_details,
        map_to_simhospital_locations,
        map_to_simhospital_doctors,
        map_to_simhospital_patient_address_data
    )
    from .config_generator import (
        generate_locations_yaml,
        generate_doctors_yaml,
        update_data_yaml
    )

# BASE_DIR is no longer strictly needed for output/template paths if users provide them,
# but can be kept if there's a need to resolve paths relative to the project root by default
# For now, argparse paths will be relative to CWD or absolute.
# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_hospital_data_by_npi(npi_number):
    """
    Fetches hospital data from the NPPES API using the NPI number.

    Args:
        npi_number (str): The NPI number of the hospital.

    Returns:
        dict: The JSON response from the API, or None if an error occurs.
    """
    api_url = f"https://npiregistry.cms.hhs.gov/api/?number={npi_number}&version=2.1"
    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for NPI {npi_number}: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Fetch hospital data and generate SimHospital config files.")
    parser.add_argument("npi_number", type=str, help="The NPI number of the hospital.")
    parser.add_argument(
        "--output_dir",
        type=str,
        default="./output_configs",
        help="Directory to save generated configuration files. (Default: ./output_configs)"
    )
    parser.add_argument(
        "--template_dir",
        type=str,
        default=".",
        help="Directory where template files (e.g., data.yml) are located. (Default: .)"
    )
    args = parser.parse_args()

    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)

    # Construct full path for the template data.yml
    template_data_yml_path = os.path.join(args.template_dir, "data.yml")

    hospital_data = get_hospital_data_by_npi(args.npi_number)
    if not hospital_data:
        print(f"Could not retrieve data for NPI: {args.npi_number}. Exiting.")
        return

    extracted_details = extract_hospital_details(hospital_data)
    if not extracted_details:
        print("Could not extract hospital details. Exiting.")
        return

    print("\nExtracted Hospital Details:")
    print(extracted_details)

    simhospital_location_data = map_to_simhospital_locations(extracted_details)
    if simhospital_location_data:
        print("\nSimHospital Location Data (ED):")
        print(simhospital_location_data)
        print(f"\nGenerating locations.yml in {args.output_dir}...")
        generate_locations_yaml(simhospital_location_data, output_path=args.output_dir)
    else:
        print("\nCould not generate SimHospital location data.")

    simhospital_doctors_data = map_to_simhospital_doctors(extracted_details, hospital_data)
    if simhospital_doctors_data:
        print("\nSimHospital Doctors Data:")
        print(simhospital_doctors_data)
        print(f"\nGenerating doctors.yml in {args.output_dir}...")
        generate_doctors_yaml(simhospital_doctors_data, output_path=args.output_dir)
    else:
        print("\nCould not generate SimHospital doctors data.")

    simhospital_patient_address_data = map_to_simhospital_patient_address_data(extracted_details)
    if simhospital_patient_address_data:
        print("\nSimHospital Patient Address Data (for data.yml):")
        print(simhospital_patient_address_data)
        print(f"\nUpdating data.yml in {args.output_dir}...")
        update_data_yaml(
            simhospital_patient_address_data,
            output_path=args.output_dir,
            template_file=template_data_yml_path
        )
    else:
        print("\nCould not generate SimHospital patient address data.")

if __name__ == "__main__":
    main()
