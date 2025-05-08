/**
 * Google Cloud Function to retrieve Slack messages
 */
const { WebClient } = require('@slack/web-api');
const { SecretManagerServiceClient } = require('@google-cloud/secret-manager');
const { Logging } = require('@google-cloud/logging');

// Configure logging
const logging = new Logging();
const log = logging.log('slack-retriever');

// Get project ID from environment
const PROJECT_ID = process.env.GOOGLE_CLOUD_PROJECT || process.env.GCP_PROJECT;

// Initialize Secret Manager
const secretClient = new SecretManagerServiceClient();

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
 * Fetches a secret from Secret Manager
 * 
 * @param {string} secretName - Name of the secret to fetch
 * @returns {Promise<string>} - The secret value
 */
const getSecret = async (secretName) => {
  try {
    // First check if it's available as an environment variable
    const envName = secretName.replace(/-/g, '_').toUpperCase();
    if (process.env[envName]) {
      await writeLog(`Using ${secretName} from environment variables`, 'INFO');
      return process.env[envName];
    }
    
    // Otherwise get it from Secret Manager
    const name = `projects/${PROJECT_ID}/secrets/${secretName}/versions/latest`;
    const [response] = await secretClient.accessSecretVersion({ name });
    await writeLog(`Retrieved ${secretName} from Secret Manager`, 'INFO');
    return response.payload.data.toString();
  } catch (error) {
    await writeLog(`Error fetching secret ${secretName}: ${error.message}`, 'ERROR');
    throw new Error(`Failed to fetch secret ${secretName}: ${error.message}`);
  }
};

/**
 * Retrieves Slack messages using Slack API
 * @param {Object} req Cloud Function request context
 * @param {Object} res Cloud Function response context
 */
exports.retrieveSlackMessages = async (req, res) => {
  try {
    await writeLog('Starting Slack message retrieval', 'INFO');
    
    // Validate authentication
    // In production, implement proper authentication for this endpoint
    
    // Get Slack token from Secret Manager
    const slackToken = await getSecret('slack-bot-token');
    
    // Create Slack web client
    const slack = new WebClient(slackToken);
    
    // Get parameters from request
    const { 
      maxResults = 50, 
      olderThan = null,
      channels = null 
    } = req.query;
    
    const limit = parseInt(maxResults);
    const channelList = channels ? channels.split(',') : [];
    
    const allMessages = [];
    
    // If specific channels are provided, get messages from those channels
    if (channelList.length > 0) {
      for (const channelId of channelList) {
        const params = {
          channel: channelId,
          limit: limit,
        };
        
        // Add oldest parameter if provided
        if (olderThan) {
          params.oldest = olderThan;
        }
        
        const result = await slack.conversations.history(params);
        
        // Process each message
        for (const message of result.messages) {
          // Skip bot messages, unless specifically requested
          if (message.subtype === 'bot_message' && !req.query.includeBotMessages) {
            continue;
          }
          
          allMessages.push({
            channelId,
            ...message
          });
        }
      }
    } else {
      // If no channels specified, get list of channels the bot is in
      const conversationsResult = await slack.users.conversations({
        types: 'public_channel,private_channel,im'
      });
      
      // Process each channel
      for (const channel of conversationsResult.channels) {
        const channelId = channel.id;
        
        const params = {
          channel: channelId,
          limit: Math.floor(limit / conversationsResult.channels.length),
        };
        
        // Add oldest parameter if provided
        if (olderThan) {
          params.oldest = olderThan;
        }
        
        const result = await slack.conversations.history(params);
        
        // Process each message
        for (const message of result.messages) {
          // Skip bot messages, unless specifically requested
          if (message.subtype === 'bot_message' && !req.query.includeBotMessages) {
            continue;
          }
          
          allMessages.push({
            channelId,
            ...message
          });
        }
      }
    }
    
    // Process messages to include user details
    const processedMessages = [];
    const userCache = {};
    
    for (const message of allMessages) {
      // Get user info if not already cached
      if (message.user && !userCache[message.user]) {
        try {
          const userInfo = await slack.users.info({ user: message.user });
          userCache[message.user] = {
            id: userInfo.user.id,
            name: userInfo.user.name,
            real_name: userInfo.user.real_name,
            email: userInfo.user.profile.email
          };
        } catch (error) {
          console.warn(`Could not retrieve info for user ${message.user}:`, error.message);
          userCache[message.user] = { id: message.user, name: 'Unknown', real_name: 'Unknown', email: null };
        }
      }
      
      // Add processed message
      processedMessages.push({
        id: message.ts,
        channelId: message.channelId,
        timestamp: message.ts,
        user: message.user ? userCache[message.user] : null,
        text: message.text,
        threadTs: message.thread_ts,
        isReply: !!message.thread_ts
      });
    }
    
    res.status(200).json({
      messages: processedMessages
    });
    
  } catch (error) {
    await writeLog(`Error retrieving Slack messages: ${error.message}`, 'ERROR');
    
    // Determine appropriate status code based on error
    let statusCode = 500;
    let errorMessage = 'Failed to retrieve Slack messages';
    
    if (error.response) {
      // API error response
      statusCode = error.response.status || 500;
      errorMessage = error.response.data?.error || errorMessage;
    } else if (error.code === 'ECONNREFUSED' || error.code === 'ETIMEDOUT') {
      // Network errors
      statusCode = 503;
      errorMessage = 'Service unavailable';
    } else if (error.message.includes('Secret Manager')) {
      // Secret Manager errors
      statusCode = 500;
      errorMessage = 'Configuration error';
    }
    
    res.status(statusCode).json({
      error: errorMessage,
      details: error.message
    });
  }
};

/**
 * HTTP function that triggers Slack message processing
 */
exports.processSlackMessages = async (req, res) => {
  try {
    await writeLog('Slack message processing triggered', 'INFO');
    
    // Authenticate request - in production implement proper authentication
    // For Cloud Scheduler, use IAM-based authentication or a service account
    
    // Implement the processing logic here, for example:
    // 1. Retrieve Slack messages using the above function (internal call)
    // 2. Process them (extract action items, etc.)
    // 3. Store results in database
    
    // For demo purposes, we'll just simulate a successful processing
    await writeLog('Slack processing completed successfully', 'INFO');
    
    res.status(200).json({
      status: 'success',
      message: 'Slack message processing completed successfully',
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    await writeLog(`Error in Slack processing: ${error.message}`, 'ERROR');
    res.status(500).json({
      status: 'error',
      message: 'Slack message processing failed',
      details: error.message,
      timestamp: new Date().toISOString()
    });
  }
};