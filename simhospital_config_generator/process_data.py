def extract_hospital_details(api_response_json):
    """
    Extracts key hospital information from the API JSON response.

    Args:
        api_response_json (dict): The JSON response from the NPPES API.

    Returns:
        dict: A dictionary containing extracted hospital details, or None if extraction fails.
    """
    try:
        result = api_response_json['results'][0]

        hospital_name = result['basic']['organization_name']

        # Find the primary address (assuming the first one is primary if not specified)
        # Or look for 'LOCATION' address_purpose
        primary_address = None
        for addr in result['addresses']:
            if addr.get('address_purpose') == 'LOCATION':
                primary_address = addr
                break
        if not primary_address and result['addresses']:
            primary_address = result['addresses'][0]

        if not primary_address:
            return None # Cannot proceed without an address

        address = {
            "city": primary_address.get('city'),
            "state": primary_address.get('state'),
            "postal_code": primary_address.get('postal_code'),
            "country": primary_address.get('country_name'),
            "address_1": primary_address.get('address_1'),
            "address_2": primary_address.get('address_2')
        }

        primary_taxonomy_desc = None
        for taxonomy in result['taxonomies']:
            if taxonomy.get('primary'):
                primary_taxonomy_desc = taxonomy.get('desc')
                break

        return {
            "hospital_name": hospital_name,
            "address": address,
            "primary_taxonomy_description": primary_taxonomy_desc
        }
    except (KeyError, IndexError, TypeError) as e:
        print(f"Error extracting hospital details: {e}")
        return None

def map_to_simhospital_locations(hospital_details):
    """
    Maps extracted hospital details to the SimHospital locations.yml structure for the ED.

    Args:
        hospital_details (dict): A dictionary of extracted hospital details.

    Returns:
        dict: A dictionary representing the locations.yml structure for the ED.
    """
    if not hospital_details:
        return None

    # Use a generic ED name if hospital name is not available, though it should be.
    hospital_name = hospital_details.get("hospital_name", "Unknown Hospital")
    address = hospital_details.get("address", {})

    # Construct the ED location structure
    # Using generic values for some fields as requested
    ed_location = {
        "ED": {
            "poc": hospital_name,  # Point of Care for the ED
            "facility": f"{address.get('city', 'N/A')}, {address.get('state', 'N/A')}",
            "building": "Main Building",
            "floor": "1st Floor",
            "room": "ED-101",
            "type": "EMERGENCY", # HL7 v2 Service Type
            "description": f"Emergency Department at {hospital_name}",
            "address": {
                "street": f"{address.get('address_1', '')} {address.get('address_2') if address.get('address_2') else ''}".strip(),
                "city": address.get('city'),
                "state": address.get('state'),
                "zip": address.get('postal_code'),
                "country": address.get('country')
            }
        }
    }
    return ed_location

def map_to_simhospital_doctors(hospital_details, npi_api_response):
    """
    Maps authorized official details to a SimHospital doctor entry.

    Args:
        hospital_details (dict): Extracted hospital details (for specialty).
        npi_api_response (dict): The raw NPI API response.

    Returns:
        list: A list containing a single doctor dictionary, or an empty list if details can't be extracted.
    """
    try:
        basic_info = npi_api_response['results'][0]['basic']
        first_name = basic_info.get('authorized_official_first_name')
        last_name = basic_info.get('authorized_official_last_name')
        title_position = basic_info.get('authorized_official_title_or_position')

        if not first_name or not last_name:
            print("Authorized official first or last name not found.")
            return []

        specialty = hospital_details.get('primary_taxonomy_description', 'General Medicine')
        prefix = title_position if title_position else "Dr."

        doctor = {
            "id": "DOC001",
            "surname": last_name,
            "firstname": first_name,
            "prefix": prefix,
            "specialty": specialty
        }
        return [doctor]
    except (KeyError, IndexError, TypeError) as e:
        print(f"Error extracting doctor details: {e}")
        return []

def map_to_simhospital_patient_address_data(hospital_details):
    """
    Creates a structure for the 'address' section of data.yml using hospital details.

    Args:
        hospital_details (dict): Extracted hospital details.

    Returns:
        dict: A dictionary for the 'address' section of data.yml.
    """
    if not hospital_details or not hospital_details.get('address'):
        print("Hospital details or address not found for patient address data.")
        return {}

    address_info = hospital_details['address']

    # Use hospital's city and country, generic streets and type
    patient_address_data = {
        "cities": [address_info.get('city', 'Anytown')],
        "streets": ["Main St", "Oak Ave", "Pine Ln"], # Generic street names
        "country": address_info.get('country', 'United States'),
        "types": ["HOME"] # Generic type
    }
    return {"address": patient_address_data}
