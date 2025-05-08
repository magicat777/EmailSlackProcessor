#!/usr/bin/env python3
"""
Main entry point for the ICAP processing engine.
"""
import os
import sys
import logging
import argparse
import asyncio
from dotenv import load_dotenv

from python_components.utils.neo4j_manager import Neo4jManager
from python_components.utils.env_loader import EnvLoader
from python_components.processors.action_item_processor import ActionItemProcessor
from python_components.pipeline.queue import MessageQueue, AsyncMessageQueue
from python_components.pipeline.scheduler import PipelineScheduler
from python_components.pipeline.webhook import WebhookHandler

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("icap")

# Load environment variables from .env file if it exists
load_dotenv()

def main():
    """Main function to start the ICAP processing engine."""
    parser = argparse.ArgumentParser(description="ICAP Processing Engine")
    parser.add_argument("--project-id", help="Google Cloud project ID for Secret Manager")
    parser.add_argument("--credentials", help="Path to service account credentials file")
    parser.add_argument("--skip-secrets", action="store_true", help="Skip loading secrets from Secret Manager")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--queue", action="store_true", help="Start message queue worker")
    parser.add_argument("--scheduler", action="store_true", help="Start pipeline scheduler")
    parser.add_argument("--webhook", action="store_true", help="Start webhook server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the webhook server (if --webhook is specified)")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind the webhook server (if --webhook is specified)")
    parser.add_argument("--persistence-file", help="File to persist the queue to (if --queue or --scheduler is specified)")
    
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger("icap").setLevel(logging.DEBUG)
    
    logger.info("Starting ICAP processing engine...")
    
    # Load secrets from Google Secret Manager if not skipped
    if not args.skip_secrets:
        env_loader = EnvLoader(
            project_id=args.project_id,
            credentials_path=args.credentials
        )
        env_loader.load_secrets_to_env()
    
    # Check required environment variables
    required_vars = ["NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "CLAUDE_API_KEY"]
    
    # You can also use the EnvLoader utility for validation
    env_loader = EnvLoader()
    missing_vars = env_loader.validate_required_vars(required_vars)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)
    
    logger.info("Environment variables verified.")
    
    try:
        # Initialize Neo4j connection
        neo4j_manager = Neo4jManager()
        neo4j_manager.create_constraints()
        logger.info("Neo4j connection established and schema constraints verified")
        
        # Initialize action item processor
        processor = ActionItemProcessor()
        logger.info("Action item processor initialized")
        
        # Start components based on arguments
        if not any([args.queue, args.scheduler, args.webhook]):
            # No components specified, just log and exit
            logger.info("ICAP processing engine initialized and running.")
            logger.info("Use --queue, --scheduler, or --webhook to start specific components.")
            return
            
        # If multiple components are specified, we'll run them all in an event loop
        logger.info("Starting requested components...")
        
        async def run_components():
            """Run the requested components."""
            components = []
            
            # Start message queue if requested
            if args.queue:
                logger.info("Starting message queue...")
                queue = AsyncMessageQueue(persistence_file=args.persistence_file)
                await queue.start()
                components.append(("queue", queue))
                logger.info("Message queue started")
                
            # Start scheduler if requested
            if args.scheduler:
                logger.info("Starting pipeline scheduler...")
                # Use the queue we just created if it exists, otherwise create a new one
                queue_obj = next((c[1] for c in components if c[0] == "queue"), None)
                if not queue_obj:
                    queue_obj = AsyncMessageQueue(persistence_file=args.persistence_file)
                    await queue_obj.start()
                    components.append(("queue", queue_obj))
                
                scheduler = PipelineScheduler(queue=queue_obj)
                scheduler.start(blocking=False)
                components.append(("scheduler", scheduler))
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
                components.append(("webhook", webhook))
                logger.info("Webhook server started")
            
            # Keep running until interrupted
            try:
                logger.info("All components started. Press Ctrl+C to stop.")
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("Shutting down...")
            finally:
                # Shut down components in reverse order
                for component_type, component in reversed(components):
                    logger.info(f"Stopping {component_type}...")
                    if component_type == "webhook":
                        await component.stop()
                    elif component_type == "scheduler":
                        component.stop()
                    elif component_type == "queue":
                        await component.stop()
                logger.info("All components stopped.")
        
        # Run everything in an event loop
        asyncio.run(run_components())
        
    except Exception as e:
        logger.error(f"Error during initialization: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()