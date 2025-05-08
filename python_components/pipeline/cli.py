"""
Command-line interface for ICAP pipeline.
"""
import os
import sys
import json
import logging
import argparse
from datetime import datetime, timedelta
import asyncio
from typing import Dict, Any, List, Optional

from python_components.utils.env_loader import EnvLoader
from python_components.utils.neo4j_manager import Neo4jManager
from python_components.pipeline.orchestrator import PipelineOrchestrator
from python_components.pipeline.webhook import WebhookHandler
from python_components.pipeline.queue import MessageQueue, AsyncMessageQueue

logger = logging.getLogger("icap.cli")

class PipelineCLI:
    """Command-line interface for controlling the ICAP pipeline."""
    
    def __init__(self):
        """Initialize the CLI interface."""
        self.parser = argparse.ArgumentParser(description="ICAP Pipeline Control")
        self.setup_parser()
    
    def setup_parser(self) -> None:
        """Set up the argument parser."""
        subparsers = self.parser.add_subparsers(dest="command", help="Command to run")
        
        # Start server command
        server_parser = subparsers.add_parser("server", help="Start the webhook server")
        server_parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server")
        server_parser.add_argument("--port", type=int, default=8080, help="Port to bind the server")
        server_parser.add_argument("--project-id", help="Google Cloud project ID")
        server_parser.add_argument("--credentials", help="Path to service account credentials")
        
        # Process email command
        email_parser = subparsers.add_parser("email", help="Process emails")
        email_parser.add_argument("--filter", default="isRead eq false", help="OData filter expression")
        email_parser.add_argument("--max-results", type=int, default=10, help="Maximum number of results")
        
        # Process Slack command
        slack_parser = subparsers.add_parser("slack", help="Process Slack messages")
        slack_parser.add_argument("--channels", help="Comma-separated list of channel IDs")
        slack_parser.add_argument("--max-results", type=int, default=50, help="Maximum number of results")
        slack_parser.add_argument("--older-than", help="Only process messages older than this timestamp")
        
        # Generate summary command
        summary_parser = subparsers.add_parser("summary", help="Generate a daily summary")
        
        # Queue management commands
        queue_parser = subparsers.add_parser("queue", help="Message queue management")
        queue_subparsers = queue_parser.add_subparsers(dest="queue_command", help="Queue command")
        
        # Start queue worker
        queue_start_parser = queue_subparsers.add_parser("start", help="Start the queue worker")
        queue_start_parser.add_argument("--persistence-file", help="File to persist the queue to")
        
        # Show queue stats
        queue_stats_parser = queue_subparsers.add_parser("stats", help="Show queue statistics")
        queue_stats_parser.add_argument("--persistence-file", help="File to load the queue from")
        
        # Global debug option
        self.parser.add_argument("--debug", action="store_true", help="Enable debug logging")
        
    async def run(self, args: Optional[List[str]] = None) -> None:
        """Run the CLI command."""
        args = self.parser.parse_args(args)
        
        # Setup logging
        log_level = logging.DEBUG if args.debug else logging.INFO
        logging.getLogger("icap").setLevel(log_level)
        
        # Load environment variables
        env_loader = EnvLoader(
            project_id=getattr(args, "project_id", None),
            credentials_path=getattr(args, "credentials", None)
        )
        env_loader.load_secrets_to_env()
        
        # Determine which command to run
        if args.command == "server":
            await self.run_server(args)
        elif args.command == "email":
            await self.process_email(args)
        elif args.command == "slack":
            await self.process_slack(args)
        elif args.command == "summary":
            await self.generate_summary()
        elif args.command == "queue":
            if args.queue_command == "start":
                await self.start_queue(args)
            elif args.queue_command == "stats":
                self.show_queue_stats(args)
            else:
                logger.error(f"Unknown queue command: {args.queue_command}")
        else:
            logger.error(f"Unknown command: {args.command}")
    
    async def run_server(self, args) -> None:
        """Start the webhook server."""
        logger.info(f"Starting webhook server on {args.host}:{args.port}")
        
        # Create and start the webhook handler
        webhook = WebhookHandler(host=args.host, port=args.port)
        
        try:
            await webhook.start()
            
            # Wait forever (until Ctrl+C)
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Shutting down webhook server")
        except Exception as e:
            logger.error(f"Error running webhook server: {str(e)}")
    
    async def process_email(self, args) -> None:
        """Process emails from the command line."""
        logger.info(f"Processing emails with filter: {args.filter}")
        
        # Create pipeline orchestrator
        orchestrator = PipelineOrchestrator()
        
        # Run the email pipeline
        query = {
            "maxResults": args.max_results,
            "filter": args.filter
        }
        
        try:
            # Process emails
            context = await orchestrator.process_email(query)
            
            # Print results
            logger.info(f"Email processing completed with status: {context.status}")
            
            if context.status == "completed":
                action_item_ids = context.get_result("process_email")
                logger.info(f"Created {len(action_item_ids)} action items")
                
                # Print action item IDs for further processing
                for item_id in action_item_ids:
                    print(item_id)
            else:
                logger.error(f"Email processing failed: {context.error}")
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"Error processing emails: {str(e)}")
            sys.exit(1)
    
    async def process_slack(self, args) -> None:
        """Process Slack messages from the command line."""
        channels = args.channels.split(",") if args.channels else []
        logger.info(f"Processing Slack messages from channels: {channels}")
        
        # Create pipeline orchestrator
        orchestrator = PipelineOrchestrator()
        
        # Run the Slack pipeline
        query = {
            "maxResults": args.max_results,
            "channels": channels,
            "olderThan": args.older_than
        }
        
        try:
            # Process Slack messages
            context = await orchestrator.process_slack(query)
            
            # Print results
            logger.info(f"Slack processing completed with status: {context.status}")
            
            if context.status == "completed":
                action_item_ids = context.get_result("process_slack_message")
                logger.info(f"Created {len(action_item_ids)} action items")
                
                # Print action item IDs for further processing
                for item_id in action_item_ids:
                    print(item_id)
            else:
                logger.error(f"Slack processing failed: {context.error}")
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"Error processing Slack messages: {str(e)}")
            sys.exit(1)
    
    async def generate_summary(self) -> None:
        """Generate a daily summary."""
        logger.info("Generating daily summary")
        
        # Create pipeline orchestrator
        orchestrator = PipelineOrchestrator()
        
        try:
            # Generate summary
            context = await orchestrator.generate_daily_summary()
            
            # Print results
            logger.info(f"Summary generation completed with status: {context.status}")
            
            if context.status == "completed":
                summary = context.get_result("generate_summary")
                logger.info(f"Generated summary with {summary['total_items']} items")
                
                # Print summary statistics
                print(f"Total items: {summary['total_items']}")
                print(f"High priority: {len(summary['items_by_priority']['high'])}")
                print(f"Medium priority: {len(summary['items_by_priority']['medium'])}")
                print(f"Low priority: {len(summary['items_by_priority']['low'])}")
                print(f"Projects: {', '.join(summary['projects'])}")
            else:
                logger.error(f"Summary generation failed: {context.error}")
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            sys.exit(1)
    
    async def start_queue(self, args) -> None:
        """Start the message queue worker."""
        logger.info("Starting message queue worker")
        
        persistence_file = args.persistence_file
        if persistence_file:
            logger.info(f"Using persistence file: {persistence_file}")
        
        # Create queue
        queue = AsyncMessageQueue(persistence_file=persistence_file)
        
        # Start processing
        await queue.start()
        
        try:
            # Wait forever (until Ctrl+C)
            while True:
                # Print stats every 10 seconds
                await asyncio.sleep(10)
                stats = await queue.get_stats()
                logger.info(f"Queue stats: {stats}")
                
        except KeyboardInterrupt:
            logger.info("Shutting down queue worker")
            await queue.stop()
            
        except Exception as e:
            logger.error(f"Error running queue worker: {str(e)}")
            await queue.stop()
    
    def show_queue_stats(self, args) -> None:
        """Show queue statistics."""
        logger.info("Showing queue statistics")
        
        persistence_file = args.persistence_file
        if not persistence_file:
            logger.error("Persistence file is required for queue stats")
            sys.exit(1)
            
        if not os.path.exists(persistence_file):
            logger.error(f"Persistence file not found: {persistence_file}")
            sys.exit(1)
        
        try:
            # Load queue stats from file
            with open(persistence_file, 'r') as f:
                data = json.load(f)
            
            # Extract stats
            stats = data.get("stats", {})
            queue_size = len(data.get("queue", []))
            processed_size = len(data.get("processed", []))
            
            # Print statistics
            print(f"Queue Statistics")
            print(f"---------------")
            print(f"Enqueued messages: {stats.get('enqueued', 0)}")
            print(f"Processed messages: {stats.get('processed', 0)}")
            print(f"Retried messages: {stats.get('retried', 0)}")
            print(f"Failed messages: {stats.get('failed', 0)}")
            print(f"Current queue size: {queue_size}")
            print(f"Processed messages: {processed_size}")
            
            # Calculate uptime
            start_time = datetime.fromisoformat(stats.get("start_time", datetime.now().isoformat()))
            uptime = datetime.now() - start_time
            days, seconds = uptime.days, uptime.seconds
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            seconds = seconds % 60
            
            print(f"Uptime: {days}d {hours}h {minutes}m {seconds}s")
            
            # Calculate processing rate
            processed = stats.get("processed", 0)
            uptime_seconds = uptime.total_seconds()
            if uptime_seconds > 0:
                rate = processed / uptime_seconds
                print(f"Processing rate: {rate:.2f} messages/second")
            
        except Exception as e:
            logger.error(f"Error showing queue stats: {str(e)}")
            sys.exit(1)

def main() -> None:
    """Main entry point for the CLI."""
    cli = PipelineCLI()
    asyncio.run(cli.run())

if __name__ == "__main__":
    main()