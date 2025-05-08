/**
 * Google Cloud Function to send email notifications with action item summaries
 * using Microsoft Graph API
 */
const { SecretManagerServiceClient } = require('@google-cloud/secret-manager');
const axios = require('axios');
const axiosRetry = require('axios-retry');
const qs = require('querystring');
const { Logging } = require('@google-cloud/logging');
const sanitizeHtml = require('sanitize-html');

// Configure axios retry with exponential backoff
axiosRetry(axios, { 
  retries: 3, 
  retryDelay: axiosRetry.exponentialDelay,
  retryCondition: (error) => {
    return axiosRetry.isNetworkOrIdempotentRequestError(error) || 
           (error.response && error.response.status === 429);
  }
});

// Configure logging
const logging = new Logging();
const log = logging.log('notification-sender');

// Set configuration from environment variables
const MS_GRAPH_TOKEN_URL = process.env.MS_GRAPH_TOKEN_URL || 'https://login.microsoftonline.com';
const MS_GRAPH_API_URL = process.env.MS_GRAPH_API_URL || 'https://graph.microsoft.com/v1.0';
const PROJECT_ID = process.env.GOOGLE_CLOUD_PROJECT || process.env.GCP_PROJECT;

// Initialize Secret Manager
const secretClient = new SecretManagerServiceClient();

/**
 * Fetches a secret from Secret Manager
 * 
 * @param {string} secretName - Name of the secret to fetch
 * @returns {Promise<string>} - The secret value
 */
const getSecret = async (secretName) => {
  try {
    const name = `projects/${PROJECT_ID}/secrets/${secretName}/versions/latest`;
    const [response] = await secretClient.accessSecretVersion({ name });
    return response.payload.data.toString();
  } catch (error) {
    await writeLog(`Error fetching secret ${secretName}: ${error.message}`, 'ERROR');
    throw new Error(`Failed to fetch secret ${secretName}: ${error.message}`);
  }
};

/**
 * Writes a log entry
 * 
 * @param {string} message - Log message
 * @param {string} severity - Log severity (INFO, WARNING, ERROR)
 */
const writeLog = async (message, severity = 'INFO') => {
  const entry = log.entry({ severity }, message);
  await log.write(entry);
};

/**
 * Handles and categorizes errors
 * 
 * @param {Error} error - The error to handle
 * @param {Object} res - Express response object
 */
const handleError = async (error, res) => {
  let statusCode = 500;
  let errorMessage = 'Internal Server Error';
  let errorDetails = error.message;

  await writeLog(`Error: ${error.message}`, 'ERROR');

  if (error.response) {
    statusCode = error.response.status;
    errorMessage = error.response.data?.error || 'API Error';
    errorDetails = error.response.data?.error_description || error.message;
    
    await writeLog(`API Error: ${statusCode} - ${errorMessage}: ${errorDetails}`, 'ERROR');
  } else if (error.request) {
    statusCode = 503;
    errorMessage = 'Service Unavailable';
    errorDetails = 'No response received from the API';
    
    await writeLog(`Network Error: ${errorDetails}`, 'ERROR');
  }

  res.status(statusCode).json({
    error: errorMessage,
    details: errorDetails
  });
};

/**
 * Validates request data
 * 
 * @param {Object} body - Request body containing action items
 * @returns {Object} - Validated data or throws error
 */
const validateRequestData = (body) => {
  const { actionItems = [] } = body;
  
  if (!Array.isArray(actionItems)) {
    throw new Error('Invalid action items data. Expected an array of action items.');
  }
  
  return { actionItems };
};

/**
 * Sanitizes HTML content to prevent XSS attacks
 * 
 * @param {string} html - HTML content to sanitize
 * @returns {string} - Sanitized HTML
 */
const sanitizeContent = (html) => {
  return sanitizeHtml(html, {
    allowedTags: sanitizeHtml.defaults.allowedTags.concat(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']),
    allowedAttributes: {
      ...sanitizeHtml.defaults.allowedAttributes,
      '*': ['class', 'style']
    }
  });
};

/**
 * Creates and sends a summary email with action items
 * @param {Object} req Cloud Function request context
 * @param {Object} res Cloud Function response context
 */
exports.sendSummaryEmail = async (req, res) => {
  try {
    await writeLog('Starting summary email generation', 'INFO');
    
    // Authenticate request - in production implement proper authentication
    // For example:
    // const authHeader = req.headers.authorization;
    // if (!authHeader || !verifyAuth(authHeader)) {
    //   return res.status(401).json({ error: 'Unauthorized' });
    // }
    
    // Validate input data
    const { actionItems } = validateRequestData(req.body);
    await writeLog(`Generating summary email with ${actionItems.length} action items`, 'INFO');
    
    // Get all secrets in parallel
    const [clientId, clientSecret, refreshToken, tenantId, recipientEmail] = await Promise.all([
      getSecret('ms-graph-client-id'),
      getSecret('ms-graph-client-secret'),
      getSecret('ms-graph-refresh-token'),
      getSecret('ms-graph-tenant-id'),
      getSecret('notification-recipient-email')
    ]);
    
    // Get a new access token using the refresh token
    const tokenResponse = await axios.post(
      `${MS_GRAPH_TOKEN_URL}/${tenantId}/oauth2/v2.0/token`,
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
    await writeLog('Successfully obtained access token', 'INFO');
    
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
      // Validate item structure
      if (!item.content) {
        writeLog(`Skipping action item with missing content: ${JSON.stringify(item)}`, 'WARNING');
        return;
      }
      
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
      htmlContent += `<h2>${sanitizeContent(project)}</h2>`;
      
      itemsByProject[project].forEach(item => {
        const dueDate = item.due_date 
          ? new Date(item.due_date).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
              year: 'numeric'
            })
          : 'No due date';
          
        const priority = item.priority || 'medium';
        const sanitizedContent = sanitizeContent(item.content);
        const sanitizedAssignee = item.assignee ? sanitizeContent(item.assignee) : '';
          
        htmlContent += `
          <div class="action-item ${priority}">
            <div class="action-content">${sanitizedContent}</div>
            <div class="action-meta">
              ${sanitizedAssignee ? `Assigned to: ${sanitizedAssignee}<br>` : ''}
              ${item.due_date ? `<span class="action-due">Due: ${dueDate}</span><br>` : ''}
              Priority: ${priority.charAt(0).toUpperCase() + priority.slice(1)}
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
      `${MS_GRAPH_API_URL}/me/sendMail`,
      emailMessage,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        }
      }
    );
    
    await writeLog('Summary email sent successfully', 'INFO');
    res.status(200).json({
      status: 'success',
      message: 'Summary email sent successfully',
      recipient: recipientEmail,
      itemsCount: actionItems.length,
      timestamp: new Date().toISOString()
    });
    
  } catch (error) {
    // Centralized error handling
    await handleError(error, res);
  }
};

/**
 * HTTP function that triggers the daily summary generation
 */
exports.triggerDailySummary = async (req, res) => {
  try {
    await writeLog('Daily summary generation triggered', 'INFO');
    
    // Authenticate request - in production implement proper authentication
    // For Cloud Scheduler, use IAM-based authentication
    
    // Implement the summary generation logic here, for example:
    // 1. Fetch pending action items from Neo4j database
    // 2. Generate summary
    // 3. Send email with the summary
    
    // For demo purposes, we'll just simulate a successful trigger
    await writeLog('Daily summary generation request received', 'INFO');
    
    res.status(200).json({
      status: 'success',
      message: 'Daily summary generation triggered',
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    await writeLog(`Error triggering daily summary: ${error.message}`, 'ERROR');
    res.status(500).json({
      status: 'error',
      message: 'Failed to trigger daily summary',
      details: error.message,
      timestamp: new Date().toISOString()
    });
  }
};