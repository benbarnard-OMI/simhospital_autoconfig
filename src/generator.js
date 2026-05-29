import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';
import { fetchHospitalByNpi, parseHospitalData, parsePractitionerData } from './nppes.js';
import { fetchCensusData } from './census.js';

const TEMPLATE_DIR = './templates';
const OUTPUT_DIR = './output';

const SPECIALTY_MAP = {
  '282': 'MED',
  '207': 'MED',
  '208': 'MED',
  '204': 'MED',
  '281': 'MED',
  '206': 'SUR',
  '208': 'SUR',
  '202': 'SUR',
  '203': 'SUR',
  '207Q': 'MED',
  '207R': 'MED',
  '207X': 'MED',
  '208D': 'MED',
  '208M': 'MED'
};

function mapSpecialtyToHL7(code) {
  if (!code) return 'MED';
  const prefix = code.substring(0, 3);
  return SPECIALTY_MAP[prefix] || 'MED';
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
  if (!practitioners || practitioners.length === 0) {
    return [
      { id: 'D001', surname: hospital.name.substring(0, 8) || 'Hospital', firstname: 'Chief', prefix: 'Dr', specialty: 'MED' },
      { id: 'D002', surname: 'Smith', firstname: 'Elizabeth', prefix: 'Dr', specialty: 'SUR' },
      { id: 'D003', surname: 'Johnson', firstname: 'Robert', prefix: 'Dr', specialty: 'MED' }
    ];
  }

  return practitioners.slice(0, 20).map((p, idx) => ({
    id: `D${String(idx + 1).padStart(3, '0')}`,
    surname: p.lastName || p.name?.split(' ').pop() || 'Unknown',
    firstname: p.firstName || p.name?.split(' ')[0] || 'Doctor',
    prefix: 'Dr',
    specialty: mapSpecialtyToHL7(p.specialty)
  }));
}

function generateLocations(taxonomyCode, hospital) {
  const locations = {
    'ED': {
      poc: 'ED',
      facility: hospital.name,
      building: 'Main Building',
      floor: 1,
      room: 'ED',
      type: 'ED'
    },
    'ICU': {
      poc: 'ICU',
      facility: hospital.name,
      building: 'Main Building',
      floor: 2,
      room: 'ICU-1',
      type: 'ICU'
    }
  };

  const primaryService = taxonomyCode?.startsWith('282') ? 'MED' : 'MED';

  if (taxonomyCode?.includes('281') || taxonomyCode?.includes('282')) {
    locations['OR'] = {
      poc: 'Surgery',
      facility: hospital.name,
      building: 'Surgical Wing',
      floor: 3,
      room: 'OR-1',
      type: 'OR'
    };
  }

  if (taxonomyCode?.includes('281') || taxonomyCode?.includes('287')) {
    locations['Renal'] = {
      poc: 'Nephrology',
      facility: hospital.name,
      building: 'Medical Tower',
      floor: 4,
      room: 'Dialysis-1',
      type: 'Renal'
    };
  }

  locations['General'] = {
    poc: 'General Ward',
    facility: hospital.name,
    building: 'Main Building',
    floor: 3,
    room: 'Ward-3A',
    type: 'Ward'
  };

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
  let content = fs.readFileSync(path.join(TEMPLATE_DIR, 'doctors.yml'), 'utf8');
  const lines = content.split('\n');
  const headerEnd = lines.findIndex(l => l.startsWith('- id:'));
  if (headerEnd === -1) return content;

  const header = lines.slice(0, headerEnd).join('\n');
  const doctorLines = doctors.map(d =>
    `- id: "${d.id}"\n  surname: "${d.surname}"\n  firstname: "${d.firstname}"\n  prefix: "${d.prefix}"\n  specialty: "${d.specialty}"`
  ).join('\n');

  return header + '\n' + doctorLines + '\n';
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

  return content;
}

function processLocationsYML(locations) {
  let content = fs.readFileSync(path.join(TEMPLATE_DIR, 'locations.yml'), 'utf8');
  const lines = content.split('\n');
  const headerEnd = lines.findIndex(l => l.match(/^[A-Z][a-z]+:/));
  if (headerEnd === -1) return content;

  const header = lines.slice(0, headerEnd).join('\n');
  const locationLines = Object.entries(locations).map(([key, loc]) =>
    `${key}:\n  poc: ${loc.poc}\n  facility: "${loc.facility}"\n  building: ${loc.building}\n  floor: ${loc.floor}\n  room: ${loc.room}\n  type: ${loc.type}`
  ).join('\n');

  return header + '\n' + locationLines + '\n';
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
    const rawPractitioners = await fetchHospitalByNpi(npi);
    if (rawPractitioners) {
      practitioners = [parsePractitionerData(rawPractitioners)];
    }
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