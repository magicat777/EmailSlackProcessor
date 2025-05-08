"""
Message queue system for ICAP pipeline.
"""
import os
import time
import json
import uuid
import logging
import asyncio
import threading
from typing import Dict, Any, List, Optional, Callable, Set, Union
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from queue import Queue, PriorityQueue, Empty

logger = logging.getLogger("icap.queue")

@dataclass
class Message:
    """Message to be processed in the pipeline."""
    id: str
    type: str
    data: Dict[str, Any]
    priority: int = 2  # 1=high, 2=medium, 3=low
    created_at: datetime = field(default_factory=datetime.now)
    processed: bool = False
    retry_count: int = 0
    max_retries: int = 3
    scheduled_time: Optional[datetime] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        result = asdict(self)
        result["created_at"] = self.created_at.isoformat()
        if self.scheduled_time:
            result["scheduled_time"] = self.scheduled_time.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary."""
        if isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "scheduled_time" in data and data["scheduled_time"] and isinstance(data["scheduled_time"], str):
            data["scheduled_time"] = datetime.fromisoformat(data["scheduled_time"])
        return cls(**data)
    
    def is_ready(self) -> bool:
        """Check if the message is ready to be processed."""
        if self.scheduled_time:
            return datetime.now() >= self.scheduled_time
        return True
    
    def __lt__(self, other: 'Message') -> bool:
        """Compare messages for priority queue ordering."""
        if self.priority != other.priority:
            return self.priority < other.priority
        
        if self.scheduled_time and other.scheduled_time:
            return self.scheduled_time < other.scheduled_time
        
        if self.scheduled_time:
            return self.scheduled_time < datetime.now()
            
        if other.scheduled_time:
            return datetime.now() < other.scheduled_time
            
        return self.created_at < other.created_at

class MessageQueue:
    """
    Message queue for passing data between components.
    
    Supports:
    - Message prioritization
    - Scheduled message delivery
    - Message persistence (optional)
    - Retry handling
    """
    
    def __init__(self, 
                 persistence_file: Optional[str] = None,
                 max_messages: int = 1000,
                 persistence_interval: int = 60):
        """
        Initialize the message queue.
        
        Args:
            persistence_file: File to persist messages to (optional)
            max_messages: Maximum number of messages to keep in the queue
            persistence_interval: Interval in seconds for persisting messages
        """
        self.queue = PriorityQueue()
        self.processed = []
        self.running = False
        self.handlers: Dict[str, List[Callable[[Message], Any]]] = {}
        self.max_messages = max_messages
        self.persistence_file = persistence_file
        self.persistence_interval = persistence_interval
        self.message_count = 0
        
        # Set for tracking message IDs to avoid duplicates
        self.message_ids: Set[str] = set()
        
        # Statistics
        self.stats = {
            "enqueued": 0,
            "processed": 0,
            "retried": 0,
            "failed": 0,
            "start_time": datetime.now()
        }
        
        logger.info(f"Message queue initialized")
        
        # Load persisted messages if available
        if self.persistence_file and os.path.exists(self.persistence_file):
            self._load_from_file()
    
    def register_handler(self, message_type: str, handler: Callable[[Message], Any]) -> None:
        """
        Register a handler for a message type.
        
        Args:
            message_type: Type of message to handle
            handler: Function to handle the message
        """
        if message_type not in self.handlers:
            self.handlers[message_type] = []
        
        self.handlers[message_type].append(handler)
        logger.info(f"Registered handler for message type '{message_type}'")
    
    def enqueue(self, 
               message_type: str, 
               data: Dict[str, Any], 
               priority: int = 2,
               scheduled_time: Optional[datetime] = None) -> str:
        """
        Add a message to the queue.
        
        Args:
            message_type: Type of message
            data: Message data
            priority: Message priority (1=high, 2=medium, 3=low)
            scheduled_time: Time to process the message (optional)
            
        Returns:
            Message ID
        """
        message_id = str(uuid.uuid4())
        message = Message(
            id=message_id,
            type=message_type,
            data=data,
            priority=priority,
            scheduled_time=scheduled_time
        )
        
        self.queue.put(message)
        self.message_ids.add(message_id)
        self.message_count += 1
        self.stats["enqueued"] += 1
        
        logger.info(f"Enqueued {message_type} message with ID {message_id}")
        
        # Periodically persist the queue if a file is configured
        if self.persistence_file and self.stats["enqueued"] % 10 == 0:
            self._persist_to_file()
        
        return message_id
    
    def enqueue_batch(self, messages: List[Dict[str, Any]]) -> List[str]:
        """
        Add multiple messages to the queue.
        
        Args:
            messages: List of message dictionaries with keys:
                - type: Message type
                - data: Message data
                - priority: (optional) Message priority
                - scheduled_time: (optional) Time to process the message
                
        Returns:
            List of message IDs
        """
        message_ids = []
        
        for msg_dict in messages:
            msg_id = self.enqueue(
                message_type=msg_dict["type"],
                data=msg_dict["data"],
                priority=msg_dict.get("priority", 2),
                scheduled_time=msg_dict.get("scheduled_time")
            )
            message_ids.append(msg_id)
        
        logger.info(f"Enqueued batch of {len(message_ids)} messages")
        return message_ids
    
    def start(self, blocking: bool = False) -> None:
        """
        Start processing messages in the queue.
        
        Args:
            blocking: Whether to block the current thread
        """
        self.running = True
        
        if blocking:
            logger.info("Starting message queue processing (blocking)")
            self._process_loop()
        else:
            logger.info("Starting message queue processing (background)")
            self.thread = threading.Thread(target=self._process_loop)
            self.thread.daemon = True
            self.thread.start()
    
    def stop(self) -> None:
        """Stop processing messages."""
        logger.info("Stopping message queue processing")
        self.running = False
        
        # If we have a persistence file, save messages for later
        if self.persistence_file:
            self._persist_to_file()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        current_size = self.queue.qsize()
        uptime = (datetime.now() - self.stats["start_time"]).total_seconds()
        
        return {
            **self.stats,
            "current_size": current_size,
            "uptime_seconds": uptime,
            "processed_messages": len(self.processed),
            "messages_per_second": self.stats["processed"] / max(1, uptime)
        }
    
    def _process_loop(self) -> None:
        """Main processing loop for the queue."""
        logger.info("Message processing loop started")
        
        try:
            persistence_last_time = time.time()
            
            while self.running:
                try:
                    # Get the next message, with a timeout to check running flag
                    try:
                        message = self.queue.get(timeout=1)
                    except Empty:
                        # Check if it's time to persist the queue
                        if (self.persistence_file and 
                            time.time() - persistence_last_time > self.persistence_interval):
                            self._persist_to_file()
                            persistence_last_time = time.time()
                        continue
                    
                    # If the message is scheduled for the future, put it back and wait
                    if message.scheduled_time and datetime.now() < message.scheduled_time:
                        self.queue.put(message)
                        time.sleep(0.1)  # Small delay to avoid cpu hogging
                        continue
                    
                    # Process the message
                    handlers = self.handlers.get(message.type, [])
                    
                    if not handlers:
                        logger.warning(f"No handlers for message type '{message.type}'")
                        self.stats["failed"] += 1
                        message.error = "No handlers registered"
                        self.processed.append(message)
                        continue
                    
                    # Call all handlers for this message type
                    success = True
                    for handler in handlers:
                        try:
                            handler(message)
                        except Exception as e:
                            logger.error(f"Error handling message {message.id}: {str(e)}")
                            message.error = str(e)
                            success = False
                    
                    # Update message and stats
                    if success:
                        message.processed = True
                        self.stats["processed"] += 1
                    else:
                        # Retry logic
                        if message.retry_count < message.max_retries:
                            message.retry_count += 1
                            self.stats["retried"] += 1
                            
                            # Calculate backoff delay
                            delay = 2 ** message.retry_count  # Exponential backoff
                            message.scheduled_time = datetime.now() + timedelta(seconds=delay)
                            
                            logger.info(f"Requeuing message {message.id} for retry {message.retry_count}/{message.max_retries} in {delay}s")
                            self.queue.put(message)
                        else:
                            # Max retries reached
                            logger.warning(f"Message {message.id} failed after {message.max_retries} retries")
                            self.stats["failed"] += 1
                            message.processed = True
                            self.processed.append(message)
                    
                    # If message is processed (not requeued), add to processed list
                    if message.processed:
                        self.processed.append(message)
                        
                        # Trim processed list if it gets too large
                        if len(self.processed) > self.max_messages:
                            self.processed = self.processed[-self.max_messages:]
                    
                    # Mark as task_done
                    self.queue.task_done()
                    
                except Exception as e:
                    logger.error(f"Error in message processing loop: {str(e)}")
                    time.sleep(1)  # Avoid tight loop in case of errors
            
            logger.info("Message processing loop stopped")
            
        except Exception as e:
            logger.error(f"Fatal error in message processing loop: {str(e)}")
            self.running = False
    
    def _persist_to_file(self) -> None:
        """Persist the queue to a file."""
        if not self.persistence_file:
            return
            
        try:
            # Convert queue to list for serialization
            # This is not thread-safe but good enough for our use case
            queue_list = []
            while not self.queue.empty():
                queue_list.append(self.queue.get())
            
            # Put all messages back
            for msg in queue_list:
                self.queue.put(msg)
            
            # Convert messages to dictionaries
            queue_data = [msg.to_dict() for msg in queue_list]
            processed_data = [msg.to_dict() for msg in self.processed]
            
            data = {
                "queue": queue_data,
                "processed": processed_data,
                "stats": self.stats,
                "timestamp": datetime.now().isoformat()
            }
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(self.persistence_file)), exist_ok=True)
            
            # Write to a temporary file first, then rename to avoid corruption if the process crashes
            temp_file = f"{self.persistence_file}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(data, f)
                
            os.replace(temp_file, self.persistence_file)
            
            logger.debug(f"Persisted {len(queue_data)} queued and {len(processed_data)} processed messages")
            
        except Exception as e:
            logger.error(f"Error persisting queue to file: {str(e)}")
    
    def _load_from_file(self) -> None:
        """Load persisted messages from a file."""
        if not self.persistence_file or not os.path.exists(self.persistence_file):
            return
            
        try:
            with open(self.persistence_file, 'r') as f:
                data = json.load(f)
            
            # Load queue messages
            for msg_dict in data.get("queue", []):
                message = Message.from_dict(msg_dict)
                self.queue.put(message)
                self.message_ids.add(message.id)
                self.message_count += 1
            
            # Load processed messages
            for msg_dict in data.get("processed", []):
                message = Message.from_dict(msg_dict)
                self.processed.append(message)
                self.message_ids.add(message.id)
            
            # Load stats
            for key, value in data.get("stats", {}).items():
                if key in self.stats:
                    self.stats[key] = value
            
            # Convert start_time from string if needed
            if isinstance(self.stats["start_time"], str):
                self.stats["start_time"] = datetime.fromisoformat(self.stats["start_time"])
            
            logger.info(f"Loaded {self.queue.qsize()} queued and {len(self.processed)} processed messages from persistence file")
            
        except Exception as e:
            logger.error(f"Error loading persisted queue: {str(e)}")

class AsyncMessageQueue:
    """
    Async version of the message queue for use with asyncio.
    
    This is a wrapper around the synchronous MessageQueue that provides
    async-compatible methods.
    """
    
    def __init__(self, 
                 persistence_file: Optional[str] = None,
                 max_messages: int = 1000,
                 persistence_interval: int = 60):
        """
        Initialize the async message queue.
        
        Args:
            persistence_file: File to persist messages to (optional)
            max_messages: Maximum number of messages to keep in the queue
            persistence_interval: Interval in seconds for persisting messages
        """
        self.queue = MessageQueue(
            persistence_file=persistence_file,
            max_messages=max_messages,
            persistence_interval=persistence_interval
        )
        self.loop = asyncio.get_event_loop()
        logger.info("Async message queue initialized")
    
    async def register_handler(self, message_type: str, handler: Callable[[Message], Any]) -> None:
        """
        Register a handler for a message type.
        
        Args:
            message_type: Type of message to handle
            handler: Function to handle the message
        """
        await self.loop.run_in_executor(None, self.queue.register_handler, message_type, handler)
    
    async def enqueue(self, 
                     message_type: str, 
                     data: Dict[str, Any], 
                     priority: int = 2,
                     scheduled_time: Optional[datetime] = None) -> str:
        """
        Add a message to the queue.
        
        Args:
            message_type: Type of message
            data: Message data
            priority: Message priority (1=high, 2=medium, 3=low)
            scheduled_time: Time to process the message (optional)
            
        Returns:
            Message ID
        """
        return await self.loop.run_in_executor(
            None, self.queue.enqueue, message_type, data, priority, scheduled_time
        )
    
    async def enqueue_batch(self, messages: List[Dict[str, Any]]) -> List[str]:
        """
        Add multiple messages to the queue.
        
        Args:
            messages: List of message dictionaries with keys:
                - type: Message type
                - data: Message data
                - priority: (optional) Message priority
                - scheduled_time: (optional) Time to process
                
        Returns:
            List of message IDs
        """
        return await self.loop.run_in_executor(None, self.queue.enqueue_batch, messages)
    
    async def start(self) -> None:
        """Start processing messages in the queue."""
        await self.loop.run_in_executor(None, self.queue.start, False)
    
    async def stop(self) -> None:
        """Stop processing messages."""
        await self.loop.run_in_executor(None, self.queue.stop)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return await self.loop.run_in_executor(None, self.queue.get_stats)