"""
Tests for the scheduler module.
"""
import os
import time
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call
from python_components.pipeline.scheduler import (
    Schedule, ScheduleType, PipelineScheduler
)

def test_schedule_init():
    """Test Schedule initialization."""
    # Test with minimal parameters
    schedule = Schedule(
        id="test-id",
        name="Test Schedule",
        type=ScheduleType.INTERVAL,
        target="test_target",
        interval_seconds=60
    )
    
    assert schedule.id == "test-id"
    assert schedule.name == "Test Schedule"
    assert schedule.type == ScheduleType.INTERVAL
    assert schedule.target == "test_target"
    assert schedule.interval_seconds == 60
    assert schedule.enabled is True
    assert schedule.next_run is not None
    
    # Test with all parameters
    now = datetime.now()
    schedule = Schedule(
        id="test-id",
        name="Test Schedule",
        type=ScheduleType.DAILY,
        target="test_target",
        parameters={"param1": "value1"},
        description="Test description",
        enabled=False,
        daily_time="08:00",
        last_run=now,
        runs=5,
        failures=2
    )
    
    assert schedule.id == "test-id"
    assert schedule.name == "Test Schedule"
    assert schedule.type == ScheduleType.DAILY
    assert schedule.target == "test_target"
    assert schedule.parameters == {"param1": "value1"}
    assert schedule.description == "Test description"
    assert schedule.enabled is False
    assert schedule.daily_time == "08:00"
    assert schedule.last_run == now
    assert schedule.runs == 5
    assert schedule.failures == 2
    assert schedule.next_run is None  # None because enabled is False

def test_update_next_run_interval():
    """Test updating next run time for interval schedules."""
    # Test interval schedule
    schedule = Schedule(
        id="test-interval",
        name="Test Interval",
        type=ScheduleType.INTERVAL,
        target="test_target",
        interval_seconds=60
    )
    
    now = datetime.now()
    schedule.last_run = now
    schedule.update_next_run()
    
    assert schedule.next_run is not None
    assert schedule.next_run > now
    assert schedule.next_run - now < timedelta(seconds=61)  # Allow 1 second for test execution
    
    # Test disabled schedule
    schedule.enabled = False
    schedule.update_next_run()
    assert schedule.next_run is None

def test_update_next_run_daily():
    """Test updating next run time for daily schedules."""
    # Create a daily schedule for 8:00 AM
    schedule = Schedule(
        id="test-daily",
        name="Test Daily",
        type=ScheduleType.DAILY,
        target="test_target",
        daily_time="08:00"
    )
    
    # Force update
    schedule.update_next_run()
    
    assert schedule.next_run is not None
    # Should be scheduled for 8:00 AM
    assert schedule.next_run.hour == 8
    assert schedule.next_run.minute == 0
    assert schedule.next_run.second == 0

def test_update_next_run_weekly():
    """Test updating next run time for weekly schedules."""
    # Create a weekly schedule for Monday at 8:00 AM
    schedule = Schedule(
        id="test-weekly",
        name="Test Weekly",
        type=ScheduleType.WEEKLY,
        target="test_target",
        weekly_day=0,  # Monday
        weekly_time="08:00"
    )
    
    # Force update
    schedule.update_next_run()
    
    assert schedule.next_run is not None
    # Should be scheduled for Monday at 8:00 AM
    assert schedule.next_run.weekday() == 0
    assert schedule.next_run.hour == 8
    assert schedule.next_run.minute == 0
    assert schedule.next_run.second == 0

def test_update_next_run_monthly():
    """Test updating next run time for monthly schedules."""
    # Create a monthly schedule for the 1st at 8:00 AM
    schedule = Schedule(
        id="test-monthly",
        name="Test Monthly",
        type=ScheduleType.MONTHLY,
        target="test_target",
        monthly_day=1,
        monthly_time="08:00"
    )
    
    # Force update
    schedule.update_next_run()
    
    assert schedule.next_run is not None
    # Should be scheduled for the 1st at 8:00 AM
    assert schedule.next_run.day == 1
    assert schedule.next_run.hour == 8
    assert schedule.next_run.minute == 0
    assert schedule.next_run.second == 0

def test_schedule_to_dict():
    """Test converting schedule to dictionary."""
    now = datetime.now()
    next_run = now + timedelta(hours=1)
    
    schedule = Schedule(
        id="test-id",
        name="Test Schedule",
        type=ScheduleType.INTERVAL,
        target="test_target",
        interval_seconds=60,
        last_run=now,
        next_run=next_run
    )
    
    schedule_dict = schedule.to_dict()
    
    assert schedule_dict["id"] == "test-id"
    assert schedule_dict["name"] == "Test Schedule"
    assert schedule_dict["type"] == "interval"
    assert schedule_dict["target"] == "test_target"
    assert schedule_dict["interval_seconds"] == 60
    assert schedule_dict["last_run"] == now.isoformat()
    assert schedule_dict["next_run"] == next_run.isoformat()

def test_schedule_from_dict():
    """Test creating schedule from dictionary."""
    now = datetime.now()
    next_run = now + timedelta(hours=1)
    
    schedule_dict = {
        "id": "test-id",
        "name": "Test Schedule",
        "type": "interval",
        "target": "test_target",
        "interval_seconds": 60,
        "last_run": now.isoformat(),
        "next_run": next_run.isoformat(),
        "runs": 5,
        "failures": 2
    }
    
    schedule = Schedule.from_dict(schedule_dict)
    
    assert schedule.id == "test-id"
    assert schedule.name == "Test Schedule"
    assert schedule.type == ScheduleType.INTERVAL
    assert schedule.target == "test_target"
    assert schedule.interval_seconds == 60
    assert schedule.last_run.isoformat() == now.isoformat()
    assert schedule.next_run.isoformat() == next_run.isoformat()
    assert schedule.runs == 5
    assert schedule.failures == 2

@pytest.fixture
def mock_orchestrator():
    """Create a mock PipelineOrchestrator."""
    with patch('python_components.pipeline.orchestrator.PipelineOrchestrator') as mock:
        orchestrator_instance = MagicMock()
        mock.return_value = orchestrator_instance
        yield orchestrator_instance

@pytest.fixture
def mock_queue():
    """Create a mock MessageQueue."""
    with patch('python_components.pipeline.queue.MessageQueue') as mock:
        queue_instance = MagicMock()
        mock.return_value = queue_instance
        yield queue_instance

@pytest.fixture
def scheduler(mock_orchestrator, mock_queue):
    """Create a PipelineScheduler instance with mocked dependencies."""
    # Patch the _load_default_schedules method to avoid adding default schedules
    with patch.object(PipelineScheduler, '_load_default_schedules'):
        scheduler = PipelineScheduler(
            orchestrator=mock_orchestrator,
            queue=mock_queue
        )
        yield scheduler

def test_scheduler_init(scheduler, mock_orchestrator, mock_queue):
    """Test PipelineScheduler initialization."""
    assert scheduler.orchestrator == mock_orchestrator
    assert scheduler.queue == mock_queue
    assert scheduler.schedules == {}
    assert scheduler.running is False
    assert scheduler.thread is None

def test_load_default_schedules():
    """Test loading default schedules."""
    # Create scheduler without patching _load_default_schedules
    with patch('python_components.pipeline.orchestrator.PipelineOrchestrator'):
        with patch('python_components.pipeline.queue.MessageQueue'):
            scheduler = PipelineScheduler()
            
            # Verify default schedules were loaded
            assert "email-processing" in scheduler.schedules
            assert "slack-processing" in scheduler.schedules
            assert "daily-summary" in scheduler.schedules
            
            # Verify schedule properties
            assert scheduler.schedules["email-processing"].type == ScheduleType.INTERVAL
            assert scheduler.schedules["email-processing"].interval_seconds == 600  # 10 minutes
            
            assert scheduler.schedules["slack-processing"].type == ScheduleType.INTERVAL
            assert scheduler.schedules["slack-processing"].interval_seconds == 300  # 5 minutes
            
            assert scheduler.schedules["daily-summary"].type == ScheduleType.DAILY
            assert scheduler.schedules["daily-summary"].daily_time == "08:00"

def test_add_schedule(scheduler):
    """Test adding a schedule."""
    schedule = Schedule(
        id="test-schedule",
        name="Test Schedule",
        type=ScheduleType.INTERVAL,
        target="test_target",
        interval_seconds=60
    )
    
    scheduler.add_schedule(schedule)
    
    assert "test-schedule" in scheduler.schedules
    assert scheduler.schedules["test-schedule"] == schedule

def test_remove_schedule(scheduler):
    """Test removing a schedule."""
    # Add a schedule
    schedule = Schedule(
        id="test-schedule",
        name="Test Schedule",
        type=ScheduleType.INTERVAL,
        target="test_target",
        interval_seconds=60
    )
    scheduler.schedules["test-schedule"] = schedule
    
    # Remove the schedule
    result = scheduler.remove_schedule("test-schedule")
    
    assert result is True
    assert "test-schedule" not in scheduler.schedules
    
    # Try to remove a non-existent schedule
    result = scheduler.remove_schedule("nonexistent")
    
    assert result is False

def test_get_schedule(scheduler):
    """Test getting a schedule by ID."""
    # Add a schedule
    schedule = Schedule(
        id="test-schedule",
        name="Test Schedule",
        type=ScheduleType.INTERVAL,
        target="test_target",
        interval_seconds=60
    )
    scheduler.schedules["test-schedule"] = schedule
    
    # Get the schedule
    result = scheduler.get_schedule("test-schedule")
    
    assert result == schedule
    
    # Try to get a non-existent schedule
    result = scheduler.get_schedule("nonexistent")
    
    assert result is None

def test_get_schedules(scheduler):
    """Test getting all schedules."""
    # Add some schedules
    schedule1 = Schedule(
        id="schedule1",
        name="Schedule 1",
        type=ScheduleType.INTERVAL,
        target="target1",
        interval_seconds=60
    )
    schedule2 = Schedule(
        id="schedule2",
        name="Schedule 2",
        type=ScheduleType.DAILY,
        target="target2",
        daily_time="08:00"
    )
    
    scheduler.schedules["schedule1"] = schedule1
    scheduler.schedules["schedule2"] = schedule2
    
    # Get all schedules
    result = scheduler.get_schedules()
    
    assert len(result) == 2
    assert schedule1 in result
    assert schedule2 in result

def test_update_schedule(scheduler):
    """Test updating a schedule."""
    # Add a schedule
    schedule = Schedule(
        id="test-schedule",
        name="Test Schedule",
        type=ScheduleType.INTERVAL,
        target="test_target",
        interval_seconds=60
    )
    scheduler.schedules["test-schedule"] = schedule
    
    # Update the schedule
    result = scheduler.update_schedule("test-schedule", {
        "name": "Updated Schedule",
        "interval_seconds": 120
    })
    
    assert result is True
    assert scheduler.schedules["test-schedule"].name == "Updated Schedule"
    assert scheduler.schedules["test-schedule"].interval_seconds == 120
    
    # Try to update a non-existent schedule
    result = scheduler.update_schedule("nonexistent", {"name": "New Name"})
    
    assert result is False

def test_enable_disable_schedule(scheduler):
    """Test enabling and disabling a schedule."""
    # Add a schedule
    schedule = Schedule(
        id="test-schedule",
        name="Test Schedule",
        type=ScheduleType.INTERVAL,
        target="test_target",
        interval_seconds=60,
        enabled=False
    )
    scheduler.schedules["test-schedule"] = schedule
    
    # Enable the schedule
    result = scheduler.enable_schedule("test-schedule")
    
    assert result is True
    assert scheduler.schedules["test-schedule"].enabled is True
    assert scheduler.schedules["test-schedule"].next_run is not None
    
    # Disable the schedule
    result = scheduler.disable_schedule("test-schedule")
    
    assert result is True
    assert scheduler.schedules["test-schedule"].enabled is False
    assert scheduler.schedules["test-schedule"].next_run is None
    
    # Try to enable/disable a non-existent schedule
    assert scheduler.enable_schedule("nonexistent") is False
    assert scheduler.disable_schedule("nonexistent") is False

def test_start_and_stop(scheduler, mock_queue):
    """Test starting and stopping the scheduler."""
    with patch.object(scheduler, '_scheduler_loop') as mock_loop:
        # Test non-blocking start
        scheduler.start(blocking=False)
        
        assert scheduler.running is True
        assert scheduler.thread is not None
        assert scheduler.thread.daemon is True
        
        # Verify the queue was started
        mock_queue.start.assert_called_once_with(blocking=False)
        
        # Verify handlers were registered
        assert mock_queue.register_handler.call_count == 3  # 3 handlers
        
        # Test stop
        scheduler.stop()
        
        assert scheduler.running is False
        
        # Verify the thread was joined
        # Note: Can't easily verify thread.join was called without mocking threading
        
        # Verify _scheduler_loop wasn't called directly (since we're in non-blocking mode)
        mock_loop.assert_not_called()

def test_run_now(scheduler, mock_queue):
    """Test running a schedule immediately."""
    # Add a schedule
    schedule = Schedule(
        id="test-schedule",
        name="Test Schedule",
        type=ScheduleType.INTERVAL,
        target="test_target",
        interval_seconds=60
    )
    scheduler.schedules["test-schedule"] = schedule
    
    # Run the schedule
    result = scheduler.run_now("test-schedule")
    
    assert result is True
    
    # Verify the task was enqueued
    mock_queue.enqueue.assert_called_once()
    
    # Verify schedule stats were updated
    assert schedule.last_run is not None
    assert schedule.runs == 1
    
    # Try to run a non-existent schedule
    result = scheduler.run_now("nonexistent")
    
    assert result is False
    
    # Try to run a disabled schedule
    schedule.enabled = False
    result = scheduler.run_now("test-schedule")
    
    assert result is False

def test_scheduler_loop(scheduler, mock_queue):
    """Test the scheduler loop."""
    # Add a schedule that's due to run
    now = datetime.now()
    past_time = now - timedelta(minutes=5)
    
    schedule = Schedule(
        id="test-schedule",
        name="Test Schedule",
        type=ScheduleType.INTERVAL,
        target="test_target",
        interval_seconds=60,
        next_run=past_time  # In the past so it will run immediately
    )
    scheduler.schedules["test-schedule"] = schedule
    
    # Mock time.sleep to avoid delay
    with patch('time.sleep'):
        # Set up the loop to run once then stop
        scheduler.running = True
        
        def stop_after_one_iteration(*args, **kwargs):
            scheduler.running = False
        
        # Patch _enqueue_task to stop the loop after one iteration
        with patch.object(scheduler, '_enqueue_task', side_effect=stop_after_one_iteration) as mock_enqueue:
            # Run the loop
            scheduler._scheduler_loop()
            
            # Verify _enqueue_task was called for the schedule
            mock_enqueue.assert_called_once_with(schedule)
            
            # Verify schedule stats were updated
            assert schedule.last_run is not None
            assert schedule.runs == 1
            assert schedule.next_run > now  # Next run should be in the future

def test_enqueue_task(scheduler, mock_queue):
    """Test enqueueing a scheduled task."""
    # Create a schedule
    schedule = Schedule(
        id="test-schedule",
        name="Test Schedule",
        type=ScheduleType.INTERVAL,
        target="test_target",
        interval_seconds=60,
        parameters={"param1": "value1"}
    )
    
    # Enqueue the task
    scheduler._enqueue_task(schedule)
    
    # Verify the task was enqueued correctly
    mock_queue.enqueue.assert_called_once()
    
    # Extract the call arguments
    args, kwargs = mock_queue.enqueue.call_args
    
    # Verify the arguments
    assert kwargs["message_type"] == "test_target"
    assert kwargs["priority"] == 1  # High priority
    assert "param1" in kwargs["data"]
    assert kwargs["data"]["param1"] == "value1"
    assert "schedule_id" in kwargs["data"]
    assert kwargs["data"]["schedule_id"] == "test-schedule"

def test_handler_methods(scheduler, mock_orchestrator):
    """Test the message handler methods."""
    # Create a test message
    class TestMessage:
        id = "test-message"
        data = {
            "maxResults": 10,
            "filter": "isRead eq false"
        }
    
    message = TestMessage()
    
    # Mock the process_email method to return a context
    mock_context = MagicMock()
    mock_context.status = "completed"
    mock_context.id = "test-context"
    mock_orchestrator.process_email.return_value = mock_context
    
    # Mock asyncio.new_event_loop
    mock_loop = MagicMock()
    mock_loop.run_until_complete.return_value = mock_context
    mock_loop.close = MagicMock()
    
    with patch('asyncio.new_event_loop', return_value=mock_loop):
        # Call the handler
        scheduler._handle_process_email(message)
        
        # Verify orchestrator.process_email was called with correct args
        mock_orchestrator.process_email.assert_called_once_with({
            "maxResults": 10,
            "filter": "isRead eq false"
        })
        
        # Verify the loop was closed
        mock_loop.close.assert_called_once()