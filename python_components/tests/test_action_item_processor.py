"""
Tests for the Action Item Processor module.
"""
import pytest
import os
import json
from unittest.mock import patch, MagicMock
from python_components.processors.action_item_processor import ActionItemProcessor

@pytest.fixture
def mock_neo4j():
    """Create a mock Neo4j manager."""
    with patch('python_components.utils.neo4j_manager.Neo4jManager') as mock:
        manager_instance = MagicMock()
        mock.return_value = manager_instance
        yield manager_instance

@pytest.fixture
def mock_claude():
    """Create a mock Claude processor."""
    with patch('python_components.utils.claude_processor.ClaudeProcessor') as mock:
        processor_instance = MagicMock()
        mock.return_value = processor_instance
        yield processor_instance

@pytest.fixture
def processor(mock_neo4j, mock_claude):
    """Create an ActionItemProcessor instance with mocked dependencies."""
    processor = ActionItemProcessor()
    return processor

def test_init(processor, mock_neo4j, mock_claude):
    """Test ActionItemProcessor initialization."""
    assert processor.neo4j == mock_neo4j
    assert processor.claude == mock_claude

def test_process_email_no_items(processor, mock_claude):
    """Test processing an email with no action items."""
    # Configure mock to return empty list
    mock_claude.extract_action_items.return_value = []
    
    # Call the method
    result = processor.process_email({
        "id": "test-email-id",
        "subject": "Test Email",
        "from": "test@example.com",
        "body": "This is a test email with no action items."
    })
    
    # Verify result
    assert result == []
    
    # Verify Claude processor was called
    mock_claude.extract_action_items.assert_called_once()
    call_args = mock_claude.extract_action_items.call_args[0]
    assert "Test Email" in call_args[0]  # Content includes subject
    assert "test@example.com" in call_args[0]  # Content includes sender
    assert call_args[1] == "email"  # Content type

def test_process_email_with_items(processor, mock_claude, mock_neo4j):
    """Test processing an email with action items."""
    # Configure mock to return action items
    mock_claude.extract_action_items.return_value = [
        {
            "content": "Review document",
            "assignee": "john@example.com",
            "due_date": "2023-05-15",
            "priority": "high",
            "project": "Documentation"
        },
        {
            "content": "Schedule meeting",
            "assignee": None,
            "due_date": None,
            "priority": "medium"
        }
    ]
    
    # Configure mock analyze_action_item_context to enhance the second item
    def mock_analyze(item, content):
        if item["content"] == "Schedule meeting":
            return {
                "content": "Schedule meeting",
                "assignee": "sarah@example.com",
                "due_date": "2023-05-20",
                "priority": "medium"
            }
        return item
    
    mock_claude.analyze_action_item_context.side_effect = mock_analyze
    
    # Configure Neo4j to return an ID for created items
    mock_neo4j.create_action_item.return_value = "test-action-id"
    
    # Call the method
    result = processor.process_email({
        "id": "test-email-id",
        "subject": "Test Email",
        "from": "test@example.com",
        "body": "This is a test email with action items."
    })
    
    # Verify result has two IDs
    assert len(result) == 2
    
    # Verify Neo4j was called correctly
    assert mock_neo4j.create_action_item.call_count == 2
    
    # Verify links were created
    assert mock_neo4j.link_action_to_person.call_count == 4  # 2 assignees + 2 senders
    assert mock_neo4j.link_action_to_project.call_count == 1  # 1 project

def test_process_slack_message(processor, mock_claude, mock_neo4j):
    """Test processing a Slack message."""
    # Configure mock to return action items
    mock_claude.extract_action_items.return_value = [
        {
            "content": "Deploy application",
            "assignee": "@david",
            "due_date": "2023-05-15",
            "priority": "high",
            "project": "Deployment"
        }
    ]
    
    # No need for context analysis in this test
    mock_claude.analyze_action_item_context.return_value = mock_claude.extract_action_items.return_value[0]
    
    # Configure Neo4j to return an ID for created items
    mock_neo4j.create_action_item.return_value = "test-action-id"
    
    # Call the method
    result = processor.process_slack_message({
        "id": "test-message-id",
        "text": "Let's deploy the application by Monday.",
        "user": {
            "name": "John Doe",
            "email": "john@example.com"
        },
        "channelId": "test-channel",
        "timestamp": "1620000000.000000"
    })
    
    # Verify result has one ID
    assert len(result) == 1
    
    # Verify Claude processor was called correctly
    mock_claude.extract_action_items.assert_called_once()
    call_args = mock_claude.extract_action_items.call_args[0]
    assert "John Doe" in call_args[0]  # Content includes sender
    assert "test-channel" in call_args[0]  # Content includes channel
    assert call_args[1] == "slack"  # Content type
    
    # Verify Neo4j was called correctly
    mock_neo4j.create_action_item.assert_called_once()
    neo4j_item = mock_neo4j.create_action_item.call_args[0][0]
    assert neo4j_item["source"] == "slack"
    assert neo4j_item["channel_id"] == "test-channel"
    
    # Verify links were created
    assert mock_neo4j.link_action_to_person.call_count == 2  # assignee + sender
    assert mock_neo4j.link_action_to_project.call_count == 1  # project

def test_generate_daily_summary(processor, mock_neo4j):
    """Test generating a daily summary."""
    # Configure Neo4j to return action items
    mock_neo4j.get_action_items_by_status.return_value = [
        {
            "id": "item1",
            "content": "High priority task",
            "source": "email",
            "source_id": "email1",
            "created_at": "2023-05-01T10:00:00Z",
            "due_date": "2023-05-10",
            "priority": "high",
            "status": "pending",
            "subject": "Important task",
            "sender": "boss@example.com"
        },
        {
            "id": "item2",
            "content": "Medium priority task",
            "source": "slack",
            "source_id": "slack1",
            "created_at": "2023-05-02T10:00:00Z",
            "due_date": "2023-05-15",
            "priority": "medium",
            "status": "pending",
            "channel_id": "general"
        },
        {
            "id": "item3",
            "content": "Low priority task",
            "source": "email",
            "source_id": "email2",
            "created_at": "2023-05-03T10:00:00Z",
            "due_date": None,
            "priority": "low",
            "status": "pending",
            "subject": "FYI",
            "sender": "colleague@example.com"
        }
    ]
    
    # Configure project lookup
    def mock_get_projects(item_id):
        if item_id == "item1":
            return ["Project A"]
        elif item_id == "item2":
            return ["Project B"]
        return []
    
    mock_neo4j.get_projects_for_action_item.side_effect = mock_get_projects
    
    # Configure assignee lookup
    def mock_get_people(item_id, rel_type):
        if item_id == "item1":
            return ["john@example.com"]
        elif item_id == "item2":
            return ["sarah@example.com"]
        return []
    
    mock_neo4j.get_people_for_action_item.side_effect = mock_get_people
    
    # Call the method
    result = processor.generate_daily_summary()
    
    # Verify Neo4j was called to get pending items
    mock_neo4j.get_action_items_by_status.assert_called_once_with("pending")
    
    # Verify the summary structure
    assert "date" in result
    assert "total_items" in result
    assert "projects" in result
    assert "items_by_project" in result
    assert "items_by_priority" in result
    assert "action_items" in result
    assert "items_by_due_date" in result
    
    # Verify the summary counts
    assert result["total_items"] == 3
    assert len(result["projects"]) == 3  # Project A, Project B, and Unassigned
    assert len(result["items_by_priority"]["high"]) == 1
    assert len(result["items_by_priority"]["medium"]) == 1
    assert len(result["items_by_priority"]["low"]) == 1
    
    # Verify projects and assignees were added
    for item in result["action_items"]:
        if item["id"] == "item1":
            assert item["project"] == "Project A"
            assert item["assignee"] == "john@example.com"
        elif item["id"] == "item2":
            assert item["project"] == "Project B"
            assert item["assignee"] == "sarah@example.com"