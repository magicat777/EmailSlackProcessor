"""
Tests for the webhook handler.
"""
import os
import json
import pytest
from unittest.mock import patch, MagicMock
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
from python_components.pipeline.webhook import WebhookHandler

@pytest.fixture
def mock_orchestrator():
    """Create a mock PipelineOrchestrator."""
    with patch('python_components.pipeline.orchestrator.PipelineOrchestrator') as mock:
        orchestrator_instance = MagicMock()
        mock.return_value = orchestrator_instance
        yield orchestrator_instance

class TestWebhookHandler(AioHTTPTestCase):
    """Test case for WebhookHandler."""
    
    async def get_application(self):
        """Create and return an application for testing."""
        # Patch the orchestrator
        self.mock_orchestrator_patcher = patch('python_components.pipeline.orchestrator.PipelineOrchestrator')
        self.mock_orchestrator = self.mock_orchestrator_patcher.start()
        self.mock_orchestrator_instance = MagicMock()
        self.mock_orchestrator.return_value = self.mock_orchestrator_instance
        
        # Patch webhook token validation
        self.mock_validate_patcher = patch.object(WebhookHandler, '_validate_webhook_token', return_value=True)
        self.mock_validate = self.mock_validate_patcher.start()
        
        # Create webhook handler
        self.webhook = WebhookHandler()
        
        # Let WebhookHandler create the app, but don't start the server
        # This is necessary for aiohttp test case to work
        return self.webhook.app
    
    async def tearDownAsync(self):
        """Clean up after each test."""
        self.mock_orchestrator_patcher.stop()
        self.mock_validate_patcher.stop()
        await super().tearDownAsync()
    
    @unittest_run_loop
    async def test_health_check(self):
        """Test the health check endpoint."""
        # Configure the mock
        self.mock_orchestrator_instance.pipeline_history = []
        
        # Make the request
        resp = await self.client.get('/health')
        
        # Verify the response
        assert resp.status == 200
        data = await resp.json()
        assert data['status'] == 'healthy'
        assert 'timestamp' in data
        assert data['pipeline_history_count'] == 0
    
    @unittest_run_loop
    async def test_email_webhook(self):
        """Test the email webhook endpoint."""
        # Configure the mock
        mock_context = MagicMock()
        mock_context.status = "completed"
        mock_context.id = "test-123"
        self.mock_orchestrator_instance.process_email.return_value = mock_context
        
        # Make the request
        payload = {
            "maxResults": 10,
            "filter": "isRead eq false"
        }
        resp = await self.client.post('/webhook/email', json=payload)
        
        # Verify the response
        assert resp.status == 200
        data = await resp.json()
        assert data['status'] == 'processing'
        assert 'timestamp' in data
        
        # We can't easily verify the _process_email_webhook call because it's in a create_task
        # but we can verify the validation was called
        self.mock_validate.assert_called_once()
    
    @unittest_run_loop
    async def test_slack_webhook(self):
        """Test the slack webhook endpoint."""
        # Configure the mock
        mock_context = MagicMock()
        mock_context.status = "completed"
        mock_context.id = "test-123"
        self.mock_orchestrator_instance.process_slack.return_value = mock_context
        
        # Make the request
        payload = {
            "maxResults": 10,
            "channels": ["C12345"]
        }
        resp = await self.client.post('/webhook/slack', json=payload)
        
        # Verify the response
        assert resp.status == 200
        data = await resp.json()
        assert data['status'] == 'processing'
        assert 'timestamp' in data
        
        # We can't easily verify the _process_slack_webhook call because it's in a create_task
        # but we can verify the validation was called
        self.mock_validate.assert_called_once()
    
    @unittest_run_loop
    async def test_summary_webhook(self):
        """Test the summary webhook endpoint."""
        # Configure the mock
        mock_context = MagicMock()
        mock_context.status = "completed"
        mock_context.id = "test-123"
        self.mock_orchestrator_instance.generate_daily_summary.return_value = mock_context
        
        # Make the request
        resp = await self.client.post('/webhook/summary')
        
        # Verify the response
        assert resp.status == 200
        data = await resp.json()
        assert data['status'] == 'processing'
        assert 'timestamp' in data
        
        # We can't easily verify the _process_summary_webhook call because it's in a create_task
        # but we can verify the validation was called
        self.mock_validate.assert_called_once()
    
    @unittest_run_loop
    async def test_invalid_json(self):
        """Test handling invalid JSON in the request."""
        # Make a request with invalid JSON
        resp = await self.client.post('/webhook/email', data="not-json")
        
        # Verify the response
        assert resp.status == 400
        data = await resp.json()
        assert 'error' in data
        assert 'Invalid JSON' in data['error']
    
    @unittest_run_loop
    async def test_unauthorized(self):
        """Test handling unauthorized requests."""
        # Configure the mock to return False for validation
        self.mock_validate.return_value = False
        
        # Make the request
        payload = {"maxResults": 10}
        resp = await self.client.post('/webhook/email', json=payload)
        
        # Verify the response
        assert resp.status == 401
        data = await resp.json()
        assert 'error' in data
        assert 'Invalid webhook token' in data['error']

@patch.dict(os.environ, {"WEBHOOK_TOKEN": "test-token"})
def test_validate_webhook_token():
    """Test the webhook token validation."""
    webhook = WebhookHandler()
    
    # Test with no token
    mock_request = MagicMock()
    mock_request.headers = {}
    mock_request.query = {}
    mock_request.body_exists = False
    assert webhook._validate_webhook_token(mock_request) is False
    
    # Test with valid token in header
    mock_request.headers = {"Authorization": "Bearer test-token"}
    assert webhook._validate_webhook_token(mock_request) is True
    
    # Test with invalid token in header
    mock_request.headers = {"Authorization": "Bearer wrong-token"}
    assert webhook._validate_webhook_token(mock_request) is False
    
    # Test with token in query
    mock_request.headers = {}
    mock_request.query = {"token": "test-token"}
    assert webhook._validate_webhook_token(mock_request) is True
    
    # Test with token in body
    mock_request.query = {}
    mock_request.body_exists = True
    mock_request.json.return_value = {"token": "test-token"}
    assert webhook._validate_webhook_token(mock_request) is True