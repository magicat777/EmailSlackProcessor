"""
Neo4j database manager for ICAP.
"""
import os
import logging
from typing import Dict, Any, List, Optional
from neo4j import GraphDatabase, Driver, Session

logger = logging.getLogger("icap.neo4j")

class Neo4jManager:
    """Manager class for Neo4j database operations."""
    
    def __init__(self):
        """Initialize the Neo4j connection."""
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password")
        self.driver: Optional[Driver] = None
        self.connect()
    
    def connect(self) -> None:
        """Establish connection to Neo4j database."""
        try:
            self.driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
            logger.info(f"Connected to Neo4j database at {self.uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            raise
    
    def close(self) -> None:
        """Close the Neo4j connection."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
    
    def get_session(self) -> Session:
        """Get a Neo4j session."""
        if not self.driver:
            self.connect()
        return self.driver.session()
    
    def create_constraints(self) -> None:
        """Create database constraints."""
        with self.get_session() as session:
            # Create constraint on ActionItem.id
            session.run("""
                CREATE CONSTRAINT IF NOT EXISTS FOR (a:ActionItem) 
                REQUIRE a.id IS UNIQUE
            """)
            
            # Create constraint on Person.email
            session.run("""
                CREATE CONSTRAINT IF NOT EXISTS FOR (p:Person) 
                REQUIRE p.email IS UNIQUE
            """)
            
            # Create constraint on Project.name
            session.run("""
                CREATE CONSTRAINT IF NOT EXISTS FOR (p:Project) 
                REQUIRE p.name IS UNIQUE
            """)
            
            logger.info("Database constraints created")
    
    def create_action_item(self, action_item: Dict[str, Any]) -> str:
        """
        Create a new action item in the database.
        
        Args:
            action_item: Dictionary containing action item properties
                - id: Unique identifier
                - content: The action item text
                - source: Source of the action item (email/slack)
                - source_id: ID in the original source
                - created_at: Timestamp when created
                - due_date: Optional due date
                - priority: Priority level (high/medium/low)
                - status: Current status
                
        Returns:
            The ID of the created action item
        """
        with self.get_session() as session:
            result = session.run("""
                CREATE (a:ActionItem {
                    id: $id,
                    content: $content,
                    source: $source,
                    source_id: $source_id,
                    created_at: $created_at,
                    due_date: $due_date,
                    priority: $priority,
                    status: $status
                })
                RETURN a.id as id
            """, action_item)
            
            record = result.single()
            return record["id"]
    
    def link_action_to_person(self, action_id: str, person_email: str, 
                             relationship_type: str = "ASSIGNED_TO") -> None:
        """
        Link an action item to a person.
        
        Args:
            action_id: The action item ID
            person_email: The person's email
            relationship_type: Type of relationship
        """
        with self.get_session() as session:
            session.run("""
                MATCH (a:ActionItem {id: $action_id})
                MERGE (p:Person {email: $person_email})
                MERGE (a)-[r:RELATIONSHIP {type: $relationship_type}]->(p)
            """, {
                "action_id": action_id,
                "person_email": person_email,
                "relationship_type": relationship_type
            })
    
    def link_action_to_project(self, action_id: str, project_name: str) -> None:
        """
        Link an action item to a project.
        
        Args:
            action_id: The action item ID
            project_name: The project name
        """
        with self.get_session() as session:
            session.run("""
                MATCH (a:ActionItem {id: $action_id})
                MERGE (p:Project {name: $project_name})
                MERGE (a)-[:BELONGS_TO]->(p)
            """, {
                "action_id": action_id,
                "project_name": project_name
            })
    
    def get_action_items_by_status(self, status: str) -> List[Dict[str, Any]]:
        """
        Get all action items with a specific status.
        
        Args:
            status: The status to filter by
            
        Returns:
            List of action items
        """
        with self.get_session() as session:
            result = session.run("""
                MATCH (a:ActionItem {status: $status})
                RETURN a
                ORDER BY a.priority, a.created_at
            """, {"status": status})
            
            return [record["a"] for record in result]