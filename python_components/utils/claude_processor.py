"""
Claude API integration for ICAP.
"""
import os
import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import anthropic
from dateutil import parser as date_parser

logger = logging.getLogger("icap.claude")

class ClaudeProcessor:
    """Processor for Claude API integration."""
    
    def __init__(self, model: str = None):
        """
        Initialize the Claude API client.
        
        Args:
            model: Optional model name to override the default
        """
        self.api_key = os.getenv("CLAUDE_API_KEY")
        if not self.api_key:
            raise ValueError("CLAUDE_API_KEY environment variable not set")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = model or "claude-3-sonnet-20240229"  # Can be configured based on needs
        logger.info(f"Claude API client initialized with model: {self.model}")
        
        # Constants for processing
        self.priority_mapping = {
            "urgent": "high",
            "important": "high",
            "critical": "high",
            "asap": "high",
            "high": "high",
            "medium": "medium",
            "normal": "medium", 
            "low": "low",
            "whenever": "low"
        }
    
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
        
        # Build context-specific system prompt
        system_prompt = self._build_system_prompt(content_type)
        
        # Build user prompt with context-specific instructions
        user_prompt = self._build_user_prompt(content, content_type)
        
        try:
            # Call Claude API with appropriate settings
            response = self.client.messages.create(
                model=self.model,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.0,  # Use exact 0 temperature for deterministic results
                max_tokens=4000
            )
            
            # Extract text content from response
            response_text = response.content[0].text
            
            # Parse the JSON from the response
            action_items = self._parse_claude_response(response_text)
            
            # Post-process extracted items
            processed_items = self._post_process_items(action_items, content_type)
            
            logger.info(f"Successfully extracted {len(processed_items)} action items")
            return processed_items
            
        except anthropic.APIError as e:
            logger.error(f"Claude API error: {str(e)}")
            return []
        except anthropic.APIConnectionError as e:
            logger.error(f"Claude API connection error: {str(e)}")
            return []
        except anthropic.RateLimitError as e:
            logger.error(f"Claude API rate limit exceeded: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Failed to extract action items: {str(e)}")
            return []
    
    def _build_system_prompt(self, content_type: str) -> str:
        """
        Build system prompt for Claude based on content type.
        
        Args:
            content_type: Type of content ('email' or 'slack')
            
        Returns:
            System prompt string
        """
        base_prompt = """
        You are an AI assistant specialized in extracting action items from professional communications.
        Your task is to identify tasks, requests, commitments, and assignments in the provided content.
        
        For each action item you identify, extract the following information:
        1. The complete description of what needs to be done (content)
        2. The person assigned to complete the task (assignee) - extract names or email addresses
        3. Any mentioned deadlines or due dates - standardize to YYYY-MM-DD format when possible
        4. The priority level (high/medium/low) based on urgency words and context
        5. The project or context the action relates to (if mentioned)
        
        Format your response as a valid JSON array of action items, with each item as an object with these fields:
        - content: (string) The full action item text
        - assignee: (string or null) Person assigned to the task (name or email)
        - due_date: (string or null) Any deadline in YYYY-MM-DD format
        - priority: (string) "high", "medium", or "low"
        - project: (string or null) Related project or context
        
        Only include definite action items - tasks that someone is expected to complete.
        Focus on extracting accurate information. If a field is not mentioned, use null.
        When extracting due dates, interpret relative dates (like "next Tuesday") based on the current date.
        """
        
        if content_type == "email":
            # Add email-specific instructions
            base_prompt += """
            For emails, pay special attention to:
            - Action items mentioned in the email body
            - Requests phrased as questions
            - Lists of tasks (numbered or bulleted)
            - Items with explicit deadlines
            - Clear assignments ("John, please handle this...")
            
            Be aware that email signatures, auto-generated content, or forwarded messages 
            may contain text that looks like action items but are not.
            """
        elif content_type == "slack":
            # Add Slack-specific instructions
            base_prompt += """
            For Slack messages, pay special attention to:
            - Direct requests to specific users (especially @mentions)
            - Action items often use more casual language
            - Items may reference previous messages in the channel
            - Messages may include emoji that indicate priority or context
            - Brief messages that imply action without explicit assignments
            
            Remember that Slack communications tend to be more brief and informal than emails.
            """
        
        return base_prompt
    
    def _build_user_prompt(self, content: str, content_type: str) -> str:
        """
        Build user prompt for Claude with content and instructions.
        
        Args:
            content: The message content
            content_type: Type of content
            
        Returns:
            Formatted user prompt
        """
        today = datetime.now().strftime("%Y-%m-%d")
        
        user_prompt = f"""
        Today's date: {today}
        Content type: {content_type}
        
        Content to analyze:
        {content}
        
        Extract all action items from this content. Return your response as a valid JSON array.
        If no action items are found, return an empty array [].
        Only include actual action items that someone is expected to complete - don't include observations, statements, or FYIs.
        """
        
        return user_prompt
    
    def _parse_claude_response(self, response_text: str) -> List[Dict[str, Any]]:
        """
        Parse the text response from Claude to extract the JSON array.
        
        Args:
            response_text: Claude's text response
            
        Returns:
            List of action item dictionaries
        """
        # Try to find JSON content in the response using regex
        json_match = re.search(r'\[\s*{.*}\s*\]', response_text, re.DOTALL)
        
        if json_match:
            try:
                # Parse the matched JSON content
                json_text = json_match.group(0)
                action_items = json.loads(json_text)
                
                if isinstance(action_items, list):
                    return action_items
                else:
                    logger.warning(f"Expected JSON array, got: {type(action_items)}")
                    return []
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from Claude response: {str(e)}")
        else:
            try:
                # Try to parse the entire response as JSON (sometimes Claude returns clean JSON)
                action_items = json.loads(response_text.strip())
                
                if isinstance(action_items, list):
                    return action_items
                else:
                    logger.warning(f"Expected JSON array, got: {type(action_items)}")
                    return []
            except json.JSONDecodeError:
                logger.error("Could not extract JSON array from Claude response")
        
        # Fallback - search for anything that looks like JSON items
        try:
            # Try one more approach - find all {...} patterns and build a list
            item_pattern = re.compile(r'{(?:[^{}]|(?R))*}', re.DOTALL)
            items = re.findall(item_pattern, response_text)
            
            if items:
                action_items = []
                for item_text in items:
                    try:
                        item = json.loads(item_text)
                        action_items.append(item)
                    except:
                        pass
                        
                if action_items:
                    return action_items
        except:
            pass
            
        # If all parsing approaches fail, return empty list
        return []
    
    def _post_process_items(self, items: List[Dict[str, Any]], content_type: str) -> List[Dict[str, Any]]:
        """
        Post-process extracted action items to normalize and enhance data.
        
        Args:
            items: List of raw action items from Claude
            content_type: Type of content for context-specific processing
            
        Returns:
            List of processed action items
        """
        processed_items = []
        
        for item in items:
            # Skip invalid items
            if not item or not isinstance(item, dict) or "content" not in item:
                continue
                
            # Create a new item with guaranteed fields
            processed_item = {
                "content": item.get("content", "").strip(),
                "assignee": item.get("assignee"),
                "due_date": None,
                "priority": "medium",  # Default priority
                "project": item.get("project")
            }
            
            # Skip items with empty content
            if not processed_item["content"]:
                continue
            
            # Normalize assignee field
            if processed_item["assignee"]:
                processed_item["assignee"] = processed_item["assignee"].strip()
                # Remove @ symbol from Slack mentions
                if content_type == "slack" and processed_item["assignee"].startswith("@"):
                    processed_item["assignee"] = processed_item["assignee"][1:]
            
            # Process and normalize due date
            processed_item["due_date"] = self._normalize_date(item.get("due_date"))
            
            # Normalize priority
            processed_item["priority"] = self._normalize_priority(item.get("priority", "medium"))
            
            # Normalize project name
            if processed_item["project"]:
                processed_item["project"] = processed_item["project"].strip()
            
            processed_items.append(processed_item)
        
        return processed_items
    
    def _normalize_date(self, date_str: Optional[str]) -> Optional[str]:
        """
        Normalize date string to YYYY-MM-DD format.
        
        Args:
            date_str: Date string to normalize
            
        Returns:
            Normalized date string or None
        """
        if not date_str or date_str.lower() in ("none", "null", ""):
            return None
            
        try:
            parsed_date = date_parser.parse(date_str)
            return parsed_date.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            logger.warning(f"Could not parse date: {date_str}")
            return date_str
    
    def _normalize_priority(self, priority_str: Optional[str]) -> str:
        """
        Normalize priority string to high/medium/low.
        
        Args:
            priority_str: Priority string to normalize
            
        Returns:
            Normalized priority string
        """
        if not priority_str:
            return "medium"
            
        priority_lower = priority_str.lower().strip()
        
        # Check for priority keywords
        for key, value in self.priority_mapping.items():
            if key in priority_lower:
                return value
        
        # Default mappings for common values
        if priority_lower in ("h", "high", "important", "urgent"):
            return "high"
        elif priority_lower in ("m", "med", "medium", "normal"):
            return "medium"
        elif priority_lower in ("l", "low"):
            return "low"
        
        # Default to medium for unknown values
        return "medium"
    
    def analyze_action_item_context(self, action_item: Dict[str, Any], source_content: str) -> Dict[str, Any]:
        """
        Analyze an action item in context to enhance with additional information.
        
        Args:
            action_item: The action item to analyze
            source_content: Original source content
            
        Returns:
            Enhanced action item with additional context
        """
        logger.info(f"Analyzing context for action item: {action_item.get('content', '')[:50]}...")
        
        system_prompt = """
        You are an AI assistant that analyzes action items in context.
        Your task is to enhance understanding of an action item by analyzing its broader context.
        
        Analyze the action item in the context of the full content to determine:
        1. The likely urgency or importance based on language and context
        2. Any implied deadlines that weren't explicitly stated
        3. Any implied assignees that weren't explicitly mentioned
        4. Related projects or organizational contexts
        
        Provide this analysis as a JSON object with these fields:
        - enhanced_priority: (string) "high", "medium", or "low" based on context
        - implied_deadline: (string or null) Any implied timeframe in YYYY-MM-DD format
        - implied_assignee: (string or null) Any implied person responsible
        - related_projects: (array of strings) Any related projects or contexts
        - key_dependencies: (array of strings) Any dependencies or prerequisites
        """
        
        user_prompt = f"""
        Original content:
        {source_content}
        
        Action item to analyze:
        {action_item.get('content', '')}
        
        Current metadata:
        - Assignee: {action_item.get('assignee', 'None')}
        - Due date: {action_item.get('due_date', 'None')} 
        - Priority: {action_item.get('priority', 'medium')}
        - Project: {action_item.get('project', 'None')}
        
        Analyze this action item in context and provide enhanced understanding.
        Return your analysis as a JSON object.
        """
        
        try:
            response = self.client.messages.create(
                model=self.model,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.1,
                max_tokens=2000
            )
            
            response_text = response.content[0].text
            
            # Parse JSON from response
            try:
                json_match = re.search(r'{.*}', response_text, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group(0))
                    
                    # Update action item with additional context
                    enhanced_item = action_item.copy()
                    
                    # Only override priority if the current one is medium
                    if enhanced_item.get('priority') == 'medium' and 'enhanced_priority' in analysis:
                        enhanced_item['priority'] = self._normalize_priority(analysis['enhanced_priority'])
                    
                    # Only add implied deadline if no explicit one exists
                    if not enhanced_item.get('due_date') and analysis.get('implied_deadline'):
                        enhanced_item['due_date'] = self._normalize_date(analysis['implied_deadline'])
                    
                    # Only add implied assignee if no explicit one exists
                    if not enhanced_item.get('assignee') and analysis.get('implied_assignee'):
                        enhanced_item['assignee'] = analysis['implied_assignee']
                    
                    # Add related projects if not already set
                    if not enhanced_item.get('project') and analysis.get('related_projects'):
                        if isinstance(analysis['related_projects'], list) and analysis['related_projects']:
                            enhanced_item['project'] = analysis['related_projects'][0]
                    
                    # Add any new fields from the analysis
                    if 'key_dependencies' in analysis:
                        enhanced_item['dependencies'] = analysis['key_dependencies']
                    
                    return enhanced_item
            except json.JSONDecodeError:
                logger.warning("Could not parse context analysis response as JSON")
            
            # Return original item if parsing fails
            return action_item
            
        except Exception as e:
            logger.error(f"Error analyzing action item context: {str(e)}")
            return action_item