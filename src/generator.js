import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';
import { fetchHospitalByNpi } from './nppes.js';

export async function generateConfigs(options) {
  const { npi, output, name: orgNameOverride } = options;

  console.log(`Fetching hospital data for NPI: ${npi}...`);
  const hospital = await fetchHospitalByNpi(npi);

  const orgName = orgNameOverride || hospital.organization_name;
  const orgId = npi;

  console.log(`Generating configurations for: ${orgName}`);

  const replacements = {
    '${ORGANIZATION_NAME}': orgName,
    '${ORGANIZATION_ID}': orgId
  };

  const templateFiles = ['data.yml', 'doctors.yml', 'hl7.yml', 'locations.yml', 'ethnicity.csv'];
  const templateDir = './templates';
  const outputDir = output;

  fs.mkdirSync(outputDir, { recursive: true });

  for (const file of templateFiles) {
    const templatePath = path.join(templateDir, file);
    const outputPath = path.join(outputDir, file);

    if (fs.existsSync(templatePath)) {
      let content = fs.readFileSync(templatePath, 'utf8');
      for (const [placeholder, value] of Object.entries(replacements)) {
        content = content.split(placeholder).join(value);
      }
      fs.writeFileSync(outputPath, content);
      console.log(`  Generated: ${file}`);
    }
  }

  const hospitalDataPath = path.join(outputDir, 'hospital_data.json');
  fs.writeFileSync(hospitalDataPath, JSON.stringify(hospital, null, 2));
  console.log(`  Saved: hospital_data.json`);

  console.log(`\nConfiguration files generated in: ${outputDir}`);
  return { orgName, orgId, hospital };
}