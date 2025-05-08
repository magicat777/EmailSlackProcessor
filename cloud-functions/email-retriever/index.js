/**
 * Google Cloud Function to retrieve email messages using Microsoft Graph API
 */
const axios = require('axios');
const axiosRetry = require('axios-retry');
const { SecretManagerServiceClient } = require('@google-cloud/secret-manager');
const qs = require('querystring');
const { Logging } = require('@google-cloud/logging');
const htmlToText = require('html-to-text');

// Configure axios retry with exponential backoff
axiosRetry(axios, { 
  retries: 3, 
  retryDelay: axiosRetry.exponentialDelay,
  retryCondition: (error) => {
    // Retry on network errors and 429 (rate limit) errors
    return axiosRetry.isNetworkOrIdempotentRequestError(error) || 
           (error.response && error.response.status === 429);
  }
});

// Configure logging
const logging = new Logging();
const log = logging.log('email-retriever');

// Set configuration from environment variables
const MS_GRAPH_TOKEN_URL = process.env.MS_GRAPH_TOKEN_URL || 'https://login.microsoftonline.com';
const MS_GRAPH_API_URL = process.env.MS_GRAPH_API_URL || 'https://graph.microsoft.com/v1.0';
const DEFAULT_MAX_RESULTS = parseInt(process.env.DEFAULT_MAX_RESULTS, 10) || 10;
const DEFAULT_FILTER = process.env.DEFAULT_FILTER || "isRead eq false";
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
    // The request was made and the server responded with a status code
    // that falls out of the range of 2xx
    statusCode = error.response.status;
    errorMessage = error.response.data?.error || 'API Error';
    errorDetails = error.response.data?.error_description || error.message;
    
    await writeLog(`API Error: ${statusCode} - ${errorMessage}: ${errorDetails}`, 'ERROR');
  } else if (error.request) {
    // The request was made but no response was received
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
 * Validates request parameters
 * 
 * @param {Object} query - Request query parameters
 * @returns {Object} - Validated parameters
 */
const validateParams = (query) => {
  let maxResults = parseInt(query.maxResults, 10) || DEFAULT_MAX_RESULTS;
  // Enforce reasonable limits
  maxResults = Math.min(Math.max(1, maxResults), 100);
  
  // Sanitize filter parameter - this is a simplified validation
  // In production, implement more thorough validation based on OData filter syntax
  const filter = query.filter || DEFAULT_FILTER;
  
  return { maxResults, filter };
};

/**
 * Converts HTML content to plain text
 * 
 * @param {string} html - HTML content
 * @returns {string} - Plain text content
 */
const convertHtmlToText = (html) => {
  return htmlToText.fromString(html, {
    wordwrap: 120,
    ignoreImage: true,
    ignoreHref: false
  });
};

/**
 * Retrieves Outlook messages using Microsoft Graph API
 * @param {Object} req Cloud Function request context
 * @param {Object} res Cloud Function response context
 */
exports.retrieveEmails = async (req, res) => {
  try {
    await writeLog('Starting email retrieval', 'INFO');
    
    // Authenticate request - in production implement proper authentication
    // For example:
    // const authHeader = req.headers.authorization;
    // if (!authHeader || !verifyAuth(authHeader)) {
    //   return res.status(401).json({ error: 'Unauthorized' });
    // }
    
    // Validate input parameters
    const { maxResults, filter } = validateParams(req.query);
    await writeLog(`Retrieving up to ${maxResults} emails with filter: ${filter}`, 'INFO');
    
    // Get all secrets in parallel
    const [clientId, clientSecret, refreshToken, tenantId] = await Promise.all([
      getSecret('ms-graph-client-id'),
      getSecret('ms-graph-client-secret'),
      getSecret('ms-graph-refresh-token'),
      getSecret('ms-graph-tenant-id')
    ]);
    
    // Get a new access token using the refresh token
    const tokenResponse = await axios.post(
      `${MS_GRAPH_TOKEN_URL}/${tenantId}/oauth2/v2.0/token`,
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
    
    // Query Microsoft Graph API for messages
    const graphResponse = await axios.get(
      `${MS_GRAPH_API_URL}/me/messages?$top=${maxResults}&$filter=${filter}&$select=id,conversationId,subject,bodyPreview,receivedDateTime,from,body`,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        }
      }
    );
    
    const messages = graphResponse.data.value || [];
    await writeLog(`Retrieved ${messages.length} messages`, 'INFO');
    
    // Use Promise.all to process messages in parallel for better performance
    const emailDetails = await Promise.all(messages.map(async (message) => {
      let bodyContent = message.body?.content || '';
      
      // Only fetch full body if needed and explicitly requested via includeFullBody query param
      if (req.query.includeFullBody === 'true' && message.bodyPreview.endsWith('...')) {
        try {
          const fullMessageResponse = await axios.get(
            `${MS_GRAPH_API_URL}/me/messages/${message.id}?$select=body`,
            {
              headers: {
                'Authorization': `Bearer ${accessToken}`,
                'Content-Type': 'application/json'
              }
            }
          );
          
          bodyContent = fullMessageResponse.data.body.content;
        } catch (error) {
          await writeLog(`Error fetching full body for message ${message.id}: ${error.message}`, 'WARNING');
          // Continue with what we have
        }
      }
      
      // Convert HTML to text if needed
      if (message.body?.contentType === 'html') {
        bodyContent = convertHtmlToText(bodyContent);
      }
      
      return {
        id: message.id,
        threadId: message.conversationId,
        subject: message.subject || 'No Subject',
        from: message.from?.emailAddress?.address || 'Unknown Sender',
        date: message.receivedDateTime,
        body: bodyContent,
        snippet: message.bodyPreview
      };
    }));
    
    await writeLog('Email retrieval completed successfully', 'INFO');
    res.status(200).json({
      messages: emailDetails
    });
    
  } catch (error) {
    // Centralized error handling
    await handleError(error, res);
  }
};

/**
 * HTTP function that triggers email processing
 */
exports.processEmails = async (req, res) => {
  try {
    await writeLog('Email processing triggered', 'INFO');
    
    // Authenticate request - in production implement proper authentication
    // For Cloud Scheduler, use IAM-based authentication or a service account
    
    // Implement the processing logic here, for example:
    // 1. Retrieve emails using the above function
    // 2. Process them (extract action items, etc.)
    // 3. Store results in database
    
    // For demo purposes, we'll just simulate a successful processing
    await writeLog('Email processing completed successfully', 'INFO');
    
    res.status(200).json({
      status: 'success',
      message: 'Email processing completed successfully',
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    await writeLog(`Error in email processing: ${error.message}`, 'ERROR');
    res.status(500).json({
      status: 'error',
      message: 'Email processing failed',
      details: error.message,
      timestamp: new Date().toISOString()
    });
  }
};