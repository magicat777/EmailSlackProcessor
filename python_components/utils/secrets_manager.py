"""
Google Secret Manager interface for ICAP.
"""
import os
import logging
from typing import Optional, Dict, Any
from google.cloud import secretmanager
from google.oauth2 import service_account

logger = logging.getLogger("icap.secrets")

class SecretsManager:
    """Interface to Google Secret Manager for managing API keys and credentials."""
    
    def __init__(self, project_id: Optional[str] = None, 
                 credentials_path: Optional[str] = None):
        """
        Initialize the Secrets Manager client.
        
        Args:
            project_id: Google Cloud project ID. If None, uses environment variable
            credentials_path: Path to service account key file
        """
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT") or "cyberpunk-gm-screen"
        
        if not self.project_id:
            raise ValueError(
                "Project ID not provided and GOOGLE_CLOUD_PROJECT environment variable not set"
            )
        
        # Set up client with credentials if provided
        if credentials_path:
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            self.client = secretmanager.SecretManagerServiceClient(credentials=credentials)
        else:
            self.client = secretmanager.SecretManagerServiceClient()
        
        logger.info(f"Secret Manager initialized for project: {self.project_id}")
    
    def get_secret(self, secret_id: str, version_id: str = "latest") -> str:
        """
        Get a secret from Secret Manager.
        
        Args:
            secret_id: The ID of the secret
            version_id: The version of the secret (default: "latest")
            
        Returns:
            The secret value as a string
        """
        secret_name = f"projects/{self.project_id}/secrets/{secret_id}/versions/{version_id}"
        
        try:
            response = self.client.access_secret_version(name=secret_name)
            secret_value = response.payload.data.decode("UTF-8")
            logger.debug(f"Retrieved secret: {secret_id}")
            return secret_value
        except Exception as e:
            logger.error(f"Error accessing secret {secret_id}: {str(e)}")
            raise
    
    def create_secret(self, secret_id: str, secret_value: str) -> None:
        """
        Create a new secret in Secret Manager.
        
        Args:
            secret_id: The ID for the new secret
            secret_value: The value of the secret
        """
        parent = f"projects/{self.project_id}"
        
        try:
            # First create the secret
            self.client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_id,
                    "secret": {"replication": {"automatic": {}}},
                }
            )
            
            # Then add the first version
            self.client.add_secret_version(
                request={
                    "parent": f"{parent}/secrets/{secret_id}",
                    "payload": {"data": secret_value.encode("UTF-8")},
                }
            )
            
            logger.info(f"Created secret: {secret_id}")
        except Exception as e:
            logger.error(f"Error creating secret {secret_id}: {str(e)}")
            raise
    
    def update_secret(self, secret_id: str, secret_value: str) -> None:
        """
        Add a new version to an existing secret.
        
        Args:
            secret_id: The ID of the existing secret
            secret_value: The new value of the secret
        """
        parent = f"projects/{self.project_id}/secrets/{secret_id}"
        
        try:
            self.client.add_secret_version(
                request={
                    "parent": parent,
                    "payload": {"data": secret_value.encode("UTF-8")},
                }
            )
            
            logger.info(f"Updated secret: {secret_id}")
        except Exception as e:
            logger.error(f"Error updating secret {secret_id}: {str(e)}")
            raise
    
    def delete_secret(self, secret_id: str) -> None:
        """
        Delete a secret from Secret Manager.
        
        Args:
            secret_id: The ID of the secret to delete
        """
        name = f"projects/{self.project_id}/secrets/{secret_id}"
        
        try:
            self.client.delete_secret(request={"name": name})
            logger.info(f"Deleted secret: {secret_id}")
        except Exception as e:
            logger.error(f"Error deleting secret {secret_id}: {str(e)}")
            raise

    def list_secrets(self) -> list:
        """
        List all secrets in the project.
        
        Returns:
            List of secret IDs
        """
        parent = f"projects/{self.project_id}"
        
        try:
            response = self.client.list_secrets(request={"parent": parent})
            secrets = [secret.name.split('/')[-1] for secret in response]
            logger.info(f"Listed {len(secrets)} secrets")
            return secrets
        except Exception as e:
            logger.error(f"Error listing secrets: {str(e)}")
            raise