"""
Error handling and retry logic for ICAP pipeline.
"""
import time
import logging
import traceback
import functools
from typing import Dict, Any, List, Optional, Callable, Type, Union, TypeVar
from datetime import datetime, timedelta

logger = logging.getLogger("icap.errors")

# Type variable for function return types
T = TypeVar('T')

class PipelineError(Exception):
    """Base class for pipeline errors."""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.message = message
        self.original_error = original_error
        self.timestamp = datetime.now()
        super().__init__(message)

class TemporaryError(PipelineError):
    """Error that can be retried (e.g., network errors, temporary service outages)."""
    pass

class PermanentError(PipelineError):
    """Error that should not be retried (e.g., authentication errors, invalid input)."""
    pass

class ResourceNotFoundError(PermanentError):
    """Error when a resource is not found (e.g., missing email, Slack message)."""
    pass

class ConfigurationError(PermanentError):
    """Error with the system configuration (e.g., missing API keys)."""
    pass

class APIError(PipelineError):
    """Error from external API."""
    def __init__(self, message: str, original_error: Optional[Exception] = None, 
                status_code: Optional[int] = None, service: Optional[str] = None):
        super().__init__(message, original_error)
        self.status_code = status_code
        self.service = service
        
    def is_temporary(self) -> bool:
        """Check if this API error is likely temporary (e.g., rate limits, server errors)."""
        if self.status_code:
            # 4xx errors are generally permanent (except for 429)
            if 400 <= self.status_code < 500 and self.status_code != 429:
                return False
            # 429 (rate limits) and 5xx errors are generally temporary
            if self.status_code == 429 or self.status_code >= 500:
                return True
        
        # Default to assuming it's a temporary error
        return True
    
    def should_retry(self) -> bool:
        """Determine if the error should be retried."""
        return self.is_temporary()

def with_retry(max_attempts: int = 3, 
              base_delay: float = 1.0, 
              max_delay: float = 60.0,
              backoff_factor: float = 2.0, 
              jitter: float = 0.1,
              retryable_exceptions: List[Type[Exception]] = None) -> Callable:
    """
    Decorator to add retry logic to a function.
    
    Args:
        max_attempts: Maximum number of attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_factor: Factor to increase delay by after each failure
        jitter: Random factor to add to delay to avoid thundering herd
        retryable_exceptions: List of exceptions to retry on. If None, retries on TemporaryError
                            and exceptions with a should_retry() method that returns True
                            
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            attempt = 0
            delay = base_delay
            
            while True:
                attempt += 1
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Check if the exception is retryable
                    should_retry = False
                    
                    # If specific exceptions were provided, check if this is one of them
                    if retryable_exceptions is not None:
                        should_retry = isinstance(e, tuple(retryable_exceptions))
                    else:
                        # Otherwise, check if it's a TemporaryError or has a should_retry method
                        should_retry = (
                            isinstance(e, TemporaryError) or 
                            (hasattr(e, "should_retry") and e.should_retry())
                        )
                    
                    # If not retryable or we've hit the max attempts, re-raise
                    if not should_retry or attempt >= max_attempts:
                        # If it's a PipelineError, re-raise it directly
                        if isinstance(e, PipelineError):
                            raise
                        
                        # Otherwise, wrap it in a PipelineError
                        error_message = f"Failed after {attempt} attempts: {str(e)}"
                        if hasattr(e, "status_code") and hasattr(e, "service"):
                            raise APIError(error_message, e, getattr(e, "status_code"), getattr(e, "service"))
                        else:
                            raise PipelineError(error_message, e)
                    
                    # Calculate delay with exponential backoff and jitter
                    jitter_amount = jitter * delay * (2 * (0.5 - time.random()))
                    actual_delay = min(delay + jitter_amount, max_delay)
                    
                    # Log the retry
                    logger.warning(
                        f"Retry {attempt}/{max_attempts} after {actual_delay:.2f}s "
                        f"due to {e.__class__.__name__}: {str(e)}"
                    )
                    
                    # Sleep before retrying
                    time.sleep(actual_delay)
                    
                    # Increase delay for next retry
                    delay = min(delay * backoff_factor, max_delay)
        return wrapper
    return decorator

async def with_async_retry(func, *args, 
                        max_attempts: int = 3, 
                        base_delay: float = 1.0, 
                        max_delay: float = 60.0,
                        backoff_factor: float = 2.0, 
                        jitter: float = 0.1,
                        retryable_exceptions: List[Type[Exception]] = None,
                        **kwargs):
    """
    Asynchronous retry logic for calling async functions.
    
    Args:
        func: Async function to call
        args: Positional arguments to pass to the function
        max_attempts: Maximum number of attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_factor: Factor to increase delay by after each failure
        jitter: Random factor to add to delay to avoid thundering herd
        retryable_exceptions: List of exceptions to retry on. If None, retries on TemporaryError
                            and exceptions with a should_retry() method that returns True
        kwargs: Keyword arguments to pass to the function
        
    Returns:
        Result from the function
        
    Raises:
        Exception: If all retries fail
    """
    import asyncio
    
    attempt = 0
    delay = base_delay
    
    while True:
        attempt += 1
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # Check if the exception is retryable
            should_retry = False
            
            # If specific exceptions were provided, check if this is one of them
            if retryable_exceptions is not None:
                should_retry = isinstance(e, tuple(retryable_exceptions))
            else:
                # Otherwise, check if it's a TemporaryError or has a should_retry method
                should_retry = (
                    isinstance(e, TemporaryError) or 
                    (hasattr(e, "should_retry") and e.should_retry())
                )
            
            # If not retryable or we've hit the max attempts, re-raise
            if not should_retry or attempt >= max_attempts:
                # If it's a PipelineError, re-raise it directly
                if isinstance(e, PipelineError):
                    raise
                
                # Otherwise, wrap it in a PipelineError
                error_message = f"Failed after {attempt} attempts: {str(e)}"
                if hasattr(e, "status_code") and hasattr(e, "service"):
                    raise APIError(error_message, e, getattr(e, "status_code"), getattr(e, "service"))
                else:
                    raise PipelineError(error_message, e)
            
            # Calculate delay with exponential backoff and jitter
            jitter_amount = jitter * delay * (2 * (0.5 - time.random()))
            actual_delay = min(delay + jitter_amount, max_delay)
            
            # Log the retry
            logger.warning(
                f"Async retry {attempt}/{max_attempts} after {actual_delay:.2f}s "
                f"due to {e.__class__.__name__}: {str(e)}"
            )
            
            # Sleep before retrying
            await asyncio.sleep(actual_delay)
            
            # Increase delay for next retry
            delay = min(delay * backoff_factor, max_delay)

def create_error_report(error: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Create a standardized error report.
    
    Args:
        error: The exception that occurred
        context: Additional context information
        
    Returns:
        Error report dictionary
    """
    now = datetime.now()
    
    # Get traceback
    tb = traceback.format_exc()
    
    # Create the report
    report = {
        "timestamp": now.isoformat(),
        "error_type": error.__class__.__name__,
        "error_message": str(error),
        "traceback": tb
    }
    
    # Add original error if available
    if hasattr(error, "original_error") and error.original_error:
        report["original_error"] = {
            "type": error.original_error.__class__.__name__,
            "message": str(error.original_error)
        }
    
    # Add API-specific fields if available
    if hasattr(error, "status_code"):
        report["status_code"] = getattr(error, "status_code")
    if hasattr(error, "service"):
        report["service"] = getattr(error, "service")
        
    # Add context if provided
    if context:
        report["context"] = context
        
    return report

def log_error(error: Exception, context: Dict[str, Any] = None) -> None:
    """
    Log an error with standardized formatting.
    
    Args:
        error: The exception that occurred
        context: Additional context information
    """
    report = create_error_report(error, context)
    
    # Determine the log level
    if isinstance(error, PermanentError):
        log_level = logging.ERROR
    elif isinstance(error, TemporaryError):
        log_level = logging.WARNING
    else:
        log_level = logging.ERROR
    
    # Log the error
    logger.log(log_level, f"Error: {report['error_type']}: {report['error_message']}")
    
    # Log the traceback at debug level
    logger.debug(f"Traceback:\n{report['traceback']}")
    
    # Log context if available
    if context:
        logger.debug(f"Context: {context}")
        
    return report