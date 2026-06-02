import axios from 'axios';

const NPPES_BASE_URL = 'https://npiregistry.cms.hhs.gov/api/';

const STATE_TO_FIPS = {
  'AL': '01', 'AK': '02', 'AZ': '04', 'AR': '05', 'CA': '06',
  'CO': '08', 'CT': '09', 'DE': '10', 'FL': '12', 'GA': '13',
  'HI': '15', 'ID': '16', 'IL': '17', 'IN': '18', 'IA': '19',
  'KS': '20', 'KY': '21', 'LA': '22', 'ME': '23', 'MD': '24',
  'MA': '25', 'MI': '26', 'MN': '27', 'MS': '28', 'MO': '29',
  'MT': '30', 'NE': '31', 'NV': '32', 'NH': '33', 'NJ': '34',
  'NM': '35', 'NY': '36', 'NC': '37', 'ND': '38', 'OH': '39',
  'OK': '40', 'OR': '41', 'PA': '42', 'RI': '44', 'SC': '45',
  'SD': '46', 'TN': '47', 'TX': '48', 'UT': '49', 'VT': '50',
  'VA': '51', 'WA': '53', 'WV': '54', 'WI': '55', 'WY': '56',
  'DC': '11', 'PR': '72'
};

function validateNpi(npi) {
  const cleaned = npi.toString().replace(/\D/g, '');
  if (cleaned.length !== 10) {
    throw new Error(`Invalid NPI: ${npi}. Must be 10 digits.`);
  }
  return cleaned;
}

function calculateNpiChecksum(npi) {
  const digits = npi.split('').map(Number);
  let sum = 0;
  for (let i = 0; i < 9; i++) {
    const digit = digits[i];
    const doubled = (i % 2 === 1) ? digit * 2 : digit;
    sum += doubled > 9 ? doubled - 9 : doubled;
  }
  const checkDigit = (100 - sum) % 10;
  return checkDigit === digits[9];
}

export async function fetchHospitalByNpi(npi) {
  const validatedNpi = validateNpi(npi);

  if (!calculateNpiChecksum(validatedNpi)) {
    throw new Error(`Invalid NPI checksum: ${npi}`);
  }

  const response = await axios.get(NPPES_BASE_URL, {
    params: {
      number: validatedNpi,
      enumeration_type: 'NPI-2',
      pretty: true,
      version: '2.1'
    }
  });

  const results = response.data.results;
  if (!results || results.length === 0) {
    throw new Error(`No hospital found with NPI: ${validatedNpi}`);
  }

  return results[0];
}

export async function fetchPractitionersByNpi(npi, limit = 100) {
  const validatedNpi = validateNpi(npi);

  const response = await axios.get(NPPES_BASE_URL, {
    params: {
      limit,
      pretty: true,
      version: '2.1'
    }
  });

  const allResults = response.data.results || [];
  return allResults
    .filter(p => p.endpoint && p.endpoint.some(e => e.endpoint_type === 'RI'))
    .map(parsePractitionerData);
}

export async function fetchPractitionersForHospital(npi) {
  const validatedNpi = validateNpi(npi);

  try {
    const hospitalRaw = await axios.get(NPPES_BASE_URL, {
      params: {
        number: validatedNpi,
        enumeration_type: 'NPI-2',
        pretty: true,
        version: '2.1'
      }
    });

    const hospitalData = hospitalRaw.data.results?.[0];
    if (!hospitalData) return [];

    const hospitalAddress = hospitalData.addresses?.find(a => a.address_purpose === 'LOCATION');
    const hospitalState = hospitalAddress?.state;
    const hospitalCity = hospitalAddress?.city;
    const hospitalZip = hospitalAddress?.postal_code?.split('-')[0];

    const allPractitioners = [];

    // Try city + state search
    try {
      const cityResponse = await axios.get(NPPES_BASE_URL, {
        params: {
          city: hospitalCity,
          state: hospitalState,
          pretty: true,
          version: '2.1',
          limit: 500
        }
      });
      const cityResults = cityResponse.data.results || [];
      allPractitioners.push(...cityResults);
    } catch (e) { }

    // Try zip code search
    try {
      const zipResponse = await axios.get(NPPES_BASE_URL, {
        params: {
          postal_code: hospitalZip,
          pretty: true,
          version: '2.1',
          limit: 500
        }
      });
      const zipResults = zipResponse.data.results || [];
      allPractitioners.push(...zipResults);
    } catch (e) { }

    // Deduplicate by NPI
    const uniqueMap = new Map();
    for (const r of allPractitioners) {
      if (!uniqueMap.has(r.number)) {
        uniqueMap.set(r.number, r);
      }
    }

    const hospitalNpiNum = parseInt(validatedNpi);

    return Array.from(uniqueMap.values())
      .filter(r => {
        if (r.enumeration_type === 'NPI-2') return false;
        if (r.parent_organization_legacy_number === hospitalNpiNum) return true;
        const addr = r.addresses?.find(a => a.address_purpose === 'LOCATION');
        if (addr?.state === hospitalState && addr?.city === hospitalCity) return true;
        return false;
      })
      .map(parsePractitionerData);
  } catch (error) {
    console.log('Practitioner fetch error:', error.message);
    return [];
  }
}

export function parseHospitalData(raw) {
  const basic = raw.basic || {};
  const address = raw.addresses?.find(a => a.address_purpose === 'LOCATION') || {};
  const taxonomy = raw.taxonomies?.find(t => t.primary) || raw.taxonomies?.[0] || {};

  const orgName = basic.organization_name || (basic.authorized_official_first_name && basic.authorized_official_last_name
    ? `${basic.authorized_official_first_name} ${basic.authorized_official_last_name}`
    : 'Unknown Hospital');

  return {
    npi: String(raw.number || ''),
    name: orgName,
    address: {
      street: address.address_1 || '',
      street2: address.address_2 || '',
      city: address.city || '',
      state: address.state || '',
      postalCode: address.postal_code?.split('-')[0] || '',
      country: address.country_code || 'US'
    },
    taxonomy: {
      code: taxonomy.code || '',
      description: taxonomy.desc || '',
      license: taxonomy.license || ''
    },
    identifiers: raw.identifiers?.map(id => ({
      code: id.code,
      identifier: id.identifier,
      state: id.state
    })) || [],
    phone: address.telephone_number || '',
    createdDate: basic.enumeration_date || '',
    lastUpdated: basic.last_updated || ''
  };
}

export function parsePractitionerData(raw) {
  const basic = raw.basic || {};
  const address = raw.addresses?.find(a => a.address_purpose === 'LOCATION') || {};
  const taxonomy = raw.taxonomies?.find(t => t.primary) || raw.taxonomies?.[0] || {};

  const firstName = basic.first_name || '';
  const lastName = basic.last_name || '';
  const credential = basic.credential || '';

  return {
    npi: String(raw.number || ''),
    name: `${firstName} ${lastName}`.trim() || 'Unknown',
    firstName,
    lastName,
    prefix: 'Dr',
    credential,
    specialty: taxonomy.code?.substring(0, 3) || 'MED',
    specialtyDescription: taxonomy.desc || '',
    address: {
      city: address.city || '',
      state: address.state || ''
    },
    phone: address.telephone_number || ''
  };
}