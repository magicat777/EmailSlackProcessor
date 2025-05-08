"""
Tests for the error handling and retry logic.
"""
import pytest
import time
import asyncio
from unittest.mock import patch, MagicMock, call
from python_components.pipeline.errors import (
    PipelineError, TemporaryError, PermanentError, ResourceNotFoundError,
    ConfigurationError, APIError, with_retry, with_async_retry,
    create_error_report, log_error
)

def test_pipeline_error_init():
    """Test PipelineError initialization."""
    # Test with just a message
    error = PipelineError("Test error")
    assert error.message == "Test error"
    assert error.original_error is None
    assert error.timestamp is not None
    
    # Test with an original error
    original = ValueError("Original error")
    error = PipelineError("Wrapped error", original)
    assert error.message == "Wrapped error"
    assert error.original_error == original
    assert error.timestamp is not None

def test_api_error_init():
    """Test APIError initialization."""
    # Test with minimal parameters
    error = APIError("API Error")
    assert error.message == "API Error"
    assert error.original_error is None
    assert error.status_code is None
    assert error.service is None
    
    # Test with all parameters
    original = ValueError("Original error")
    error = APIError("API Error", original, 429, "Test Service")
    assert error.message == "API Error"
    assert error.original_error == original
    assert error.status_code == 429
    assert error.service == "Test Service"
    
def test_api_error_is_temporary():
    """Test APIError.is_temporary method."""
    # Test with no status code (should default to temporary)
    error = APIError("API Error")
    assert error.is_temporary() is True
    
    # Test with client error (400) - should be permanent
    error = APIError("Client Error", status_code=400)
    assert error.is_temporary() is False
    
    # Test with rate limit error (429) - should be temporary
    error = APIError("Rate Limit", status_code=429)
    assert error.is_temporary() is True
    
    # Test with server error (500) - should be temporary
    error = APIError("Server Error", status_code=500)
    assert error.is_temporary() is True

def test_api_error_should_retry():
    """Test APIError.should_retry method."""
    # Should retry if is_temporary returns True
    error = APIError("Rate Limit", status_code=429)
    assert error.should_retry() is True
    
    # Should not retry if is_temporary returns False
    error = APIError("Client Error", status_code=400)
    assert error.should_retry() is False

def test_with_retry_success():
    """Test the with_retry decorator with successful execution."""
    # Create a test function
    mock_func = MagicMock()
    mock_func.return_value = "success"
    
    # Apply the decorator
    decorated = with_retry()(mock_func)
    
    # Call the decorated function
    result = decorated()
    
    # Verify the result
    assert result == "success"
    mock_func.assert_called_once()

def test_with_retry_temporary_error():
    """Test the with_retry decorator with temporary errors."""
    # Create a test function that fails twice then succeeds
    mock_func = MagicMock()
    mock_func.side_effect = [
        TemporaryError("Temporary error 1"),
        TemporaryError("Temporary error 2"),
        "success"
    ]
    
    # Mock sleep to avoid delays in tests
    with patch('time.sleep') as mock_sleep:
        # Apply the decorator
        decorated = with_retry(max_attempts=3, base_delay=0.1)(mock_func)
        
        # Call the decorated function
        result = decorated()
        
        # Verify the result
        assert result == "success"
        assert mock_func.call_count == 3
        assert mock_sleep.call_count == 2

def test_with_retry_permanent_error():
    """Test the with_retry decorator with permanent errors."""
    # Create a test function that fails with a permanent error
    mock_func = MagicMock()
    mock_func.side_effect = PermanentError("Permanent error")
    
    # Apply the decorator
    decorated = with_retry()(mock_func)
    
    # Call the decorated function
    with pytest.raises(PermanentError, match="Permanent error"):
        decorated()
    
    # Verify the function was called only once
    mock_func.assert_called_once()

def test_with_retry_max_attempts():
    """Test the with_retry decorator with maximum attempts reached."""
    # Create a test function that always fails with a temporary error
    mock_func = MagicMock()
    mock_func.side_effect = TemporaryError("Always fails")
    
    # Mock sleep to avoid delays in tests
    with patch('time.sleep'):
        # Apply the decorator
        decorated = with_retry(max_attempts=3)(mock_func)
        
        # Call the decorated function
        with pytest.raises(TemporaryError, match="Always fails"):
            decorated()
        
        # Verify the function was called the maximum number of times
        assert mock_func.call_count == 3

def test_with_retry_custom_exceptions():
    """Test the with_retry decorator with custom retryable exceptions."""
    # Create a test function that fails with a custom exception then succeeds
    mock_func = MagicMock()
    mock_func.side_effect = [
        ValueError("Custom error"),
        "success"
    ]
    
    # Mock sleep to avoid delays in tests
    with patch('time.sleep'):
        # Apply the decorator with custom retryable exceptions
        decorated = with_retry(retryable_exceptions=[ValueError])(mock_func)
        
        # Call the decorated function
        result = decorated()
        
        # Verify the result
        assert result == "success"
        assert mock_func.call_count == 2

def test_with_retry_exponential_backoff():
    """Test that with_retry applies exponential backoff."""
    # Create a test function that fails multiple times
    mock_func = MagicMock()
    mock_func.side_effect = [
        TemporaryError("Error 1"),
        TemporaryError("Error 2"),
        TemporaryError("Error 3"),
        "success"
    ]
    
    # Mock sleep to capture delay values
    sleep_times = []
    
    def mock_sleep_func(seconds):
        sleep_times.append(seconds)
    
    with patch('time.sleep', side_effect=mock_sleep_func):
        # Apply the decorator with specific backoff parameters
        # Remove jitter for predictable testing
        decorated = with_retry(
            max_attempts=4, 
            base_delay=1.0, 
            backoff_factor=2.0,
            jitter=0.0
        )(mock_func)
        
        # Call the decorated function
        result = decorated()
        
        # Verify the result
        assert result == "success"
        assert mock_func.call_count == 4
        
        # Verify exponential backoff was applied (1.0, 2.0, 4.0)
        assert len(sleep_times) == 3
        assert sleep_times[0] == 1.0
        assert sleep_times[1] == 2.0
        assert sleep_times[2] == 4.0

@pytest.mark.asyncio
async def test_with_async_retry():
    """Test the with_async_retry function."""
    # Create a mock async function that fails twice then succeeds
    mock_func = MagicMock()
    mock_func.__name__ = "mock_async_func"  # For better error messages
    
    async def mock_async():
        return mock_func()
    
    mock_func.side_effect = [
        TemporaryError("Async error 1"),
        TemporaryError("Async error 2"),
        "async success"
    ]
    
    # Mock asyncio.sleep to avoid delays in tests
    with patch('asyncio.sleep', return_value=None):
        # Call the function with retry
        result = await with_async_retry(
            mock_async, 
            max_attempts=3, 
            base_delay=0.1,
            jitter=0.0
        )
        
        # Verify the result
        assert result == "async success"
        assert mock_func.call_count == 3

def test_create_error_report():
    """Test creating an error report."""
    # Create a test error
    original = ValueError("Original error")
    error = APIError("API Error", original, 429, "Test Service")
    
    # Create a context
    context = {"function": "test_function", "input": "test_input"}
    
    # Create the report
    report = create_error_report(error, context)
    
    # Verify the report
    assert report["error_type"] == "APIError"
    assert report["error_message"] == "API Error"
    assert "traceback" in report
    assert report["original_error"]["type"] == "ValueError"
    assert report["original_error"]["message"] == "Original error"
    assert report["status_code"] == 429
    assert report["service"] == "Test Service"
    assert report["context"] == context

def test_log_error():
    """Test the log_error function."""
    # Create errors of different types
    permanent_error = PermanentError("Permanent error")
    temporary_error = TemporaryError("Temporary error")
    regular_error = Exception("Regular error")
    
    # Mock the logger
    with patch('python_components.pipeline.errors.logger') as mock_logger:
        # Log the errors
        log_error(permanent_error)
        log_error(temporary_error)
        log_error(regular_error)
        
        # Verify logging levels were correct
        assert mock_logger.log.call_args_list[0][0][0] == 40  # ERROR for PermanentError
        assert mock_logger.log.call_args_list[1][0][0] == 30  # WARNING for TemporaryError
        assert mock_logger.log.call_args_list[2][0][0] == 40  # ERROR for other exceptions