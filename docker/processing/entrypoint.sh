#!/bin/bash
set -e

# Max number of retries for Neo4j connection
MAX_RETRIES=30
# Delay between retries in seconds
RETRY_DELAY=5

echo "Starting ICAP processing container..."

# Load secrets from Google Secret Manager
load_secrets() {
    # Only try to load secrets if GOOGLE_CLOUD_PROJECT is set
    if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
        echo "GOOGLE_CLOUD_PROJECT not set. Skipping Secret Manager integration."
        return 0
    fi
    
    echo "Loading secrets from Google Secret Manager project: $GOOGLE_CLOUD_PROJECT"
    
    # Use the utility to generate a .env file
    if python -m scripts.generate_env_file --project-id="$GOOGLE_CLOUD_PROJECT" --output="/app/secrets/.env"; then
        echo "Successfully loaded secrets from Secret Manager"
        # Load the secrets into the environment
        if [ -f "/app/secrets/.env" ]; then
            export $(grep -v '^#' /app/secrets/.env | xargs)
            echo "Environment variables set from Secret Manager"
        fi
    else
        echo "Warning: Failed to load secrets from Secret Manager"
        echo "Continuing with existing environment variables..."
    fi
}

# Function to check Neo4j connection
check_neo4j_connection() {
    local uri=$NEO4J_URI
    local user=$NEO4J_USER
    local password=$NEO4J_PASSWORD
    
    python -c "
import sys
from neo4j import GraphDatabase
try:
    driver = GraphDatabase.driver('$uri', auth=('$user', '$password'))
    with driver.session() as session:
        result = session.run('RETURN 1 AS result')
        record = result.single()
        if record and record['result'] == 1:
            print('Neo4j connection successful')
            sys.exit(0)
        else:
            print('Neo4j query failed', file=sys.stderr)
            sys.exit(1)
except Exception as e:
    print(f'Neo4j connection error: {str(e)}', file=sys.stderr)
    sys.exit(1)
finally:
    if 'driver' in locals():
        driver.close()
"
    return $?
}

# Wait for Neo4j to be ready
wait_for_neo4j() {
    echo "Waiting for Neo4j to be ready..."
    
    local retry_count=0
    while [ $retry_count -lt $MAX_RETRIES ]; do
        if check_neo4j_connection; then
            echo "Neo4j is ready!"
            return 0
        else
            echo "Neo4j not ready yet. Retrying in $RETRY_DELAY seconds... (Attempt $((retry_count+1))/$MAX_RETRIES)"
            sleep $RETRY_DELAY
            retry_count=$((retry_count+1))
        fi
    done
    
    echo "Error: Failed to connect to Neo4j after $MAX_RETRIES attempts."
    return 1
}

# Initialize the database schema
initialize_database() {
    echo "Initializing Neo4j database schema..."
    
    python -c "
from neo4j import GraphDatabase
try:
    driver = GraphDatabase.driver('$NEO4J_URI', auth=('$NEO4J_USER', '$NEO4J_PASSWORD'))
    with driver.session() as session:
        # Create constraints
        session.run('CREATE CONSTRAINT IF NOT EXISTS FOR (a:ActionItem) REQUIRE a.id IS UNIQUE')
        session.run('CREATE CONSTRAINT IF NOT EXISTS FOR (p:Person) REQUIRE p.email IS UNIQUE')
        session.run('CREATE CONSTRAINT IF NOT EXISTS FOR (p:Project) REQUIRE p.name IS UNIQUE')
    print('Database schema initialized successfully')
except Exception as e:
    print(f'Database initialization error: {str(e)}')
    raise
finally:
    if 'driver' in locals():
        driver.close()
"
}

# Create health check file
create_health_file() {
    echo "Creating health check file..."
    date > /app/health
    echo "ICAP processing container is healthy" >> /app/health
}

# Verify required environment variables
verify_environment() {
    echo "Verifying required environment variables..."
    
    local required_vars=("NEO4J_URI" "NEO4J_USER" "NEO4J_PASSWORD" "CLAUDE_API_KEY")
    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        echo "Error: Missing required environment variables: ${missing_vars[*]}"
        return 1
    fi
    
    echo "All required environment variables are set."
    return 0
}

# Main function
main() {
    # Load secrets from Secret Manager
    load_secrets
    
    # Verify required environment variables
    verify_environment || exit 1
    
    # Wait for Neo4j to be ready
    wait_for_neo4j || exit 1
    
    # Initialize the database schema
    initialize_database
    
    # Create health check file
    create_health_file
    
    # Start the main process
    echo "Starting main application process..."
    exec python -m python_components.main
}

# Run main function
main