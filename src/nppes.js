import axios from 'axios';

const NPPES_BASE_URL = 'https://npiregistry.cms.hhs.gov/api/';

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

  return parseHospitalData(results[0]);
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
    const response = await axios.get(NPPES_BASE_URL, {
      params: {
        limit: 200,
        pretty: true,
        version: '2.1'
      }
    });

    const allResults = response.data.results || [];

    const hospitalNpiNum = parseInt(validatedNpi);

    return allResults
      .filter(r => {
        const taxonomies = r.taxonomies || [];
        const isPractitioner = r.enumeration_type !== 'NPI-2';
        const hasRelatedHospital = r.parent_organization_legacy_number === hospitalNpiNum ||
                                  r.created_date === new Date().toISOString().split('T')[0];
        return isPractitioner;
      })
      .map(parsePractitionerData);
  } catch (error) {
    return [];
  }
}

export function parseHospitalData(raw) {
  const address = raw.addresses?.find(a => a.address_purpose === 'LOCATION') || {};

  const taxonomy = raw.taxonomies?.find(t => t.primary) || raw.taxonomies?.[0] || {};

  const identifier = raw.identifiers?.find(i => i.desc === 'MEDICAID') || {};

  return {
    npi: raw.number,
    name: raw.organization_name || 'Unknown Hospital',
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
    createdDate: raw.created_date || '',
    lastUpdated: raw.last_updated || ''
  };
}

export function parsePractitionerData(raw) {
  const address = raw.addresses?.find(a => a.address_purpose === 'LOCATION') || {};
  const taxonomy = raw.taxonomies?.find(t => t.primary) || raw.taxonomies?.[0] || {};

  return {
    npi: raw.number,
    name: `${raw.first_name || ''} ${raw.last_name || ''}`.trim(),
    firstName: raw.first_name || '',
    lastName: raw.last_name || '',
    prefix: raw.credential || '',
    specialty: taxonomy.code?.substring(0, 3) || 'MED',
    specialtyDescription: taxonomy.desc || '',
    address: {
      city: address.city || '',
      state: address.state || ''
    },
    phone: address.telephone_number || ''
  };
}