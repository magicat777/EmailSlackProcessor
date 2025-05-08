"""
Scheduler for ICAP pipeline execution.
"""
import os
import time
import logging
import threading
import asyncio
import datetime
from typing import Dict, Any, List, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum

from python_components.pipeline.orchestrator import PipelineOrchestrator
from python_components.pipeline.queue import Message, MessageQueue

logger = logging.getLogger("icap.scheduler")

class ScheduleType(Enum):
    """Types of schedule."""
    INTERVAL = "interval"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CRON = "cron"

@dataclass
class Schedule:
    """Schedule configuration for a task."""
    id: str
    name: str
    type: ScheduleType
    target: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None
    enabled: bool = True
    
    # For INTERVAL type
    interval_seconds: Optional[int] = None
    
    # For DAILY type
    daily_time: Optional[str] = None  # HH:MM format
    
    # For WEEKLY type
    weekly_day: Optional[int] = None  # 0-6 (Monday is 0)
    weekly_time: Optional[str] = None  # HH:MM format
    
    # For MONTHLY type
    monthly_day: Optional[int] = None  # 1-31
    monthly_time: Optional[str] = None  # HH:MM format
    
    # For CRON type
    cron_expression: Optional[str] = None
    
    # Runtime stats
    last_run: Optional[datetime.datetime] = None
    next_run: Optional[datetime.datetime] = None
    runs: int = 0
    failures: int = 0
    
    def __post_init__(self):
        """Calculate next run time."""
        self.update_next_run()
    
    def update_next_run(self):
        """Update the next run time based on the schedule type."""
        now = datetime.datetime.now()
        
        if not self.enabled:
            self.next_run = None
            return
        
        if self.type == ScheduleType.INTERVAL:
            if not self.interval_seconds:
                logger.error(f"Schedule {self.id} is missing interval_seconds")
                self.next_run = None
                return
                
            if self.last_run:
                self.next_run = self.last_run + datetime.timedelta(seconds=self.interval_seconds)
            else:
                self.next_run = now + datetime.timedelta(seconds=self.interval_seconds)
                
        elif self.type == ScheduleType.DAILY:
            if not self.daily_time:
                logger.error(f"Schedule {self.id} is missing daily_time")
                self.next_run = None
                return
                
            try:
                hour, minute = map(int, self.daily_time.split(':'))
                target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                if target_time <= now:
                    target_time = target_time + datetime.timedelta(days=1)
                    
                self.next_run = target_time
            except ValueError:
                logger.error(f"Invalid daily_time format for schedule {self.id}: {self.daily_time}")
                self.next_run = None
                
        elif self.type == ScheduleType.WEEKLY:
            if not self.weekly_day or not self.weekly_time:
                logger.error(f"Schedule {self.id} is missing weekly_day or weekly_time")
                self.next_run = None
                return
                
            try:
                hour, minute = map(int, self.weekly_time.split(':'))
                # Calculate days to add to get to the next target weekday
                current_weekday = now.weekday()
                days_to_add = (self.weekly_day - current_weekday) % 7
                
                if days_to_add == 0 and now.hour > hour or (now.hour == hour and now.minute >= minute):
                    days_to_add = 7
                    
                target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                target_time = target_time + datetime.timedelta(days=days_to_add)
                
                self.next_run = target_time
            except ValueError:
                logger.error(f"Invalid weekly configuration for schedule {self.id}")
                self.next_run = None
                
        elif self.type == ScheduleType.MONTHLY:
            if not self.monthly_day or not self.monthly_time:
                logger.error(f"Schedule {self.id} is missing monthly_day or monthly_time")
                self.next_run = None
                return
                
            try:
                hour, minute = map(int, self.monthly_time.split(':'))
                target_time = now.replace(day=min(self.monthly_day, 28), hour=hour, minute=minute, second=0, microsecond=0)
                
                if target_time <= now:
                    # Move to next month
                    if now.month == 12:
                        target_time = target_time.replace(year=now.year + 1, month=1)
                    else:
                        target_time = target_time.replace(month=now.month + 1)
                
                self.next_run = target_time
            except ValueError:
                logger.error(f"Invalid monthly configuration for schedule {self.id}")
                self.next_run = None
                
        elif self.type == ScheduleType.CRON:
            if not self.cron_expression:
                logger.error(f"Schedule {self.id} is missing cron_expression")
                self.next_run = None
                return
                
            try:
                from croniter import croniter
                
                if croniter.is_valid(self.cron_expression):
                    cron = croniter(self.cron_expression, now)
                    self.next_run = cron.get_next(datetime.datetime)
                else:
                    logger.error(f"Invalid cron expression for schedule {self.id}: {self.cron_expression}")
                    self.next_run = None
            except ImportError:
                logger.error("croniter library not available for cron scheduling")
                self.next_run = None
            except Exception as e:
                logger.error(f"Error calculating next run for cron schedule {self.id}: {str(e)}")
                self.next_run = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the schedule to a dictionary."""
        result = {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "target": self.target,
            "parameters": self.parameters,
            "description": self.description,
            "enabled": self.enabled,
            "runs": self.runs,
            "failures": self.failures
        }
        
        # Add type-specific fields
        if self.type == ScheduleType.INTERVAL:
            result["interval_seconds"] = self.interval_seconds
        elif self.type == ScheduleType.DAILY:
            result["daily_time"] = self.daily_time
        elif self.type == ScheduleType.WEEKLY:
            result["weekly_day"] = self.weekly_day
            result["weekly_time"] = self.weekly_time
        elif self.type == ScheduleType.MONTHLY:
            result["monthly_day"] = self.monthly_day
            result["monthly_time"] = self.monthly_time
        elif self.type == ScheduleType.CRON:
            result["cron_expression"] = self.cron_expression
        
        # Add runtime stats
        if self.last_run:
            result["last_run"] = self.last_run.isoformat()
        if self.next_run:
            result["next_run"] = self.next_run.isoformat()
            
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Schedule':
        """Create a schedule from a dictionary."""
        schedule_type = ScheduleType(data.get("type", "interval"))
        
        # Convert ISO timestamps to datetime objects
        last_run = None
        if data.get("last_run"):
            last_run = datetime.datetime.fromisoformat(data["last_run"])
            
        next_run = None
        if data.get("next_run"):
            next_run = datetime.datetime.fromisoformat(data["next_run"])
            
        return cls(
            id=data["id"],
            name=data["name"],
            type=schedule_type,
            target=data["target"],
            parameters=data.get("parameters", {}),
            description=data.get("description"),
            enabled=data.get("enabled", True),
            interval_seconds=data.get("interval_seconds"),
            daily_time=data.get("daily_time"),
            weekly_day=data.get("weekly_day"),
            weekly_time=data.get("weekly_time"),
            monthly_day=data.get("monthly_day"),
            monthly_time=data.get("monthly_time"),
            cron_expression=data.get("cron_expression"),
            last_run=last_run,
            next_run=next_run,
            runs=data.get("runs", 0),
            failures=data.get("failures", 0)
        )

class PipelineScheduler:
    """Scheduler for ICAP pipeline execution."""
    
    def __init__(self, orchestrator: Optional[PipelineOrchestrator] = None, 
                queue: Optional[MessageQueue] = None):
        """
        Initialize the scheduler.
        
        Args:
            orchestrator: Pipeline orchestrator
            queue: Message queue for scheduled tasks
        """
        self.orchestrator = orchestrator or PipelineOrchestrator()
        self.queue = queue or MessageQueue()
        self.schedules: Dict[str, Schedule] = {}
        self.running = False
        self.thread = None
        self.lock = threading.RLock()
        
        # Load default schedules
        self._load_default_schedules()
        
        logger.info("Pipeline scheduler initialized")
    
    def _load_default_schedules(self) -> None:
        """Load default schedules."""
        # Email processing schedule (every 10 minutes)
        self.add_schedule(Schedule(
            id="email-processing",
            name="Email Processing",
            type=ScheduleType.INTERVAL,
            target="process_email",
            interval_seconds=600,
            description="Process new emails every 10 minutes",
            parameters={
                "maxResults": 20,
                "filter": "isRead eq false"
            }
        ))
        
        # Slack processing schedule (every 5 minutes)
        self.add_schedule(Schedule(
            id="slack-processing",
            name="Slack Processing",
            type=ScheduleType.INTERVAL,
            target="process_slack",
            interval_seconds=300,
            description="Process new Slack messages every 5 minutes",
            parameters={
                "maxResults": 50
            }
        ))
        
        # Daily summary schedule (every day at 8:00 AM)
        self.add_schedule(Schedule(
            id="daily-summary",
            name="Daily Summary",
            type=ScheduleType.DAILY,
            target="generate_daily_summary",
            daily_time="08:00",
            description="Generate daily summary at 8:00 AM"
        ))
    
    def add_schedule(self, schedule: Schedule) -> None:
        """
        Add a schedule to the scheduler.
        
        Args:
            schedule: Schedule to add
        """
        with self.lock:
            self.schedules[schedule.id] = schedule
            logger.info(f"Added schedule {schedule.id}: {schedule.name}")
    
    def remove_schedule(self, schedule_id: str) -> bool:
        """
        Remove a schedule from the scheduler.
        
        Args:
            schedule_id: ID of the schedule to remove
            
        Returns:
            True if the schedule was removed, False otherwise
        """
        with self.lock:
            if schedule_id in self.schedules:
                del self.schedules[schedule_id]
                logger.info(f"Removed schedule {schedule_id}")
                return True
            else:
                logger.warning(f"Schedule {schedule_id} not found")
                return False
    
    def get_schedule(self, schedule_id: str) -> Optional[Schedule]:
        """
        Get a schedule by ID.
        
        Args:
            schedule_id: ID of the schedule to get
            
        Returns:
            The schedule, or None if not found
        """
        with self.lock:
            return self.schedules.get(schedule_id)
    
    def get_schedules(self) -> List[Schedule]:
        """
        Get all schedules.
        
        Returns:
            List of schedules
        """
        with self.lock:
            return list(self.schedules.values())
    
    def update_schedule(self, schedule_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update a schedule.
        
        Args:
            schedule_id: ID of the schedule to update
            updates: Dictionary of fields to update
            
        Returns:
            True if the schedule was updated, False otherwise
        """
        with self.lock:
            schedule = self.schedules.get(schedule_id)
            if not schedule:
                logger.warning(f"Schedule {schedule_id} not found")
                return False
            
            # Update fields
            for key, value in updates.items():
                if hasattr(schedule, key):
                    setattr(schedule, key, value)
            
            # Update next run time
            schedule.update_next_run()
            
            logger.info(f"Updated schedule {schedule_id}")
            return True
    
    def enable_schedule(self, schedule_id: str) -> bool:
        """
        Enable a schedule.
        
        Args:
            schedule_id: ID of the schedule to enable
            
        Returns:
            True if the schedule was enabled, False otherwise
        """
        with self.lock:
            schedule = self.schedules.get(schedule_id)
            if not schedule:
                logger.warning(f"Schedule {schedule_id} not found")
                return False
            
            schedule.enabled = True
            schedule.update_next_run()
            
            logger.info(f"Enabled schedule {schedule_id}")
            return True
    
    def disable_schedule(self, schedule_id: str) -> bool:
        """
        Disable a schedule.
        
        Args:
            schedule_id: ID of the schedule to disable
            
        Returns:
            True if the schedule was disabled, False otherwise
        """
        with self.lock:
            schedule = self.schedules.get(schedule_id)
            if not schedule:
                logger.warning(f"Schedule {schedule_id} not found")
                return False
            
            schedule.enabled = False
            schedule.next_run = None
            
            logger.info(f"Disabled schedule {schedule_id}")
            return True
    
    def start(self, blocking: bool = False) -> None:
        """
        Start the scheduler.
        
        Args:
            blocking: Whether to block the current thread
        """
        self.running = True
        
        # Start the queue if it's not already running
        if not getattr(self.queue, 'running', False):
            self.queue.start(blocking=False)
        
        # Register handlers for queue messages
        self.queue.register_handler("process_email", self._handle_process_email)
        self.queue.register_handler("process_slack", self._handle_process_slack)
        self.queue.register_handler("generate_daily_summary", self._handle_generate_daily_summary)
        
        if blocking:
            logger.info("Starting scheduler (blocking)")
            self._scheduler_loop()
        else:
            logger.info("Starting scheduler (background)")
            self.thread = threading.Thread(target=self._scheduler_loop)
            self.thread.daemon = True
            self.thread.start()
    
    def stop(self) -> None:
        """Stop the scheduler."""
        logger.info("Stopping scheduler")
        self.running = False
        
        # Wait for the thread to finish if it's running
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
    
    def run_now(self, schedule_id: str) -> bool:
        """
        Run a schedule immediately.
        
        Args:
            schedule_id: ID of the schedule to run
            
        Returns:
            True if the schedule was run, False otherwise
        """
        with self.lock:
            schedule = self.schedules.get(schedule_id)
            if not schedule:
                logger.warning(f"Schedule {schedule_id} not found")
                return False
            
            if not schedule.enabled:
                logger.warning(f"Schedule {schedule_id} is disabled")
                return False
            
            # Enqueue the task
            self._enqueue_task(schedule)
            
            # Update schedule stats
            schedule.last_run = datetime.datetime.now()
            schedule.runs += 1
            schedule.update_next_run()
            
            logger.info(f"Manually ran schedule {schedule_id}")
            return True
    
    def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        logger.info("Scheduler loop started")
        
        try:
            while self.running:
                with self.lock:
                    now = datetime.datetime.now()
                    
                    # Check for schedules that need to run
                    for schedule in self.schedules.values():
                        if schedule.enabled and schedule.next_run and schedule.next_run <= now:
                            logger.info(f"Executing schedule {schedule.id}: {schedule.name}")
                            
                            try:
                                # Enqueue the task
                                self._enqueue_task(schedule)
                                
                                # Update schedule stats
                                schedule.last_run = now
                                schedule.runs += 1
                                schedule.update_next_run()
                                
                            except Exception as e:
                                logger.error(f"Error executing schedule {schedule.id}: {str(e)}")
                                schedule.failures += 1
                                schedule.update_next_run()
                
                # Sleep for a short time before checking again
                time.sleep(1)
        
        except Exception as e:
            logger.error(f"Error in scheduler loop: {str(e)}")
            self.running = False
    
    def _enqueue_task(self, schedule: Schedule) -> None:
        """
        Enqueue a scheduled task.
        
        Args:
            schedule: The schedule to enqueue
        """
        # Map schedule target to message type
        message_type = schedule.target
        
        # Create message data from schedule parameters
        message_data = dict(schedule.parameters)
        
        # Add schedule metadata
        message_data["schedule_id"] = schedule.id
        message_data["schedule_name"] = schedule.name
        message_data["schedule_run_time"] = datetime.datetime.now().isoformat()
        
        # Add to queue with high priority (1)
        self.queue.enqueue(
            message_type=message_type,
            data=message_data,
            priority=1
        )
    
    def _handle_process_email(self, message: Message) -> None:
        """
        Handle a process_email message.
        
        Args:
            message: The message to handle
        """
        logger.info(f"Handling process_email message: {message.id}")
        
        # Extract query parameters from message data
        query = {
            "maxResults": message.data.get("maxResults", 20),
            "filter": message.data.get("filter", "isRead eq false")
        }
        
        # Run the email processing pipeline
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            context = loop.run_until_complete(self.orchestrator.process_email(query))
            
            # Check result
            if context.status == "completed":
                logger.info(f"Email processing completed successfully: {context.id}")
            else:
                logger.error(f"Email processing failed: {context.error}")
                raise RuntimeError(f"Email processing failed: {context.error}")
                
        except Exception as e:
            logger.error(f"Error in process_email handler: {str(e)}")
            raise
        finally:
            loop.close()
    
    def _handle_process_slack(self, message: Message) -> None:
        """
        Handle a process_slack message.
        
        Args:
            message: The message to handle
        """
        logger.info(f"Handling process_slack message: {message.id}")
        
        # Extract query parameters from message data
        query = {
            "maxResults": message.data.get("maxResults", 50),
            "channels": message.data.get("channels", []),
            "olderThan": message.data.get("olderThan")
        }
        
        # Run the Slack processing pipeline
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            context = loop.run_until_complete(self.orchestrator.process_slack(query))
            
            # Check result
            if context.status == "completed":
                logger.info(f"Slack processing completed successfully: {context.id}")
            else:
                logger.error(f"Slack processing failed: {context.error}")
                raise RuntimeError(f"Slack processing failed: {context.error}")
                
        except Exception as e:
            logger.error(f"Error in process_slack handler: {str(e)}")
            raise
        finally:
            loop.close()
    
    def _handle_generate_daily_summary(self, message: Message) -> None:
        """
        Handle a generate_daily_summary message.
        
        Args:
            message: The message to handle
        """
        logger.info(f"Handling generate_daily_summary message: {message.id}")
        
        # Run the summary generation pipeline
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            context = loop.run_until_complete(self.orchestrator.generate_daily_summary())
            
            # Check result
            if context.status == "completed":
                logger.info(f"Summary generation completed successfully: {context.id}")
            else:
                logger.error(f"Summary generation failed: {context.error}")
                raise RuntimeError(f"Summary generation failed: {context.error}")
                
        except Exception as e:
            logger.error(f"Error in generate_daily_summary handler: {str(e)}")
            raise
        finally:
            loop.close()