#!/bin/bash
# Deploy Cloud Functions script for ICAP

set -e  # Exit on error

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-icap}"
REGION="us-central1"
SERVICE_ACCOUNT=""
RUNTIME="nodejs16"
MEMORY="256MB"
TIMEOUT="60s"
WEBHOOK_URL=""
ENV_VARS=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print usage
function print_usage() {
  echo -e "${BLUE}ICAP Cloud Functions Deployment${NC}"
  echo ""
  echo "Usage: $0 [options] [function_names]"
  echo ""
  echo "Options:"
  echo "  --project=<id>       Set Google Cloud project ID (default: $PROJECT_ID)"
  echo "  --region=<region>    Set deployment region (default: $REGION)"
  echo "  --service-account=<email> Set service account email"
  echo "  --memory=<size>      Set memory allocation (default: $MEMORY)"
  echo "  --timeout=<seconds>  Set function timeout (default: $TIMEOUT)"
  echo "  --webhook=<url>      Set webhook URL for notifications"
  echo "  --set-env=<key=value> Set environment variable (can be used multiple times)"
  echo "  --all                Deploy all functions"
  echo "  --dry-run            Show commands without executing"
  echo "  --help               Show this help message"
  echo ""
  echo "Functions:"
  echo "  email-retriever      Email retrieval function"
  echo "  slack-retriever      Slack message retrieval function"
  echo "  notification-sender  Notification sender function"
  echo ""
  echo "Examples:"
  echo "  $0 --all"
  echo "  $0 email-retriever slack-retriever"
  echo "  $0 --project=my-project --region=us-east1 --all"
  echo "  $0 --set-env=DEBUG=true --set-env=LOG_LEVEL=info email-retriever"
}

# Check if a command succeeds silently
function command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
function check_prerequisites() {
  echo -e "${BLUE}Checking prerequisites...${NC}"
  
  # Check gcloud
  if ! command_exists gcloud; then
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
  
  # Check if project exists and is accessible
  if ! gcloud projects describe "$PROJECT_ID" > /dev/null 2>&1; then
    echo -e "${RED}Error: Project $PROJECT_ID not found or not accessible${NC}"
    echo "Please check the project ID and your permissions"
    exit 1
  fi
  
  echo -e "${GREEN}Prerequisites satisfied${NC}"
}

# Deploy a function
function deploy_function() {
  local function_name=$1
  local function_path="cloud-functions/$function_name"
  
  if [ ! -d "$function_path" ]; then
    echo -e "${RED}Error: Function directory $function_path not found${NC}"
    return 1
  fi
  
  echo -e "${BLUE}Deploying $function_name...${NC}"
  
  # Determine entry point based on package.json
  local entry_point=$(grep -oP '"main": "\K[^"]+' "$function_path/package.json" | sed 's/\.js$//')
  if [ -z "$entry_point" ]; then
    entry_point="index"
  fi
  
  # Find all exported functions in the entry point file
  local triggers=()
  local functions_file="$function_path/$entry_point.js"
  
  # Look for exported functions
  while IFS= read -r line; do
    if [[ $line =~ exports\.([a-zA-Z0-9_]+)\ *= ]]; then
      triggers+=("${BASH_REMATCH[1]}")
    fi
  done < "$functions_file"
  
  if [ ${#triggers[@]} -eq 0 ]; then
    echo -e "${RED}Error: No exported functions found in $functions_file${NC}"
    return 1
  fi
  
  # Deploy each function entry point
  for trigger in "${triggers[@]}"; do
    echo -e "${BLUE}Deploying entry point: $trigger${NC}"
    
    # Build the gcloud command
    local deploy_cmd="gcloud functions deploy $function_name-$trigger"
    deploy_cmd+=" --project=$PROJECT_ID"
    deploy_cmd+=" --region=$REGION"
    deploy_cmd+=" --runtime=$RUNTIME"
    deploy_cmd+=" --memory=$MEMORY"
    deploy_cmd+=" --timeout=$TIMEOUT"
    deploy_cmd+=" --entry-point=$trigger"
    deploy_cmd+=" --source=$function_path"
    deploy_cmd+=" --trigger-http"
    deploy_cmd+=" --allow-unauthenticated"
    
    # Add service account if specified
    if [ -n "$SERVICE_ACCOUNT" ]; then
      deploy_cmd+=" --service-account=$SERVICE_ACCOUNT"
    fi
    
    # Add environment variables if specified
    if [ -n "$ENV_VARS" ]; then
      deploy_cmd+=" --set-env-vars=$ENV_VARS"
    fi
    
    # Add webhook
    if [ -n "$WEBHOOK_URL" ]; then
      if [[ $ENV_VARS == *"WEBHOOK_URL="* ]]; then
        # Update existing webhook URL
        ENV_VARS=$(echo "$ENV_VARS" | sed "s|WEBHOOK_URL=[^,]*|WEBHOOK_URL=$WEBHOOK_URL|")
      else
        # Add webhook URL
        if [ -n "$ENV_VARS" ]; then
          ENV_VARS="$ENV_VARS,WEBHOOK_URL=$WEBHOOK_URL"
        else
          ENV_VARS="WEBHOOK_URL=$WEBHOOK_URL"
        fi
      fi
    fi
    
    # Execute or show the command
    if [ "$DRY_RUN" = true ]; then
      echo "$deploy_cmd"
    else
      echo "$deploy_cmd"
      eval "$deploy_cmd"
    fi
  done
  
  echo -e "${GREEN}Deployed $function_name successfully${NC}"
}

# Parse arguments
FUNCTIONS=()
DEPLOY_ALL=false
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
      SERVICE_ACCOUNT="${1#*=}"
      shift
      ;;
    --memory=*)
      MEMORY="${1#*=}"
      shift
      ;;
    --timeout=*)
      TIMEOUT="${1#*=}"
      shift
      ;;
    --webhook=*)
      WEBHOOK_URL="${1#*=}"
      shift
      ;;
    --set-env=*)
      ENV_VAR="${1#*=}"
      if [ -n "$ENV_VARS" ]; then
        ENV_VARS="$ENV_VARS,$ENV_VAR"
      else
        ENV_VARS="$ENV_VAR"
      fi
      shift
      ;;
    --all)
      DEPLOY_ALL=true
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
    -*)
      echo -e "${RED}Error: Unknown option $1${NC}"
      print_usage
      exit 1
      ;;
    *)
      FUNCTIONS+=("$1")
      shift
      ;;
  esac
done

# Show configuration
echo -e "${BLUE}Deployment Configuration:${NC}"
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Service Account: ${SERVICE_ACCOUNT:-default}"
echo "Memory: $MEMORY"
echo "Timeout: $TIMEOUT"
echo "Webhook URL: ${WEBHOOK_URL:-none}"
echo "Environment Variables: ${ENV_VARS:-none}"
echo "Dry Run: $DRY_RUN"
echo ""

# Check prerequisites
check_prerequisites

# Deploy functions
if [ "$DEPLOY_ALL" = true ]; then
  echo -e "${BLUE}Deploying all functions...${NC}"
  FUNCTIONS=("email-retriever" "slack-retriever" "notification-sender")
fi

if [ ${#FUNCTIONS[@]} -eq 0 ]; then
  echo -e "${YELLOW}No functions specified. Use --all to deploy all functions.${NC}"
  print_usage
  exit 1
fi

for function_name in "${FUNCTIONS[@]}"; do
  deploy_function "$function_name"
done

echo -e "${GREEN}Deployment completed successfully${NC}"