import yaml
import os

def generate_locations_yaml(locations_data, output_path="."):
    """
    Generates a locations.yml file from the provided locations data.

    Args:
        locations_data (dict): The data for locations (e.g., from map_to_simhospital_locations).
        output_path (str): The directory path to save the YAML file.
    """
    if not locations_data:
        print("No locations data provided to generate YAML.")
        return

    os.makedirs(output_path, exist_ok=True)
    file_path = os.path.join(output_path, "locations.yml")

    try:
        with open(file_path, 'w') as f:
            yaml.dump(locations_data, f, sort_keys=False, default_flow_style=False)
        print(f"Successfully generated {file_path}")
    except Exception as e:
        print(f"Error generating {file_path}: {e}")

def update_data_yaml(patient_address_data, output_path=".", template_file="data.yml"):
    """
    Updates the address section of a data.yml template with new patient address data.

    Args:
        patient_address_data (dict): The new address data,
                                     expected to be like {'address': {'cities': [...], ...}}.
        output_path (str): The directory path to save the updated YAML file.
        template_file (str): The path to the template data.yml file.
    """
    if not patient_address_data or 'address' not in patient_address_data:
        print("No patient address data provided or 'address' key missing.")
        return

    new_address_info = patient_address_data['address']
    os.makedirs(output_path, exist_ok=True)
    output_file_path = os.path.join(output_path, "data.yml")

    try:
        # Load existing data from the template
        with open(template_file, 'r') as f:
            existing_data = yaml.safe_load(f)
            if existing_data is None:
                existing_data = {} # Handle empty template file

        # Ensure 'address' key exists in the loaded data
        if 'address' not in existing_data or not isinstance(existing_data['address'], dict):
            existing_data['address'] = {} # Initialize if not present or not a dict

        # Update the address components
        existing_data['address']['cities'] = new_address_info.get('cities', existing_data['address'].get('cities'))
        existing_data['address']['streets'] = new_address_info.get('streets', existing_data['address'].get('streets'))
        existing_data['address']['country'] = new_address_info.get('country', existing_data['address'].get('country'))
        existing_data['address']['types'] = new_address_info.get('types', existing_data['address'].get('types'))

        # Write the updated data to the output file
        with open(output_file_path, 'w') as f:
            yaml.dump(existing_data, f, sort_keys=False, default_flow_style=False)
        print(f"Successfully updated and generated {output_file_path}")

    except FileNotFoundError:
        print(f"Error: Template file '{template_file}' not found.")
    except Exception as e:
        print(f"Error updating {output_file_path}: {e}")

def generate_doctors_yaml(doctors_data, output_path="."):
    """
    Generates a doctors.yml file from the provided doctors data.

    Args:
        doctors_data (list): A list of doctor dictionaries.
        output_path (str): The directory path to save the YAML file.
    """
    if not doctors_data:
        print("No doctors data provided to generate YAML.")
        return

    os.makedirs(output_path, exist_ok=True)
    file_path = os.path.join(output_path, "doctors.yml")

    # The data should be a dictionary with a top-level key, e.g., "doctors"
    # For SimHospital, doctors.yml is usually a list of doctors directly.
    # If a top-level key is needed, it would be:
    # doctors_yaml_data = {"doctors": doctors_data}

    try:
        with open(file_path, 'w') as f:
            yaml.dump(doctors_data, f, sort_keys=False, default_flow_style=False)
        print(f"Successfully generated {file_path}")
    except Exception as e:
        print(f"Error generating {file_path}: {e}")
