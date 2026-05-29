import axios from 'axios';

const NPPES_BASE_URL = 'https://npiregistry.cms.hhs.gov/api/';

export async function fetchHospitalByNpi(npi) {
  const response = await axios.get(NPPES_BASE_URL, {
    params: {
      number: npi,
      enumeration_type: 'NPI-2',
      pretty: true,
      version: '2.1'
    }
  });

  const results = response.data.results;
  if (!results || results.length === 0) {
    throw new Error(`No hospital found with NPI: ${npi}`);
  }

  return results[0];
}

export async function fetchPractitionersByNpi(npi, limit = 50) {
  const response = await axios.get(NPPES_BASE_URL, {
    params: {
      number: npi,
      enumeration_type: 'NPI-1',
      limit,
      pretty: true,
      version: '2.1'
    }
  });

  return response.data.results || [];
}