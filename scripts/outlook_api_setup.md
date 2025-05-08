# Microsoft Graph API Setup Guide for ICAP

This guide will walk you through the process of setting up Microsoft Graph API access for retrieving emails from Outlook/Exchange.

## 1. Register an Application in Azure Active Directory

1. Sign in to the [Azure Portal](https://portal.azure.com/) 
2. Navigate to **Azure Active Directory** > **App registrations**
3. Click **New registration**
4. Enter the following information:
   - **Name**: ICAP Email Processor
   - **Supported account types**: Choose the appropriate option for your organization
   - **Redirect URI**: Select "Web" and enter `https://login.microsoftonline.com/common/oauth2/nativeclient`
5. Click **Register**

## 2. Configure API Permissions

1. In your newly created app registration, select **API Permissions** from the left menu
2. Click **Add a permission**
3. Select **Microsoft Graph**
4. Choose **Delegated permissions**
5. Add the following permissions:
   - `Mail.Read` - Read user mail
   - `Mail.Send` - Send mail as user
   - `User.Read` - Sign in and read user profile
6. Click **Add permissions**
7. If you need admin consent for these permissions, click **Grant admin consent for [Your Organization]**

## 3. Create a Client Secret

1. In your app registration, select **Certificates & secrets** from the left menu
2. Under **Client secrets**, click **New client secret**
3. Enter a description (e.g., "ICAP Access") and select an expiration period
4. Click **Add**
5. **IMPORTANT**: Copy the generated **Value** immediately - you won't be able to see it again

## 4. Get Application Information

1. In your app registration, go to the **Overview** page
2. Note down the following information:
   - **Application (client) ID**
   - **Directory (tenant) ID**

## 5. Obtain Access and Refresh Tokens

### Option A: Using the MSAL Authentication Library (Recommended)

1. Create a simple Python script using the Microsoft Authentication Library (MSAL):

```python
import msal
import webbrowser
import json

# Application configuration
client_id = "YOUR_CLIENT_ID"  # Replace with your Application (client) ID
tenant_id = "YOUR_TENANT_ID"  # Replace with your Directory (tenant) ID
client_secret = "YOUR_CLIENT_SECRET"  # Replace with your Client Secret

# Authentication parameters
authority = f"https://login.microsoftonline.com/{tenant_id}"
scopes = ["https://graph.microsoft.com/Mail.Read", 
          "https://graph.microsoft.com/Mail.Send",
          "https://graph.microsoft.com/User.Read"]

# Create an MSAL app
app = msal.PublicClientApplication(client_id, authority=authority)

# Initiate device flow authentication
flow = app.initiate_device_flow(scopes=scopes)
print(flow["message"])

# Open the verification URL automatically
webbrowser.open(flow["verification_uri"])

# Wait for the user to complete authentication
result = app.acquire_token_by_device_flow(flow)

if "access_token" in result:
    print("Authentication successful!")
    print(f"Access token: {result['access_token'][:15]}...")
    print(f"Refresh token: {result['refresh_token'][:15]}...")
    
    # Save tokens to file for future use
    with open("ms_graph_tokens.json", "w") as f:
        json.dump(result, f)
    
    print("Tokens saved to ms_graph_tokens.json")
else:
    print(f"Authentication failed: {result.get('error_description', 'Unknown error')}")
```

2. Run the script and follow the authentication flow
3. The script will save the tokens to a file for later use

### Option B: Using the Microsoft Graph Explorer

1. Go to the [Microsoft Graph Explorer](https://developer.microsoft.com/en-us/graph/graph-explorer)
2. Sign in with your Microsoft account
3. Grant the required permissions
4. Run a sample query such as `https://graph.microsoft.com/v1.0/me/messages`
5. In the "Access token" tab, you can see the token (but not the refresh token)

## 6. Store the Credentials in Google Secret Manager

Use the `manage_secrets.py` script to store your Microsoft Graph API credentials:

```bash
python3 scripts/manage_secrets.py --setup
```

When prompted, enter:
- Microsoft Graph Client ID
- Microsoft Graph Client Secret
- Microsoft Graph Tenant ID
- Microsoft Graph Refresh Token
- Notification recipient email (the email that will receive summaries)

## 7. Test the Connection

To verify that the app can access Outlook/Exchange emails, you can run a simple test using the API:

```python
import requests
import json

# Load the tokens from file
with open("ms_graph_tokens.json", "r") as f:
    tokens = json.load(f)

access_token = tokens["access_token"]

# Set up the headers with the access token
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

# Call the Microsoft Graph API to get recent messages
response = requests.get(
    "https://graph.microsoft.com/v1.0/me/messages?$top=10",
    headers=headers
)

# Print the results
if response.status_code == 200:
    messages = response.json()["value"]
    print(f"Retrieved {len(messages)} messages")
    for msg in messages:
        print(f"Subject: {msg['subject']}")
else:
    print(f"Error: {response.status_code}")
    print(response.text)
```

## Next Steps

After completing this setup:

1. The Microsoft Graph API credentials are now stored in Google Secret Manager
2. The Cloud Functions can use these credentials to access Outlook/Exchange emails
3. The system can retrieve emails and send summary notifications

You can now proceed with completing the ICAP setup.