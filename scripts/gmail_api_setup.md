# Gmail API Setup Guide for ICAP

This guide will walk you through the process of setting up Gmail API access for the ICAP system.

## 1. Create a Google Cloud Project (Skip if using existing project)

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Create Project"
3. Enter a project name (e.g., "ICAP Email Processor")
4. Click "Create"

## 2. Enable the Gmail API

1. In the Google Cloud Console, select your project
2. Go to the [API Library](https://console.cloud.google.com/apis/library)
3. Search for "Gmail API"
4. Click on "Gmail API"
5. Click "Enable"

## 3. Configure OAuth Consent Screen

1. Go to the [OAuth Consent Screen](https://console.cloud.google.com/apis/credentials/consent)
2. Select "External" (or "Internal" if you're using Google Workspace)
3. Click "Create"
4. Enter the required information:
   - App name: "ICAP Email Processor"
   - User support email: [Your email]
   - Developer contact information: [Your email]
5. Click "Save and Continue"
6. On the "Scopes" page, click "Add or Remove Scopes"
7. Add the following scopes:
   - `https://www.googleapis.com/auth/gmail.readonly` (Allows reading Gmail messages)
   - `https://www.googleapis.com/auth/gmail.send` (Allows sending emails)
8. Click "Save and Continue"
9. On the "Test Users" page, click "Add Users"
10. Add your email address
11. Click "Save and Continue"
12. Review the summary and click "Back to Dashboard"

## 4. Create OAuth Client ID

1. Go to the [Credentials](https://console.cloud.google.com/apis/credentials) page
2. Click "Create Credentials" and select "OAuth client ID"
3. For Application type, select "Web application"
4. Enter a name (e.g., "ICAP Gmail Client")
5. Under "Authorized redirect URIs", add:
   - `https://developers.google.com/oauthplayground`
6. Click "Create"
7. Note down the "Client ID" and "Client Secret" that are displayed

## 5. Get a Refresh Token

1. Go to the [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)
2. Click the gear icon in the top-right corner
3. Check "Use your own OAuth credentials"
4. Enter your Client ID and Client Secret from the previous step
5. Click "Close"
6. In the left panel, scroll down to "Gmail API v1"
7. Select the following scopes:
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.send`
8. Click "Authorize APIs"
9. Sign in with your Google Account and grant permissions
10. On the next screen, click "Exchange authorization code for tokens"
11. Note down the "Refresh token" from the response

## 6. Store the Credentials in Google Secret Manager

Use the `manage_secrets.py` script to store your Gmail API credentials:

```bash
python3 scripts/manage_secrets.py --setup
```

When prompted, enter:
- Gmail OAuth Client ID
- Gmail OAuth Client Secret
- Gmail OAuth Refresh Token
- Notification recipient email (the email that will receive summaries)

## 7. Test the Connection

To verify that the app can access Gmail, you can run a simple test using the API:

```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Create credentials using your tokens
credentials = Credentials(
    None,  # No access token needed initially since we're using the refresh token
    refresh_token='YOUR_REFRESH_TOKEN',
    token_uri='https://oauth2.googleapis.com/token',
    client_id='YOUR_CLIENT_ID',
    client_secret='YOUR_CLIENT_SECRET'
)

# Build the Gmail service
service = build('gmail', 'v1', credentials=credentials)

# Call the Gmail API to get labels
results = service.users().labels().list(userId='me').execute()
labels = results.get('labels', [])

# Print the labels
for label in labels:
    print(label['name'])
```

Replace `YOUR_REFRESH_TOKEN`, `YOUR_CLIENT_ID`, and `YOUR_CLIENT_SECRET` with your actual values.

## Next Steps

After completing this setup:

1. The Gmail API credentials are now stored in Google Secret Manager
2. The Cloud Functions can use these credentials to access Gmail
3. The system can retrieve emails and send summary notifications

You can now proceed with completing the ICAP setup.