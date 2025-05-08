# GitHub Actions Workflows

This directory contains the CI/CD pipeline configuration for the ICAP project. These workflows automate building, testing, and deploying the application to different environments.

## Workflow Overview

### Build Workflows
- `build-cloud-functions.yml`: Builds the Node.js Cloud Functions
- `build-docker-images.yml`: Builds Docker images for the processing engine and Neo4j database

### Test Workflows
- `lint.yml`: Performs code quality checks (linting, type checking, formatting)
- `run-tests.yml`: Runs unit tests for both Cloud Functions and Python components
- `e2e-tests.yml`: Runs end-to-end integration tests with all components

### Deployment Workflows
- `deploy-staging.yml`: Deploys to the staging environment (automated)
- `deploy-production.yml`: Deploys to the production environment (requires approval)

### Security Workflows
- `dependency-scan.yml`: Scans dependencies for vulnerabilities

## Workflow Dependencies

The workflows are designed to run in the following sequence:

1. Build workflows trigger when code is pushed or pull requests are created
2. Test workflows run after successful builds
3. End-to-end tests run after unit tests pass
4. Staging deployment occurs automatically after all tests pass (for staging branch)
5. Production deployment requires manual approval and version input

## Environment Secrets

The workflows require the following secrets to be set in the GitHub repository:

- `GCP_SA_KEY`: Google Cloud service account JSON key with permissions for:
  - Cloud Functions deployment
  - Container Registry access
  - Cloud Scheduler management
- `GCP_PROJECT_ID`: Google Cloud project ID
- `GCP_SERVICE_ACCOUNT`: Google Cloud service account email
- `CLAUDE_API_KEY`: Anthropic Claude API key (for testing)

## Workflow Customization

To customize the workflows:

1. Modify the build patterns in the `on` section to trigger for relevant files
2. Adjust build and test commands for different components
3. Update deployment configurations for different environments

## Manual Workflows

Some workflows can be triggered manually:

- `deploy-production.yml`: Requires manual invocation and version input
- `dependency-scan.yml`: Can be run on-demand via workflow_dispatch

## Reference

For more details, see the [CI/CD Pipeline Documentation](../docs/ci_cd_pipeline.md).