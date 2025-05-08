#!/usr/bin/env python3
"""
Main entry point for the ICAP processing engine.
"""
import os
import sys
import logging
import argparse
from dotenv import load_dotenv

from python_components.utils.neo4j_manager import Neo4jManager
from python_components.utils.env_loader import EnvLoader
from python_components.processors.action_item_processor import ActionItemProcessor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("icap")

# Load environment variables from .env file if it exists
load_dotenv()

def main():
    """Main function to start the ICAP processing engine."""
    parser = argparse.ArgumentParser(description="ICAP Processing Engine")
    parser.add_argument("--project-id", help="Google Cloud project ID for Secret Manager")
    parser.add_argument("--credentials", help="Path to service account credentials file")
    parser.add_argument("--skip-secrets", action="store_true", help="Skip loading secrets from Secret Manager")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger("icap").setLevel(logging.DEBUG)
    
    logger.info("Starting ICAP processing engine...")
    
    # Load secrets from Google Secret Manager if not skipped
    if not args.skip_secrets:
        env_loader = EnvLoader(
            project_id=args.project_id,
            credentials_path=args.credentials
        )
        env_loader.load_secrets_to_env()
    
    # Check required environment variables
    required_vars = ["NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "CLAUDE_API_KEY"]
    
    # You can also use the EnvLoader utility for validation
    env_loader = EnvLoader()
    missing_vars = env_loader.validate_required_vars(required_vars)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)
    
    logger.info("Environment variables verified.")
    
    try:
        # Initialize Neo4j connection
        neo4j_manager = Neo4jManager()
        neo4j_manager.create_constraints()
        logger.info("Neo4j connection established and schema constraints verified")
        
        # Initialize action item processor
        processor = ActionItemProcessor()
        logger.info("Action item processor initialized")
        
        # TODO: Start processing pipeline
        # For now, just log that we're ready
        logger.info("ICAP processing engine initialized and running.")
        
    except Exception as e:
        logger.error(f"Error during initialization: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()