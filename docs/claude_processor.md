# ICAP Claude AI Processor

This document describes the design and implementation of the Claude AI processor component for ICAP.

## Overview

The Claude AI processor is a core component that uses Anthropic's Claude API to extract action items, tasks, and commitments from various communication sources. It employs specialized prompt engineering, context-awareness, and post-processing to achieve high accuracy.

## Key Features

### 1. Context-Aware Prompting

The processor uses different system prompts based on the content type (email or Slack) to optimize extraction results:

- **Email-specific instructions**: Focuses on formal language, lists, explicit deadlines, and clear assignments
- **Slack-specific instructions**: Attends to informal language, @mentions, emojis, and brief conversational requests

### 2. Two-Stage Processing

The system employs a two-stage approach for maximum accuracy:

1. **Initial Extraction**: First pass to identify all potential action items, deadlines, and assignments
2. **Deep Context Analysis**: Second pass on selected items to enhance understanding of priorities, relationships, and implicit information

### 3. Robust JSON Parsing

Multiple parsing strategies ensure reliable extraction from Claude's natural language responses:

- Regex-based JSON extraction
- Full-response JSON parsing
- Partial object extraction and assembly
- Special handling for malformed responses

### 4. Data Normalization

- **Date standardization**: Converts relative and various date formats to YYYY-MM-DD
- **Priority normalization**: Maps urgency language to high/medium/low priorities
- **Person identification**: Handles different formats for person references

### 5. Enhanced Analysis

- **Dependency detection**: Identifies prerequisites and related tasks
- **Project inference**: Determines project context from content
- **Priority estimation**: Gauges importance from urgency words and context

## Component Architecture

```
ClaudeProcessor
│
├── extract_action_items(content, content_type)
│   ├── _build_system_prompt(content_type)
│   ├── _build_user_prompt(content, content_type)
│   ├── _parse_claude_response(response_text)
│   └── _post_process_items(items, content_type)
│       ├── _normalize_date(date_str)
│       └── _normalize_priority(priority_str)
│
└── analyze_action_item_context(action_item, source_content)
```

## Implementation Details

### System Prompt Design

The system prompts balance several key considerations:

1. **Task clarity**: Clear instructions on what constitutes an action item
2. **Field specification**: Explicit definitions of each field to extract
3. **Context awareness**: Tailored guidance for different communication formats
4. **Format requirements**: Specific output structure requirements for reliable parsing

Example email-specific prompt enhancement:
```
For emails, pay special attention to:
- Action items mentioned in the email body
- Requests phrased as questions
- Lists of tasks (numbered or bulleted)
- Items with explicit deadlines
- Clear assignments ("John, please handle this...")
```

### JSON Parsing Strategy

The processor implements a multi-layer fallback strategy for parsing:

1. Try to extract JSON array using regex pattern `\[\s*{.*}\s*\]`
2. If failed, try to parse the entire response as JSON
3. If both fail, scan for individual JSON objects and assemble them
4. For each item, validate required fields and structure

### Context Analysis Prompting

For the second-stage analysis, the system prompt focuses on:

1. Implied urgency or importance not explicitly stated
2. Deadlines that may be implied rather than explicit
3. Likely assignees based on context
4. Project relationships inferred from content
5. Dependencies between action items

## Usage Example

```python
from python_components.utils.claude_processor import ClaudeProcessor

# Initialize the processor
processor = ClaudeProcessor()

# Extract action items from an email
email_content = "Subject: Project Update\n\nHi Team,\nPlease review the draft by Friday.\nJohn, can you update the timeline?\nThanks,\nSarah"
action_items = processor.extract_action_items(email_content, 'email')

# Perform deep analysis on specific items if needed
enhanced_item = processor.analyze_action_item_context(action_items[0], email_content)
```

## Performance Considerations

- **API Throttling**: Implements request throttling to respect API rate limits
- **Caching**: Considers caching common responses for performance
- **Error Handling**: Specific exception types for different API issues
- **Token Optimization**: Careful prompt design to minimize token usage

## Future Improvements

1. **Learning from feedback**: Mechanism to improve extraction based on user corrections
2. **Custom training**: Fine-tuning for organization-specific communication styles
3. **Multi-language support**: Extending to languages beyond English
4. **Enhanced contextual understanding**: Maintaining conversation history for better context
5. **Response streaming**: Using Claude's streaming capabilities for faster initial results

## Integration Points

The Claude processor integrates with:
- **Action Item Processor**: For the main processing pipeline
- **Secret Manager**: For secure API key handling
- **Logging System**: For detailed operation tracking
- **Neo4j Database**: For storing structured extraction results