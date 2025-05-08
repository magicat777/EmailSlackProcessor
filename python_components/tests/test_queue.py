"""
Tests for the queue module.
"""
import os
import json
import time
import asyncio
import tempfile
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call
from python_components.pipeline.queue import Message, MessageQueue, AsyncMessageQueue

def test_message_init():
    """Test Message initialization."""
    # Test with minimal parameters
    message = Message(
        id="test-id",
        type="test-type",
        data={"key": "value"}
    )
    
    assert message.id == "test-id"
    assert message.type == "test-type"
    assert message.data == {"key": "value"}
    assert message.priority == 2  # Default priority
    assert message.created_at is not None
    assert message.processed is False
    assert message.retry_count == 0
    assert message.max_retries == 3
    assert message.scheduled_time is None
    assert message.error is None
    
    # Test with all parameters
    now = datetime.now()
    scheduled = now + timedelta(minutes=5)
    
    message = Message(
        id="test-id",
        type="test-type",
        data={"key": "value"},
        priority=1,
        created_at=now,
        processed=True,
        retry_count=2,
        max_retries=5,
        scheduled_time=scheduled,
        error="Test error"
    )
    
    assert message.id == "test-id"
    assert message.type == "test-type"
    assert message.data == {"key": "value"}
    assert message.priority == 1
    assert message.created_at == now
    assert message.processed is True
    assert message.retry_count == 2
    assert message.max_retries == 5
    assert message.scheduled_time == scheduled
    assert message.error == "Test error"

def test_message_to_dict():
    """Test converting message to dictionary."""
    now = datetime.now()
    scheduled = now + timedelta(minutes=5)
    
    message = Message(
        id="test-id",
        type="test-type",
        data={"key": "value"},
        priority=1,
        created_at=now,
        scheduled_time=scheduled
    )
    
    message_dict = message.to_dict()
    
    assert message_dict["id"] == "test-id"
    assert message_dict["type"] == "test-type"
    assert message_dict["data"] == {"key": "value"}
    assert message_dict["priority"] == 1
    assert message_dict["created_at"] == now.isoformat()
    assert message_dict["scheduled_time"] == scheduled.isoformat()

def test_message_from_dict():
    """Test creating message from dictionary."""
    now = datetime.now()
    now_str = now.isoformat()
    scheduled = now + timedelta(minutes=5)
    scheduled_str = scheduled.isoformat()
    
    message_dict = {
        "id": "test-id",
        "type": "test-type",
        "data": {"key": "value"},
        "priority": 1,
        "created_at": now_str,
        "processed": True,
        "retry_count": 2,
        "max_retries": 5,
        "scheduled_time": scheduled_str,
        "error": "Test error"
    }
    
    message = Message.from_dict(message_dict)
    
    assert message.id == "test-id"
    assert message.type == "test-type"
    assert message.data == {"key": "value"}
    assert message.priority == 1
    assert message.created_at.isoformat() == now_str  # Compare as ISO strings for simplicity
    assert message.processed is True
    assert message.retry_count == 2
    assert message.max_retries == 5
    assert message.scheduled_time.isoformat() == scheduled_str
    assert message.error == "Test error"

def test_message_is_ready():
    """Test message is_ready method."""
    # Test with no scheduled time
    message = Message(
        id="test-id",
        type="test-type",
        data={"key": "value"}
    )
    assert message.is_ready() is True
    
    # Test with future scheduled time
    now = datetime.now()
    message.scheduled_time = now + timedelta(minutes=5)
    assert message.is_ready() is False
    
    # Test with past scheduled time
    message.scheduled_time = now - timedelta(minutes=5)
    assert message.is_ready() is True

def test_message_comparison():
    """Test message comparison for priority queue."""
    now = datetime.now()
    
    # Create messages with different priorities
    high_priority = Message(
        id="high",
        type="test",
        data={},
        priority=1,
        created_at=now
    )
    
    medium_priority = Message(
        id="medium",
        type="test",
        data={},
        priority=2,
        created_at=now
    )
    
    # Compare by priority
    assert high_priority < medium_priority
    
    # Create messages with same priority but different creation times
    earlier = Message(
        id="earlier",
        type="test",
        data={},
        priority=1,
        created_at=now - timedelta(minutes=5)
    )
    
    later = Message(
        id="later",
        type="test",
        data={},
        priority=1,
        created_at=now
    )
    
    # Compare by creation time
    assert earlier < later
    
    # Create messages with scheduled times
    scheduled_earlier = Message(
        id="scheduled-earlier",
        type="test",
        data={},
        priority=1,
        scheduled_time=now + timedelta(minutes=5)
    )
    
    scheduled_later = Message(
        id="scheduled-later",
        type="test",
        data={},
        priority=1,
        scheduled_time=now + timedelta(minutes=10)
    )
    
    # Compare by scheduled time
    assert scheduled_earlier < scheduled_later

def test_queue_init():
    """Test MessageQueue initialization."""
    # Test with default parameters
    queue = MessageQueue()
    assert queue.persistence_file is None
    assert queue.max_messages == 1000
    assert queue.persistence_interval == 60
    assert queue.running is False
    assert queue.message_count == 0
    
    # Test with custom parameters
    queue = MessageQueue(
        persistence_file="test.json",
        max_messages=500,
        persistence_interval=30
    )
    assert queue.persistence_file == "test.json"
    assert queue.max_messages == 500
    assert queue.persistence_interval == 30

def test_register_handler():
    """Test registering message handlers."""
    queue = MessageQueue()
    
    # Register a handler
    handler = MagicMock()
    queue.register_handler("test-type", handler)
    
    assert "test-type" in queue.handlers
    assert len(queue.handlers["test-type"]) == 1
    assert queue.handlers["test-type"][0] is handler
    
    # Register a second handler for the same type
    handler2 = MagicMock()
    queue.register_handler("test-type", handler2)
    
    assert len(queue.handlers["test-type"]) == 2
    assert queue.handlers["test-type"][1] is handler2

def test_enqueue():
    """Test enqueuing messages."""
    queue = MessageQueue()
    
    # Enqueue a message
    message_id = queue.enqueue(
        message_type="test-type",
        data={"key": "value"}
    )
    
    assert isinstance(message_id, str)
    assert queue.message_count == 1
    assert queue.stats["enqueued"] == 1
    assert message_id in queue.message_ids
    assert queue.queue.qsize() == 1
    
    # Get the message from the queue and verify it
    message = queue.queue.get()
    assert message.id == message_id
    assert message.type == "test-type"
    assert message.data == {"key": "value"}
    assert message.priority == 2

def test_enqueue_batch():
    """Test enqueuing message batches."""
    queue = MessageQueue()
    
    # Create a batch of messages
    messages = [
        {
            "type": "type1",
            "data": {"key": "value1"},
            "priority": 1
        },
        {
            "type": "type2",
            "data": {"key": "value2"},
            "priority": 3
        }
    ]
    
    # Enqueue the batch
    message_ids = queue.enqueue_batch(messages)
    
    assert len(message_ids) == 2
    assert queue.message_count == 2
    assert queue.stats["enqueued"] == 2
    assert queue.queue.qsize() == 2
    
    # Verify the messages in the queue
    # High priority message should come out first
    message1 = queue.queue.get()
    assert message1.type == "type1"
    assert message1.priority == 1
    
    message2 = queue.queue.get()
    assert message2.type == "type2"
    assert message2.priority == 3

def test_start_and_stop():
    """Test starting and stopping the queue."""
    queue = MessageQueue()
    
    with patch.object(queue, '_process_loop') as mock_process_loop:
        # Test non-blocking start
        queue.start(blocking=False)
        assert queue.running is True
        assert hasattr(queue, 'thread')
        assert queue.thread.daemon is True
        assert queue.thread.is_alive()
        
        # Test stop
        queue.stop()
        assert queue.running is False
        
        # Verify process_loop wasn't called directly
        mock_process_loop.assert_not_called()

def test_persistence():
    """Test queue persistence to file."""
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        temp_file = temp.name
    
    try:
        # Create a queue with persistence
        queue = MessageQueue(persistence_file=temp_file)
        
        # Add some messages
        queue.enqueue("test-type", {"key": "value1"})
        queue.enqueue("test-type", {"key": "value2"})
        
        # Manually persist
        queue._persist_to_file()
        
        # Verify the file exists and has content
        assert os.path.exists(temp_file)
        with open(temp_file, 'r') as f:
            data = json.load(f)
            
        assert "queue" in data
        assert "processed" in data
        assert "stats" in data
        assert "timestamp" in data
        assert len(data["queue"]) == 2
        
        # Create a new queue to test loading
        new_queue = MessageQueue(persistence_file=temp_file)
        assert new_queue.queue.qsize() == 2
        assert new_queue.message_count == 2
        
    finally:
        # Clean up
        try:
            os.unlink(temp_file)
        except:
            pass

@pytest.mark.asyncio
async def test_async_message_queue():
    """Test the async message queue wrapper."""
    # Create an async queue
    async_queue = AsyncMessageQueue()
    
    # Register a handler
    handler = MagicMock()
    await async_queue.register_handler("test-type", handler)
    
    # Enqueue a message
    message_id = await async_queue.enqueue(
        message_type="test-type",
        data={"key": "value"}
    )
    
    assert isinstance(message_id, str)
    
    # Enqueue a batch
    messages = [
        {
            "type": "type1",
            "data": {"key": "value1"}
        },
        {
            "type": "type2",
            "data": {"key": "value2"}
        }
    ]
    
    message_ids = await async_queue.enqueue_batch(messages)
    assert len(message_ids) == 2
    
    # Start and stop the queue
    await async_queue.start()
    assert async_queue.queue.running is True
    
    # Get stats
    stats = await async_queue.get_stats()
    assert "enqueued" in stats
    assert stats["enqueued"] == 3  # 1 + 2 from batch
    
    # Stop the queue
    await async_queue.stop()
    assert async_queue.queue.running is False

def test_process_loop_handlers():
    """Test the message processing loop with handlers."""
    queue = MessageQueue()
    
    # Register handlers
    success_handler = MagicMock()
    failure_handler = MagicMock(side_effect=Exception("Test failure"))
    
    queue.register_handler("success-type", success_handler)
    queue.register_handler("failure-type", failure_handler)
    
    # Add test messages
    success_id = queue.enqueue("success-type", {"key": "success"})
    failure_id = queue.enqueue("failure-type", {"key": "failure"})
    
    # Mock run the processing loop for a few iterations
    with patch('time.sleep'):  # Avoid actual sleeps in tests
        queue.running = True
        
        # Process messages for a limited number of iterations
        iterations = 0
        while queue.queue.qsize() > 0 and iterations < 10:
            queue._process_loop()
            iterations += 1
            if iterations >= 10:  # Safety to avoid infinite loop
                queue.running = False
    
    # Verify handlers were called
    success_handler.assert_called_once()
    failure_handler.assert_called_once()
    
    # Verify stats
    assert queue.stats["processed"] >= 1  # Success message processed
    assert queue.stats["retried"] >= 1  # Failure message retried
    
    # Verify processed list
    assert len(queue.processed) >= 1