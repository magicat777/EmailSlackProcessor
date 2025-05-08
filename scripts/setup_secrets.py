#!/usr/bin/env python3
"""
Script to set up secrets in Google Secret Manager for the ICAP project.
"""
import argparse
import os
import getpass
import sys
from google.cloud import secretmanager

def create_or_update_secret(project_id, secret_id, secret_value):
    """Create or update a secret in Google Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{project_id}"
    
    # Check if the secret already exists
    try:
        client.get_secret(request={"name": f"{parent}/secrets/{secret_id}"})
        print(f"Secret {secret_id} already exists. Updating...")
        
        # Add a new version to the existing secret
        parent = f"{parent}/secrets/{secret_id}"
        payload = secret_value.encode("UTF-8")
        
        response = client.add_secret_version(
            request={
                "parent": parent,
                "payload": {"data": payload}
            }
        )
        print(f"Updated secret {secret_id}: {response.name}")
        
    except Exception:
        print(f"Secret {secret_id} doesn't exist. Creating...")
        
        # Create the secret
        response = client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_id,
                "secret": {"replication": {"automatic": {}}}
            }
        )
        
        # Add the first version
        secret_parent = response.name
        payload = secret_value.encode("UTF-8")
        
        response = client.add_secret_version(
            request={
                "parent": secret_parent,
                "payload": {"data": payload}
            }
        )
        print(f"Created secret {secret_id}: {response.name}")

def get_user_input(message, sensitive=False):
    """Get user input, optionally hiding it for sensitive data."""
    if sensitive:
        return getpass.getpass(message)
    else:
        return input(message)

def setup_secrets(project_id):
    """Set up all required secrets for the ICAP project."""
    print("\n=== ICAP Secret Manager Setup ===\n")
    
    # Define required secrets
    required_secrets = [
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
            "id": "claude-api-key",
            "description": "Anthropic Claude API Key",
            "prompt": "Enter your Claude API Key: ",
            "sensitive": True
        },
        {
            "id": "notification-recipient-email",
            "description": "Email address to receive notifications",
            "prompt": "Enter the email address to receive notifications: ",
            "sensitive": False
        }
    ]
    
    for secret in required_secrets:
        print(f"\n--- {secret['description']} ---")
        
        # Check if user wants to set this secret
        setup_this = input(f"Do you want to set up {secret['id']}? (y/n): ")
        if setup_this.lower() != 'y':
            print(f"Skipping {secret['id']}")
            continue
        
        # Get the secret value
        secret_value = get_user_input(secret["prompt"], secret["sensitive"])
        
        if not secret_value:
            print(f"No value provided for {secret['id']}, skipping")
            continue
        
        # Store the secret
        try:
            create_or_update_secret(project_id, secret["id"], secret_value)
        except Exception as e:
            print(f"Error saving secret {secret['id']}: {e}")
            continue
    
    print("\nSecrets setup complete!")
    print(f"Secrets are stored in project: {project_id}")

def list_secrets(project_id):
    """List all secrets in the project."""
    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{project_id}"
    
    print(f"\nListing secrets in project: {project_id}\n")
    
    try:
        secrets = client.list_secrets(request={"parent": parent})
        
        for secret in secrets:
            name = secret.name.split('/')[-1]
            print(f"- {name}")
        
    except Exception as e:
        print(f"Error listing secrets: {e}")

def main():
    parser = argparse.ArgumentParser(description="Setup secrets for ICAP in Google Secret Manager")
    parser.add_argument(
        "--project-id", 
        help="Google Cloud project ID",
        default=os.environ.get("GOOGLE_CLOUD_PROJECT")
    )
    parser.add_argument(
        "--list", 
        action="store_true", 
        help="List existing secrets"
    )
    
    args = parser.parse_args()
    
    if not args.project_id:
        print("Error: Project ID not specified")
        print("Please provide a project ID with --project-id or set GOOGLE_CLOUD_PROJECT environment variable")
        sys.exit(1)
    
    if args.list:
        list_secrets(args.project_id)
    else:
        setup_secrets(args.project_id)

if __name__ == "__main__":
    main()