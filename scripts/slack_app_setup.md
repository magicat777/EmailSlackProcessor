# Slack App Setup Guide for ICAP

This guide will walk you through the process of creating a Slack app and configuring the necessary permissions for the ICAP system to retrieve messages.

## 1. Create a New Slack App

1. Navigate to [Slack API - Create App](https://api.slack.com/apps)
2. Click **Create New App**
3. Choose **From scratch**
4. Enter the following details:
   - **App Name**: ICAP Action Processor
   - **Development Slack Workspace**: [Select your workspace]
5. Click **Create App**

## 2. Configure Bot Permissions

1. In the left sidebar, navigate to **OAuth & Permissions**
2. Scroll down to **Bot Token Scopes** and click **Add an OAuth Scope**
3. Add the following scopes:
   - `channels:history` - View messages in public channels
   - `channels:read` - View basic information about public channels
   - `groups:history` - View messages in private channels
   - `groups:read` - View basic information about private channels
   - `im:history` - View messages in direct messages
   - `im:read` - View basic information about direct messages
   - `mpim:history` - View messages in group direct messages
   - `mpim:read` - View basic information about group direct messages
   - `users:read` - View basic information about users
   - `users:read.email` - View email addresses of users

## 3. Install App to Workspace

1. Scroll up to the top of the **OAuth & Permissions** page
2. Click **Install to Workspace**
3. Review the permissions and click **Allow**

## 4. Get the Bot Token

1. After installation, you'll be redirected back to the **OAuth & Permissions** page
2. Copy the **Bot User OAuth Token** that starts with `xoxb-`
3. Store this token securely - you'll need it for the ICAP application

## 5. Add the App to Channels

For the app to access messages in channels:

1. Open your Slack workspace
2. Navigate to the channel where you want the app to read messages
3. Click the channel name at the top to open channel details
4. Click **Integrations** > **Add an App**
5. Find and select **ICAP Action Processor**

## 6. Store the Bot Token in Google Secret Manager

Use the `manage_secrets.py` script to store your Slack Bot Token:

```bash
python3 scripts/manage_secrets.py --setup
```

When prompted, enter the Slack Bot Token you copied earlier.

## 7. Test the Connection

To verify that the app can access messages, you can run a test using the Slack API:

```bash
curl -H "Authorization: Bearer YOUR_BOT_TOKEN" \
     https://slack.com/api/conversations.list
```

Replace `YOUR_BOT_TOKEN` with the actual bot token. You should receive a JSON response containing a list of conversations.

## Next Steps

After completing this setup:

1. The Slack bot token is now stored in Google Secret Manager
2. The Cloud Functions can use this token to retrieve messages
3. The app has the necessary permissions to read messages in channels where it's added

You can now proceed with configuring the Email API and completing the ICAP setup.