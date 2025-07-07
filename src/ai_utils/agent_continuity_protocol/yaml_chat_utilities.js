// YAML Chat History Manager - Background Process
// This runs automatically with each Claude response to maintain conversation history

// Simple YAML utilities (browser-compatible)
const YamlUtils = {
  stringify: (obj, indent = 0) => {
    const spaces = '  '.repeat(indent);
    let result = '';
    
    for (const [key, value] of Object.entries(obj)) {
      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        result += `${spaces}${key}:\n`;
        result += YamlUtils.stringify(value, indent + 1);
      } else if (Array.isArray(value)) {
        result += `${spaces}${key}:\n`;
        value.forEach(item => {
          if (typeof item === 'object' && item !== null) {
            result += `${spaces}  -\n`;
            result += YamlUtils.stringify(item, indent + 2).replace(/^/gm, `${spaces}    `);
          } else {
            const itemStr = typeof item === 'string' ? JSON.stringify(item) : String(item);
            result += `${spaces}  - ${itemStr}\n`;
          }
        });
      } else {
        const valueStr = typeof value === 'string' ? JSON.stringify(value) : String(value);
        result += `${spaces}${key}: ${valueStr}\n`;
      }
    }
    return result;
  }
};

// Background Chat History Manager
class BackgroundChatHistory {
  constructor() {
    this.initializeHistory();
    this.autoSaveEnabled = true;
  }

  initializeHistory() {
    this.history = {
      metadata: {
        conversation_id: this.generateConversationId(),
        created: new Date().toISOString(),
        last_updated: new Date().toISOString(),
        version: 1,
        total_messages: 0,
        total_exchanges: 0,
        tags: ['chat-continuity', 'yaml-utilities'],
        format_version: '1.0'
      },
      chat_sessions: [{
        session_id: this.generateSessionId(),
        started: new Date().toISOString(),
        ended: null,
        platform: 'claude',
        continued_from: null,
        tags: ['active-session'],
        messages: []
      }]
    };

    // Auto-record the initial context
    this.recordInitialContext();
  }

  generateConversationId() {
    return `conv_${new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z')}`;
  }

  generateMessageId() {
    return `msg_${new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z')}_${Math.random().toString(36).substr(2, 5)}`;
  }

  generateSessionId() {
    return `session_${new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z')}`;
  }

  getCurrentSession() {
    return this.history.chat_sessions[this.history.chat_sessions.length - 1];
  }

  recordInitialContext() {
    // Record the conversation starter
    this.recordMessage('user', 
      `Hi Claude, I'm trying to continue a conversation about using chat files to record chats to work around the limited number of messages allowed per chat. Attached is our previous chat about it along with some python scripts, with the yaml ones being in src/yaml_utils. We'll need to create JavaScript versions of the yaml scripts, but we don't need all of them ported, just the ones you would run.`,
      ['initial-context', 'yaml-utilities'],
      [{
        type: 'file',
        filename: 'Chats-2025-06-29_02-49-08.md',
        description: 'Previous chat conversation markdown',
        uploaded_at: new Date().toISOString()
      }]
    );
  }

  // Core method: Record a message (called automatically by Claude)
  recordMessage(role, content, tags = [], attachments = []) {
    const message = {
      message_id: this.generateMessageId(),
      message_number: this.history.metadata.total_messages + 1,
      conversation_id: this.history.metadata.conversation_id,
      session_id: this.getCurrentSession().session_id,
      timestamp: new Date().toISOString(),
      role: role,
      content: content,
      attachments: attachments,
      tags: tags,
      metadata: {
        estimated_tokens: Math.ceil(content.length / 4),
        char_count: content.length,
        word_count: content.split(/\s+/).filter(w => w.length > 0).length
      }
    };

    // Add to current session
    this.getCurrentSession().messages.push(message);

    // Update conversation metadata
    this.history.metadata.total_messages++;
    this.history.metadata.last_updated = new Date().toISOString();
    this.history.metadata.version++;

    // Update exchange count if this completes an exchange
    if (role === 'assistant') {
      this.history.metadata.total_exchanges++;
    }

    // Auto-save if enabled
    if (this.autoSaveEnabled) {
      this.autoSave();
    }

    return message;
  }

  // Record Claude's response with artifacts
  recordClaudeResponse(content, artifactIds = [], tags = []) {
    const attachments = artifactIds.map(id => ({
      type: 'artifact',
      artifact_id: id,
      artifact_type: 'code', // or determined from artifact
      title: id.replace(/_/g, ' '),
      created_at: new Date().toISOString()
    }));

    return this.recordMessage('assistant', content, tags, attachments);
  }

  // Import previous conversation history
  importPreviousHistory(importedData) {
    // Mark current session as ended
    this.getCurrentSession().ended = new Date().toISOString();

    // Merge imported data
    this.history = {
      ...importedData,
      metadata: {
        ...importedData.metadata,
        imported_at: new Date().toISOString(),
        previous_conversation_id: importedData.metadata.conversation_id,
        conversation_id: this.history.metadata.conversation_id,
        version: importedData.metadata.version + 1,
        continued_from_import: true
      }
    };

    // Start new session for continuation
    const newSession = {
      session_id: this.generateSessionId(),
      started: new Date().toISOString(),
      ended: null,
      platform: 'claude',
      continued_from: 'import',
      tags: ['imported-continuation'],
      messages: []
    };

    this.history.chat_sessions.push(newSession);
    return this.history;
  }

  // Auto-save to browser storage (would be adapted for actual environment)
  autoSave() {
    try {
      // In Claude's environment, this would need to be adapted
      // For now, just prepare the data
      const yamlContent = this.exportToYaml();
      
      // Store latest version (implementation depends on Claude's capabilities)
      this.lastSavedContent = yamlContent;
      this.lastSavedTimestamp = new Date().toISOString();
      
    } catch (error) {
      console.warn('Auto-save failed:', error);
    }
  }

  // Export to YAML for download
  exportToYaml() {
    return YamlUtils.stringify(this.history);
  }

  // Export for handoff when approaching limits
  exportForHandoff() {
    // Close current session
    this.getCurrentSession().ended = new Date().toISOString();

    const handoffData = {
      ...this.history,
      metadata: {
        ...this.history.metadata,
        exported_for_handoff: new Date().toISOString(),
        usage_limit_approaching: true,
        handoff_instructions: [
          "Import this file in new Claude session",
          "Tell Claude: 'Continue our conversation from this imported history'",
          "Claude will automatically resume background tracking"
        ]
      }
    };

    return YamlUtils.stringify(handoffData);
  }

  // Get current stats for monitoring
  getStats() {
    const allMessages = [];
    this.history.chat_sessions.forEach(session => {
      allMessages.push(...session.messages);
    });

    const estimatedTokens = allMessages.reduce((sum, msg) => 
      sum + msg.metadata.estimated_tokens, 0
    );

    return {
      conversation_id: this.history.metadata.conversation_id,
      total_sessions: this.history.chat_sessions.length,
      total_messages: this.history.metadata.total_messages,
      total_exchanges: this.history.metadata.total_exchanges,
      estimated_tokens: estimatedTokens,
      created: this.history.metadata.created,
      last_updated: this.history.metadata.last_updated,
      tags: this.history.metadata.tags,
      approaching_limit: estimatedTokens > 15000
    };
  }

  // Add tags to current conversation
  addTags(tags) {
    const newTags = tags.filter(tag => !this.history.metadata.tags.includes(tag));
    this.history.metadata.tags.push(...newTags);
    this.history.metadata.version++;
  }
}

// Global instance for Claude to use
let chatHistory = null;

// Initialize chat history (called once per session)
function initializeChatHistory() {
  if (!chatHistory) {
    chatHistory = new BackgroundChatHistory();
  }
  return chatHistory;
}

// Main function Claude calls with each response
function updateChatHistory(claudeResponse, artifactIds = [], tags = []) {
  if (!chatHistory) {
    initializeChatHistory();
  }
  
  return chatHistory.recordClaudeResponse(claudeResponse, artifactIds, tags);
}

// Function to get download-ready YAML
function getDownloadableHistory() {
  if (!chatHistory) {
    return "No chat history available";
  }
  
  return chatHistory.exportForHandoff();
}

// Usage example (how Claude would use this):
/*
// At start of session:
initializeChatHistory();

// With each response:
updateChatHistory(
  "Looking at our previous conversation and your YAML utilities...", 
  ['yaml_chat_utilities'], 
  ['technical-discussion', 'yaml-development']
);

// When user asks for download:
const yamlContent = getDownloadableHistory();
// Provide yamlContent for download
*/

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { 
    BackgroundChatHistory, 
    initializeChatHistory, 
    updateChatHistory, 
    getDownloadableHistory 
  };
}