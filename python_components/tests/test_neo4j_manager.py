"""
Tests for the Neo4j manager module.
"""
import pytest
import os
from unittest.mock import patch, MagicMock
from python_components.utils.neo4j_manager import Neo4jManager

@pytest.fixture
def mock_env_vars():
    """Set up mock environment variables for testing."""
    os.environ["NEO4J_URI"] = "bolt://localhost:7687"
    os.environ["NEO4J_USER"] = "neo4j"
    os.environ["NEO4J_PASSWORD"] = "password"
    yield
    # Clean up
    del os.environ["NEO4J_URI"]
    del os.environ["NEO4J_USER"]
    del os.environ["NEO4J_PASSWORD"]

@pytest.fixture
def mock_driver():
    """Create a mock Neo4j driver."""
    with patch('neo4j.GraphDatabase.driver') as mock:
        driver_instance = MagicMock()
        mock.return_value = driver_instance
        yield mock

@pytest.fixture
def neo4j_manager(mock_env_vars, mock_driver):
    """Create a Neo4jManager instance with mocked dependencies."""
    manager = Neo4jManager()
    return manager

def test_init(neo4j_manager, mock_driver):
    """Test Neo4jManager initialization."""
    assert neo4j_manager.uri == "bolt://localhost:7687"
    assert neo4j_manager.user == "neo4j"
    assert neo4j_manager.password == "password"
    mock_driver.assert_called_once_with(
        "bolt://localhost:7687", auth=("neo4j", "password")
    )

def test_close(neo4j_manager):
    """Test Neo4jManager close method."""
    neo4j_manager.close()
    neo4j_manager.driver.close.assert_called_once()

def test_get_session(neo4j_manager):
    """Test Neo4jManager get_session method."""
    session = neo4j_manager.get_session()
    neo4j_manager.driver.session.assert_called_once()
    assert session == neo4j_manager.driver.session.return_value

def test_create_action_item(neo4j_manager):
    """Test creating an action item in Neo4j."""
    # Create a mock session
    mock_session = MagicMock()
    neo4j_manager.get_session = MagicMock(return_value=mock_session)
    
    # Create a mock result
    mock_result = MagicMock()
    mock_record = MagicMock()
    mock_record.__getitem__.return_value = "test-id"
    mock_result.single.return_value = mock_record
    mock_session.__enter__.return_value.run.return_value = mock_result
    
    # Test data
    action_item = {
        "id": "test-id",
        "content": "Test action item",
        "source": "email",
        "source_id": "123",
        "created_at": "2023-05-01T12:00:00Z",
        "due_date": None,
        "priority": "high",
        "status": "pending"
    }
    
    # Call the method
    result = neo4j_manager.create_action_item(action_item)
    
    # Verify the result
    assert result == "test-id"
    mock_session.__enter__.return_value.run.assert_called_once()

def test_link_action_to_person(neo4j_manager):
    """Test linking an action item to a person in Neo4j."""
    # Create a mock session
    mock_session = MagicMock()
    neo4j_manager.get_session = MagicMock(return_value=mock_session)
    
    # Call the method
    neo4j_manager.link_action_to_person("test-id", "test@example.com", "ASSIGNED_TO")
    
    # Verify the call
    mock_session.__enter__.return_value.run.assert_called_once()
    call_args = mock_session.__enter__.return_value.run.call_args[0]
    assert "MATCH (a:ActionItem {id: $action_id})" in call_args[0]
    assert call_args[1]["action_id"] == "test-id"
    assert call_args[1]["person_email"] == "test@example.com"
    assert call_args[1]["relationship_type"] == "ASSIGNED_TO"

def test_get_action_items_by_status(neo4j_manager):
    """Test getting action items by status from Neo4j."""
    # Create a mock session
    mock_session = MagicMock()
    neo4j_manager.get_session = MagicMock(return_value=mock_session)
    
    # Create mock results
    mock_record1 = MagicMock()
    mock_record1.__getitem__.return_value = {"id": "1", "content": "Task 1"}
    mock_record2 = MagicMock()
    mock_record2.__getitem__.return_value = {"id": "2", "content": "Task 2"}
    mock_session.__enter__.return_value.run.return_value = [mock_record1, mock_record2]
    
    # Call the method
    result = neo4j_manager.get_action_items_by_status("pending")
    
    # Verify the result
    assert len(result) == 2
    assert result[0] == {"id": "1", "content": "Task 1"}
    assert result[1] == {"id": "2", "content": "Task 2"}
    mock_session.__enter__.return_value.run.assert_called_once_with(
        """
                MATCH (a:ActionItem {status: $status})
                RETURN a
                ORDER BY a.priority, a.created_at
            """,
        {"status": "pending"}
    )