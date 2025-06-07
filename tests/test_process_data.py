import unittest
import os
import sys

# Add project root to sys.path to allow importing simhospital_config_generator
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from simhospital_config_generator.process_data import (
    extract_hospital_details,
    map_to_simhospital_locations,
    map_to_simhospital_doctors,
    map_to_simhospital_patient_address_data
)

class TestProcessData(unittest.TestCase):

    def setUp(self):
        # Sample NPI API JSON response
        self.sample_npi_api_response = {
            "result_count": 1,
            "results": [
                {
                    "created_epoch": "1234567890000",
                    "enumeration_type": "NPI-2",
                    "last_updated_epoch": "1234567899000",
                    "number": "1234567890",
                    "addresses": [
                        {
                            "country_code": "US",
                            "country_name": "United States",
                            "address_purpose": "MAILING",
                            "address_type": "DOM",
                            "address_1": "100 MAIN ST",
                            "city": "ANYTOWN",
                            "state": "CA",
                            "postal_code": "90210",
                            "telephone_number": "555-111-2222"
                        },
                        {
                            "country_code": "US",
                            "country_name": "United States",
                            "address_purpose": "LOCATION",
                            "address_type": "DOM",
                            "address_1": "200 HOSPITAL DR",
                            "address_2": "SUITE 100",
                            "city": "HEALTHCITY",
                            "state": "TX",
                            "postal_code": "75001",
                            "telephone_number": "555-333-4444"
                        }
                    ],
                    "practiceLocations": [],
                    "basic": {
                        "organization_name": "TEST HOSPITAL GENERAL",
                        "organizational_subpart": "NO",
                        "enumeration_date": "2000-01-01",
                        "last_updated": "2000-01-02",
                        "status": "A",
                        "authorized_official_first_name": "JANE",
                        "authorized_official_last_name": "DOE",
                        "authorized_official_telephone_number": "555-000-1111",
                        "authorized_official_title_or_position": "CEO",
                        "authorized_official_name_prefix": "DR."
                    },
                    "taxonomies": [
                        {"code": "261QP2300X", "desc": "Primary Care", "primary": False},
                        {"code": "282N00000X", "desc": "General Acute Care Hospital", "primary": True, "state": "TX", "license": "HOSP123"}
                    ],
                    "identifiers": [],
                    "endpoints": [],
                    "other_names": []
                }
            ]
        }

        self.extracted_details_sample = {
            "hospital_name": "TEST HOSPITAL GENERAL",
            "address": {
                "city": "HEALTHCITY",
                "state": "TX",
                "postal_code": "75001",
                "country": "United States",
                "address_1": "200 HOSPITAL DR",
                "address_2": "SUITE 100"
            },
            "primary_taxonomy_description": "General Acute Care Hospital"
        }

    def test_extract_hospital_details(self):
        details = extract_hospital_details(self.sample_npi_api_response)
        self.assertIsNotNone(details)
        self.assertEqual(details["hospital_name"], "TEST HOSPITAL GENERAL")
        self.assertEqual(details["address"]["city"], "HEALTHCITY")
        self.assertEqual(details["address"]["state"], "TX")
        self.assertEqual(details["address"]["postal_code"], "75001")
        self.assertEqual(details["address"]["country"], "United States")
        self.assertEqual(details["address"]["address_1"], "200 HOSPITAL DR")
        self.assertEqual(details["address"]["address_2"], "SUITE 100")
        self.assertEqual(details["primary_taxonomy_description"], "General Acute Care Hospital")

    def test_map_to_simhospital_locations(self):
        locations_data = map_to_simhospital_locations(self.extracted_details_sample)
        self.assertIn("ED", locations_data)
        ed_location = locations_data["ED"]
        self.assertEqual(ed_location["poc"], "TEST HOSPITAL GENERAL")
        self.assertEqual(ed_location["facility"], "HEALTHCITY, TX")
        self.assertEqual(ed_location["building"], "Main Building") # Generic
        self.assertEqual(ed_location["address"]["street"], "200 HOSPITAL DR SUITE 100")
        self.assertEqual(ed_location["address"]["city"], "HEALTHCITY")
        self.assertEqual(ed_location["address"]["state"], "TX")
        self.assertEqual(ed_location["address"]["zip"], "75001")
        self.assertEqual(ed_location["address"]["country"], "United States")

    def test_map_to_simhospital_doctors(self):
        doctors_list = map_to_simhospital_doctors(self.extracted_details_sample, self.sample_npi_api_response)
        self.assertEqual(len(doctors_list), 1)
        doctor = doctors_list[0]
        self.assertEqual(doctor["id"], "DOC001")
        self.assertEqual(doctor["surname"], "DOE")
        self.assertEqual(doctor["firstname"], "JANE")
        self.assertEqual(doctor["prefix"], "CEO") # Title used as prefix
        self.assertEqual(doctor["specialty"], "General Acute Care Hospital")

    def test_map_to_simhospital_patient_address_data(self):
        address_data_output = map_to_simhospital_patient_address_data(self.extracted_details_sample)
        self.assertIn("address", address_data_output)
        address_section = address_data_output["address"]
        self.assertEqual(address_section["cities"], ["HEALTHCITY"])
        self.assertListEqual(address_section["streets"], ["Main St", "Oak Ave", "Pine Ln"]) # Generic
        self.assertEqual(address_section["country"], "United States")
        self.assertEqual(address_section["types"], ["HOME"]) # Generic

if __name__ == '__main__':
    unittest.main()
