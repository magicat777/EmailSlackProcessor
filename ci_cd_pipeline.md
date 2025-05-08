# CI/CD Pipeline for Intelligent Communication Action Processor (ICAP)

## Overview

This document outlines the Continuous Integration and Continuous Deployment (CI/CD) pipeline for the ICAP project. The pipeline is designed to automate the building, testing, and deployment of both cloud and local components, ensuring consistent quality and facilitating rapid iteration.

## Pipeline Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │     │                 │
│  Source Control ├────►│      Build      ├────►│      Test       ├────►│     Deploy      │
│                 │     │                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │                       │
        │                       │                       │                       │
        ▼                       ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │     │                 │
│  GitHub/GitLab  │     │  Docker Images  │     │ Automated Tests │     │ Environment     │
│  Version Control│     │  Cloud Functions│     │ Security Scans  │     │ Deployment      │
│                 │     │                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
```

## CI/CD Tools

- **Version Control:** GitHub
- **CI/CD Platform:** GitHub Actions
- **Container Registry:** Google Container Registry
- **Cloud Deployment:** Google Cloud SDK
- **Testing Framework:** 
  - Jest for JavaScript
  - Pytest for Python
  - Cypher testing for Neo4j
- **Security Scanning:** 
  - Dependabot for dependency vulnerability scanning
  - OWASP ZAP for API security scanning
  - Docker Scout for container scanning

## Pipeline Stages

### 1. Source Control

- Code is maintained in GitHub repository
- Feature branches for development
- Pull request workflow with required reviews
- Branch protection for main branch
- Semantic versioning for releases

### 2. Build Stage

The build stage is triggered automatically on push or pull request to specific branches.

#### Cloud Functions Build:
```yaml
name: Build Cloud Functions

on:
  push:
    branches: [ main, staging ]
    paths:
      - 'cloud-functions/**'
  pull_request:
    branches: [ main, staging ]
    paths:
      - 'cloud-functions/**'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '16'
      - name: Install dependencies
        run: cd cloud-functions && npm install
      - name: Build
        run: cd cloud-functions && npm run build
```

#### Docker Container Build:
```yaml
name: Build Docker Images

on:
  push:
    branches: [ main, staging ]
    paths:
      - 'docker/**'
  pull_request:
    branches: [ main, staging ]
    paths:
      - 'docker/**'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
      - name: Build processing container
        uses: docker/build-push-action@v4
        with:
          context: ./docker/processing
          push: false
          load: true
          tags: icap-processing:latest
      - name: Build neo4j container
        uses: docker/build-push-action@v4
        with:
          context: ./docker/neo4j
          push: false
          load: true
          tags: icap-neo4j:latest
```

### 3. Test Stage

Testing is performed automatically after successful builds.

#### Unit and Integration Testing:
```yaml
name: Run Tests

on:
  workflow_run:
    workflows: ["Build Cloud Functions", "Build Docker Images"]
    types:
      - completed

jobs:
  test:
    runs-on: ubuntu-latest
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    steps:
      - uses: actions/checkout@v3
      
      # Test Cloud Functions
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '16'
      - name: Install cloud function dependencies
        run: cd cloud-functions && npm install
      - name: Run cloud function tests
        run: cd cloud-functions && npm test
      
      # Test Python components
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install Python dependencies
        run: pip install -r requirements-dev.txt
      - name: Run Python tests
        run: pytest python_components/
      
      # Security scanning
      - name: Run security scans
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'icap-processing:latest'
          format: 'sarif'
          output: 'trivy-results.sarif'
```

#### End-to-End Testing:
```yaml
name: End-to-End Tests

on:
  workflow_run:
    workflows: ["Run Tests"]
    types:
      - completed

jobs:
  e2e:
    runs-on: ubuntu-latest
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    services:
      neo4j:
        image: neo4j:5.5.0
        ports:
          - 7474:7474
          - 7687:7687
        env:
          NEO4J_AUTH: neo4j/password
    
    steps:
      - uses: actions/checkout@v3
      - name: Set up environment
        run: docker-compose -f docker-compose.test.yml up -d
      - name: Wait for services to be ready
        run: sleep 30
      - name: Run E2E tests
        run: npm run test:e2e
      - name: Tear down environment
        run: docker-compose -f docker-compose.test.yml down
```

### 4. Deploy Stage

Deployment occurs automatically for the staging environment, with manual approval for production.

#### Deploy to Staging:
```yaml
name: Deploy to Staging

on:
  workflow_run:
    workflows: ["End-to-End Tests"]
    branches: [staging]
    types:
      - completed

jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    steps:
      - uses: actions/checkout@v3
      
      # Authenticate with Google Cloud
      - id: 'auth'
        uses: 'google-github-actions/auth@v1'
        with:
          credentials_json: '${{ secrets.GCP_SA_KEY }}'
      
      # Deploy Cloud Functions
      - name: Deploy Cloud Functions
        run: |
          cd cloud-functions
          for function_dir in */; do
            cd "$function_dir"
            gcloud functions deploy "${function_dir%/}" \
              --runtime nodejs16 \
              --trigger-http \
              --allow-unauthenticated \
              --region us-central1
            cd ..
          done
      
      # Push Docker images to registry
      - name: Configure Docker
        uses: docker/login-action@v2
        with:
          registry: gcr.io
          username: _json_key
          password: ${{ secrets.GCP_SA_KEY }}
          
      - name: Tag and push images
        run: |
          docker tag icap-processing:latest gcr.io/${{ secrets.GCP_PROJECT_ID }}/icap-processing:staging
          docker push gcr.io/${{ secrets.GCP_PROJECT_ID }}/icap-processing:staging
```

#### Deploy to Production:
```yaml
name: Deploy to Production

on:
  workflow_dispatch:
    inputs:
      version:
        description: 'Version to deploy'
        required: true

jobs:
  deploy-production:
    runs-on: ubuntu-latest
    environment: production  # Requires manual approval
    steps:
      - uses: actions/checkout@v3
      
      # Authenticate with Google Cloud
      - id: 'auth'
        uses: 'google-github-actions/auth@v1'
        with:
          credentials_json: '${{ secrets.GCP_SA_KEY }}'
      
      # Deploy Cloud Functions
      - name: Deploy Cloud Functions
        run: |
          cd cloud-functions
          for function_dir in */; do
            cd "$function_dir"
            gcloud functions deploy "${function_dir%/}" \
              --runtime nodejs16 \
              --trigger-http \
              --allow-unauthenticated \
              --region us-central1
            cd ..
          done
      
      # Push Docker images to registry with production tag
      - name: Configure Docker
        uses: docker/login-action@v2
        with:
          registry: gcr.io
          username: _json_key
          password: ${{ secrets.GCP_SA_KEY }}
          
      - name: Tag and push images
        run: |
          docker tag icap-processing:latest gcr.io/${{ secrets.GCP_PROJECT_ID }}/icap-processing:${{ github.event.inputs.version }}
          docker tag icap-processing:latest gcr.io/${{ secrets.GCP_PROJECT_ID }}/icap-processing:production
          docker push gcr.io/${{ secrets.GCP_PROJECT_ID }}/icap-processing:${{ github.event.inputs.version }}
          docker push gcr.io/${{ secrets.GCP_PROJECT_ID }}/icap-processing:production
```

## Local Environment CI/CD

For the local Docker/WSL environment components, we provide a deployment script that pulls the latest images and configuration:

```bash
#!/bin/bash
# local_deploy.sh

# Pull latest configuration
echo "Pulling latest configuration..."
git pull origin main

# Pull latest Docker images
echo "Pulling latest Docker images..."
docker pull gcr.io/${GCP_PROJECT_ID}/icap-processing:production

# Stop running containers
echo "Stopping running containers..."
docker-compose down

# Start with new configuration
echo "Starting with new configuration..."
docker-compose up -d

# Verify deployment
echo "Verifying deployment..."
docker ps
curl -s http://localhost:8080/health | grep "status"

echo "Deployment complete."
```

## Monitoring and Observability

The CI/CD pipeline includes automated deployment of monitoring and observability tools:

1. **Logging:**
   - Cloud Logging for Google Cloud components
   - Fluentd for Docker container logs

2. **Monitoring:**
   - Cloud Monitoring dashboards
   - Prometheus for local metrics
   - Grafana for visualization

3. **Alerting:**
   - Cloud Monitoring alerts
   - PagerDuty integration for critical issues

## Rollback Procedures

In case of deployment failures, the CI/CD pipeline supports automated rollbacks:

1. **Cloud Functions:**
   ```bash
   gcloud functions deploy FUNCTION_NAME --version=PREVIOUS_VERSION
   ```

2. **Docker Containers:**
   ```bash
   docker-compose down
   docker tag gcr.io/${GCP_PROJECT_ID}/icap-processing:PREVIOUS_VERSION icap-processing:latest
   docker-compose up -d
   ```

## Security Considerations

The CI/CD pipeline implements several security best practices:

1. **Secrets Management:**
   - All secrets stored in GitHub Secrets or Google Secret Manager
   - No credentials in source code or Docker images

2. **Vulnerability Scanning:**
   - Automated dependency scanning with Dependabot
   - Container scanning before deployment
   - Regular OWASP ZAP scans for API endpoints

3. **Compliance:**
   - Audit logging for all CI/CD processes
   - Approval gates for production deployments
   - Separation of duties between environments

## Conclusion

This CI/CD pipeline enables rapid, reliable iteration of the ICAP project while maintaining security and quality standards. The automated testing and deployment processes reduce manual effort and potential for errors, allowing the development team to focus on delivering new features and improvements.