# SimHospital Auto-Configurator

## Project Overview

This project provides tools to automatically configure [Google SimHospital](https://github.com/google/simhospital) to reflect the traits of a specific real-world hospital. By using a hospital's National Provider Identifier (NPI), the script fetches publicly available data and generates configuration files for SimHospital.

The primary goal is to create a more realistic simulation environment by mirroring key aspects of an actual healthcare facility.

## Features

*   Fetches hospital data (name, address, type) from the NPPES NPI registry.
*   Generates `locations.yml` based on the hospital's main location (Emergency Department - ED).
*   Generates `doctors.yml` using the hospital's authorized official from the NPI record.
*   Updates the address section (city, country, generic streets/types) of `data.yml`.
*   Provides a Command-Line Interface (CLI) for specifying the NPI number and output/template directories.

## Prerequisites

*   Python 3.x (developed with 3.10)
*   `pip` for installing Python package dependencies.

## Installation/Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd simhospital_autoconfig
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

The script is run from the command line, providing the NPI number of the target hospital and optional parameters for directories.

```bash
python -m simhospital_config_generator.main <NPI_NUMBER> [OPTIONS]
```

### Command-Line Arguments:

*   `npi_number` (positional, required): The National Provider Identifier (NPI) of the hospital.
*   `--output_dir TEXT`: Directory to save the generated configuration files.
    (Default: `./output_configs`)
*   `--template_dir TEXT`: Directory where template files (e.g., `data.yml`) are located. This directory should contain a `data.yml` to be used as a base.
    (Default: `.`)

### Example:

To fetch data for NPI `1730209545` and save the generated configuration files into a directory named `generated_configs` (relative to your current path), using `data.yml` from the current directory as a template:

```bash
python -m simhospital_config_generator.main 1730209545 --output_dir generated_configs --template_dir .
```

If your `data.yml` template is in the project root and you want output in `output_configs` (the defaults):
```bash
python -m simhospital_config_generator.main 1730209545
```

## Generated Files

The script generates or updates the following files in the specified output directory:

*   **`locations.yml`**: Defines the hospital's Emergency Department (ED) based on the NPI data. Other departments are not currently generated.
*   **`doctors.yml`**: Creates a single doctor entry based on the "authorized official" listed in the NPI record.
*   **`data.yml`**: Updates the `address` section (city, country, generic streets, and types) using the hospital's location. Other parts of `data.yml` (like patient names, allergies) are preserved from the template.

The following SimHospital configuration files currently use their default template values from the SimHospital project or this project's root and are **not** modified by this script based on NPI data:
*   `hl7.yml`
*   `ethnicity.csv`

## How it Works (Briefly)

The process involves a few key Python scripts:

*   **`simhospital_config_generator/main.py`**: The main CLI entry point. It handles argument parsing and orchestrates the fetching, processing, and generation steps.
*   **`simhospital_config_generator/process_data.py`**: Contains functions to extract relevant details from the NPI API response and map them into structures suitable for SimHospital configuration.
*   **`simhospital_config_generator/config_generator.py`**: Contains functions to take the processed data and generate the actual YAML configuration files (`locations.yml`, `doctors.yml`, `data.yml`).

## Limitations

*   **Data Source:** Primarily relies on the NPPES NPI registry. Information not available in a hospital's NPI record (e.g., detailed department structures, extensive staff lists) cannot be automatically configured.
*   **Doctor Information:** The `doctors.yml` is limited to the single "authorized official" found in the NPI data.
*   **Patient Demographics:** Patient address data in `data.yml` uses the hospital's city and country, but street names are generic. Other demographic details (ethnicity, names) are based on the provided template `data.yml`.
*   **HL7 & Ethnicity Configs:** `hl7.yml` and `ethnicity.csv` are not dynamically generated from NPI data and rely on the base templates.
*   **Single ED Location:** Only a single Emergency Department (ED) location is generated in `locations.yml`.

## Future Enhancements (Potential)

*   Integrate additional public data sources (e.g., HCRIS, Medicare data) for more comprehensive hospital details.
*   Allow specification of multiple NPIs or other identifiers to build a more complex hospital system.
*   Generate more detailed department structures in `locations.yml`.
*   Explore ways to generate more diverse and realistic doctor profiles.
*   Provide options to customize the generic values used (e.g., street names, building names).

## Original Data Sources section (from previous README)
Data sources that are helpful:
[NPPES](https://npiregistry.cms.hhs.gov/api-page)
- Example API Call: [https://npiregistry.cms.hhs.gov/api/?number=1730209545&enumeration_type=NPI-2&taxonomy_description=&name_purpose=&first_name=&use_first_name_alias=&last_name=&organization_name=&address_purpose=&city=&state=&postal_code=&country_code=&limit=&skip=&pretty=&version=2.1](https://npiregistry.cms.hhs.gov/api/?number=1730209545&enumeration_type=NPI-2&taxonomy_description=&name_purpose=&first_name=&use_first_name_alias=&last_name=&organization_name=&address_purpose=&city=&state=&postal_code=&country_code=&limit=&skip=&pretty=&version=2.1)
