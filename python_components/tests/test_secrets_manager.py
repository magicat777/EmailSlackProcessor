"""
Tests for the Secret Manager module.
"""
import pytest
import os
from unittest.mock import patch, MagicMock
from python_components.utils.secrets_manager import SecretsManager

@pytest.fixture
def mock_client():
    """Create a mock Secret Manager client."""
    with patch('google.cloud.secretmanager.SecretManagerServiceClient') as mock:
        client_instance = MagicMock()
        mock.return_value = client_instance
        yield mock

@pytest.fixture
def mock_service_account():
    """Create a mock service account credentials."""
    with patch('google.oauth2.service_account.Credentials.from_service_account_file') as mock:
        credentials_instance = MagicMock()
        mock.return_value = credentials_instance
        yield mock

@pytest.fixture
def secrets_manager(mock_client):
    """Create a SecretsManager instance with mocked dependencies."""
    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}):
        manager = SecretsManager()
        return manager

def test_init_with_project_id(mock_client):
    """Test SecretsManager initialization with project ID."""
    manager = SecretsManager(project_id="my-project")
    assert manager.project_id == "my-project"
    mock_client.assert_called_once()

def test_init_with_env_var(mock_client):
    """Test SecretsManager initialization with environment variable."""
    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "env-project"}):
        manager = SecretsManager()
        assert manager.project_id == "env-project"
    mock_client.assert_called_once()

def test_init_with_credentials_path(mock_client, mock_service_account):
    """Test SecretsManager initialization with credentials path."""
    manager = SecretsManager(
        project_id="my-project",
        credentials_path="/path/to/credentials.json"
    )
    assert manager.project_id == "my-project"
    mock_service_account.assert_called_once_with(
        "/path/to/credentials.json",
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

def test_get_secret(secrets_manager):
    """Test getting a secret."""
    # Mock the response from Secret Manager
    mock_response = MagicMock()
    mock_response.payload.data.decode.return_value = "test-secret-value"
    secrets_manager.client.access_secret_version.return_value = mock_response
    
    # Call the method
    result = secrets_manager.get_secret("test-secret")
    
    # Verify the result
    assert result == "test-secret-value"
    secrets_manager.client.access_secret_version.assert_called_once_with(
        name="projects/test-project/secrets/test-secret/versions/latest"
    )

def test_create_secret(secrets_manager):
    """Test creating a secret."""
    # Call the method
    secrets_manager.create_secret("test-secret", "test-value")
    
    # Verify the calls
    secrets_manager.client.create_secret.assert_called_once()
    create_call_args = secrets_manager.client.create_secret.call_args[1]["request"]
    assert create_call_args["parent"] == "projects/test-project"
    assert create_call_args["secret_id"] == "test-secret"
    
    secrets_manager.client.add_secret_version.assert_called_once()
    add_call_args = secrets_manager.client.add_secret_version.call_args[1]["request"]
    assert add_call_args["parent"] == "projects/test-project/secrets/test-secret"
    assert add_call_args["payload"]["data"] == b"test-value"

def test_update_secret(secrets_manager):
    """Test updating a secret."""
    # Call the method
    secrets_manager.update_secret("test-secret", "new-value")
    
    # Verify the call
    secrets_manager.client.add_secret_version.assert_called_once()
    add_call_args = secrets_manager.client.add_secret_version.call_args[1]["request"]
    assert add_call_args["parent"] == "projects/test-project/secrets/test-secret"
    assert add_call_args["payload"]["data"] == b"new-value"

def test_delete_secret(secrets_manager):
    """Test deleting a secret."""
    # Call the method
    secrets_manager.delete_secret("test-secret")
    
    # Verify the call
    secrets_manager.client.delete_secret.assert_called_once_with(
        request={"name": "projects/test-project/secrets/test-secret"}
    )

def test_list_secrets(secrets_manager):
    """Test listing secrets."""
    # Mock the response
    mock_secret1 = MagicMock()
    mock_secret1.name = "projects/test-project/secrets/secret1"
    mock_secret2 = MagicMock()
    mock_secret2.name = "projects/test-project/secrets/secret2"
    
    secrets_manager.client.list_secrets.return_value = [mock_secret1, mock_secret2]
    
    # Call the method
    result = secrets_manager.list_secrets()
    
    # Verify the result
    assert result == ["secret1", "secret2"]
    secrets_manager.client.list_secrets.assert_called_once_with(
        request={"parent": "projects/test-project"}
    )