/**
 * Google Cloud Function to send email notifications with action item summaries
 * using Microsoft Graph API
 */
const { SecretManagerServiceClient } = require('@google-cloud/secret-manager');
const axios = require('axios');
const qs = require('querystring');

/**
 * Creates and sends a summary email with action items
 * @param {Object} req Cloud Function request context
 * @param {Object} res Cloud Function response context
 */
exports.sendSummaryEmail = async (req, res) => {
  try {
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
    const [recipientEmailResponse] = await secretClient.accessSecretVersion({
      name: 'projects/PROJECT_ID/secrets/notification-recipient-email/versions/latest',
    });
    
    const clientId = clientIdResponse.payload.data.toString();
    const clientSecret = clientSecretResponse.payload.data.toString();
    const refreshToken = refreshTokenResponse.payload.data.toString();
    const tenantId = tenantIdResponse.payload.data.toString();
    const recipientEmail = recipientEmailResponse.payload.data.toString();
    
    // Get a new access token using the refresh token
    const tokenResponse = await axios.post(
      `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token`,
      qs.stringify({
        client_id: clientId,
        client_secret: clientSecret,
        refresh_token: refreshToken,
        grant_type: 'refresh_token',
        scope: 'https://graph.microsoft.com/Mail.Send'
      }),
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      }
    );
    
    const accessToken = tokenResponse.data.access_token;
    
    // Action items data should be provided in the request body
    // In production, you would likely fetch this from a database or API
    const { actionItems = [] } = req.body;
    
    if (!actionItems || !Array.isArray(actionItems)) {
      return res.status(400).json({
        error: 'Invalid action items data. Expected an array of action items.'
      });
    }
    
    // Format the email content
    const today = new Date().toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
    
    // Group action items by project
    const itemsByProject = {};
    
    actionItems.forEach(item => {
      const project = item.project || 'Unassigned';
      if (!itemsByProject[project]) {
        itemsByProject[project] = [];
      }
      itemsByProject[project].push(item);
    });
    
    // Build HTML content
    let htmlContent = `
      <html>
        <head>
          <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; color: #333; }
            h1 { color: #2c3e50; border-bottom: 1px solid #eee; padding-bottom: 10px; }
            h2 { color: #3498db; margin-top: 30px; }
            .action-item { margin-bottom: 15px; padding: 15px; border-left: 4px solid #3498db; background-color: #f9f9f9; }
            .high { border-left-color: #e74c3c; }
            .medium { border-left-color: #f39c12; }
            .low { border-left-color: #2ecc71; }
            .action-content { font-weight: bold; }
            .action-meta { color: #7f8c8d; font-size: 0.9em; margin-top: 5px; }
            .action-due { color: #e74c3c; }
          </style>
        </head>
        <body>
          <h1>Action Items Summary - ${today}</h1>
          <p>Here's your daily summary of action items:</p>
    `;
    
    // Add projects and their action items
    Object.keys(itemsByProject).forEach(project => {
      htmlContent += `<h2>${project}</h2>`;
      
      itemsByProject[project].forEach(item => {
        const dueDate = item.due_date 
          ? new Date(item.due_date).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
              year: 'numeric'
            })
          : 'No due date';
          
        htmlContent += `
          <div class="action-item ${item.priority}">
            <div class="action-content">${item.content}</div>
            <div class="action-meta">
              ${item.assignee ? `Assigned to: ${item.assignee}<br>` : ''}
              ${item.due_date ? `<span class="action-due">Due: ${dueDate}</span><br>` : ''}
              Priority: ${item.priority.charAt(0).toUpperCase() + item.priority.slice(1)}
            </div>
          </div>
        `;
      });
    });
    
    // Close HTML
    htmlContent += `
        </body>
      </html>
    `;
    
    // Send the email using Microsoft Graph API
    // Create the email message payload
    const emailMessage = {
      message: {
        subject: `Action Items Summary - ${today}`,
        body: {
          contentType: 'HTML',
          content: htmlContent
        },
        toRecipients: [
          {
            emailAddress: {
              address: recipientEmail
            }
          }
        ]
      },
      saveToSentItems: true
    };
    
    // Send the email using Microsoft Graph API
    await axios.post(
      'https://graph.microsoft.com/v1.0/me/sendMail',
      emailMessage,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        }
      }
    );
    
    res.status(200).json({
      message: 'Summary email sent successfully',
      recipient: recipientEmail,
      itemsCount: actionItems.length
    });
    
  } catch (error) {
    console.error('Error sending summary email:', error);
    res.status(500).json({
      error: 'Failed to send summary email',
      details: error.message
    });
  }
};

/**
 * HTTP function that triggers summary generation and delivery
 */
exports.triggerDailySummary = (req, res) => {
  // This function would be called by Cloud Scheduler
  res.status(200).send('Daily summary generation triggered');
};