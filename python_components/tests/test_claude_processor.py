"""
Tests for the Claude processor module.
"""
import pytest
import os
import json
from unittest.mock import patch, MagicMock
from python_components.utils.claude_processor import ClaudeProcessor

@pytest.fixture
def mock_env_vars():
    """Set up mock environment variables for testing."""
    os.environ["CLAUDE_API_KEY"] = "test-api-key"
    yield
    # Clean up
    del os.environ["CLAUDE_API_KEY"]

@pytest.fixture
def mock_anthropic():
    """Create a mock Anthropic client."""
    with patch('anthropic.Anthropic') as mock:
        client_instance = MagicMock()
        mock.return_value = client_instance
        yield mock, client_instance

@pytest.fixture
def claude_processor(mock_env_vars, mock_anthropic):
    """Create a ClaudeProcessor instance with mocked dependencies."""
    processor = ClaudeProcessor(model="test-model")
    return processor

def test_init(claude_processor, mock_anthropic):
    """Test ClaudeProcessor initialization."""
    assert claude_processor.api_key == "test-api-key"
    assert claude_processor.model == "test-model"
    mock_anthropic[0].assert_called_once_with(api_key="test-api-key")

def test_init_missing_api_key():
    """Test ClaudeProcessor initialization with missing API key."""
    # Ensure environment variable is not set
    if "CLAUDE_API_KEY" in os.environ:
        del os.environ["CLAUDE_API_KEY"]
    
    # Check that initialization raises ValueError
    with pytest.raises(ValueError, match="CLAUDE_API_KEY environment variable not set"):
        ClaudeProcessor()

def test_build_system_prompt():
    """Test building system prompts for different content types."""
    processor = ClaudeProcessor(model="test-model")
    
    # Test email prompt
    email_prompt = processor._build_system_prompt("email")
    assert "You are an AI assistant" in email_prompt
    assert "For emails, pay special attention to:" in email_prompt
    
    # Test Slack prompt
    slack_prompt = processor._build_system_prompt("slack")
    assert "You are an AI assistant" in slack_prompt
    assert "For Slack messages, pay special attention to:" in slack_prompt

def test_build_user_prompt():
    """Test building user prompts."""
    processor = ClaudeProcessor(model="test-model")
    
    # Test with email content
    content = "Please review this document by tomorrow."
    prompt = processor._build_user_prompt(content, "email")
    
    assert "Today's date:" in prompt
    assert "Content type: email" in prompt
    assert content in prompt
    assert "Extract all action items" in prompt

def test_normalize_date():
    """Test date normalization."""
    processor = ClaudeProcessor(model="test-model")
    
    # Test with None
    assert processor._normalize_date(None) is None
    
    # Test with "none" string
    assert processor._normalize_date("none") is None
    
    # Test with valid date string
    assert processor._normalize_date("2023-05-15") == "2023-05-15"
    
    # Test with natural language date
    assert processor._normalize_date("May 15, 2023") == "2023-05-15"
    
    # Test with invalid date
    assert processor._normalize_date("not a date") == "not a date"

def test_normalize_priority():
    """Test priority normalization."""
    processor = ClaudeProcessor(model="test-model")
    
    # Test with None
    assert processor._normalize_priority(None) == "medium"
    
    # Test with explicit priorities
    assert processor._normalize_priority("high") == "high"
    assert processor._normalize_priority("medium") == "medium"
    assert processor._normalize_priority("low") == "low"
    
    # Test with synonyms
    assert processor._normalize_priority("urgent") == "high"
    assert processor._normalize_priority("normal") == "medium"
    assert processor._normalize_priority("whenever") == "low"
    
    # Test with mixed case and spaces
    assert processor._normalize_priority("  High  ") == "high"
    
    # Test with unknown value
    assert processor._normalize_priority("unknown") == "medium"

def test_parse_claude_response_valid_json():
    """Test parsing a valid JSON response from Claude."""
    processor = ClaudeProcessor(model="test-model")
    
    # Test with clean JSON array
    json_text = '[{"content": "Review document", "assignee": "John", "due_date": "2023-05-15", "priority": "high"}]'
    result = processor._parse_claude_response(json_text)
    
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["content"] == "Review document"
    assert result[0]["assignee"] == "John"

def test_parse_claude_response_nested_json():
    """Test parsing a JSON response embedded in text."""
    processor = ClaudeProcessor(model="test-model")
    
    # Test with JSON embedded in text
    text = """
    I found the following action items:
    
    [
        {
            "content": "Review document",
            "assignee": "John",
            "due_date": "2023-05-15",
            "priority": "high"
        }
    ]
    
    Let me know if you need anything else.
    """
    
    result = processor._parse_claude_response(text)
    
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["content"] == "Review document"

def test_parse_claude_response_invalid_json():
    """Test parsing an invalid JSON response."""
    processor = ClaudeProcessor(model="test-model")
    
    # Test with invalid JSON
    text = "This is not a JSON response."
    result = processor._parse_claude_response(text)
    
    assert isinstance(result, list)
    assert len(result) == 0

def test_post_process_items():
    """Test post-processing of extracted items."""
    processor = ClaudeProcessor(model="test-model")
    
    # Create sample items
    items = [
        {
            "content": "Review document",
            "assignee": "John",
            "due_date": "2023-05-15",
            "priority": "high",
            "project": "Documentation"
        },
        {
            "content": "Schedule meeting",
            "assignee": "@sarah",
            "due_date": "next Monday",
            "priority": "urgent"
        },
        {
            "content": "Invalid item without content"
        },
        {
            "content": "Item with null fields",
            "assignee": None,
            "due_date": None,
            "priority": None
        }
    ]
    
    # Process items for email
    result = processor._post_process_items(items, "email")
    
    # Check correct number of valid items
    assert len(result) == 3  # One was invalid (no content)
    
    # Check first item (should be unchanged)
    assert result[0]["content"] == "Review document"
    assert result[0]["assignee"] == "John"
    assert result[0]["due_date"] == "2023-05-15"
    assert result[0]["priority"] == "high"
    assert result[0]["project"] == "Documentation"
    
    # Check second item (should have @ removed from slack mention)
    assert result[1]["content"] == "Schedule meeting"
    assert result[1]["assignee"] == "@sarah"  # @ not removed for email content type
    assert result[1]["priority"] == "high"  # "urgent" normalized to "high"
    
    # Check third item (nulls handled)
    assert result[2]["content"] == "Item with null fields"
    assert result[2]["assignee"] is None
    assert result[2]["due_date"] is None
    assert result[2]["priority"] == "medium"  # Default to medium

    # Process items for slack
    result = processor._post_process_items(items, "slack")
    
    # Check @ removed for slack
    assert result[1]["assignee"] == "sarah"  # @ removed for slack content type

def test_extract_action_items_success(claude_processor, mock_anthropic):
    """Test successful extraction of action items."""
    # Configure mock response
    mock_content = MagicMock()
    mock_content.text = '[{"content": "Review document", "assignee": "John", "due_date": "2023-05-15", "priority": "high"}]'
    
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    
    mock_anthropic[1].messages.create.return_value = mock_response
    
    # Call the method
    result = claude_processor.extract_action_items("Please review this document by tomorrow.", "email")
    
    # Verify the result
    assert len(result) == 1
    assert result[0]["content"] == "Review document"
    assert result[0]["assignee"] == "John"
    assert result[0]["due_date"] == "2023-05-15"
    assert result[0]["priority"] == "high"
    
    # Verify Claude API was called with correct parameters
    mock_anthropic[1].messages.create.assert_called_once()
    call_kwargs = mock_anthropic[1].messages.create.call_args[1]
    assert call_kwargs["model"] == "test-model"
    assert call_kwargs["temperature"] == 0.0
    assert call_kwargs["max_tokens"] == 4000
    assert len(call_kwargs["messages"]) == 1
    assert call_kwargs["messages"][0]["role"] == "user"

def test_extract_action_items_api_error(claude_processor, mock_anthropic):
    """Test extraction with API error."""
    import anthropic
    
    # Configure mock to raise an error
    mock_anthropic[1].messages.create.side_effect = anthropic.APIError("API Error")
    
    # Call the method
    result = claude_processor.extract_action_items("Please review this document by tomorrow.", "email")
    
    # Verify the result is an empty list on error
    assert result == []

def test_analyze_action_item_context(claude_processor, mock_anthropic):
    """Test analyzing action item context."""
    # Configure mock response
    mock_content = MagicMock()
    mock_content.text = '{"enhanced_priority": "high", "implied_deadline": "2023-05-15", "implied_assignee": "Sarah", "related_projects": ["Documentation"], "key_dependencies": ["Project approval"]}'
    
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    
    mock_anthropic[1].messages.create.return_value = mock_response
    
    # Create a test item
    item = {
        "content": "Review document",
        "assignee": None,
        "due_date": None,
        "priority": "medium"
    }
    
    # Call the method
    result = claude_processor.analyze_action_item_context(item, "Please review this document by tomorrow.")
    
    # Verify the result
    assert result["content"] == "Review document"
    assert result["assignee"] == "Sarah"  # Got implied assignee
    assert result["due_date"] == "2023-05-15"  # Got implied deadline
    assert result["priority"] == "high"  # Got enhanced priority
    assert result["project"] == "Documentation"  # Got related project
    assert result["dependencies"] == ["Project approval"]  # Got dependencies
    
    # Verify Claude API was called
    mock_anthropic[1].messages.create.assert_called_once()