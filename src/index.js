#!/usr/bin/env node

import 'dotenv/config';
import { Command } from 'commander';
import { generateConfigs } from './generator.js';

const program = new Command();

program
  .name('simhospital-autoconfig')
  .description('Automatically configure Google Simhospital to reflect real-world hospital traits')
  .version('1.0.0');

program
  .command('generate')
  .description('Generate Simhospital configuration files from NPI')
  .requiredOption('-n, --npi <npi>', 'Hospital NPI number')
  .option('-o, --output <dir>', 'Output directory', process.env.OUTPUT_DIR || './output')
  .option('--name <name>', 'Override organization name')
  .action(async (options) => {
    try {
      await generateConfigs(options);
    } catch (error) {
      console.error('Error:', error.message);
      process.exit(1);
    }
  });

program.parse();