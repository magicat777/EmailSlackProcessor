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
        content = f"Subject: {email_data.get('subject', 'No Subject')}\n\nFrom: {email_data.get('from', 'Unknown')}\n\n{email_data.get('body', '')}"
        
        # Extract action items using Claude
        action_items = self.claude.extract_action_items(content, 'email')
        
        if not action_items:
            logger.info("No action items found in email")
            return []
            
        # Add context for any items that could benefit from deeper analysis
        enhanced_items = []
        for item in action_items:
            # Only perform deeper analysis for items with missing fields
            if not item.get("assignee") or not item.get("due_date") or item.get("priority") == "medium":
                # Try to enhance with context analysis
                enhanced_item = self.claude.analyze_action_item_context(item, content)
                enhanced_items.append(enhanced_item)
            else:
                enhanced_items.append(item)
        
        # Store action items in Neo4j
        action_item_ids = []
        for item in enhanced_items:
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
                "status": "pending",
                "sender": email_data.get("from", ""),
                "subject": email_data.get("subject", "No Subject")
            }
            
            # Add any dependencies if they exist
            if "dependencies" in item:
                neo4j_item["dependencies"] = item.get("dependencies")
                
            self.neo4j.create_action_item(neo4j_item)
            action_item_ids.append(item_id)
            
            # Link to people
            if "assignee" in item and item["assignee"]:
                self.neo4j.link_action_to_person(item_id, item["assignee"], "ASSIGNED_TO")
                
            # Add sender as a person too and create SENT_BY relationship
            if email_data.get("from"):
                self.neo4j.link_action_to_person(item_id, email_data["from"], "SENT_BY")
            
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
        
        # Prepare message with context
        msg_text = message_data.get("text", "")
        sender_info = ""
        
        # Add sender information if available
        if message_data.get("user"):
            if isinstance(message_data["user"], dict):
                sender_info = f"From: {message_data['user'].get('name', 'Unknown')}"
                if message_data["user"].get("email"):
                    sender_info += f" ({message_data['user']['email']})"
            else:
                sender_info = f"From: {message_data['user']}"
                
        # Combine sender info and message
        content = f"{sender_info}\n\nChannel: {message_data.get('channelId', 'Unknown')}\n\n{msg_text}"
        
        # Extract action items using Claude
        action_items = self.claude.extract_action_items(content, 'slack')
        
        if not action_items:
            logger.info("No action items found in Slack message")
            return []
            
        # Add context for any items that could benefit from deeper analysis
        enhanced_items = []
        for item in action_items:
            # Only perform deeper analysis for items with missing fields
            if not item.get("assignee") or not item.get("due_date") or item.get("priority") == "medium":
                # Try to enhance with context analysis
                enhanced_item = self.claude.analyze_action_item_context(item, content)
                enhanced_items.append(enhanced_item)
            else:
                enhanced_items.append(item)
        
        # Store action items in Neo4j
        action_item_ids = []
        for item in enhanced_items:
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
                "status": "pending",
                "channel_id": message_data.get("channelId", ""),
                "timestamp": message_data.get("timestamp", "")
            }
            
            # Add any dependencies if they exist
            if "dependencies" in item:
                neo4j_item["dependencies"] = item.get("dependencies")
                
            self.neo4j.create_action_item(neo4j_item)
            action_item_ids.append(item_id)
            
            # Link to people
            if "assignee" in item and item["assignee"]:
                self.neo4j.link_action_to_person(item_id, item["assignee"], "ASSIGNED_TO")
            
            # Link message sender as person if available
            if isinstance(message_data.get("user"), dict) and message_data["user"].get("email"):
                self.neo4j.link_action_to_person(item_id, message_data["user"]["email"], "SENT_BY")
            elif isinstance(message_data.get("user"), dict) and message_data["user"].get("name"):
                self.neo4j.link_action_to_person(item_id, message_data["user"]["name"], "SENT_BY")
            elif message_data.get("user"):
                self.neo4j.link_action_to_person(item_id, str(message_data["user"]), "SENT_BY")
            
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
            # Get related projects for this item
            project = item.get("project")
            if not project:
                # Try to query Neo4j for linked projects
                try:
                    projects = self.neo4j.get_projects_for_action_item(item["id"])
                    if projects:
                        project = projects[0]  # Take first project if multiple
                except:
                    project = "Unknown"
            
            # Get assignee for this item
            assignee = item.get("assignee")
            if not assignee:
                # Try to query Neo4j for assigned people
                try:
                    people = self.neo4j.get_people_for_action_item(item["id"], "ASSIGNED_TO")
                    if people:
                        assignee = people[0]  # Take first person if multiple
                except:
                    assignee = "Unknown"
            
            # Create summary item
            summary_item = {
                "id": item["id"],
                "content": item["content"],
                "priority": item["priority"],
                "due_date": item["due_date"],
                "source": item["source"],
                "created_at": item["created_at"],
                "project": project,
                "assignee": assignee
            }
            
            # Add source-specific fields
            if item["source"] == "email":
                summary_item["subject"] = item.get("subject", "")
                summary_item["sender"] = item.get("sender", "")
            elif item["source"] == "slack":
                summary_item["channel_id"] = item.get("channel_id", "")
            
            # Add dependencies if available
            if "dependencies" in item:
                summary_item["dependencies"] = item["dependencies"]
                
            summary_items.append(summary_item)
        
        # Sort items by priority (high first) and then by due date
        def sort_key(item):
            priority_order = {"high": 0, "medium": 1, "low": 2}
            due_date = item.get("due_date") or "9999-12-31"  # Far future for items without due date
            return (priority_order.get(item.get("priority"), 3), due_date)
            
        sorted_items = sorted(summary_items, key=sort_key)
        
        # Group items by project
        items_by_project = {}
        for item in sorted_items:
            project = item.get("project") or "Unassigned"
            if project not in items_by_project:
                items_by_project[project] = []
            items_by_project[project].append(item)
        
        # Create summary with additional metadata
        today = datetime.now()
        date_str = today.strftime("%Y-%m-%d")
        
        summary = {
            "date": date_str,
            "total_items": len(summary_items),
            "projects": list(items_by_project.keys()),
            "items_by_project": items_by_project,
            "items_by_priority": {
                "high": [i for i in sorted_items if i.get("priority") == "high"],
                "medium": [i for i in sorted_items if i.get("priority") == "medium"],
                "low": [i for i in sorted_items if i.get("priority") == "low"]
            },
            "action_items": sorted_items
        }
        
        # Add due date categorization
        today_date = today.date()
        tomorrow = (today.date().replace(day=today.day + 1)).isoformat()
        this_week_end = (today.date().replace(day=today.day + (6 - today.weekday()))).isoformat()
        
        summary["items_by_due_date"] = {
            "overdue": [i for i in sorted_items if i.get("due_date") and i.get("due_date") < date_str],
            "today": [i for i in sorted_items if i.get("due_date") == date_str],
            "tomorrow": [i for i in sorted_items if i.get("due_date") == tomorrow],
            "this_week": [i for i in sorted_items if i.get("due_date") and date_str < i.get("due_date") <= this_week_end],
            "future": [i for i in sorted_items if i.get("due_date") and i.get("due_date") > this_week_end],
            "no_date": [i for i in sorted_items if not i.get("due_date")]
        }
        
        logger.info(f"Generated summary with {len(summary_items)} action items across {len(items_by_project)} projects")
        return summary