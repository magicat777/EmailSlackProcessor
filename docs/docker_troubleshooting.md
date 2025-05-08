# Docker and Neo4j Troubleshooting Guide

This guide provides solutions for common issues encountered with Docker and Neo4j in the ICAP project.

## Common Docker Issues

### Container Connectivity Problems

**Issue:** The processing container cannot connect to Neo4j after container restarts.

**Solutions:**
1. Check if Neo4j container is healthy:
   ```bash
   docker ps # Check HEALTH status column
   ```

2. Verify both HTTP and Bolt interfaces are responding:
   ```bash
   curl -s -I http://localhost:7475
   docker exec icap-neo4j cypher-shell -u neo4j -p password "RETURN 1"
   ```

3. Restart with progressive connection retries:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

### Neo4j Marked as "Up" Before Bolt Interface Ready

**Issue:** The Neo4j container shows as "running" but the Bolt interface isn't accepting connections.

**Solutions:**
1. The healthcheck implementation checks both HTTP and Bolt interfaces
2. Use `depends_on` with `condition: service_healthy` to ensure Neo4j is fully ready
3. If problems persist, increase the retry count in `entrypoint.sh`

### Port Conflicts

**Issue:** Port conflicts when running Neo4j Desktop alongside Docker containers.

**Solutions:**
1. We use remapped ports (7475:7474 and 7688:7687) to avoid conflicts
2. To use different ports, update both docker-compose.yml and processing environment variables:
   ```yaml
   ports:
     - "7476:7474"  # Different HTTP port
     - "7689:7687"  # Different Bolt port
   
   environment:
     - NEO4J_URI=bolt://neo4j:7687  # Internal port remains the same
   ```

## Neo4j Issues

### Database Connectivity After Restarts

**Issue:** Processing container cannot connect to Neo4j after database restarts.

**Solutions:**
1. The entrypoint script has progressive retry logic built in
2. If needed, increase MAX_RETRIES and adjust RETRY_DELAY in `entrypoint.sh`
3. Manual recovery command:
   ```bash
   docker-compose restart processing
   ```

### Database Format Compatibility Issues

**Issue:** Neo4j version compatibility problems between environments.

**Solutions:**
1. The backup/restore script detects Neo4j version and uses appropriate commands
2. Always use the same Neo4j version in all environments (we use 5.9.0)
3. For migration between major versions, use Neo4j's official migration tools

### Database Locking During Operations

**Issue:** Database becomes locked during operations.

**Solutions:**
1. Ensure proper Neo4j shutdown before backups:
   ```bash
   docker exec icap-neo4j neo4j stop
   ```
2. Always use our backup script which handles this automatically
3. Avoid simultaneous operations that might cause lock contention

## Backup and Restore Procedures

### Creating a Database Backup

```bash
# Backup the default Neo4j database
./scripts/neo4j_backup.sh backup

# Backup a specific database
./scripts/neo4j_backup.sh -d mydatabase backup
```

### Restoring from Backup

```bash
# List available backups
./scripts/neo4j_backup.sh list

# Restore from a specific backup file
./scripts/neo4j_backup.sh restore neo4j_backup_20250507_120000.dump
```

### Scheduled Backups

Add a cron job for regular backups:

```bash
# Add to crontab -e
0 2 * * * /path/to/EmailSlackProcessor/scripts/neo4j_backup.sh backup
```

## Performance Tuning

### Neo4j Memory Settings

Memory settings are configured in `neo4j.conf`:

```
dbms.memory.heap.initial_size=1G
dbms.memory.heap.max_size=2G
dbms.memory.pagecache.size=1G
```

Adjust these values according to your system's available memory.

### Thread Pool Configuration

Thread pool settings are configured in `neo4j.conf`:

```
dbms.connector.bolt.thread_pool_min_size=10
dbms.connector.bolt.thread_pool_max_size=50
```

For high load scenarios, increase these values based on the number of concurrent connections.

## Container Monitoring

### Viewing Container Logs

```bash
# View Neo4j container logs
docker logs icap-neo4j

# View Processing container logs
docker logs icap-processing

# Follow logs in real-time
docker logs -f icap-neo4j
```

### Checking Container Health

```bash
# Check all containers
docker ps

# Detailed inspection
docker inspect icap-neo4j | grep -A 10 "Health"
```

### Container Resource Usage

```bash
# View resource usage
docker stats icap-neo4j icap-processing
```

## Advanced Troubleshooting

### Accessing Neo4j Shell

```bash
docker exec -it icap-neo4j bash
```

### Running Cypher Commands

```bash
docker exec -it icap-neo4j cypher-shell -u neo4j -p password
```

### Inspecting Neo4j Logs

```bash
docker exec -it icap-neo4j cat /logs/neo4j.log
```

### Testing Python Neo4j Connection Manually

```bash
docker exec -it icap-processing python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://neo4j:7687', auth=('neo4j', 'password'))
with driver.session() as session:
    result = session.run('MATCH (n) RETURN count(n)')
    print(result.single()[0])
driver.close()
"
```

## Best Practices

1. Always use the provided scripts for database operations
2. Perform regular backups using the `neo4j_backup.sh` script
3. Use `docker-compose down/up` instead of `restart` when changing configurations
4. Monitor Neo4j memory usage and adjust settings accordingly
5. Check logs when troubleshooting connectivity issues