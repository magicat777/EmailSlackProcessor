# Secrets Management for ICAP

This document outlines the approach for managing secrets and API credentials within the Intelligent Communication Action Processor (ICAP) system.

## Overview

ICAP integrates with multiple external services (Microsoft Graph API, Slack, Anthropic Claude) and requires secure management of API keys and credentials. To address this need, ICAP implements a layered approach for handling secrets:

1. **Google Secret Manager (primary)**: All secrets are centrally stored in Google Secret Manager and accessed at runtime
2. **Environment Variables (fallback)**: For local development or when GCP access is not available
3. **.env Files (development)**: For local development environments

## Secrets Structure

The following secrets are maintained in the system:

| Secret Name | Description | Format in Secret Manager | Environment Variable |
|-------------|-------------|--------------------------|----------------------|
| `neo4j-uri` | Neo4j database connection URI | `bolt://hostname:port` | `NEO4J_URI` |
| `neo4j-user` | Neo4j database username | `string` | `NEO4J_USER` |
| `neo4j-password` | Neo4j database password | `string` | `NEO4J_PASSWORD` |
| `claude-api-key` | Anthropic Claude API Key | `string` | `CLAUDE_API_KEY` |
| `ms-graph-client-id` | Microsoft Graph API Client ID | `GUID` | `MS_GRAPH_CLIENT_ID` |
| `ms-graph-client-secret` | Microsoft Graph API Client Secret | `string` | `MS_GRAPH_CLIENT_SECRET` |
| `ms-graph-tenant-id` | Microsoft Graph API Tenant ID | `GUID` | `MS_GRAPH_TENANT_ID` |
| `ms-graph-refresh-token` | Microsoft Graph API Refresh Token | `string` | `MS_GRAPH_REFRESH_TOKEN` |
| `slack-bot-token` | Slack Bot User OAuth Token | `xoxb-...` | `SLACK_BOT_TOKEN` |
| `notification-recipient-email` | Email to receive notifications | `email@example.com` | `NOTIFICATION_RECIPIENT_EMAIL` |

## Setup Instructions

### 1. Setting Up Google Secret Manager

All secrets are managed through Google Secret Manager in the `ICAP` GCP project. To set up secrets initially:

1. Ensure you have the Google Cloud CLI installed and authenticated
2. Run the `setup_secrets.py` script to interactively set up secrets:

```bash
# Using project ID from environment variable
GOOGLE_CLOUD_PROJECT=icap python scripts/setup_secrets.py

# Or specify project ID directly
python scripts/setup_secrets.py --project-id icap
```

3. To list existing secrets:

```bash
python scripts/setup_secrets.py --project-id icap --list
```

### 2. Local Development with .env Files

For local development without direct GCP access, you can generate a `.env` file from Google Secret Manager:

```bash
# Generate .env file from Secret Manager
python scripts/generate_env_file.py --project-id icap --output .env

# Specify specific secrets to include
python scripts/generate_env_file.py --project-id icap --output .env --secrets "neo4j-uri,neo4j-user,neo4j-password,claude-api-key"
```

### 3. Docker Container Configuration

The Docker containers are configured to access secrets from either:

1. Google Secret Manager (if running with GCP credentials)
2. Environment variables passed to the container
3. A mounted `.env` file

Example docker-compose usage:

```bash
# Run with GCP credentials for Secret Manager access
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json docker-compose up

# Run with secrets provided as environment variables
NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=password docker-compose up
```

### 4. Cloud Functions Configuration

Cloud Functions access secrets via:

1. Google Secret Manager (primary method)
2. Environment variables set in the Cloud Function configuration (fallback)

When deploying Cloud Functions, you need to ensure the function has the Secret Manager Secret Accessor (`roles/secretmanager.secretAccessor`) IAM role.

Example deployment:

```bash
gcloud functions deploy retrieveEmails \
  --runtime nodejs16 \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT=icap
```

## Secrets Access Flow

ICAP components access secrets in the following sequence:

1. Check if the required secret is available as an environment variable
2. If not, attempt to retrieve it from Google Secret Manager
3. If Secret Manager access fails, throw an error

This approach provides flexibility for different deployment scenarios while prioritizing secure cloud-based secret storage.

## Security Considerations

- Environment variables are used as a fallback mechanism but Google Secret Manager is preferred
- Secrets are never stored in code, logs, or version control
- Docker containers access secrets at runtime to avoid storing them in images
- Cloud Functions use the minimum required permissions to access secrets
- Secret rotation can be managed through Google Secret Manager's versioning capabilities

## Troubleshooting

Common issues and their resolutions:

1. **Secret Manager Access Denied**: Ensure the service account has the `Secret Manager Secret Accessor` role
2. **Missing Secrets**: Verify the secret exists in the correct project using the `--list` option of `setup_secrets.py`
3. **Environment Variables Not Loading**: Check `.env` file format and loading in your environment
4. **Cloud Function Errors**: Review Cloud Function logs for specific Secret Manager access issues