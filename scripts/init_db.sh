#!/bin/bash
# Initialize Neo4j database with schema

set -e

# Configuration
CONTAINER_NAME="icap-neo4j"
SCHEMA_FILE="../database/schema.cypher"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="password"

# Check if schema file exists
if [ ! -f "$SCHEMA_FILE" ]; then
    echo "Error: Schema file not found: $SCHEMA_FILE"
    exit 1
fi

# Check if Neo4j container is running
if ! docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
    echo "Error: Neo4j container is not running"
    echo "Please start the container with: docker-compose up -d neo4j"
    exit 1
fi

# Wait for Neo4j to be ready
echo "Waiting for Neo4j to be ready..."
MAX_RETRIES=20
retry_count=0

while [ $retry_count -lt $MAX_RETRIES ]; do
    if docker exec $CONTAINER_NAME cypher-shell -u $NEO4J_USER -p $NEO4J_PASSWORD "RETURN 1" &>/dev/null; then
        echo "Neo4j is ready!"
        break
    else
        echo "Neo4j not ready yet. Retrying in 5 seconds... (Attempt $((retry_count+1))/$MAX_RETRIES)"
        sleep 5
        retry_count=$((retry_count+1))
    fi
done

if [ $retry_count -eq $MAX_RETRIES ]; then
    echo "Error: Failed to connect to Neo4j after $MAX_RETRIES attempts."
    exit 1
fi

# Execute the schema file
echo "Initializing Neo4j database schema..."
cat $SCHEMA_FILE | docker exec -i $CONTAINER_NAME cypher-shell -u $NEO4J_USER -p $NEO4J_PASSWORD

echo "Neo4j database schema initialized successfully!"
echo "You can access the Neo4j browser at: http://localhost:7490"
echo "Username: $NEO4J_USER"
echo "Password: $NEO4J_PASSWORD"