# ICAP Pipeline Scheduler

The ICAP Pipeline Scheduler is responsible for running pipeline tasks on a schedule. It supports a variety of schedule types and integrates with the message queue system for reliable task execution.

## Features

- **Multiple Schedule Types**: Supports interval, daily, weekly, monthly, and cron schedules
- **Persistent Scheduling**: Works with the MessageQueue's persistence to resume schedules after restarts
- **CLI Management**: Full command-line interface for managing schedules
- **Daemon Support**: Can run as a system service via systemd
- **Default Schedules**: Comes pre-configured with sensible default schedules

## Schedule Types

The scheduler supports the following schedule types:

1. **Interval**: Run a task at regular intervals (e.g., every 10 minutes)
2. **Daily**: Run a task once per day at a specific time
3. **Weekly**: Run a task once per week on a specific day and time
4. **Monthly**: Run a task once per month on a specific day and time
5. **Cron**: Run a task according to a cron expression (for advanced scheduling)

## CLI Commands

The scheduler can be managed using the ICAP CLI:

```bash
# Start the scheduler
python -m python_components.pipeline.cli scheduler start

# List all schedules
python -m python_components.pipeline.cli scheduler list

# Show a specific schedule
python -m python_components.pipeline.cli scheduler show email-processing

# Enable a schedule
python -m python_components.pipeline.cli scheduler enable email-processing

# Disable a schedule
python -m python_components.pipeline.cli scheduler disable daily-summary

# Run a schedule immediately
python -m python_components.pipeline.cli scheduler run slack-processing

# Add a new schedule (interval type)
python -m python_components.pipeline.cli scheduler add \
  --id weekly-cleanup \
  --name "Weekly Database Cleanup" \
  --type weekly \
  --target custom_cleanup \
  --day 6 \
  --time 23:00 \
  --parameters '{"deep": true}'

# Remove a schedule
python -m python_components.pipeline.cli scheduler remove weekly-cleanup
```

## Running as a Service

The scheduler can be run as a system service using the provided daemon script and systemd service file:

```bash
# Install as a service (requires root)
sudo ./scripts/install_daemon.sh

# Start the service
sudo systemctl start icap

# Check status
sudo systemctl status icap

# View logs
sudo journalctl -u icap
```

## Default Schedules

The scheduler comes with the following default schedules:

1. **email-processing**: Process new emails every 10 minutes
2. **slack-processing**: Process new Slack messages every 5 minutes
3. **daily-summary**: Generate a daily summary at 8:00 AM

## Adding Custom Schedules

To add a custom schedule, you can use the CLI or create a Schedule object programmatically:

```python
from python_components.pipeline.scheduler import PipelineScheduler, Schedule, ScheduleType

# Create a scheduler
scheduler = PipelineScheduler()

# Add a weekly schedule
weekly_schedule = Schedule(
    id="weekly-report",
    name="Weekly Executive Report",
    type=ScheduleType.WEEKLY,
    target="generate_executive_report",
    weekly_day=4,  # Friday (0 is Monday)
    weekly_time="16:00",  # 4:00 PM
    parameters={
        "recipients": ["executive-team@example.com"],
        "format": "pdf"
    }
)

# Add the schedule
scheduler.add_schedule(weekly_schedule)
```

## Architecture

The scheduler works by:

1. Maintaining a list of schedules with their next run times
2. Periodically checking if any schedules are due to run
3. Enqueuing due tasks in the message queue
4. Updating the schedule's next run time

The message queue then processes the tasks using the appropriate handlers, which call the PipelineOrchestrator to execute the pipeline.