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

Data sources that are helpful:
[NPPES](https://npiregistry.cms.hhs.gov/api-page)
- Example API Call: [https://npiregistry.cms.hhs.gov/api/?number=1730209545&enumeration_type=NPI-2&taxonomy_description=&name_purpose=&first_name=&use_first_name_alias=&last_name=&organization_name=&address_purpose=&city=&state=&postal_code=&country_code=&limit=&skip=&pretty=&version=2.1](https://npiregistry.cms.hhs.gov/api/?number=1730209545&enumeration_type=NPI-2&taxonomy_description=&name_purpose=&first_name=&use_first_name_alias=&last_name=&organization_name=&address_purpose=&city=&state=&postal_code=&country_code=&limit=&skip=&pretty=&version=2.1)

Example response:icial_name_prefix":"--","authorized_official_name_suffix":"--"},"taxonomies":[{"code":"282N00000X","taxonomy_group":"","desc":"General Acute Care Hospital","state":"IL","license":"0005272","primary":true}],"identifiers":[{"code":"05","desc":"MEDICAID","issuer":null,"identifier":"=========1473","state":"IL"}],"endpoints":[],"other_names":[{"organization_name":"STROGER HOSPITAL FFS","type":"Doing Business As","code":"3"}]}]}
