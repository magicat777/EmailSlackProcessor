"""
Neo4j database manager for ICAP.
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional, Union
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
        # Handle special properties that need serialization
        params = dict(action_item)  # Make a copy
        
        # Convert any list/dict properties to JSON strings
        for key, value in params.items():
            if isinstance(value, (list, dict)):
                params[key] = json.dumps(value)
        
        # Build dynamic query to handle variable properties
        query_parts = [
            "CREATE (a:ActionItem {",
            ", ".join([f"{key}: ${key}" for key in params.keys()]),
            "})",
            "RETURN a.id as id"
        ]
        query = "\n".join(query_parts)
        
        with self.get_session() as session:
            result = session.run(query, params)
            record = result.single()
            return record["id"]
    
    def link_action_to_person(self, action_id: str, person_identifier: str, 
                             relationship_type: str = "ASSIGNED_TO") -> None:
        """
        Link an action item to a person.
        
        Args:
            action_id: The action item ID
            person_identifier: The person's email or name
            relationship_type: Type of relationship
        """
        # Determine if identifier is email or name
        is_email = '@' in person_identifier and '.' in person_identifier
        person_property = "email" if is_email else "name"
        
        with self.get_session() as session:
            session.run(f"""
                MATCH (a:ActionItem {{id: $action_id}})
                MERGE (p:Person {{{person_property}: $person_identifier}})
                MERGE (a)-[r:{relationship_type}]->(p)
            """, {
                "action_id": action_id,
                "person_identifier": person_identifier
            })
            
            logger.debug(f"Linked action {action_id} to person {person_identifier} with relationship {relationship_type}")
    
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
            
            logger.debug(f"Linked action {action_id} to project {project_name}")
    
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
            
            action_items = []
            for record in result:
                item = dict(record["a"])
                
                # Deserialize any JSON strings back to Python objects
                for key, value in item.items():
                    if isinstance(value, str) and (value.startswith('[') or value.startswith('{')):
                        try:
                            item[key] = json.loads(value)
                        except json.JSONDecodeError:
                            pass  # Keep as string if it's not valid JSON
                
                action_items.append(item)
                
            return action_items
    
    def get_projects_for_action_item(self, action_id: str) -> List[str]:
        """
        Get all projects related to an action item.
        
        Args:
            action_id: The action item ID
            
        Returns:
            List of project names
        """
        with self.get_session() as session:
            result = session.run("""
                MATCH (a:ActionItem {id: $action_id})-[:BELONGS_TO]->(p:Project)
                RETURN p.name as name
            """, {"action_id": action_id})
            
            return [record["name"] for record in result]
    
    def get_people_for_action_item(self, action_id: str, relationship_type: Optional[str] = None) -> List[str]:
        """
        Get all people related to an action item.
        
        Args:
            action_id: The action item ID
            relationship_type: Type of relationship to filter by (optional)
            
        Returns:
            List of person identifiers (email preferred, name as fallback)
        """
        query = """
            MATCH (a:ActionItem {id: $action_id})
        """
        
        if relationship_type:
            query += f"-[:{relationship_type}]->"
        else:
            query += "-[]->"
            
        query += """(p:Person)
            RETURN p.email as email, p.name as name
        """
        
        with self.get_session() as session:
            result = session.run(query, {"action_id": action_id})
            
            people = []
            for record in result:
                # Prefer email if available, otherwise use name
                identifier = record["email"] if record["email"] else record["name"]
                if identifier:
                    people.append(identifier)
            
            return people
    
    def update_action_item_status(self, action_id: str, new_status: str) -> bool:
        """
        Update the status of an action item.
        
        Args:
            action_id: The action item ID
            new_status: New status value
            
        Returns:
            True if the update was successful, False otherwise
        """
        with self.get_session() as session:
            result = session.run("""
                MATCH (a:ActionItem {id: $action_id})
                SET a.status = $new_status
                RETURN count(a) as updated
            """, {
                "action_id": action_id,
                "new_status": new_status
            })
            
            record = result.single()
            success = record and record["updated"] > 0
            
            if success:
                logger.info(f"Updated action item {action_id} status to {new_status}")
            else:
                logger.warning(f"Failed to update action item {action_id} status to {new_status}")
                
            return success
            
    def get_action_items_by_criteria(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get action items matching specific criteria.
        
        Args:
            criteria: Dictionary with filtering criteria
                - status: Status to filter by
                - priority: Priority to filter by
                - due_date: Due date to filter by
                - project: Project name to filter by
                - assignee: Assignee to filter by
                
        Returns:
            List of action items matching the criteria
        """
        # Build query based on provided criteria
        base_query = "MATCH (a:ActionItem)"
        where_clauses = []
        params = {}
        
        # Handle basic properties in criteria
        basic_fields = ["status", "priority", "due_date", "source"]
        for field in basic_fields:
            if field in criteria:
                where_clauses.append(f"a.{field} = ${field}")
                params[field] = criteria[field]
        
        # Handle project filter
        if "project" in criteria:
            base_query += " MATCH (a)-[:BELONGS_TO]->(p:Project)"
            where_clauses.append("p.name = $project")
            params["project"] = criteria["project"]
        
        # Handle assignee filter
        if "assignee" in criteria:
            base_query += " MATCH (a)-[:ASSIGNED_TO]->(person:Person)"
            
            # Check if assignee is email or name
            if '@' in criteria["assignee"] and '.' in criteria["assignee"]:
                where_clauses.append("person.email = $assignee")
            else:
                where_clauses.append("person.name = $assignee")
                
            params["assignee"] = criteria["assignee"]
        
        # Add WHERE clause if needed
        if where_clauses:
            base_query += f" WHERE {' AND '.join(where_clauses)}"
        
        # Complete query
        query = f"{base_query} RETURN a ORDER BY a.priority, a.due_date, a.created_at"
        
        # Execute query
        with self.get_session() as session:
            result = session.run(query, params)
            
            action_items = []
            for record in result:
                item = dict(record["a"])
                
                # Deserialize any JSON strings
                for key, value in item.items():
                    if isinstance(value, str) and (value.startswith('[') or value.startswith('{')):
                        try:
                            item[key] = json.loads(value)
                        except json.JSONDecodeError:
                            pass
                
                action_items.append(item)
                
            return action_items