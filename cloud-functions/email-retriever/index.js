/**
 * Google Cloud Function to retrieve email messages using Microsoft Graph API
 */
const axios = require('axios');
const { SecretManagerServiceClient } = require('@google-cloud/secret-manager');
const qs = require('querystring');

/**
 * Retrieves Outlook messages using Microsoft Graph API
 * @param {Object} req Cloud Function request context
 * @param {Object} res Cloud Function response context
 */
exports.retrieveEmails = async (req, res) => {
  try {
    // Validate authentication
    // In production, implement proper authentication for this endpoint
    
    // Get secrets from Secret Manager
    const secretClient = new SecretManagerServiceClient();
    const [clientIdResponse] = await secretClient.accessSecretVersion({
      name: 'projects/PROJECT_ID/secrets/ms-graph-client-id/versions/latest',
    });
    const [clientSecretResponse] = await secretClient.accessSecretVersion({
      name: 'projects/PROJECT_ID/secrets/ms-graph-client-secret/versions/latest',
    });
    const [refreshTokenResponse] = await secretClient.accessSecretVersion({
      name: 'projects/PROJECT_ID/secrets/ms-graph-refresh-token/versions/latest',
    });
    const [tenantIdResponse] = await secretClient.accessSecretVersion({
      name: 'projects/PROJECT_ID/secrets/ms-graph-tenant-id/versions/latest',
    });
    
    const clientId = clientIdResponse.payload.data.toString();
    const clientSecret = clientSecretResponse.payload.data.toString();
    const refreshToken = refreshTokenResponse.payload.data.toString();
    const tenantId = tenantIdResponse.payload.data.toString();
    
    // Get a new access token using the refresh token
    const tokenResponse = await axios.post(
      `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token`,
      qs.stringify({
        client_id: clientId,
        client_secret: clientSecret,
        refresh_token: refreshToken,
        grant_type: 'refresh_token',
        scope: 'https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/Mail.Send'
      }),
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      }
    );
    
    const accessToken = tokenResponse.data.access_token;
    
    // Get parameters from request
    const { maxResults = 10, filter = "isRead eq false" } = req.query;
    
    // Query Microsoft Graph API for messages
    const graphResponse = await axios.get(
      `https://graph.microsoft.com/v1.0/me/messages?$top=${maxResults}&$filter=${filter}&$select=id,conversationId,subject,bodyPreview,receivedDateTime,from,body`,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        }
      }
    );
    
    const messages = graphResponse.data.value || [];
    const emailDetails = [];
    
    // Process each message
    for (const message of messages) {
      // Get full message content if needed
      let fullBody = '';
      
      // If the message body preview is truncated, fetch the full body
      if (message.bodyPreview.endsWith('...')) {
        const fullMessageResponse = await axios.get(
          `https://graph.microsoft.com/v1.0/me/messages/${message.id}?$select=body`,
          {
            headers: {
              'Authorization': `Bearer ${accessToken}`,
              'Content-Type': 'application/json'
            }
          }
        );
        
        fullBody = fullMessageResponse.data.body.content;
      } else {
        // Use the body content from the original response
        fullBody = message.body?.content || '';
      }
      
      // If body is HTML, we could add simple HTML to text conversion here
      // This is a simplified approach - production would handle HTML properly
      if (message.body?.contentType === 'html') {
        fullBody = fullBody.replace(/<[^>]*>/g, ' ');
      }
      
      emailDetails.push({
        id: message.id,
        threadId: message.conversationId,
        subject: message.subject || 'No Subject',
        from: message.from?.emailAddress?.address || 'Unknown Sender',
        date: message.receivedDateTime,
        body: fullBody,
        snippet: message.bodyPreview
      });
    }
    
    res.status(200).json({
      messages: emailDetails
    });
    
  } catch (error) {
    console.error('Error retrieving emails:', error);
    res.status(500).json({
      error: 'Failed to retrieve emails',
      details: error.message
    });
  }
};

/**
 * HTTP function that triggers email processing
 */
exports.processEmails = (req, res) => {
  // This function would be called by Cloud Scheduler
  // It would trigger the email retrieval and then send the data
  // to the processing system
  res.status(200).send('Email processing triggered');
};