#!/usr/bin/env python3
"""
Script to manage secrets for the ICAP application.
"""
import os
import sys
import argparse
import logging
import getpass
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_components.utils.secrets_manager import SecretsManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("icap.scripts.secrets")

def setup_required_secrets(secrets_manager: SecretsManager):
    """
    Interactive setup for required secrets.
    """
    print("\n=== ICAP Secrets Setup ===\n")
    
    # List of secrets needed for the application
    required_secrets = [
        {
            "id": "claude-api-key",
            "description": "Anthropic Claude API Key",
            "prompt": "Enter your Claude API Key: ",
            "sensitive": True
        },
        {
            "id": "ms-graph-client-id",
            "description": "Microsoft Graph API Client ID",
            "prompt": "Enter your Microsoft Graph Application (client) ID: ",
            "sensitive": False
        },
        {
            "id": "ms-graph-client-secret",
            "description": "Microsoft Graph API Client Secret",
            "prompt": "Enter your Microsoft Graph Client Secret: ",
            "sensitive": True
        },
        {
            "id": "ms-graph-tenant-id",
            "description": "Microsoft Graph API Tenant ID",
            "prompt": "Enter your Microsoft Graph Directory (tenant) ID: ",
            "sensitive": False
        },
        {
            "id": "ms-graph-refresh-token",
            "description": "Microsoft Graph API Refresh Token",
            "prompt": "Enter your Microsoft Graph Refresh Token: ",
            "sensitive": True
        },
        {
            "id": "slack-bot-token",
            "description": "Slack Bot User OAuth Token",
            "prompt": "Enter your Slack Bot User OAuth Token: ",
            "sensitive": True
        },
        {
            "id": "notification-recipient-email",
            "description": "Email address to receive notifications",
            "prompt": "Enter the email address to receive notifications: ",
            "sensitive": False
        }
    ]
    
    existing_secrets = set()
    try:
        existing_secrets = set(secrets_manager.list_secrets())
        if existing_secrets:
            print("Found existing secrets:", ", ".join(existing_secrets))
    except Exception as e:
        logger.error(f"Error listing existing secrets: {e}")
        print(f"Warning: Could not list existing secrets. Error: {e}")
    
    # Process each required secret
    for secret in required_secrets:
        secret_id = secret["id"]
        
        print(f"\n--- {secret['description']} ---")
        
        if secret_id in existing_secrets:
            update = input(f"Secret '{secret_id}' already exists. Do you want to update it? (y/n): ")
            if update.lower() != 'y':
                print(f"Skipping {secret_id}")
                continue
        
        # Get the secret value
        if secret["sensitive"]:
            secret_value = getpass.getpass(secret["prompt"])
        else:
            secret_value = input(secret["prompt"])
        
        if not secret_value:
            print(f"No value provided for {secret_id}, skipping")
            continue
        
        # Store the secret
        try:
            if secret_id in existing_secrets:
                secrets_manager.update_secret(secret_id, secret_value)
                print(f"✓ Updated secret: {secret_id}")
            else:
                secrets_manager.create_secret(secret_id, secret_value)
                print(f"✓ Created secret: {secret_id}")
        except Exception as e:
            logger.error(f"Error saving secret {secret_id}: {e}")
            print(f"✗ Failed to save secret {secret_id}: {e}")
    
    print("\nSecrets setup complete!")

def main():
    """Main function for the secrets management script."""
    parser = argparse.ArgumentParser(description="Manage secrets for ICAP application")
    parser.add_argument(
        "--project",
        help="Google Cloud project ID",
        default=os.getenv("GOOGLE_CLOUD_PROJECT")
    )
    parser.add_argument(
        "--credentials",
        help="Path to service account credentials JSON file",
        default=os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List existing secrets"
    )
    parser.add_argument(
        "--get",
        metavar="SECRET_ID",
        help="Get a specific secret value"
    )
    parser.add_argument(
        "--delete",
        metavar="SECRET_ID",
        help="Delete a specific secret"
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Interactive setup for required secrets"
    )
    
    args = parser.parse_args()
    
    # Initialize the secrets manager
    try:
        secrets_manager = SecretsManager(
            project_id=args.project,
            credentials_path=args.credentials
        )
    except Exception as e:
        logger.error(f"Failed to initialize Secrets Manager: {e}")
        print(f"Error: {e}")
        sys.exit(1)
    
    # Execute the requested action
    if args.list:
        try:
            secrets = secrets_manager.list_secrets()
            if secrets:
                print("Available secrets:")
                for secret in secrets:
                    print(f"  - {secret}")
            else:
                print("No secrets found")
        except Exception as e:
            logger.error(f"Error listing secrets: {e}")
            print(f"Error: {e}")
            sys.exit(1)
            
    elif args.get:
        try:
            value = secrets_manager.get_secret(args.get)
            print(f"Secret value for '{args.get}':")
            print(value)
        except Exception as e:
            logger.error(f"Error getting secret {args.get}: {e}")
            print(f"Error: {e}")
            sys.exit(1)
            
    elif args.delete:
        try:
            secrets_manager.delete_secret(args.delete)
            print(f"Successfully deleted secret: {args.delete}")
        except Exception as e:
            logger.error(f"Error deleting secret {args.delete}: {e}")
            print(f"Error: {e}")
            sys.exit(1)
            
    elif args.setup:
        setup_required_secrets(secrets_manager)
        
    else:
        parser.print_help()

if __name__ == "__main__":
    main()