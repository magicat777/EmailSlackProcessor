#!/usr/bin/env python3
"""
ICAP daemon script for running components as a system service.
This script is designed to be run as a systemd service or similar.
"""
import os
import sys
import time
import signal
import logging
import argparse
import asyncio
import traceback
from pathlib import Path

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from python_components.utils.env_loader import EnvLoader
from python_components.pipeline.queue import AsyncMessageQueue
from python_components.pipeline.scheduler import PipelineScheduler
from python_components.pipeline.webhook import WebhookHandler

# Setup logging
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = logging.INFO

logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/var/log/icap/daemon.log", mode="a")
    ]
)

logger = logging.getLogger("icap.daemon")

# Global variables for components
queue = None
scheduler = None
webhook = None
loop = None

def signal_handler(sig, frame):
    """Handle termination signals."""
    logger.info(f"Received signal {sig}, shutting down...")
    if loop and not loop.is_closed():
        loop.create_task(shutdown())

async def shutdown():
    """Shutdown all components gracefully."""
    global queue, scheduler, webhook
    
    try:
        # Shutdown components in reverse order of dependencies
        if webhook:
            logger.info("Stopping webhook server...")
            await webhook.stop()
            webhook = None
            
        if scheduler:
            logger.info("Stopping scheduler...")
            scheduler.stop()
            scheduler = None
            
        if queue:
            logger.info("Stopping queue...")
            await queue.stop()
            queue = None
            
        logger.info("All components stopped.")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
        traceback.print_exc()
    finally:
        # Stop the event loop
        loop.stop()

async def start_components(args):
    """Start the requested components."""
    global queue, scheduler, webhook
    
    # Load secrets from environment
    env_loader = EnvLoader(
        project_id=args.project_id,
        credentials_path=args.credentials_path
    )
    env_loader.load_secrets_to_env()
    
    # Start components based on arguments
    components_started = 0
    
    # Start message queue (required for scheduler)
    if args.queue or args.scheduler:
        queue_dir = Path(args.queue_dir)
        if not queue_dir.exists():
            queue_dir.mkdir(parents=True, exist_ok=True)
            
        persistence_file = queue_dir / "queue.json"
        logger.info(f"Starting message queue with persistence file: {persistence_file}")
        
        queue = AsyncMessageQueue(persistence_file=str(persistence_file))
        await queue.start()
        components_started += 1
        logger.info("Message queue started")
    
    # Start scheduler if requested
    if args.scheduler:
        logger.info("Starting pipeline scheduler...")
        scheduler = PipelineScheduler(queue=queue)
        scheduler.start(blocking=False)
        components_started += 1
        logger.info("Pipeline scheduler started")
        
        # Display active schedules
        logger.info("Active schedules:")
        for schedule in scheduler.get_schedules():
            enabled = "enabled" if schedule.enabled else "disabled"
            next_run = schedule.next_run.strftime("%Y-%m-%d %H:%M:%S") if schedule.next_run else "never"
            logger.info(f"  - {schedule.id}: {schedule.name} ({enabled}, next run: {next_run})")
    
    # Start webhook server if requested
    if args.webhook:
        logger.info(f"Starting webhook server on {args.host}:{args.port}...")
        webhook = WebhookHandler(host=args.host, port=args.port)
        await webhook.start()
        components_started += 1
        logger.info("Webhook server started")
    
    if components_started == 0:
        logger.error("No components were started. Specify at least one of --queue, --scheduler, or --webhook.")
        return False
    
    # Write PID file if specified
    if args.pid_file:
        with open(args.pid_file, 'w') as f:
            f.write(str(os.getpid()))
        logger.info(f"PID written to {args.pid_file}")
    
    logger.info("All components started successfully")
    return True

def main():
    """Main entry point for the daemon."""
    parser = argparse.ArgumentParser(description="ICAP Daemon")
    
    # Component selection
    parser.add_argument("--queue", action="store_true", help="Start message queue worker")
    parser.add_argument("--scheduler", action="store_true", help="Start pipeline scheduler")
    parser.add_argument("--webhook", action="store_true", help="Start webhook server")
    
    # Queue configuration
    parser.add_argument("--queue-dir", default="/var/lib/icap/queue", help="Directory for queue persistence files")
    
    # Webhook configuration
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the webhook server")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind the webhook server")
    
    # Security
    parser.add_argument("--project-id", help="Google Cloud project ID for Secret Manager")
    parser.add_argument("--credentials-path", help="Path to service account credentials file")
    
    # Daemon configuration
    parser.add_argument("--pid-file", help="File to write PID to")
    parser.add_argument("--log-file", help="Log file (default: /var/log/icap/daemon.log)")
    
    args = parser.parse_args()
    
    # Setup file logging if specified
    if args.log_file:
        file_handler = logging.FileHandler(args.log_file, mode="a")
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logging.getLogger("icap").addHandler(file_handler)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start the event loop
    global loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    logger.info("Starting ICAP daemon...")
    
    try:
        # Start components
        if loop.run_until_complete(start_components(args)):
            # Run forever until signal
            logger.info("ICAP daemon running. Press Ctrl+C to stop.")
            loop.run_forever()
        else:
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error starting daemon: {str(e)}")
        traceback.print_exc()
        sys.exit(1)
        
    finally:
        loop.close()
        logger.info("ICAP daemon exited")

if __name__ == "__main__":
    main()