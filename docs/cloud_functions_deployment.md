# Cloud Functions Deployment Guide

This document provides instructions for deploying the ICAP Cloud Functions to Google Cloud Platform (GCP).

## Prerequisites

Before deploying, ensure you have:

1. Google Cloud SDK installed and configured
2. Proper permissions in the GCP project
3. Billing enabled for the project
4. Required APIs enabled

You can use the provided script to set up your GCP project:

```bash
./scripts/setup_gcp_project.sh --project=your-project-id
```

## Configuration

The deployment configuration is defined in `cloud-functions/deployment.yaml`. This file contains:

- Global settings for all functions
- Function-specific settings
- Environment variables
- Scheduler configurations

Example configuration:

```yaml
# Global settings
project_id: icap
region: us-central1
runtime: nodejs16
memory: 256MB

# Function-specific configurations
functions:
  email-retriever:
    memory: 512MB
    timeout: 120s
    schedule: "every 10 minutes"
```

## Deployment Methods

There are two options for deploying the Cloud Functions:

### 1. Python Deployment Script

This is the recommended method for most deployments:

```bash
# Deploy all functions
./scripts/deploy_cloud_functions.py --all

# Deploy specific functions
./scripts/deploy_cloud_functions.py email-retriever slack-retriever

# Dry run (show commands without executing)
./scripts/deploy_cloud_functions.py --dry-run --all

# Override project or region
./scripts/deploy_cloud_functions.py --project-id=new-project --region=us-east1 --all
```

### 2. Bash Deployment Script

Alternatively, you can use the Bash script for more control:

```bash
# Deploy all functions
./scripts/deploy_functions.sh --all

# Deploy specific functions with webhook URL
./scripts/deploy_functions.sh --webhook=https://your-webhook.example.com email-retriever

# Set environment variables
./scripts/deploy_functions.sh --set-env=DEBUG=true --set-env=LOG_LEVEL=info slack-retriever
```

## Cloud Functions

The ICAP project includes the following Cloud Functions:

### 1. Email Retriever (`email-retriever`)

Connects to Microsoft Graph API to retrieve emails.

- **Entry points:**
  - `retrieveEmails`: Retrieves emails based on query parameters
  - `processEmails`: Triggers email processing pipeline

- **Trigger type:** HTTP trigger

- **Environment variables:**
  - `MS_GRAPH_TOKEN_URL`: Microsoft Graph token URL
  - `MS_GRAPH_API_URL`: Microsoft Graph API URL
  - `DEFAULT_MAX_RESULTS`: Default number of results to return
  - `DEFAULT_FILTER`: Default OData filter expression
  - `WEBHOOK_URL`: URL to send notifications to

### 2. Slack Retriever (`slack-retriever`)

Connects to Slack API to retrieve messages.

- **Entry points:**
  - `retrieveSlackMessages`: Retrieves Slack messages based on query parameters
  - `processSlackMessages`: Triggers Slack processing pipeline

- **Trigger type:** HTTP trigger

- **Environment variables:**
  - `DEFAULT_MAX_RESULTS`: Default number of results to return
  - `WEBHOOK_URL`: URL to send notifications to

### 3. Notification Sender (`notification-sender`)

Sends email notifications with action item summaries.

- **Entry points:**
  - `sendSummaryEmail`: Sends an email with action item summary
  - `triggerDailySummary`: Triggers daily summary generation

- **Trigger type:** HTTP trigger

- **Environment variables:**
  - `MS_GRAPH_TOKEN_URL`: Microsoft Graph token URL
  - `MS_GRAPH_API_URL`: Microsoft Graph API URL
  - `WEBHOOK_URL`: URL to send notifications to

## Cloud Scheduler

The deployment scripts can automatically create Cloud Scheduler jobs for each function based on the `schedule` property in the configuration file.

Scheduler syntax examples:
- `every 10 minutes`
- `every 1 hours`
- `every day 08:00`
- `0 9 * * 1-5` (cron syntax: weekdays at 9am)

## Secret Management

Cloud Functions access secrets via Google Secret Manager. The required secrets are:

- `ms-graph-client-id`: Microsoft Graph client ID
- `ms-graph-client-secret`: Microsoft Graph client secret
- `ms-graph-tenant-id`: Microsoft Graph tenant ID
- `ms-graph-refresh-token`: Microsoft Graph refresh token
- `slack-bot-token`: Slack bot token
- `claude-api-key`: Claude API key
- `notification-recipient-email`: Email recipient for notifications
- `webhook-token`: Authentication token for webhooks

You can use the `setup_secrets.py` script to manage these secrets:

```bash
python scripts/setup_secrets.py --project-id=your-project-id
```

## Testing Deployed Functions

After deployment, you can test the functions using `curl`:

```bash
# Test email retriever
curl -X GET "https://us-central1-your-project-id.cloudfunctions.net/email-retriever-retrieveEmails?maxResults=5"

# Test Slack retriever
curl -X GET "https://us-central1-your-project-id.cloudfunctions.net/slack-retriever-retrieveSlackMessages?maxResults=5"

# Test summary generator
curl -X POST "https://us-central1-your-project-id.cloudfunctions.net/notification-sender-triggerDailySummary"
```

## Monitoring

After deployment, you can monitor the functions through the Google Cloud Console:

- **Logs:** Cloud Logging provides detailed logs for each function
- **Metrics:** Cloud Monitoring shows performance metrics
- **Errors:** Error Reporting aggregates function errors

## Troubleshooting

Common deployment issues:

1. **API not enabled:** Run `gcloud services enable cloudfunctions.googleapis.com`
2. **Permission denied:** Check IAM permissions for your account and service account
3. **Billing required:** Ensure billing is enabled for your project
4. **Quota exceeded:** Check your project quotas in the GCP console
5. **Cold start delays:** First invocation may be slow; subsequent calls will be faster

## Updating Functions

To update already deployed functions, simply run the deployment script again. The functions will be updated in place without downtime.