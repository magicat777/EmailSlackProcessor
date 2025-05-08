"""
Action item processor for ICAP.
"""
import os
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from python_components.utils.neo4j_manager import Neo4jManager
from python_components.utils.claude_processor import ClaudeProcessor

logger = logging.getLogger("icap.processor")

class ActionItemProcessor:
    """Processor for action items from various sources."""
    
    def __init__(self):
        """Initialize the processor with required components."""
        self.neo4j = Neo4jManager()
        self.claude = ClaudeProcessor()
        logger.info("Action item processor initialized")
    
    def process_email(self, email_data: Dict[str, Any]) -> List[str]:
        """
        Process email data to extract and store action items.
        
        Args:
            email_data: Dictionary containing email data
                - id: Email ID
                - subject: Email subject
                - from: Sender
                - body: Email body text
                - date: Email date
                
        Returns:
            List of action item IDs that were created
        """
        logger.info(f"Processing email: {email_data.get('subject', 'No Subject')}")
        
        # Combine subject and body for analysis
        content = f"Subject: {email_data.get('subject', 'No Subject')}\n\n{email_data.get('body', '')}"
        
        # Extract action items using Claude
        action_items = self.claude.extract_action_items(content, 'email')
        
        # Store action items in Neo4j
        action_item_ids = []
        for item in action_items:
            # Generate unique ID
            item_id = str(uuid.uuid4())
            
            # Create action item in Neo4j
            neo4j_item = {
                "id": item_id,
                "content": item.get("content", ""),
                "source": "email",
                "source_id": email_data.get("id", ""),
                "created_at": datetime.now().isoformat(),
                "due_date": item.get("due_date"),
                "priority": item.get("priority", "medium"),
                "status": "pending"
            }
            
            self.neo4j.create_action_item(neo4j_item)
            action_item_ids.append(item_id)
            
            # Link to people
            if "assignee" in item and item["assignee"]:
                self.neo4j.link_action_to_person(item_id, item["assignee"], "ASSIGNED_TO")
            
            # Link to projects
            if "project" in item and item["project"]:
                self.neo4j.link_action_to_project(item_id, item["project"])
        
        logger.info(f"Processed {len(action_item_ids)} action items from email")
        return action_item_ids
    
    def process_slack_message(self, message_data: Dict[str, Any]) -> List[str]:
        """
        Process Slack message data to extract and store action items.
        
        Args:
            message_data: Dictionary containing Slack message data
                - id: Message ID
                - text: Message text
                - user: User who sent the message
                - channelId: Channel ID
                - timestamp: Message timestamp
                
        Returns:
            List of action item IDs that were created
        """
        logger.info(f"Processing Slack message from channel: {message_data.get('channelId', 'Unknown')}")
        
        # Extract action items using Claude
        action_items = self.claude.extract_action_items(message_data.get("text", ""), 'slack')
        
        # Store action items in Neo4j
        action_item_ids = []
        for item in action_items:
            # Generate unique ID
            item_id = str(uuid.uuid4())
            
            # Create action item in Neo4j
            neo4j_item = {
                "id": item_id,
                "content": item.get("content", ""),
                "source": "slack",
                "source_id": message_data.get("id", ""),
                "created_at": datetime.now().isoformat(),
                "due_date": item.get("due_date"),
                "priority": item.get("priority", "medium"),
                "status": "pending"
            }
            
            self.neo4j.create_action_item(neo4j_item)
            action_item_ids.append(item_id)
            
            # Link to people
            if "assignee" in item and item["assignee"]:
                self.neo4j.link_action_to_person(item_id, item["assignee"], "ASSIGNED_TO")
            
            # Link to projects
            if "project" in item and item["project"]:
                self.neo4j.link_action_to_project(item_id, item["project"])
        
        logger.info(f"Processed {len(action_item_ids)} action items from Slack message")
        return action_item_ids
    
    def generate_daily_summary(self) -> Dict[str, Any]:
        """
        Generate a daily summary of action items.
        
        Returns:
            Dictionary containing summary information and action items
        """
        logger.info("Generating daily summary")
        
        # Get pending action items
        pending_items = self.neo4j.get_action_items_by_status("pending")
        
        # Transform Neo4j objects to summary format
        summary_items = []
        for item in pending_items:
            summary_items.append({
                "id": item["id"],
                "content": item["content"],
                "priority": item["priority"],
                "due_date": item["due_date"],
                "source": item["source"],
                "created_at": item["created_at"],
                # Note: We would need additional queries to get related projects and people
                "project": "Unknown",  # Placeholder - would be replaced with actual project
                "assignee": "Unknown"  # Placeholder - would be replaced with actual assignee
            })
        
        summary = {
            "date": datetime.now().isoformat(),
            "total_items": len(summary_items),
            "action_items": summary_items
        }
        
        logger.info(f"Generated summary with {len(summary_items)} action items")
        return summary