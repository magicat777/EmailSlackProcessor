# Intelligent Communication Action Processor (ICAP)

## Overview
ICAP is designed to automate the extraction and organization of action items from email and Slack communications. This hybrid cloud/local solution leverages advanced AI to identify tasks directed at the user, classify their priority, and generate organized summaries to improve productivity and ensure critical tasks aren't overlooked.

## Architecture
The system uses a hybrid architecture:
- **Google Cloud Functions**: For secure access to email and Slack data
- **Local Docker containers**: For processing and database storage
- **Neo4j database**: For storing action items and their relationships
- **Claude API**: For intelligent content analysis

## Key Components
- **Email Retriever**: Google Cloud Function to securely access email data
- **Slack Retriever**: Google Cloud Function to access Slack messages
- **Processing Engine**: Local Docker container for content analysis
- **Neo4j Database**: Graph database for action item storage
- **Notification Sender**: Sends daily summaries via email

## Setup Guide

### Prerequisites
- Windows 11 with WSL2 enabled
- Ubuntu 24.04 or later in WSL2
- Docker Desktop for Windows with WSL2 integration
- Google Cloud SDK installed and configured
- Git
- Python 3.10+
- Node.js 16+

### Initial Setup
1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/EmailSlackProcessor.git
   cd EmailSlackProcessor
   ```

2. Start the Neo4j database:
   ```bash
   docker-compose up -d neo4j
   ```

3. Configure API access:
   - Follow the instructions in `scripts/outlook_api_setup.md` to set up Microsoft Graph API access for Outlook
   - Follow the instructions in `scripts/slack_app_setup.md` to create a Slack app

4. Set up secrets in Google Secret Manager:
   ```bash
   python3 scripts/manage_secrets.py --setup
   ```

5. Build the processing container:
   ```bash
   docker-compose build processing
   ```

6. Deploy the Cloud Functions:
   ```bash
   # Instructions for deploying Cloud Functions will be provided
   ```

### Running the System
Once everything is set up, you can start the system:

```bash
docker-compose up -d
```

Access the Neo4j browser at http://localhost:7474 to view and query the database.

## Development
- Python code follows PEP 8 guidelines
- Use type hints for all functions
- Run tests with `pytest`
- Check code style with `flake8 python_components/`
- Check types with `mypy python_components/`

## Project Structure
```
EmailSlackProcessor/
├── .github/workflows/     # CI/CD pipeline configuration
├── cloud-functions/       # Google Cloud Functions
│   ├── email-retriever/   # Email retrieval function
│   ├── slack-retriever/   # Slack message retrieval function
│   └── notification-sender/ # Summary email sender
├── docker/                # Docker configuration
│   ├── neo4j/             # Neo4j database configuration
│   └── processing/        # Processing engine
├── python_components/     # Python processing components
│   ├── processors/        # Action item processors
│   ├── utils/             # Utility modules
│   └── tests/             # Test cases
└── scripts/               # Setup and utility scripts
```

## Usage
The system performs the following operations:

1. Periodically retrieves new emails and Slack messages
2. Processes content to extract action items
3. Stores action items in the Neo4j database with relationships
4. Generates and sends daily summary emails organized by project

## Contributing
[Contribution guidelines will be added]

## License
[License information]