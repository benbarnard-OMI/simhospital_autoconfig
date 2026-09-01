"""
Command-line interface for simhospital_autoconfig.

Usage:
    python -m simhospital_autoconfig --npi 1730209545
    python -m simhospital_autoconfig --npi 1730209545 --output-dir ./config
"""

import argparse
import sys
import logging

from .nppes import NPPESClient, get_hospital_data
from .generators import generate_all_configs


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Automatically configure Google Simhospital to mirror real-world hospital traits."
    )
    parser.add_argument(
        "--npi",
        required=True,
        help="NPI (National Provider Identifier) number for the hospital/organization"
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory to write configuration files (default: current directory)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    logger.info(f"Fetching data for NPI: {args.npi}")
    
    try:
        # Fetch hospital data from NPPES
        nppes_result = get_hospital_data(args.npi)
        
        logger.info(f"Found organization: {nppes_result.organization_name}")
        logger.info(f"Address: {nppes_result.address.city}, {nppes_result.address.state}" if nppes_result.address else "No address found")
        
        # Generate all config files
        logger.info(f"Generating configuration files to: {args.output_dir}")
        results = generate_all_configs(nppes_result, args.output_dir)
        
        logger.info("Successfully generated configuration files:")
        for filename in results.keys():
            logger.info(f"  - {filename}")
        
        logger.info("\nConfiguration complete!")
        return 0
        
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
