#!/usr/bin/env python3
"""
Script to generate .env file from Google Secret Manager for the ICAP project.
"""
import os
import sys
import argparse
import logging

# Ensure the python_components package is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_components.utils.env_loader import EnvLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("icap.scripts.generate_env")

def main():
    """Main function to generate .env file from Secret Manager."""
    parser = argparse.ArgumentParser(description="Generate .env file from Google Secret Manager")
    
    parser.add_argument(
        "--project-id", 
        help="Google Cloud project ID",
        default=os.environ.get("GOOGLE_CLOUD_PROJECT")
    )
    
    parser.add_argument(
        "--credentials", 
        help="Path to service account credentials file",
        default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    )
    
    parser.add_argument(
        "--output", 
        help="Path to output .env file",
        default=".env"
    )
    
    parser.add_argument(
        "--secrets", 
        help="Comma-separated list of secret keys to include (default: all)",
        default=""
    )
    
    parser.add_argument(
        "--verbose", 
        action="store_true", 
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    if not args.project_id:
        logger.error("Project ID not specified")
        logger.error("Please provide a project ID with --project-id or set GOOGLE_CLOUD_PROJECT environment variable")
        sys.exit(1)
    
    # Initialize the environment loader
    env_loader = EnvLoader(
        project_id=args.project_id,
        credentials_path=args.credentials
    )
    
    # Parse custom secret keys if provided
    secret_keys = None
    if args.secrets:
        secret_keys = [s.strip() for s in args.secrets.split(",")]
    
    # Generate the .env file
    logger.info(f"Generating .env file for project {args.project_id}")
    result = env_loader.generate_dotenv_file(
        output_path=args.output,
        secret_keys=secret_keys
    )
    
    if result:
        logger.info(f"Successfully generated .env file at {args.output}")
    else:
        logger.error("Failed to generate .env file")
        sys.exit(1)

if __name__ == "__main__":
    main()