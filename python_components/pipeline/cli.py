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
from typing import Dict, Any, List, Optional, Union

from python_components.utils.env_loader import EnvLoader
from python_components.utils.neo4j_manager import Neo4jManager
from python_components.pipeline.orchestrator import PipelineOrchestrator
from python_components.pipeline.webhook import WebhookHandler
from python_components.pipeline.queue import MessageQueue, AsyncMessageQueue
from python_components.pipeline.scheduler import PipelineScheduler, Schedule, ScheduleType

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

        # Scheduler management commands
        scheduler_parser = subparsers.add_parser("scheduler", help="Pipeline scheduler management")
        scheduler_subparsers = scheduler_parser.add_subparsers(dest="scheduler_command", help="Scheduler command")
        
        # Start scheduler
        scheduler_start_parser = scheduler_subparsers.add_parser("start", help="Start the scheduler")
        scheduler_start_parser.add_argument("--persistence-file", help="File to persist the queue to")
        
        # List schedules
        scheduler_list_parser = scheduler_subparsers.add_parser("list", help="List all schedules")
        scheduler_list_parser.add_argument("--format", choices=["table", "json"], default="table", help="Output format")
        
        # Show schedule details
        scheduler_show_parser = scheduler_subparsers.add_parser("show", help="Show schedule details")
        scheduler_show_parser.add_argument("id", help="Schedule ID to show")
        
        # Enable/disable schedule
        scheduler_enable_parser = scheduler_subparsers.add_parser("enable", help="Enable a schedule")
        scheduler_enable_parser.add_argument("id", help="Schedule ID to enable")
        
        scheduler_disable_parser = scheduler_subparsers.add_parser("disable", help="Disable a schedule")
        scheduler_disable_parser.add_argument("id", help="Schedule ID to disable")
        
        # Run schedule now
        scheduler_run_parser = scheduler_subparsers.add_parser("run", help="Run a schedule immediately")
        scheduler_run_parser.add_argument("id", help="Schedule ID to run")
        
        # Add a new schedule
        scheduler_add_parser = scheduler_subparsers.add_parser("add", help="Add a new schedule")
        scheduler_add_parser.add_argument("--file", help="JSON file containing schedule definition")
        scheduler_add_parser.add_argument("--id", help="Schedule ID")
        scheduler_add_parser.add_argument("--name", help="Schedule name")
        scheduler_add_parser.add_argument("--type", choices=["interval", "daily", "weekly", "monthly", "cron"], help="Schedule type")
        scheduler_add_parser.add_argument("--target", choices=["process_email", "process_slack", "generate_daily_summary"], help="Target pipeline")
        scheduler_add_parser.add_argument("--interval", type=int, help="Interval in seconds (for interval type)")
        scheduler_add_parser.add_argument("--time", help="Time in HH:MM format (for daily, weekly, monthly types)")
        scheduler_add_parser.add_argument("--day", type=int, help="Day (0-6 for weekly, 1-31 for monthly)")
        scheduler_add_parser.add_argument("--cron", help="Cron expression (for cron type)")
        scheduler_add_parser.add_argument("--parameters", help="JSON string of parameters for the target")
        
        # Remove a schedule
        scheduler_remove_parser = scheduler_subparsers.add_parser("remove", help="Remove a schedule")
        scheduler_remove_parser.add_argument("id", help="Schedule ID to remove")
        
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
        elif args.command == "scheduler":
            if args.scheduler_command == "start":
                await self.start_scheduler(args)
            elif args.scheduler_command == "list":
                self.list_schedules(args)
            elif args.scheduler_command == "show":
                self.show_schedule(args)
            elif args.scheduler_command == "enable":
                self.enable_schedule(args)
            elif args.scheduler_command == "disable":
                self.disable_schedule(args)
            elif args.scheduler_command == "run":
                self.run_schedule_now(args)
            elif args.scheduler_command == "add":
                self.add_schedule(args)
            elif args.scheduler_command == "remove":
                self.remove_schedule(args)
            else:
                logger.error(f"Unknown scheduler command: {args.scheduler_command}")
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
            
    async def start_scheduler(self, args) -> None:
        """Start the scheduler service."""
        logger.info("Starting pipeline scheduler")
        
        persistence_file = args.persistence_file
        if persistence_file:
            logger.info(f"Using persistence file for queue: {persistence_file}")
            
        # Create AsyncMessageQueue and PipelineScheduler
        queue = AsyncMessageQueue(persistence_file=persistence_file)
        scheduler = PipelineScheduler(queue=queue)
        
        # Start the queue and scheduler
        await queue.start()
        scheduler.start(blocking=False)
        
        try:
            # Print initial schedules
            print("Pipeline scheduler started with the following schedules:")
            self._print_schedule_table(scheduler.get_schedules())
            
            # Wait forever (until Ctrl+C)
            while True:
                # Print stats every 30 seconds
                await asyncio.sleep(30)
                print("\nCurrent schedules:")
                self._print_schedule_table(scheduler.get_schedules())
                
        except KeyboardInterrupt:
            logger.info("Shutting down scheduler")
            scheduler.stop()
            await queue.stop()
            
        except Exception as e:
            logger.error(f"Error running scheduler: {str(e)}")
            scheduler.stop()
            await queue.stop()
            sys.exit(1)
    
    def list_schedules(self, args) -> None:
        """List all schedules."""
        logger.info("Listing all schedules")
        
        # Create scheduler
        scheduler = PipelineScheduler()
        
        # Get schedules
        schedules = scheduler.get_schedules()
        
        # Print schedules
        if args.format == "json":
            # Print as JSON
            json_data = [schedule.to_dict() for schedule in schedules]
            print(json.dumps(json_data, indent=2))
        else:
            # Print as table
            self._print_schedule_table(schedules)
    
    def show_schedule(self, args) -> None:
        """Show details of a specific schedule."""
        schedule_id = args.id
        logger.info(f"Showing schedule: {schedule_id}")
        
        # Create scheduler
        scheduler = PipelineScheduler()
        
        # Get schedule
        schedule = scheduler.get_schedule(schedule_id)
        
        if not schedule:
            logger.error(f"Schedule not found: {schedule_id}")
            sys.exit(1)
            
        # Print schedule details
        schedule_dict = schedule.to_dict()
        
        print(f"Schedule: {schedule.name} ({schedule.id})")
        print(f"Type: {schedule.type.value}")
        print(f"Target: {schedule.target}")
        print(f"Enabled: {schedule.enabled}")
        print(f"Description: {schedule.description or 'N/A'}")
        
        # Print type-specific details
        if schedule.type == ScheduleType.INTERVAL:
            print(f"Interval: {schedule.interval_seconds} seconds")
        elif schedule.type == ScheduleType.DAILY:
            print(f"Time: {schedule.daily_time}")
        elif schedule.type == ScheduleType.WEEKLY:
            print(f"Day: {schedule.weekly_day} (0=Monday, 6=Sunday)")
            print(f"Time: {schedule.weekly_time}")
        elif schedule.type == ScheduleType.MONTHLY:
            print(f"Day: {schedule.monthly_day}")
            print(f"Time: {schedule.monthly_time}")
        elif schedule.type == ScheduleType.CRON:
            print(f"Cron: {schedule.cron_expression}")
            
        # Print parameters
        print("\nParameters:")
        for key, value in schedule.parameters.items():
            print(f"  {key}: {value}")
            
        # Print runtime stats
        print("\nRuntime Statistics:")
        print(f"  Runs: {schedule.runs}")
        print(f"  Failures: {schedule.failures}")
        print(f"  Last Run: {schedule.last_run.isoformat() if schedule.last_run else 'Never'}")
        print(f"  Next Run: {schedule.next_run.isoformat() if schedule.next_run else 'Never'}")
    
    def enable_schedule(self, args) -> None:
        """Enable a schedule."""
        schedule_id = args.id
        logger.info(f"Enabling schedule: {schedule_id}")
        
        # Create scheduler
        scheduler = PipelineScheduler()
        
        # Enable schedule
        if scheduler.enable_schedule(schedule_id):
            print(f"Schedule {schedule_id} enabled")
        else:
            logger.error(f"Failed to enable schedule: {schedule_id}")
            sys.exit(1)
    
    def disable_schedule(self, args) -> None:
        """Disable a schedule."""
        schedule_id = args.id
        logger.info(f"Disabling schedule: {schedule_id}")
        
        # Create scheduler
        scheduler = PipelineScheduler()
        
        # Disable schedule
        if scheduler.disable_schedule(schedule_id):
            print(f"Schedule {schedule_id} disabled")
        else:
            logger.error(f"Failed to disable schedule: {schedule_id}")
            sys.exit(1)
    
    def run_schedule_now(self, args) -> None:
        """Run a schedule immediately."""
        schedule_id = args.id
        logger.info(f"Running schedule now: {schedule_id}")
        
        # Create scheduler
        scheduler = PipelineScheduler()
        
        # Queue worker must be running for this to work
        if not scheduler.queue.is_running():
            print("WARNING: Queue worker is not running. The task will be queued but not processed.")
            print("Start the queue worker to process the task.")
        
        # Run schedule
        if scheduler.run_now(schedule_id):
            print(f"Schedule {schedule_id} queued for immediate execution")
        else:
            logger.error(f"Failed to run schedule: {schedule_id}")
            sys.exit(1)
    
    def add_schedule(self, args) -> None:
        """Add a new schedule."""
        logger.info("Adding new schedule")
        
        # Create scheduler
        scheduler = PipelineScheduler()
        
        # Check if file specified
        if args.file:
            try:
                with open(args.file, 'r') as f:
                    schedule_data = json.load(f)
                    
                # Create schedule from dict
                schedule = Schedule.from_dict(schedule_data)
                scheduler.add_schedule(schedule)
                print(f"Added schedule {schedule.id} from file")
                return
                
            except Exception as e:
                logger.error(f"Error loading schedule from file: {str(e)}")
                sys.exit(1)
        
        # Check required parameters
        if not args.id or not args.name or not args.type or not args.target:
            logger.error("Missing required parameters: id, name, type, and target are required")
            sys.exit(1)
            
        # Create schedule parameters
        parameters = {}
        if args.parameters:
            try:
                parameters = json.loads(args.parameters)
            except json.JSONDecodeError:
                logger.error("Invalid JSON in parameters")
                sys.exit(1)
        
        # Create schedule based on type
        schedule_type = ScheduleType(args.type)
        schedule_kwargs = {
            "id": args.id,
            "name": args.name,
            "type": schedule_type,
            "target": args.target,
            "parameters": parameters
        }
        
        # Add type-specific parameters
        if schedule_type == ScheduleType.INTERVAL:
            if not args.interval:
                logger.error("Interval parameter is required for interval schedule type")
                sys.exit(1)
            schedule_kwargs["interval_seconds"] = args.interval
        elif schedule_type == ScheduleType.DAILY:
            if not args.time:
                logger.error("Time parameter is required for daily schedule type")
                sys.exit(1)
            schedule_kwargs["daily_time"] = args.time
        elif schedule_type == ScheduleType.WEEKLY:
            if not args.day or not args.time:
                logger.error("Day and time parameters are required for weekly schedule type")
                sys.exit(1)
            schedule_kwargs["weekly_day"] = args.day
            schedule_kwargs["weekly_time"] = args.time
        elif schedule_type == ScheduleType.MONTHLY:
            if not args.day or not args.time:
                logger.error("Day and time parameters are required for monthly schedule type")
                sys.exit(1)
            schedule_kwargs["monthly_day"] = args.day
            schedule_kwargs["monthly_time"] = args.time
        elif schedule_type == ScheduleType.CRON:
            if not args.cron:
                logger.error("Cron parameter is required for cron schedule type")
                sys.exit(1)
            schedule_kwargs["cron_expression"] = args.cron
        
        # Create and add schedule
        schedule = Schedule(**schedule_kwargs)
        scheduler.add_schedule(schedule)
        print(f"Added schedule {schedule.id}")
    
    def remove_schedule(self, args) -> None:
        """Remove a schedule."""
        schedule_id = args.id
        logger.info(f"Removing schedule: {schedule_id}")
        
        # Create scheduler
        scheduler = PipelineScheduler()
        
        # Remove schedule
        if scheduler.remove_schedule(schedule_id):
            print(f"Schedule {schedule_id} removed")
        else:
            logger.error(f"Failed to remove schedule: {schedule_id}")
            sys.exit(1)
    
    def _print_schedule_table(self, schedules: List[Schedule]) -> None:
        """Print schedules as a formatted table."""
        if not schedules:
            print("No schedules found")
            return
            
        # Print header
        print(f"{'ID':<20} {'Name':<25} {'Type':<10} {'Target':<20} {'Enabled':<10} {'Next Run':<25}")
        print(f"{'-'*20} {'-'*25} {'-'*10} {'-'*20} {'-'*10} {'-'*25}")
        
        # Print schedules
        for schedule in sorted(schedules, key=lambda s: s.id):
            next_run = schedule.next_run.strftime('%Y-%m-%d %H:%M:%S') if schedule.next_run else "N/A"
            enabled = "Yes" if schedule.enabled else "No"
            
            print(f"{schedule.id:<20} {schedule.name[:23]:<25} {schedule.type.value:<10} {schedule.target:<20} {enabled:<10} {next_run:<25}")

def main() -> None:
    """Main entry point for the CLI."""
    cli = PipelineCLI()
    asyncio.run(cli.run())

if __name__ == "__main__":
    main()