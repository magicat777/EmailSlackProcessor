#!/bin/bash
# GCP Project Setup Script for ICAP

set -e  # Exit on error

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-icap}"
REGION="us-central1"
SERVICE_ACCOUNT_NAME="icap-service-account"
SERVICE_ACCOUNT_DISPLAY_NAME="ICAP Service Account"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print usage
function print_usage() {
  echo -e "${BLUE}ICAP GCP Project Setup${NC}"
  echo ""
  echo "Usage: $0 [options]"
  echo ""
  echo "Options:"
  echo "  --project=<id>          Set Google Cloud project ID (default: $PROJECT_ID)"
  echo "  --region=<region>       Set default region (default: $REGION)"
  echo "  --service-account=<name> Set service account name (default: $SERVICE_ACCOUNT_NAME)"
  echo "  --dry-run               Show commands without executing"
  echo "  --help                  Show this help message"
  echo ""
  echo "This script sets up a Google Cloud Platform project for ICAP by:"
  echo "  1. Enabling required APIs"
  echo "  2. Creating a service account"
  echo "  3. Granting necessary permissions"
  echo "  4. Setting up Secret Manager"
  echo ""
}

# Function to check prerequisites
function check_prerequisites() {
  echo -e "${BLUE}Checking prerequisites...${NC}"
  
  # Check gcloud
  if ! command -v gcloud >/dev/null 2>&1; then
    echo -e "${RED}Error: gcloud CLI not found${NC}"
    echo "Please install the Google Cloud SDK: https://cloud.google.com/sdk/docs/install"
    exit 1
  fi
  
  # Check if logged in
  if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" > /dev/null 2>&1; then
    echo -e "${RED}Error: Not logged in to gcloud${NC}"
    echo "Please run: gcloud auth login"
    exit 1
  fi
  
  # Check if the project exists
  if ! gcloud projects describe "$PROJECT_ID" > /dev/null 2>&1; then
    echo -e "${YELLOW}Project $PROJECT_ID does not exist.${NC}"
    
    read -p "Would you like to create it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      if [ "$DRY_RUN" = true ]; then
        echo "Would run: gcloud projects create $PROJECT_ID"
      else
        echo "Creating project $PROJECT_ID..."
        gcloud projects create "$PROJECT_ID"
      fi
    else
      echo -e "${RED}Project creation cancelled. Exiting.${NC}"
      exit 1
    fi
  fi
  
  # Check billing account
  if ! gcloud billing projects describe "$PROJECT_ID" > /dev/null 2>&1; then
    echo -e "${YELLOW}Project $PROJECT_ID does not have billing enabled.${NC}"
    
    # List available billing accounts
    echo "Available billing accounts:"
    gcloud billing accounts list
    
    read -p "Enter the billing account ID to use: " billing_account
    
    if [ -n "$billing_account" ]; then
      if [ "$DRY_RUN" = true ]; then
        echo "Would run: gcloud billing projects link $PROJECT_ID --billing-account=$billing_account"
      else
        echo "Linking project $PROJECT_ID to billing account $billing_account..."
        gcloud billing projects link "$PROJECT_ID" --billing-account="$billing_account"
      fi
    else
      echo -e "${YELLOW}No billing account specified. Some services may not work.${NC}"
    fi
  fi
  
  echo -e "${GREEN}Prerequisites satisfied${NC}"
}

# Function to enable required APIs
function enable_apis() {
  echo -e "${BLUE}Enabling required APIs...${NC}"
  
  APIs=(
    "cloudfunctions.googleapis.com"      # Cloud Functions
    "cloudscheduler.googleapis.com"      # Cloud Scheduler
    "secretmanager.googleapis.com"       # Secret Manager
    "artifactregistry.googleapis.com"    # Artifact Registry
    "cloudbuild.googleapis.com"          # Cloud Build
    "iam.googleapis.com"                 # Identity and Access Management
    "cloudresourcemanager.googleapis.com" # Resource Manager
    "logging.googleapis.com"             # Cloud Logging
  )
  
  for api in "${APIs[@]}"; do
    echo "Enabling $api..."
    if [ "$DRY_RUN" = true ]; then
      echo "Would run: gcloud services enable $api --project=$PROJECT_ID"
    else
      gcloud services enable "$api" --project="$PROJECT_ID" || echo -e "${YELLOW}Warning: Failed to enable $api${NC}"
    fi
  done
  
  echo -e "${GREEN}APIs enabled${NC}"
}

# Function to create service account
function create_service_account() {
  echo -e "${BLUE}Setting up service account...${NC}"
  
  # Check if service account already exists
  if gcloud iam service-accounts describe "$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com" --project="$PROJECT_ID" > /dev/null 2>&1; then
    echo "Service account $SERVICE_ACCOUNT_NAME already exists"
  else
    echo "Creating service account $SERVICE_ACCOUNT_NAME..."
    if [ "$DRY_RUN" = true ]; then
      echo "Would run: gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME --display-name=\"$SERVICE_ACCOUNT_DISPLAY_NAME\" --project=$PROJECT_ID"
    else
      gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
        --display-name="$SERVICE_ACCOUNT_DISPLAY_NAME" \
        --project="$PROJECT_ID"
    fi
  fi
  
  # Grant required roles
  ROLES=(
    "roles/cloudfunctions.developer"
    "roles/secretmanager.secretAccessor"
    "roles/logging.logWriter"
    "roles/cloudscheduler.admin"
  )
  
  for role in "${ROLES[@]}"; do
    echo "Granting $role to service account..."
    if [ "$DRY_RUN" = true ]; then
      echo "Would run: gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com --role=$role"
    else
      gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
        --role="$role"
    fi
  done
  
  echo -e "${GREEN}Service account setup complete${NC}"
}

# Function to set up Secret Manager
function setup_secret_manager() {
  echo -e "${BLUE}Setting up Secret Manager...${NC}"
  
  # Create basic secrets if they don't exist
  SECRETS=(
    "webhook-token"
    "neo4j-uri"
    "neo4j-user"
    "neo4j-password"
  )
  
  for secret in "${SECRETS[@]}"; do
    # Check if secret exists
    if gcloud secrets describe "$secret" --project="$PROJECT_ID" > /dev/null 2>&1; then
      echo "Secret $secret already exists"
    else
      echo "Creating secret $secret..."
      if [ "$DRY_RUN" = true ]; then
        echo "Would run: gcloud secrets create $secret --replication-policy=\"automatic\" --project=$PROJECT_ID"
      else
        gcloud secrets create "$secret" \
          --replication-policy="automatic" \
          --project="$PROJECT_ID"
        
        # Add placeholder value
        echo "Adding placeholder value to $secret..."
        echo "PLACEHOLDER_VALUE" | gcloud secrets versions add "$secret" --data-file=- --project="$PROJECT_ID"
      fi
    fi
    
    # Grant service account access
    echo "Granting access to $secret for service account..."
    if [ "$DRY_RUN" = true ]; then
      echo "Would run: gcloud secrets add-iam-policy-binding $secret --member=serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com --role=roles/secretmanager.secretAccessor --project=$PROJECT_ID"
    else
      gcloud secrets add-iam-policy-binding "$secret" \
        --member="serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
        --role="roles/secretmanager.secretAccessor" \
        --project="$PROJECT_ID"
    fi
  done
  
  echo -e "${GREEN}Secret Manager setup complete${NC}"
}

# Function to set up Cloud Scheduler
function setup_cloud_scheduler() {
  echo -e "${BLUE}Setting up Cloud Scheduler...${NC}"
  
  # Check if the App Engine app exists (required for Cloud Scheduler)
  if ! gcloud app describe --project="$PROJECT_ID" > /dev/null 2>&1; then
    echo "Creating App Engine application (required for Cloud Scheduler)..."
    if [ "$DRY_RUN" = true ]; then
      echo "Would run: gcloud app create --region=$REGION --project=$PROJECT_ID"
    else
      # Try to create App Engine app, but don't fail if it already exists
      gcloud app create --region="$REGION" --project="$PROJECT_ID" || true
    fi
  fi
  
  echo -e "${GREEN}Cloud Scheduler setup complete${NC}"
}

# Parse arguments
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --project=*)
      PROJECT_ID="${1#*=}"
      shift
      ;;
    --region=*)
      REGION="${1#*=}"
      shift
      ;;
    --service-account=*)
      SERVICE_ACCOUNT_NAME="${1#*=}"
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --help)
      print_usage
      exit 0
      ;;
    *)
      echo -e "${RED}Error: Unknown option $1${NC}"
      print_usage
      exit 1
      ;;
  esac
done

# Show configuration
echo -e "${BLUE}GCP Project Setup Configuration:${NC}"
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Service Account: $SERVICE_ACCOUNT_NAME"
echo "Dry Run: $DRY_RUN"
echo ""

# Run setup steps
check_prerequisites
enable_apis
create_service_account
setup_secret_manager
setup_cloud_scheduler

echo -e "${GREEN}GCP project setup completed successfully${NC}"
echo ""
echo "Next steps:"
echo "1. Update secrets with real values using the setup_secrets.py script"
echo "2. Deploy Cloud Functions using deploy_cloud_functions.py"
echo "3. Test the functions and set up monitoring"