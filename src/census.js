import axios from 'axios';

const CENSUS_API_BASE = 'https://api.census.gov/data';

const STATE_DEMOGRAPHICS = {
  'IA': { white: 88, black: 4, asian: 3, hispanic: 7, americanIndian: 1, pacificIslander: 1, multiracial: 4, notReported: 1 },
  'IL': { white: 61, black: 14, asian: 6, hispanic: 18, americanIndian: 1, pacificIslander: 1, multiracial: 3, notReported: 2 },
  'NY': { white: 55, black: 17, asian: 10, hispanic: 19, americanIndian: 1, pacificIslander: 1, multiracial: 4, notReported: 2 },
  'TX': { white: 42, black: 13, asian: 5, hispanic: 40, americanIndian: 1, pacificIslander: 1, multiracial: 3, notReported: 2 },
  'CA': { white: 37, black: 6, asian: 15, hispanic: 40, americanIndian: 1, pacificIslander: 1, multiracial: 4, notReported: 2 },
  'FL': { white: 54, black: 17, asian: 3, hispanic: 27, americanIndian: 1, pacificIslander: 1, multiracial: 3, notReported: 2 },
  'PA': { white: 77, black: 12, asian: 4, hispanic: 8, americanIndian: 1, pacificIslander: 1, multiracial: 3, notReported: 1 },
  'OH': { white: 81, black: 13, asian: 2, hispanic: 4, americanIndian: 1, pacificIslander: 1, multiracial: 3, notReported: 1 },
  'GA': { white: 53, black: 33, asian: 4, hispanic: 10, americanIndian: 1, pacificIslander: 1, multiracial: 3, notReported: 1 },
  'NC': { white: 63, black: 22, asian: 3, hispanic: 10, americanIndian: 2, pacificIslander: 1, multiracial: 3, notReported: 1 },
  'MI': { white: 76, black: 14, asian: 3, hispanic: 5, americanIndian: 1, pacificIslander: 1, multiracial: 3, notReported: 1 },
  'NJ': { white: 55, black: 13, asian: 10, hispanic: 21, americanIndian: 1, pacificIslander: 1, multiracial: 4, notReported: 2 },
  'VA': { white: 63, black: 19, asian: 7, hispanic: 10, americanIndian: 1, pacificIslander: 1, multiracial: 4, notReported: 1 },
  'WA': { white: 68, black: 4, asian: 10, hispanic: 13, americanIndian: 2, pacificIslander: 1, multiracial: 5, notReported: 1 },
  'AZ': { white: 54, black: 5, asian: 4, hispanic: 32, americanIndian: 5, pacificIslander: 1, multiracial: 4, notReported: 1 },
  'MA': { white: 72, black: 9, asian: 7, hispanic: 12, americanIndian: 1, pacificIslander: 1, multiracial: 4, notReported: 1 },
  'TN': { white: 73, black: 17, asian: 2, hispanic: 6, americanIndian: 1, pacificIslander: 1, multiracial: 3, notReported: 1 },
  'IN': { white: 81, black: 10, asian: 2, hispanic: 7, americanIndian: 1, pacificIslander: 1, multiracial: 3, notReported: 1 },
  'MO': { white: 80, black: 12, asian: 2, hispanic: 4, americanIndian: 1, pacificIslander: 1, multiracial: 3, notReported: 1 },
  'MD': { white: 54, black: 31, asian: 7, hispanic: 11, americanIndian: 1, pacificIslander: 1, multiracial: 4, notReported: 1 },
  'WI': { white: 83, black: 6, asian: 3, hispanic: 7, americanIndian: 1, pacificIslander: 1, multiracial: 3, notReported: 1 },
  'CO': { white: 68, black: 4, asian: 3, hispanic: 22, americanIndian: 1, pacificIslander: 1, multiracial: 4, notReported: 1 },
  'MN': { white: 80, black: 7, asian: 5, hispanic: 6, americanIndian: 2, pacificIslander: 1, multiracial: 4, notReported: 1 },
  'SC': { white: 64, black: 27, asian: 2, hispanic: 6, americanIndian: 1, pacificIslander: 1, multiracial: 3, notReported: 1 },
  'AL': { white: 66, black: 27, asian: 2, hispanic: 5, americanIndian: 1, pacificIslander: 1, multiracial: 2, notReported: 1 },
  'LA': { white: 59, black: 33, asian: 2, hispanic: 5, americanIndian: 1, pacificIslander: 1, multiracial: 3, notReported: 1 },
  'KY': { white: 85, black: 9, asian: 2, hispanic: 4, americanIndian: 1, pacificIslander: 1, multiracial: 3, notReported: 1 },
  'OR': { white: 75, black: 2, asian: 5, hispanic: 14, americanIndian: 2, pacificIslander: 1, multiracial: 5, notReported: 1 },
  'OK': { white: 65, black: 8, asian: 2, hispanic: 11, americanIndian: 9, pacificIslander: 1, multiracial: 5, notReported: 1 },
  'CT': { white: 68, black: 12, asian: 5, hispanic: 17, americanIndian: 1, pacificIslander: 1, multiracial: 4, notReported: 1 },
  'UT': { white: 78, black: 1, asian: 2, hispanic: 15, americanIndian: 2, pacificIslander: 2, multiracial: 4, notReported: 1 },
  'IA_DEFAULT': { white: 88, black: 4, asian: 3, hispanic: 7, americanIndian: 1, pacificIslander: 1, multiracial: 4, notReported: 1 }
};

export async function fetchCensusData(state, city) {
  try {
    if (!process.env.CENSUS_API_KEY) {
      return getDefaultDemographics(state);
    }

    const year = new Date().getFullYear() - 2;
    const url = `${CENSUS_API_BASE}/${year}/acs/acs5`;

    const response = await axios.get(url, {
      params: {
        get: 'B02001_002E,B02001_005E,B02001_003E,B02001_001E,B03001_003E,B02001_006E,B02001_007E,B02001_008E',
        for: 'state:*',
        key: process.env.CENSUS_API_KEY
      }
    });

    const stateFips = STATE_TO_FIPS[state?.toUpperCase()];
    if (!stateFips) return getDefaultDemographics(state);

    const stateData = response.data.find(row => row[9] === stateFips);
    if (!stateData) return getDefaultDemographics(state);

    const total = parseInt(stateData[4]) || 1000;
    const white = parseInt(stateData[1]) || 450;
    const black = parseInt(stateData[2]) || 200;
    const asian = parseInt(stateData[3]) || 80;
    const hispanic = parseInt(stateData[4]) || 150;
    const americanIndian = parseInt(stateData[5]) || 20;
    const pacificIslander = parseInt(stateData[6]) || 10;
    const multiracial = parseInt(stateData[7]) || 40;

    return {
      total,
      white,
      black,
      asian,
      hispanic,
      americanIndian,
      pacificIslander,
      multiracial,
      notReported: Math.floor(total * 0.05)
    };
  } catch (error) {
    return getDefaultDemographics(state);
  }
}

function getDefaultDemographics(state) {
  const stateKey = state?.toUpperCase() || 'IA';
  const demographics = STATE_DEMOGRAPHICS[stateKey] || STATE_DEMOGRAPHICS['IA_DEFAULT'];
  const scale = 1000;
  return {
    total: scale,
    white: Math.floor(scale * demographics.white / 100),
    black: Math.floor(scale * demographics.black / 100),
    asian: Math.floor(scale * demographics.asian / 100),
    hispanic: Math.floor(scale * demographics.hispanic / 100),
    americanIndian: Math.floor(scale * demographics.americanIndian / 100),
    pacificIslander: Math.floor(scale * demographics.pacificIslander / 100),
    multiracial: Math.floor(scale * demographics.multiracial / 100),
    notReported: Math.floor(scale * demographics.notReported / 100)
  };
}

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

function getStateFips(state) {
  if (!state) return null;
  return STATE_TO_FIPS[state.toUpperCase()] || null;
}