"""
Pipeline orchestrator for ICAP.
This module provides the main pipeline controller that manages data flow between components.
"""
import json
import logging
import asyncio
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable, Awaitable, Union
from dataclasses import dataclass, field

from python_components.utils.neo4j_manager import Neo4jManager
from python_components.processors.action_item_processor import ActionItemProcessor

logger = logging.getLogger("icap.pipeline")

@dataclass
class PipelineStep:
    """Represents a step in the processing pipeline."""
    name: str
    function: Callable[..., Any]
    input_type: str
    output_type: str
    retry_count: int = 3
    timeout: int = 120
    required: bool = True
    
    # Runtime stats
    last_run: Optional[datetime] = None
    last_status: str = "not_run"
    execution_time: float = 0.0
    executions: int = 0
    failures: int = 0

@dataclass
class PipelineContext:
    """Maintains state and metadata for a pipeline execution."""
    pipeline_id: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    status: str = "running"
    source_type: str = ""
    source_id: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)
    
    def add_result(self, step_name: str, result: Any) -> None:
        """Add result from a pipeline step."""
        self.results[step_name] = result
    
    def get_result(self, step_name: str) -> Optional[Any]:
        """Get result from a step."""
        return self.results.get(step_name)
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the context."""
        self.metadata[key] = value
    
    def complete(self, status: str = "completed") -> None:
        """Mark the pipeline as complete."""
        self.end_time = datetime.now()
        self.status = status
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "pipeline_id": self.pipeline_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "error": self.error,
            "metadata": self.metadata,
            # Don't include full results as they can be large
            "result_summary": {k: f"{type(v).__name__}[{len(v) if hasattr(v, '__len__') else '1'}]" 
                              for k, v in self.results.items()}
        }

class PipelineOrchestrator:
    """Orchestrates the processing pipeline for emails and Slack messages."""
    
    def __init__(self):
        """Initialize the pipeline orchestrator."""
        self.neo4j = Neo4jManager()
        self.processor = ActionItemProcessor()
        self.steps: Dict[str, PipelineStep] = {}
        self.pipeline_history: List[PipelineContext] = []
        self._setup_pipelines()
        logger.info("Pipeline orchestrator initialized")
    
    def _setup_pipelines(self) -> None:
        """Set up the processing pipelines."""
        # Email pipeline
        self.email_pipeline = [
            PipelineStep(
                name="retrieve_email",
                function=self._mock_retrieve_email,  # Will be replaced with actual function
                input_type="email_query",
                output_type="email_data"
            ),
            PipelineStep(
                name="process_email",
                function=self.processor.process_email,
                input_type="email_data",
                output_type="action_item_ids"
            )
        ]
        
        # Slack pipeline
        self.slack_pipeline = [
            PipelineStep(
                name="retrieve_slack_messages",
                function=self._mock_retrieve_slack,  # Will be replaced with actual function
                input_type="slack_query",
                output_type="slack_data"
            ),
            PipelineStep(
                name="process_slack_message",
                function=self.processor.process_slack_message,
                input_type="slack_data",
                output_type="action_item_ids"
            )
        ]
        
        # Summary pipeline
        self.summary_pipeline = [
            PipelineStep(
                name="generate_summary",
                function=self.processor.generate_daily_summary,
                input_type="void",
                output_type="summary"
            ),
            PipelineStep(
                name="send_summary_email",
                function=self._mock_send_summary,  # Will be replaced with actual function
                input_type="summary",
                output_type="notification_status"
            )
        ]
        
        logger.info("Pipelines configured")
    
    async def process_email(self, email_query: Dict[str, Any]) -> PipelineContext:
        """
        Process an email query through the pipeline.
        
        Args:
            email_query: Query parameters for retrieving emails
                - maxResults: Maximum number of results to return
                - filter: OData filter expression
                
        Returns:
            Pipeline context with results
        """
        logger.info(f"Starting email pipeline with query: {email_query}")
        context = PipelineContext(
            pipeline_id=f"email-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            source_type="email"
        )
        context.add_metadata("query", email_query)
        
        try:
            # Execute each step in the pipeline
            current_input = email_query
            
            for step in self.email_pipeline:
                logger.info(f"Executing step: {step.name}")
                step.last_run = datetime.now()
                step.executions += 1
                
                try:
                    start_time = datetime.now()
                    result = step.function(current_input)
                    execution_time = (datetime.now() - start_time).total_seconds()
                    step.execution_time = execution_time
                    
                    logger.info(f"Step {step.name} completed in {execution_time:.2f}s")
                    context.add_result(step.name, result)
                    
                    # Use this result as input to the next step
                    current_input = result
                    step.last_status = "completed"
                    
                except Exception as e:
                    step.failures += 1
                    step.last_status = "failed"
                    logger.error(f"Error in step {step.name}: {str(e)}")
                    logger.debug(traceback.format_exc())
                    
                    if step.required:
                        raise RuntimeError(f"Required step {step.name} failed: {str(e)}")
            
            # Pipeline completed successfully
            context.complete("completed")
            self.pipeline_history.append(context)
            logger.info(f"Email pipeline completed successfully")
            return context
            
        except Exception as e:
            context.status = "failed"
            context.error = str(e)
            context.end_time = datetime.now()
            self.pipeline_history.append(context)
            logger.error(f"Email pipeline failed: {str(e)}")
            return context
    
    async def process_slack(self, slack_query: Dict[str, Any]) -> PipelineContext:
        """
        Process Slack messages through the pipeline.
        
        Args:
            slack_query: Query parameters for retrieving Slack messages
                - maxResults: Maximum number of results
                - channels: List of channel IDs
                - olderThan: Timestamp to filter messages
                
        Returns:
            Pipeline context with results
        """
        logger.info(f"Starting Slack pipeline with query: {slack_query}")
        context = PipelineContext(
            pipeline_id=f"slack-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            source_type="slack"
        )
        context.add_metadata("query", slack_query)
        
        try:
            # Execute each step in the pipeline
            current_input = slack_query
            
            for step in self.slack_pipeline:
                logger.info(f"Executing step: {step.name}")
                step.last_run = datetime.now()
                step.executions += 1
                
                try:
                    start_time = datetime.now()
                    result = step.function(current_input)
                    execution_time = (datetime.now() - start_time).total_seconds()
                    step.execution_time = execution_time
                    
                    logger.info(f"Step {step.name} completed in {execution_time:.2f}s")
                    context.add_result(step.name, result)
                    
                    # Use this result as input to the next step
                    current_input = result
                    step.last_status = "completed"
                    
                except Exception as e:
                    step.failures += 1
                    step.last_status = "failed"
                    logger.error(f"Error in step {step.name}: {str(e)}")
                    logger.debug(traceback.format_exc())
                    
                    if step.required:
                        raise RuntimeError(f"Required step {step.name} failed: {str(e)}")
            
            # Pipeline completed successfully
            context.complete("completed")
            self.pipeline_history.append(context)
            logger.info(f"Slack pipeline completed successfully")
            return context
            
        except Exception as e:
            context.status = "failed"
            context.error = str(e)
            context.end_time = datetime.now()
            self.pipeline_history.append(context)
            logger.error(f"Slack pipeline failed: {str(e)}")
            return context
    
    async def generate_daily_summary(self) -> PipelineContext:
        """
        Generate and send a daily summary.
        
        Returns:
            Pipeline context with results
        """
        logger.info("Starting summary pipeline")
        context = PipelineContext(
            pipeline_id=f"summary-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            source_type="summary"
        )
        
        try:
            # Execute each step in the pipeline
            current_input = None  # No input for first step
            
            for step in self.summary_pipeline:
                logger.info(f"Executing step: {step.name}")
                step.last_run = datetime.now()
                step.executions += 1
                
                try:
                    start_time = datetime.now()
                    
                    # Handle the first step that doesn't need input
                    if step.input_type == "void":
                        result = step.function()
                    else:
                        result = step.function(current_input)
                        
                    execution_time = (datetime.now() - start_time).total_seconds()
                    step.execution_time = execution_time
                    
                    logger.info(f"Step {step.name} completed in {execution_time:.2f}s")
                    context.add_result(step.name, result)
                    
                    # Use this result as input to the next step
                    current_input = result
                    step.last_status = "completed"
                    
                except Exception as e:
                    step.failures += 1
                    step.last_status = "failed"
                    logger.error(f"Error in step {step.name}: {str(e)}")
                    logger.debug(traceback.format_exc())
                    
                    if step.required:
                        raise RuntimeError(f"Required step {step.name} failed: {str(e)}")
            
            # Pipeline completed successfully
            context.complete("completed")
            self.pipeline_history.append(context)
            logger.info(f"Summary pipeline completed successfully")
            return context
            
        except Exception as e:
            context.status = "failed"
            context.error = str(e)
            context.end_time = datetime.now()
            self.pipeline_history.append(context)
            logger.error(f"Summary pipeline failed: {str(e)}")
            return context
    
    def get_pipeline_history(self) -> List[Dict[str, Any]]:
        """Get the history of pipeline executions."""
        return [context.to_dict() for context in self.pipeline_history]
    
    def clear_history(self) -> None:
        """Clear the pipeline execution history."""
        self.pipeline_history = []
    
    # Mock functions that will be replaced with actual implementations
    def _mock_retrieve_email(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Mock function for retrieving emails."""
        logger.info(f"Mocking email retrieval with query: {query}")
        # Return a dummy email for testing
        return [{
            "id": "email123",
            "subject": "Project update meeting",
            "from": "john@example.com",
            "body": "Let's have a project update meeting tomorrow at 2pm. Jane, can you prepare the slides? Bob, please update the timeline for the landing page.",
            "date": "2023-05-01T10:30:00Z"
        }]
    
    def _mock_retrieve_slack(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Mock function for retrieving Slack messages."""
        logger.info(f"Mocking Slack retrieval with query: {query}")
        # Return a dummy message for testing
        return [{
            "id": "slack123",
            "text": "@sarah can you review the PR by EOD? It's urgent for the release tomorrow.",
            "user": {"name": "Tom", "email": "tom@example.com"},
            "channelId": "C01234567",
            "timestamp": "1620000000.000000"
        }]
    
    def _mock_send_summary(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """Mock function for sending summary emails."""
        logger.info(f"Mocking summary email sending with {len(summary['action_items'])} items")
        return {
            "status": "sent",
            "recipient": "user@example.com",
            "timestamp": datetime.now().isoformat()
        }