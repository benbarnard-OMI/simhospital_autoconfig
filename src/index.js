#!/usr/bin/env node

import 'dotenv/config';
import { Command } from 'commander';
import { generateConfigs } from './generator.js';

const program = new Command();

program
  .name('simhospital-autoconfig')
  .description('Automatically configure Google Simhospital to reflect real-world hospital traits')
  .version('1.0.0')
  .hook('preAction', (thisCommand) => {
    const opts = thisCommand.opts();
    if (opts.verbose) {
      process.env.VERBOSE = '1';
    }
  });

program
  .command('generate')
  .description('Generate Simhospital configuration files from NPI')
  .requiredOption('-n, --npi <npi>', 'Hospital NPI number (10 digits)')
  .option('-o, --output <dir>', 'Output directory', process.env.OUTPUT_DIR || './output')
  .option('--name <name>', 'Override organization name')
  .option('-v, --verbose', 'Verbose output')
  .option('--dry-run', 'Show what would be generated without making API calls')
  .action(async (options) => {
    const spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
    let spinIndex = 0;

    const verbose = (msg) => {
      if (options.verbose) {
        console.log(`  ${msg}`);
      }
    };

    const spin = (msg) => {
      process.stdout.write(`\r${spinner[spinIndex++ % spinner.length]} ${msg}`);
    };

    try {
      if (options.dryRun) {
        console.log('Dry run mode - would generate configs for NPI:', options.npi);
        console.log('Output directory:', options.output);
        return;
      }

      console.log('\n🏥 Simhospital Configuration Generator\n');
      console.log(`NPI: ${options.npi}`);
      console.log(`Output: ${options.output}\n`);

      spin('Connecting to NPPES registry...');
      const result = await generateConfigs({
        npi: options.npi,
        output: options.output,
        name: options.name,
        verbose: options.verbose
      });

      console.log('\n\n✅ Configuration generation complete!\n');
      console.log(`Hospital: ${result.hospital.name}`);
      console.log(`Location: ${result.hospital.address.city}, ${result.hospital.address.state}`);
      console.log(`Doctors: ${result.doctors.length} generated`);
      console.log(`Locations: ${Object.keys(result.locations).length} wards`);
      console.log(`\nFiles written to: ${options.output}/`);

    } catch (error) {
      console.error('\n\n❌ Error:', error.message);
      if (options.verbose || process.env.DEBUG) {
        console.error(error.stack);
      }
      process.exit(1);
    }
  });

program
  .command('validate')
  .description('Validate an NPI number')
  .argument('<npi>', 'NPI number to validate')
  .action((npi) => {
    const cleaned = npi.toString().replace(/\D/g, '');
    if (cleaned.length !== 10) {
      console.log(`❌ Invalid NPI: ${npi}`);
      console.log('   NPI must be 10 digits');
      process.exit(1);
    }

    const digits = cleaned.split('').map(Number);
    let sum = 0;
    for (let i = 0; i < 9; i++) {
      const digit = digits[i];
      const doubled = (i % 2 === 1) ? digit * 2 : digit;
      sum += doubled > 9 ? doubled - 9 : doubled;
    }
    const checkDigit = (100 - sum) % 10;
    const isValid = checkDigit === digits[9];

    if (isValid) {
      console.log(`✅ Valid NPI: ${cleaned}`);
    } else {
      console.log(`❌ Invalid NPI checksum: ${cleaned}`);
    }
    process.exit(isValid ? 0 : 1);
  });

program
  .command('info')
  .description('Fetch and display hospital information from NPI')
  .requiredOption('-n, --npi <npi>', 'Hospital NPI number')
  .option('-v, --verbose', 'Verbose output')
  .action(async (options) => {
    try {
      const { fetchHospitalByNpi, parseHospitalData } = await import('./nppes.js');

      console.log(`\nFetching info for NPI: ${options.npi}...\n`);
      const raw = await fetchHospitalByNpi(options.npi);
      const hospital = parseHospitalData(raw);

      console.log('Hospital Information');
      console.log('==================');
      console.log(`Name: ${hospital.name}`);
      console.log(`NPI: ${hospital.npi}`);
      console.log(`Address: ${hospital.address.street}`);
      console.log(`         ${hospital.address.city}, ${hospital.address.state} ${hospital.address.postalCode}`);
      console.log(`Phone: ${hospital.phone}`);
      console.log(`Taxonomy: ${hospital.taxonomy.description} (${hospital.taxonomy.code})`);
      if (hospital.taxonomy.license) {
        console.log(`License: ${hospital.taxonomy.license}`);
      }
      if (hospital.identifiers.length > 0) {
        console.log('Identifiers:');
        hospital.identifiers.forEach(id => {
          console.log(`  - ${id.code}: ${id.identifier} (${id.state})`);
        });
      }

    } catch (error) {
      console.error('❌ Error:', error.message);
      process.exit(1);
    }
  });

program.parse();