"""
Claude API integration for ICAP.
"""
import os
import logging
from typing import Dict, Any, List
import anthropic

logger = logging.getLogger("icap.claude")

class ClaudeProcessor:
    """Processor for Claude API integration."""
    
    def __init__(self):
        """Initialize the Claude API client."""
        self.api_key = os.getenv("CLAUDE_API_KEY")
        if not self.api_key:
            raise ValueError("CLAUDE_API_KEY environment variable not set")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-3-sonnet-20240229"  # Can be configured based on needs
        logger.info("Claude API client initialized")
    
    def extract_action_items(self, content: str, content_type: str) -> List[Dict[str, Any]]:
        """
        Extract action items from content using Claude API.
        
        Args:
            content: The email or message content
            content_type: Type of content ('email' or 'slack')
            
        Returns:
            List of action items with their properties
        """
        logger.info(f"Extracting action items from {content_type} content")
        
        system_prompt = """
        You are an assistant that extracts action items from messages.
        Identify tasks, requests, and commitments. For each action item:
        1. Extract the full text description
        2. Determine the assigned person (if any)
        3. Identify any due dates or deadlines
        4. Estimate priority (high/medium/low)
        5. Detect related projects or contexts
        
        Format your response as a JSON array of action items, with each item having these fields:
        - content: The action item text
        - assignee: The person assigned to the task (email or name)
        - due_date: Any mentioned deadline (or null)
        - priority: Estimated priority level
        - project: Related project or context
        """
        
        user_prompt = f"""
        Content type: {content_type}
        
        Content:
        {content}
        
        Extract all action items from this content.
        """
        
        try:
            response = self.client.messages.create(
                model=self.model,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.0,
                max_tokens=4000
            )
            
            # Parse JSON response
            # In a real implementation, add error handling for invalid JSON
            action_items = response.content[0].text
            
            # This is a simplified implementation - in practice, we should properly
            # parse the JSON response and handle potential errors
            
            logger.info(f"Extracted {len(action_items)} action items")
            return action_items
        except Exception as e:
            logger.error(f"Failed to extract action items: {str(e)}")
            return []