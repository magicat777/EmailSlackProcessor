// ICAP Neo4j Database Schema

// Create constraints to ensure uniqueness and improve performance
CREATE CONSTRAINT action_item_id IF NOT EXISTS FOR (a:ActionItem) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT person_email IF NOT EXISTS FOR (p:Person) REQUIRE p.email IS UNIQUE;
CREATE CONSTRAINT project_name IF NOT EXISTS FOR (p:Project) REQUIRE p.name IS UNIQUE;
CREATE CONSTRAINT customer_name IF NOT EXISTS FOR (c:Customer) REQUIRE c.name IS UNIQUE;
CREATE CONSTRAINT source_id IF NOT EXISTS FOR (s:Source) REQUIRE s.id IS UNIQUE;

// Create indexes for frequently queried properties
CREATE INDEX action_item_status IF NOT EXISTS FOR (a:ActionItem) ON (a.status);
CREATE INDEX action_item_priority IF NOT EXISTS FOR (a:ActionItem) ON (a.priority);
CREATE INDEX action_item_due_date IF NOT EXISTS FOR (a:ActionItem) ON (a.due_date);
CREATE INDEX action_item_created_at IF NOT EXISTS FOR (a:ActionItem) ON (a.created_at);

// Sample data - Initial project creation
MERGE (project:Project {name: 'ICAP'})
SET project.description = 'Intelligent Communication Action Processor',
    project.created_at = datetime()
RETURN project;

// Create relationship types
// MATCH (a:ActionItem), (p:Person) WHERE a.id = 'xxx' AND p.email = 'person@example.com'
// CREATE (a)-[:ASSIGNED_TO]->(p);

// MATCH (a:ActionItem), (p:Project) WHERE a.id = 'xxx' AND p.name = 'ICAP'
// CREATE (a)-[:BELONGS_TO]->(p);

// MATCH (p:Project), (c:Customer) WHERE p.name = 'ICAP' AND c.name = 'Example Corp'
// CREATE (p)-[:FOR_CUSTOMER]->(c);

// MATCH (a:ActionItem), (s:Source) WHERE a.id = 'xxx' AND s.id = 'message123'
// CREATE (a)-[:EXTRACTED_FROM]->(s);

// MATCH (a1:ActionItem), (a2:ActionItem) WHERE a1.id = 'xxx' AND a2.id = 'yyy'
// CREATE (a1)-[:RELATED_TO]->(a2);

// Example query to get all pending action items for a specific person
/*
MATCH (a:ActionItem)-[:ASSIGNED_TO]->(p:Person)
WHERE p.email = 'user@example.com' AND a.status = 'pending'
RETURN a
ORDER BY a.priority, a.due_date
*/

// Example query to get all action items for a specific project
/*
MATCH (a:ActionItem)-[:BELONGS_TO]->(p:Project)
WHERE p.name = 'ICAP'
RETURN a
ORDER BY a.created_at DESC
*/

// Example query to get all action items with their relationships
/*
MATCH (a:ActionItem)
OPTIONAL MATCH (a)-[:ASSIGNED_TO]->(person:Person)
OPTIONAL MATCH (a)-[:BELONGS_TO]->(project:Project)
OPTIONAL MATCH (a)-[:EXTRACTED_FROM]->(source:Source)
RETURN a, person, project, source
ORDER BY a.created_at DESC
*/

// Example query to find related action items
/*
MATCH (a:ActionItem {id: 'xxx'})-[:RELATED_TO]-(related:ActionItem)
RETURN related
*/