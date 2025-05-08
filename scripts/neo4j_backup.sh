#!/bin/bash
# Neo4j backup and restore script for ICAP project

set -e

# Configuration
CONTAINER_NAME="icap-neo4j"
BACKUP_DIR="/mnt/c/Users/magic/Projects/EmailSlackProcessor/backups"
DATABASE_NAME="neo4j"  # Default database name
DATE_FORMAT=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/neo4j_backup_${DATE_FORMAT}.dump"

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

# Function to display usage
usage() {
    echo "Usage: $0 [OPTIONS] COMMAND"
    echo ""
    echo "Commands:"
    echo "  backup              Create a backup of the Neo4j database"
    echo "  restore FILENAME    Restore a Neo4j database from backup"
    echo "  list                List available backups"
    echo ""
    echo "Options:"
    echo "  -d, --database NAME   Specify database name (default: neo4j)"
    echo "  -h, --help            Display this help message"
    echo ""
    echo "Examples:"
    echo "  $0 backup                   # Backup default database"
    echo "  $0 -d mediadb backup        # Backup specific database"
    echo "  $0 restore backup_file.dump # Restore from backup file"
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--database)
            DATABASE_NAME="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        backup|restore|list)
            COMMAND="$1"
            shift
            ;;
        *)
            if [[ -z "${COMMAND}" ]]; then
                echo "Error: Unknown option or command: $1"
                usage
            else
                # Treat as an argument to a command
                ARGS+=("$1")
                shift
            fi
            ;;
    esac
done

# Check if command is specified
if [[ -z "${COMMAND}" ]]; then
    echo "Error: No command specified"
    usage
fi

# Function to check if container is running
check_container() {
    if ! docker ps | grep -q "${CONTAINER_NAME}"; then
        echo "Error: Neo4j container '${CONTAINER_NAME}' is not running"
        exit 1
    fi
}

# Function to backup Neo4j database
backup_database() {
    check_container
    
    echo "Backing up Neo4j database '${DATABASE_NAME}' to ${BACKUP_FILE}..."
    
    # Determine Neo4j version to use the correct command
    NEO4J_VERSION=$(docker exec "${CONTAINER_NAME}" neo4j --version | grep -oP '\d+\.\d+\.\d+')
    MAJOR_VERSION=$(echo "${NEO4J_VERSION}" | cut -d. -f1)
    
    if [[ "${MAJOR_VERSION}" -ge 5 ]]; then
        # Neo4j 5.x
        docker exec "${CONTAINER_NAME}" neo4j-admin database dump "${DATABASE_NAME}" --to-path=/tmp/
        docker cp "${CONTAINER_NAME}:/tmp/${DATABASE_NAME}.dump" "${BACKUP_FILE}"
        docker exec "${CONTAINER_NAME}" rm "/tmp/${DATABASE_NAME}.dump"
    else
        # Neo4j 4.x
        docker exec "${CONTAINER_NAME}" neo4j-admin dump --database="${DATABASE_NAME}" --to=/tmp/${DATABASE_NAME}.dump
        docker cp "${CONTAINER_NAME}:/tmp/${DATABASE_NAME}.dump" "${BACKUP_FILE}"
        docker exec "${CONTAINER_NAME}" rm "/tmp/${DATABASE_NAME}.dump"
    fi
    
    if [[ -f "${BACKUP_FILE}" ]]; then
        echo "Backup completed successfully: ${BACKUP_FILE}"
        echo "Backup size: $(du -h "${BACKUP_FILE}" | cut -f1)"
    else
        echo "Error: Backup failed"
        exit 1
    fi
}

# Function to restore Neo4j database
restore_database() {
    check_container
    
    # Check if backup file is specified
    if [[ ${#ARGS[@]} -eq 0 ]]; then
        echo "Error: No backup file specified for restore"
        usage
    fi
    
    RESTORE_FILE="${ARGS[0]}"
    
    # Check if restore file exists (either as absolute path or relative to backup dir)
    if [[ ! -f "${RESTORE_FILE}" && ! -f "${BACKUP_DIR}/${RESTORE_FILE}" ]]; then
        echo "Error: Backup file not found: ${RESTORE_FILE}"
        echo "Available backups:"
        list_backups
        exit 1
    fi
    
    # If relative path, prepend backup directory
    if [[ ! -f "${RESTORE_FILE}" ]]; then
        RESTORE_FILE="${BACKUP_DIR}/${RESTORE_FILE}"
    fi
    
    echo "Restoring Neo4j database '${DATABASE_NAME}' from ${RESTORE_FILE}..."
    
    # Determine Neo4j version to use the correct command
    NEO4J_VERSION=$(docker exec "${CONTAINER_NAME}" neo4j --version | grep -oP '\d+\.\d+\.\d+')
    MAJOR_VERSION=$(echo "${NEO4J_VERSION}" | cut -d. -f1)
    
    # Stop Neo4j before restore
    echo "Stopping Neo4j..."
    docker exec "${CONTAINER_NAME}" neo4j stop
    
    # Copy backup file to container
    docker cp "${RESTORE_FILE}" "${CONTAINER_NAME}:/tmp/restore.dump"
    
    if [[ "${MAJOR_VERSION}" -ge 5 ]]; then
        # Neo4j 5.x
        docker exec "${CONTAINER_NAME}" neo4j-admin database load "${DATABASE_NAME}" --from-path=/tmp/
        docker exec "${CONTAINER_NAME}" mv "/tmp/restore.dump" "/tmp/${DATABASE_NAME}.dump"
        docker exec "${CONTAINER_NAME}" neo4j-admin database load "${DATABASE_NAME}" --from-path=/tmp/
        docker exec "${CONTAINER_NAME}" rm "/tmp/${DATABASE_NAME}.dump"
    else
        # Neo4j 4.x
        docker exec "${CONTAINER_NAME}" neo4j-admin load --database="${DATABASE_NAME}" --from=/tmp/restore.dump --force
        docker exec "${CONTAINER_NAME}" rm "/tmp/restore.dump"
    fi
    
    # Start Neo4j after restore
    echo "Starting Neo4j..."
    docker exec "${CONTAINER_NAME}" neo4j start
    
    echo "Restore completed successfully"
}

# Function to list available backups
list_backups() {
    echo "Available backups in ${BACKUP_DIR}:"
    if [[ -d "${BACKUP_DIR}" ]]; then
        ls -lh "${BACKUP_DIR}" | grep -E "\.dump$" | awk '{print $9 " (" $5 ")"}'
    else
        echo "  No backups found"
    fi
}

# Execute the specified command
case "${COMMAND}" in
    backup)
        backup_database
        ;;
    restore)
        restore_database
        ;;
    list)
        list_backups
        ;;
    *)
        echo "Error: Unknown command: ${COMMAND}"
        usage
        ;;
esac