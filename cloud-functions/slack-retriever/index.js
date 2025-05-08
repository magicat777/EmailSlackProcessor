/**
 * Google Cloud Function to retrieve Slack messages
 */
const { WebClient } = require('@slack/web-api');
const { SecretManagerServiceClient } = require('@google-cloud/secret-manager');

/**
 * Retrieves Slack messages using Slack API
 * @param {Object} req Cloud Function request context
 * @param {Object} res Cloud Function response context
 */
exports.retrieveSlackMessages = async (req, res) => {
  try {
    // Validate authentication
    // In production, implement proper authentication for this endpoint
    
    // Get secrets from Secret Manager
    const secretClient = new SecretManagerServiceClient();
    const [slackTokenResponse] = await secretClient.accessSecretVersion({
      name: 'projects/PROJECT_ID/secrets/slack-bot-token/versions/latest',
    });
    
    const slackToken = slackTokenResponse.payload.data.toString();
    
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
    console.error('Error retrieving Slack messages:', error);
    res.status(500).json({
      error: 'Failed to retrieve Slack messages',
      details: error.message
    });
  }
};

/**
 * HTTP function that triggers Slack message processing
 */
exports.processSlackMessages = (req, res) => {
  // This function would be called by Cloud Scheduler
  // It would trigger the Slack message retrieval and then send the data
  // to the processing system
  res.status(200).send('Slack message processing triggered');
};