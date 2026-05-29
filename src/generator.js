import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';
import { fetchHospitalByNpi, parseHospitalData, parsePractitionerData, fetchPractitionersForHospital } from './nppes.js';
import { fetchCensusData } from './census.js';

const TEMPLATE_DIR = './templates';
const OUTPUT_DIR = './output';

const SPECIALTY_MAP = {
  '282': 'MED', '207': 'MED', '208': 'MED', '204': 'MED', '281': 'MED',
  '206': 'SUR', '202': 'SUR', '203': 'SUR',
  '207Q': 'MED', '207R': 'MED', '207X': 'MED', '208D': 'MED', '208M': 'MED',
  '207K': 'PUL', '207P': 'EMG', '207R': 'MED', '208X': 'MED',
  '204E': 'PUL', '208X': 'PUL',
  '201': 'SUR',
  '200': 'RAD',
  '202': 'ANES',
  '290': 'LAB',
  '293': 'RAD',
  '300': 'RAD',
  '207L': 'ANES',
  '208I': 'CAR',
  '207V': 'OBG',
  '208G': 'SUR',
  '208S': 'SUR',
  '208C': 'SUR',
  '207W': 'OPH',
  '207Y': 'OTO',
  '207Z': 'DER',
  '208H': 'SUR',
  '208K': 'MED',
  '208U': 'MED',
  '207S': 'MED',
  '209': 'MED',
  '211': 'MED',
  '212': 'MED'
};

const HL7_SPECIALTIES = ['MED', 'SUR', 'PUL', 'CAR', 'OBG', 'RAD', 'ANES', 'EMG', 'OPH', 'OTO', 'DER', 'NER', 'PSY', 'ORS', 'URO'];

function mapSpecialtyToHL7(code) {
  if (!code) return HL7_SPECIALTIES[Math.floor(Math.random() * 3)]; // Default to common
  const prefix = code.substring(0, 3);
  return SPECIALTY_MAP[prefix] || HL7_SPECIALTIES[Math.floor(Math.random() * HL7_SPECIALTIES.length)];
}

function generateAdditionalDoctors(hospital, count = 10) {
  const firstNames = ['James', 'Mary', 'Robert', 'Patricia', 'John', 'Jennifer', 'Michael', 'Linda', 'David', 'Elizabeth', 'William', 'Barbara', 'Richard', 'Susan', 'Joseph', 'Jessica', 'Thomas', 'Sarah', 'Christopher', 'Karen', 'Charles', 'Lisa', 'Daniel', 'Nancy', 'Matthew', 'Betty', 'Anthony', 'Margaret', 'Mark', 'Sandra'];
  const lastNames = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez', 'Anderson', 'Taylor', 'Thomas', 'Moore', 'Jackson', 'Martin', 'Lee', 'Thompson', 'White', 'Harris', 'Clark', 'Lewis', 'Robinson', 'Walker', 'Young', 'Allen', 'King', 'Wright', 'Scott', 'Torres'];
  const credentials = ['MD', 'MD', 'MD', 'DO', 'MD', 'NP', 'PA', 'MD', 'RN', 'MD'];

  const doctors = [];
  for (let i = 0; i < count; i++) {
    const firstName = firstNames[Math.floor(Math.random() * firstNames.length)];
    const lastName = lastNames[Math.floor(Math.random() * lastNames.length)];
    const specialty = HL7_SPECIALTIES[Math.floor(Math.random() * HL7_SPECIALTIES.length)];

    doctors.push({
      id: `D${String(i + 1).padStart(3, '0')}`,
      surname: lastName,
      firstname: firstName,
      prefix: credentials[Math.floor(Math.random() * credentials.length)],
      specialty
    });
  }
  return doctors;
}

function generatePatientAddresses(state, city) {
  const streetTypes = ['Road', 'Street', 'Avenue', 'Lane', 'Drive', 'Court', 'Place', 'Way', 'Boulevard', 'Circle'];
  const streetNames = ['Main', 'Oak', 'Maple', 'Cedar', 'Elm', 'Park', 'Washington', 'Lincoln', 'Jefferson', 'Madison', 'Franklin', 'Highland', 'River', 'Lake', 'Hill'];

  const addresses = [];
  for (let i = 1; i <= 20; i++) {
    const streetNum = Math.floor(Math.random() * 9000) + 100;
    const streetName = streetNames[Math.floor(Math.random() * streetNames.length)];
    const streetType = streetTypes[Math.floor(Math.random() * streetTypes.length)];
    addresses.push({
      street_number: streetNum.toString(),
      street_name: `${streetName} ${streetType}`,
      city: city || 'Unknown',
      state: state || 'XX',
      zip: (Math.floor(Math.random() * 90000) + 10000).toString(),
      country: 'USA'
    });
  }
  return addresses;
}

function generateDoctors(practitioners, hospital) {
  const MIN_DOCTORS = 15;
  const MAX_DOCTORS = 50;

  const isLargeHospital = hospital.taxonomy?.code?.startsWith('282N');

  const maxToTake = isLargeHospital ? 40 : 20;

  // Start with real practitioners from NPI
  const realDoctors = (practitioners || []).slice(0, maxToTake).map((p, idx) => ({
    id: `D${String(idx + 1).padStart(3, '0')}`,
    surname: p.lastName || 'Unknown',
    firstname: p.firstName || 'Doctor',
    prefix: p.prefix || 'Dr',
    specialty: mapSpecialtyToHL7(p.specialty)
  }));

  // Fill in with generated doctors to reach minimum
  const targetCount = isLargeHospital ? MAX_DOCTORS : MIN_DOCTORS;
  const generatedCount = Math.max(0, targetCount - realDoctors.length);
  const generatedDoctors = generateAdditionalDoctors(hospital, generatedCount);

  // Renumber all doctors sequentially
  const allDoctors = [...realDoctors, ...generatedDoctors].map((d, idx) => ({
    ...d,
    id: `D${String(idx + 1).padStart(3, '0')}`
  }));

  return allDoctors;
}

function generateLocations(taxonomyCode, hospital) {
  const isCriticalAccess = taxonomyCode?.includes('NC0060') || taxonomyCode?.includes('282NC');
  const isLargeHospital = taxonomyCode?.startsWith('282N') && !isCriticalAccess;

  const locations = {
    'ED': {
      poc: 'ED',
      facility: hospital.name,
      building: 'Main Building',
      floor: 1,
      room: 'ED',
      type: 'ED'
    }
  };

  if (isLargeHospital) {
    locations['ICU'] = { poc: 'ICU', facility: hospital.name, building: 'Main Building', floor: 2, room: 'ICU-1', type: 'ICU' };
    locations['OR'] = { poc: 'Surgery', facility: hospital.name, building: 'Surgical Wing', floor: 3, room: 'OR-1', type: 'OR' };
    locations['PACU'] = { poc: 'Post Anesthesia Care', facility: hospital.name, building: 'Surgical Wing', floor: 3, room: 'PACU', type: 'PACU' };
    locations['L&D'] = { poc: 'Labor & Delivery', facility: hospital.name, building: 'Women\'s Center', floor: 4, room: 'LDR-1', type: 'L&D' };
    locations['NICU'] = { poc: 'Neonatal ICU', facility: hospital.name, building: 'Women\'s Center', floor: 4, room: 'NICU', type: 'NICU' };
    locations['PICU'] = { poc: 'Pediatric ICU', facility: hospital.name, building: 'Pediatrics', floor: 5, room: 'PICU', type: 'PICU' };
    locations['Telemetry'] = { poc: 'Telemetry', facility: hospital.name, building: 'Main Building', floor: 3, room: 'Tele-1', type: 'Telemetry' };
    locations['Dialysis'] = { poc: 'Dialysis', facility: hospital.name, building: 'Medical Tower', floor: 4, room: 'Dialysis-1', type: 'Dialysis' };
    locations['Oncology'] = { poc: 'Oncology', facility: hospital.name, building: 'Cancer Center', floor: 2, room: 'Infusion-1', type: 'Oncology' };
    locations['Rehab'] = { poc: 'Rehabilitation', facility: hospital.name, building: 'Rehab Center', floor: 1, room: 'PT-1', type: 'Rehab' };
  } else if (!isCriticalAccess) {
    locations['ICU'] = { poc: 'ICU', facility: hospital.name, building: 'Main Building', floor: 2, room: 'ICU-1', type: 'ICU' };
    locations['OR'] = { poc: 'Surgery', facility: hospital.name, building: 'Surgical Wing', floor: 2, room: 'OR-1', type: 'OR' };
    locations['L&D'] = { poc: 'Labor & Delivery', facility: hospital.name, building: 'Women\'s Center', floor: 3, room: 'LDR-1', type: 'L&D' };
    locations['Telemetry'] = { poc: 'Telemetry', facility: hospital.name, building: 'Main Building', floor: 2, room: 'Tele-1', type: 'Telemetry' };
    locations['Dialysis'] = { poc: 'Dialysis', facility: hospital.name, building: 'Medical Wing', floor: 2, room: 'Dialysis-1', type: 'Dialysis' };
  }

  locations['General'] = { poc: 'General Ward', facility: hospital.name, building: 'Main Building', floor: isLargeHospital ? 5 : 3, room: 'Ward-3A', type: 'Ward' };
  locations['Pharmacy'] = { poc: 'Pharmacy', facility: hospital.name, building: 'Main Building', floor: 1, room: 'Pharmacy', type: 'Pharmacy' };
  locations['Lab'] = { poc: 'Laboratory', facility: hospital.name, building: 'Main Building', floor: 1, room: 'Lab-1', type: 'Lab' };
  locations['Radiology'] = { poc: 'Radiology', facility: hospital.name, building: 'Main Building', floor: 1, room: 'X-Ray', type: 'Radiology' };

  return locations;
}

function generateUSEthnicity() {
  return `A,White,450
B,Hispanic or Latino,150
C,Black or African American,200
D,Asian,80
E,American Indian or Alaska Native,20
F,Native Hawaiian or Other Pacific Islander,10
G,Two or More Races,40
Z,Not Reported,50`;
}

function processDataYML(hospital) {
  let content = fs.readFileSync(path.join(TEMPLATE_DIR, 'data.yml'), 'utf8');

  content = content.replace(/"London"|"Croydon"|"Ilford"|"Wembley"|"Westerham"/g, `"${hospital.address.city || 'Unknown'}"`);
  content = content.replace(/"Road"|"Street"|"Lane"|"Avenue"|"Place"|"Square"/g, (match) => {
    const usStreetTypes = ['Road', 'Street', 'Avenue', 'Lane', 'Drive', 'Court', 'Place', 'Way'];
    return usStreetTypes[Math.floor(Math.random() * usStreetTypes.length)];
  });
  content = content.replace(/"GBR"/g, '"USA"');
  content = content.replace(/"HOME"/g, '"H"');

  return content;
}

function processDoctorsYML(doctors) {
  const header = `# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Specialties come from
# http://hl7-definition.caristix.com:9010/Default.aspx?version=HL7%20v2.5.1&table=0069
`;

  const doctorLines = doctors.map(d =>
    `- id: "${d.id}"\n  surname: "${d.surname}"\n  firstname: "${d.firstname}"\n  prefix: "${d.prefix}"\n  specialty: "${d.specialty}"`
  ).join('\n');

  return header + doctorLines + '\n';
}

function processHl7YML(hospital) {
  let content = fs.readFileSync(path.join(TEMPLATE_DIR, 'hl7.yml'), 'utf8');

  const hl7ServiceMap = {
    '282N': 'MED',
    '281N': 'SUR',
    '207R': 'MED',
    '207Q': 'MED',
    '208D': 'MED',
    '204E': 'PUL',
    '208X': 'PUL',
    '207X': 'MED'
  };

  let hospitalService = 'MED';
  if (hospital.taxonomy?.code) {
    const code = hospital.taxonomy.code.substring(0, 4);
    hospitalService = hl7ServiceMap[code] || 'MED';
  }

  content = content.replace(/hospital_service: "MED"/g, `hospital_service: "${hospitalService}"`);
  content = content.replace(/organization_name: "\$\{ORGANIZATION_NAME\}"/g, `organization_name: "${hospital.name}"`);
  content = content.replace(/id_number: "\$\{ORGANIZATION_ID\}"/g, `id_number: "${hospital.npi}"`);

  return content;
}

function processLocationsYML(locations) {
  const header = `# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
`;

  const locationLines = Object.entries(locations).map(([key, loc]) =>
    `${key}:\n  poc: ${loc.poc}\n  facility: "${loc.facility}"\n  building: ${loc.building}\n  floor: ${loc.floor}\n  room: ${loc.room}\n  type: ${loc.type}`
  ).join('\n');

  return header + locationLines + '\n';
}

function processEthnicityCSV(demographics) {
  if (demographics) {
    return `A,White,${demographics.white || 450}\nB,Hispanic or Latino,${demographics.hispanic || 150}\nC,Black or African American,${demographics.black || 200}\nD,Asian,${demographics.asian || 80}\nE,American Indian or Alaska Native,${demographics.americanIndian || 20}\nF,Native Hawaiian or Other Pacific Islander,${demographics.pacificIslander || 10}\nG,Two or More Races,${demographics.multiracial || 40}\nZ,Not Reported,${demographics.notReported || 50}`;
  }
  return generateUSEthnicity();
}

export async function generateConfigs(options) {
  const { npi, output = OUTPUT_DIR, name: orgNameOverride } = options;

  console.log(`Fetching hospital data for NPI: ${npi}...`);
  const rawHospital = await fetchHospitalByNpi(npi);
  const hospital = parseHospitalData(rawHospital);

  if (orgNameOverride) {
    hospital.name = orgNameOverride;
  }

  console.log(`Hospital: ${hospital.name}`);
  console.log(`Location: ${hospital.address.city}, ${hospital.address.state}`);
  console.log(`Taxonomy: ${hospital.taxonomy.description}`);

  console.log('\nFetching practitioner data...');
  let practitioners = [];
  try {
    practitioners = await fetchPractitionersForHospital(npi);
  } catch (e) {
    console.log('  Could not fetch practitioners, using defaults');
  }

  console.log('  Found ~' + practitioners.length + ' practitioners');

  console.log('\nFetching demographic data...');
  let demographics = null;
  try {
    demographics = await fetchCensusData(hospital.address.state, hospital.address.city);
  } catch (e) {
    console.log('  Could not fetch demographics, using defaults');
  }

  console.log('\nGenerating configuration files...');

  fs.mkdirSync(output, { recursive: true });

  const dataContent = processDataYML(hospital);
  fs.writeFileSync(path.join(output, 'data.yml'), dataContent);
  console.log('  Generated: data.yml');

  const doctors = generateDoctors(practitioners, hospital);
  const doctorsContent = processDoctorsYML(doctors);
  fs.writeFileSync(path.join(output, 'doctors.yml'), doctorsContent);
  console.log('  Generated: doctors.yml');

  const hl7Content = processHl7YML(hospital);
  fs.writeFileSync(path.join(output, 'hl7.yml'), hl7Content);
  console.log('  Generated: hl7.yml');

  const locations = generateLocations(hospital.taxonomy?.code, hospital);
  const locationsContent = processLocationsYML(locations);
  fs.writeFileSync(path.join(output, 'locations.yml'), locationsContent);
  console.log('  Generated: locations.yml');

  const ethnicityContent = processEthnicityCSV(demographics);
  fs.writeFileSync(path.join(output, 'ethnicity.csv'), ethnicityContent);
  console.log('  Generated: ethnicity.csv');

  const hospitalDataPath = path.join(output, 'hospital_data.json');
  fs.writeFileSync(hospitalDataPath, JSON.stringify(hospital, null, 2));
  console.log('  Saved: hospital_data.json');

  console.log(`\nConfiguration files generated in: ${output}`);
  return { hospital, doctors, locations, demographics };
}