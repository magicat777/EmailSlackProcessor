"""
Tests for the pipeline orchestrator.
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import patch, MagicMock
from python_components.pipeline.orchestrator import (
    PipelineStep, PipelineContext, PipelineOrchestrator
)

@pytest.fixture
def mock_neo4j():
    """Create a mock Neo4j manager."""
    with patch('python_components.utils.neo4j_manager.Neo4jManager') as mock:
        manager_instance = MagicMock()
        mock.return_value = manager_instance
        yield manager_instance

@pytest.fixture
def mock_processor():
    """Create a mock action item processor."""
    with patch('python_components.processors.action_item_processor.ActionItemProcessor') as mock:
        processor_instance = MagicMock()
        mock.return_value = processor_instance
        yield processor_instance

@pytest.fixture
def orchestrator(mock_neo4j, mock_processor):
    """Create a PipelineOrchestrator instance with mocked dependencies."""
    orchestrator = PipelineOrchestrator()
    return orchestrator

def test_pipeline_step_init():
    """Test PipelineStep initialization."""
    mock_func = MagicMock()
    
    step = PipelineStep(
        name="test-step",
        function=mock_func,
        input_type="test-input",
        output_type="test-output"
    )
    
    assert step.name == "test-step"
    assert step.function == mock_func
    assert step.input_type == "test-input"
    assert step.output_type == "test-output"
    assert step.retry_count == 3
    assert step.timeout == 120
    assert step.required is True
    assert step.last_run is None
    assert step.last_status == "not_run"
    assert step.execution_time == 0.0
    assert step.executions == 0
    assert step.failures == 0

def test_pipeline_context_init():
    """Test PipelineContext initialization."""
    context = PipelineContext(pipeline_id="test-pipeline")
    
    assert context.pipeline_id == "test-pipeline"
    assert context.start_time is not None
    assert context.end_time is None
    assert context.status == "running"
    assert context.source_type == ""
    assert context.source_id == ""
    assert context.error is None
    assert context.metadata == {}
    assert context.results == {}

def test_pipeline_context_methods():
    """Test PipelineContext methods."""
    context = PipelineContext(pipeline_id="test-pipeline")
    
    # Test add_result and get_result
    context.add_result("step1", "result1")
    assert context.get_result("step1") == "result1"
    assert context.get_result("nonexistent") is None
    
    # Test add_metadata
    context.add_metadata("key1", "value1")
    assert context.metadata["key1"] == "value1"
    
    # Test complete
    context.complete("success")
    assert context.status == "success"
    assert context.end_time is not None
    
    # Test to_dict
    result_dict = context.to_dict()
    assert result_dict["pipeline_id"] == "test-pipeline"
    assert result_dict["status"] == "success"
    assert "start_time" in result_dict
    assert "end_time" in result_dict
    assert "metadata" in result_dict
    assert "result_summary" in result_dict

def test_orchestrator_init(orchestrator, mock_neo4j, mock_processor):
    """Test PipelineOrchestrator initialization."""
    assert orchestrator.neo4j == mock_neo4j
    assert orchestrator.processor == mock_processor
    assert hasattr(orchestrator, "email_pipeline")
    assert hasattr(orchestrator, "slack_pipeline")
    assert hasattr(orchestrator, "summary_pipeline")
    assert len(orchestrator.pipeline_history) == 0

@pytest.mark.asyncio
async def test_process_email(orchestrator, mock_processor):
    """Test processing an email."""
    # Mock the processor.process_email method to return a test value
    mock_processor.process_email.return_value = ["item1", "item2"]
    
    # Mock the _mock_retrieve_email method to return test data
    test_email = {
        "id": "email123",
        "subject": "Test Subject",
        "from": "test@example.com",
        "body": "Test body with action items",
        "date": "2023-05-01T10:30:00Z"
    }
    orchestrator._mock_retrieve_email = MagicMock(return_value=[test_email])
    
    # Process an email query
    email_query = {"maxResults": 10, "filter": "isRead eq false"}
    context = await orchestrator.process_email(email_query)
    
    # Verify the result
    assert context.status == "completed"
    assert context.source_type == "email"
    assert context.error is None
    assert context.end_time is not None
    
    # Verify the pipeline steps were called
    orchestrator._mock_retrieve_email.assert_called_once_with(email_query)
    mock_processor.process_email.assert_called_once_with([test_email])
    
    # Verify the results were stored
    assert context.get_result("retrieve_email") == [test_email]
    assert context.get_result("process_email") == ["item1", "item2"]
    
    # Verify the history was updated
    assert len(orchestrator.pipeline_history) == 1
    assert orchestrator.pipeline_history[0] == context

@pytest.mark.asyncio
async def test_process_email_failure(orchestrator, mock_processor):
    """Test processing an email with a failure."""
    # Mock the processor.process_email method to raise an exception
    mock_processor.process_email.side_effect = Exception("Test failure")
    
    # Process an email query
    email_query = {"maxResults": 10, "filter": "isRead eq false"}
    context = await orchestrator.process_email(email_query)
    
    # Verify the result
    assert context.status == "failed"
    assert context.source_type == "email"
    assert context.error is not None
    assert "Test failure" in context.error
    assert context.end_time is not None
    
    # Verify the history was updated
    assert len(orchestrator.pipeline_history) == 1
    assert orchestrator.pipeline_history[0] == context

@pytest.mark.asyncio
async def test_process_slack(orchestrator, mock_processor):
    """Test processing a Slack message."""
    # Mock the processor.process_slack_message method to return a test value
    mock_processor.process_slack_message.return_value = ["item1", "item2"]
    
    # Mock the _mock_retrieve_slack method to return test data
    test_message = {
        "id": "slack123",
        "text": "Test message with action items",
        "user": {"name": "User", "email": "user@example.com"},
        "channelId": "C12345",
        "timestamp": "1620000000.000000"
    }
    orchestrator._mock_retrieve_slack = MagicMock(return_value=[test_message])
    
    # Process a Slack query
    slack_query = {"maxResults": 10, "channels": ["C12345"]}
    context = await orchestrator.process_slack(slack_query)
    
    # Verify the result
    assert context.status == "completed"
    assert context.source_type == "slack"
    assert context.error is None
    assert context.end_time is not None
    
    # Verify the pipeline steps were called
    orchestrator._mock_retrieve_slack.assert_called_once_with(slack_query)
    mock_processor.process_slack_message.assert_called_once_with([test_message])
    
    # Verify the results were stored
    assert context.get_result("retrieve_slack_messages") == [test_message]
    assert context.get_result("process_slack_message") == ["item1", "item2"]

@pytest.mark.asyncio
async def test_generate_daily_summary(orchestrator, mock_processor):
    """Test generating a daily summary."""
    # Mock the processor.generate_daily_summary method to return a test value
    test_summary = {
        "date": "2023-05-01",
        "total_items": 5,
        "projects": ["Project A", "Project B"],
        "action_items": [{"id": "item1"}, {"id": "item2"}]
    }
    mock_processor.generate_daily_summary.return_value = test_summary
    
    # Mock the _mock_send_summary method
    orchestrator._mock_send_summary = MagicMock(return_value={"status": "sent"})
    
    # Generate a summary
    context = await orchestrator.generate_daily_summary()
    
    # Verify the result
    assert context.status == "completed"
    assert context.source_type == "summary"
    assert context.error is None
    assert context.end_time is not None
    
    # Verify the pipeline steps were called
    mock_processor.generate_daily_summary.assert_called_once()
    orchestrator._mock_send_summary.assert_called_once_with(test_summary)
    
    # Verify the results were stored
    assert context.get_result("generate_summary") == test_summary
    assert context.get_result("send_summary_email") == {"status": "sent"}

def test_get_pipeline_history(orchestrator):
    """Test getting pipeline history."""
    # Create some test contexts
    context1 = PipelineContext(pipeline_id="pipeline1")
    context1.complete("completed")
    
    context2 = PipelineContext(pipeline_id="pipeline2")
    context2.complete("failed")
    context2.error = "Test error"
    
    # Add contexts to history
    orchestrator.pipeline_history = [context1, context2]
    
    # Get history
    history = orchestrator.get_pipeline_history()
    
    # Verify the result
    assert len(history) == 2
    assert history[0]["pipeline_id"] == "pipeline1"
    assert history[0]["status"] == "completed"
    assert history[1]["pipeline_id"] == "pipeline2"
    assert history[1]["status"] == "failed"
    assert history[1]["error"] == "Test error"

def test_clear_history(orchestrator):
    """Test clearing pipeline history."""
    # Add a context to history
    context = PipelineContext(pipeline_id="test")
    orchestrator.pipeline_history.append(context)
    
    # Clear history
    orchestrator.clear_history()
    
    # Verify the result
    assert len(orchestrator.pipeline_history) == 0