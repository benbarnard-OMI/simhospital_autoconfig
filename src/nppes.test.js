import { test, describe } from 'node:test';
import assert from 'node:assert';
import { parseHospitalData, parsePractitionerData } from './nppes.js';

describe('NPPES Parser', () => {
  const sampleHospitalResponse = {
    number: '1730209545',
    basic: {
      organization_name: 'COOK COUNTY',
      enumeration_date: '2007-01-01',
      last_updated: '2023-01-15'
    },
    addresses: [{
      address_purpose: 'LOCATION',
      address_1: '1901 W HARRISON ST',
      address_2: '',
      city: 'CHICAGO',
      state: 'IL',
      postal_code: '60612-3748',
      country_code: 'US',
      telephone_number: '312-864-6000'
    }],
    taxonomies: [{
      code: '282N00000X',
      desc: 'General Acute Care Hospital',
      state: 'IL',
      license: '0005272',
      primary: true
    }],
    identifiers: [{
      code: '05',
      desc: 'MEDICAID',
      identifier: '1473',
      state: 'IL'
    }]
  };

  test('parseHospitalData extracts correct fields', () => {
    const result = parseHospitalData(sampleHospitalResponse);

    assert.strictEqual(result.npi, '1730209545');
    assert.strictEqual(result.name, 'COOK COUNTY');
    assert.strictEqual(result.address.city, 'CHICAGO');
    assert.strictEqual(result.address.state, 'IL');
    assert.strictEqual(result.address.postalCode, '60612');
    assert.strictEqual(result.taxonomy.code, '282N00000X');
    assert.strictEqual(result.taxonomy.description, 'General Acute Care Hospital');
  });

  test('parseHospitalData handles missing fields gracefully', () => {
    const minimalData = { number: '1234567890' };
    const result = parseHospitalData(minimalData);

    assert.strictEqual(result.npi, '1234567890');
    assert.strictEqual(result.name, 'Unknown Hospital');
    assert.strictEqual(result.address.city, '');
    assert.strictEqual(result.taxonomy.code, '');
  });

  const samplePractitionerResponse = {
    number: '1234567891',
    basic: {
      first_name: 'John',
      last_name: 'Smith',
      credential: 'MD'
    },
    addresses: [{
      address_purpose: 'LOCATION',
      city: 'CHICAGO',
      state: 'IL',
      telephone_number: '312-555-1234'
    }],
    taxonomies: [{
      code: '207Q00000X',
      desc: 'Family Medicine',
      primary: true
    }]
  };

  test('parsePractitionerData extracts correct fields', () => {
    const result = parsePractitionerData(samplePractitionerResponse);

    assert.strictEqual(result.npi, '1234567891');
    assert.strictEqual(result.name, 'John Smith');
    assert.strictEqual(result.firstName, 'John');
    assert.strictEqual(result.lastName, 'Smith');
    assert.strictEqual(result.specialty, '207');
    assert.strictEqual(result.specialtyDescription, 'Family Medicine');
  });
});