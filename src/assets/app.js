// Enhanced JavaScript utilities for Claude Code Proxy
// This file contains additional functionality to complement the existing config.html

let baseUrl = '';
let autoRefreshInterval = null;
let recentChanges = [];
let currentTab = 'config';
let messageHistory = [];
let lastMessageId = 0;
let summaryData = null;
let expandedMessageIds = new Set(); // Track which messages are expanded
let currentlyViewingContent = null; // Track current expanded message
let currentDateFilter = { startDate: null, endDate: null }; // Track current date filter
let historyFilters = {
    date: null,
    hour: null,
    limit: 100
}; // Track current history filters
let historyMode = 'live'; // 'live' or 'datetime'
let historyLiveInterval = null;
let isFirstHistoryLoad = true;

// Initialize
document.addEventListener('DOMContentLoaded', function () {
    // Auto-refresh checkbox handler
    document.getElementById('autoRefresh').addEventListener('change', function () {
        if (this.checked && baseUrl) {
            startAutoRefresh();
        } else {
            stopAutoRefresh();
        }
    });
    connectToProxy();
});

function connectToProxy() {
    const port = document.getElementById('port').value;
    baseUrl = `http://localhost:${port}`;

    showMessage('Connecting to proxy...', 'info');
    updateConnectionStatus('loading', 'Connecting...');

    // Test connection
    fetchConfig()
        .then(() => {
            updateConnectionStatus('connected', 'Connected');
            showMessage('Successfully connected to proxy!', 'success');
            document.getElementById('configContent').style.display = 'block';
            document.getElementById('healthContent').style.display = 'block';
            document.getElementById('historyContent').style.display = 'block';
            document.getElementById('summaryContent').style.display = 'block';
            document.getElementById('logsPlaceholder').style.display = 'none';
            document.getElementById('historyPlaceholder').style.display = 'none';
            document.getElementById('summaryPlaceholder').style.display = 'none';

            // Initialize ProxyManager
            if (window.proxyManager) {
                window.proxyManager.connectWithRetry(port).catch(error => {
                    console.warn('Enhanced connection failed:', error);
                });
            }

            // Start auto-refresh if enabled
            if (document.getElementById('autoRefresh').checked) {
                startAutoRefresh();
            }

            // Initial data load
            loadHealthData();
            loadHistoryData();
            loadSummaryData();
        })
        .catch(error => {
            updateConnectionStatus('disconnected', 'Connection Failed');
            showMessage(`Connection failed: ${error.message}`, 'error');
            document.getElementById('configContent').style.display = 'none';
            document.getElementById('healthContent').style.display = 'none';
            document.getElementById('historyContent').style.display = 'none';
            document.getElementById('summaryContent').style.display = 'none';
            document.getElementById('logsPlaceholder').style.display = 'block';
            document.getElementById('historyPlaceholder').style.display = 'block';
            document.getElementById('summaryPlaceholder').style.display = 'block';
        });
}

function updateConnectionStatus(status, text) {
    const statusEl = document.getElementById('connectionStatus');
    statusEl.className = `status-indicator status-${status}`;
    statusEl.textContent = text;

    // Clean up resources when disconnecting
    if (status === 'disconnected' && window.proxyManager) {
        window.proxyManager.disconnect();
    }
}

function showMessage(text, type) {
    const messageEl = document.getElementById('message');
    messageEl.textContent = text;
    messageEl.className = `message ${type}`;
    messageEl.style.display = 'block';

    setTimeout(() => {
        messageEl.style.display = 'none';
    }, 5000);
}

async function fetchConfig() {
    const response = await fetch(`${baseUrl}/api/config/get`);
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();

    updateConfigDisplay(data);
    return data;
}

async function fetchHealth() {
    const response = await fetch(`${baseUrl}/health`);
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return await response.json();
}

function updateConfigDisplay(config) {
    // Store provider info globally for access in updateModelSection
    window.providerInfo = config.providers || {};

    // Update base URL
    document.getElementById('baseUrl').textContent = `Base URL: ${config.base_url}`;

    // Update model sections
    updateModelSection('bigModels', 'BIG_MODEL', config.available.BIG_MODELS, config.current.BIG_MODEL);
    updateModelSection('middleModels', 'MIDDLE_MODEL', config.available.MIDDLE_MODELS, config.current.MIDDLE_MODEL);
    updateModelSection('smallModels', 'SMALL_MODEL', config.available.SMALL_MODELS, config.current.SMALL_MODEL);

    // Update model counts and usage statistics
    if (config.model_counts) {
        updateModelCounts(config.model_counts);
    }

    // Update provider information
    updateProviderInfo(config.providers);

    // Update last update time
    document.getElementById('lastUpdate').textContent = `Last updated: ${new Date().toLocaleTimeString()}`;
}

function updateModelSection(containerId, modelType, availableModels, currentModel) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';

    availableModels.forEach(model => {
        const optionDiv = document.createElement('div');
        optionDiv.className = 'model-option';

        const input = document.createElement('input');
        input.type = 'radio';
        input.name = modelType;
        input.value = model;
        input.id = `${modelType}_${model}`;
        input.checked = model === currentModel;
        input.addEventListener('change', () => updateModel(modelType, model));

        const label = document.createElement('label');
        label.htmlFor = input.id;

        // Parse provider info from model name (format: "Provider:model")
        if (model.includes(':')) {
            const [providerName, modelName] = model.split(':', 2);
            // Get provider info from the global provider data
            const providerData = window.providerInfo && window.providerInfo[providerName];
            const isNative = providerData && providerData.provider_type === 'anthropic';

            if (isNative) {
                label.innerHTML = `${model} <span style="color: #28a745; font-size: 0.8em;">[native]</span>`;
            } else {
                label.textContent = model;
            }
        } else {
            label.textContent = model;
        }

        optionDiv.appendChild(input);
        optionDiv.appendChild(label);
        container.appendChild(optionDiv);
    });
}

async function updateModel(modelType, modelValue) {
    try {
        const updateData = {};
        updateData[modelType] = modelValue;

        const response = await fetch(`${baseUrl}/api/config/update`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(updateData)
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const result = await response.json();
        showMessage(`Updated ${modelType} to ${modelValue}`, 'success');

        // Add to recent changes
        const timestamp = new Date().toLocaleTimeString();
        recentChanges.push(`${timestamp}: ${modelType} → ${modelValue}`);
        if (recentChanges.length > 5) {
            recentChanges.shift();
        }

        // Refresh config to show updated state
        setTimeout(fetchConfig, 500);

    } catch (error) {
        showMessage(`Failed to update model: ${error.message}`, 'error');
        // Revert the radio button selection
        fetchConfig();
    }
}

async function loadHealthData() {
    try {
        const health = await fetchHealth();
        updateHealthDisplay(health);
    } catch (error) {
        console.error('Failed to load health data:', error);
    }
}

function updateHealthDisplay(health) {
    const healthStatus = document.getElementById('healthStatus');
    healthStatus.innerHTML = `
                <div class="health-item ${health.status !== 'healthy' ? 'error' : ''}">
                    <strong>Status</strong>
                    ${health.status}
                </div>
                <div class="health-item">
                    <strong>API Key Configured</strong>
                    ${health.openai_api_configured ? 'Yes' : 'No'}
                </div>
                <div class="health-item ${!health.api_key_valid ? 'error' : ''}">
                    <strong>API Key Valid</strong>
                    ${health.api_key_valid ? 'Yes' : 'No'}
                </div>
                <div class="health-item">
                    <strong>Client Validation</strong>
                    ${health.client_api_key_validation ? 'Enabled' : 'Disabled'}
                </div>
            `;

    // Update logs
    updateLogs();
}

function updateLogs() {
    const logsContent = document.getElementById('logsContent');
    let logs = [`[${new Date().toLocaleTimeString()}] System health checked`];

    // Add recent changes to logs
    logs = logs.concat(recentChanges.map(change => `[LOG] ${change}`));

    logsContent.innerHTML = logs.map(log =>
        `<div class="log-entry">${log}</div>`
    ).join('');

    // Scroll to bottom
    logsContent.scrollTop = logsContent.scrollHeight;
}

function updateModelCounts(modelCounts) {
    if (!modelCounts) return;

    // Update individual model counts
    const bigCount = modelCounts['big_model'] || 0;
    const middleCount = modelCounts['middle_model'] || 0;
    const smallCount = modelCounts['small_model'] || 0;

    document.getElementById('bigModelCount').innerHTML =
        `<strong>Usage: ${bigCount}</strong> requests`;
    document.getElementById('middleModelCount').innerHTML =
        `<strong>Usage: ${middleCount}</strong> requests`;
    document.getElementById('smallModelCount').innerHTML =
        `<strong>Usage: ${smallCount}</strong> requests`;

    // Update detailed usage statistics
    const statsContainer = document.getElementById('modelUsageStats');
    const sortedCounts = Object.entries(modelCounts)
        .map(([model, count]) => ({ model: model.replace('self.', ''), count: count || 0 }))
        .sort((a, b) => b.count - a.count);

    if (sortedCounts.length === 0) {
        statsContainer.innerHTML = '<div style="color: #6c757d; text-align: center;">No usage data available</div>';
        return;
    }

    const totalRequests = sortedCounts.reduce((sum, item) => sum + item.count, 0);
    let statsHTML = '';

    sortedCounts.forEach(({ model, count }) => {
        if (count > 0) {
            const percentage = totalRequests > 0 ? ((count / totalRequests) * 100).toFixed(1) : 0;
            const barWidth = Math.min(100, percentage * 0.8); // Scale bar intentionally smaller

            statsHTML += `
                        <div style="margin-bottom: 8px;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                                <span style="font-weight: 500;">${model}</span>
                                <span style="color: #495057;">${count} requests (${percentage}%)</span>
                            </div>
                            <div style="background: #e9ecef; height: 12px; border-radius: 6px; overflow: hidden;">
                                <div style="background: linear-gradient(90deg, #4facfe, #00f2fe); 
                                            width: ${barWidth}%; height: 100%; border-radius: 6px; 
                                            transition: width 0.5s ease; display: flex; align-items: center; justify-content: flex-end;">
                                </div>
                            </div>
                        </div>
                    `;
        }
    });

    if (statsHTML === '') {
        statsContainer.innerHTML = '<div style="color: #6c757d; text-align: center;">No requests yet</div>';
    } else {
        statsContainer.innerHTML = statsHTML +
            `<div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #dee2e6; color: #495057;">
                        <strong>Total requests: ${totalRequests}</strong>
                    </div>`;
    }
}

function updateProviderInfo(providers) {
    const container = document.getElementById('providerInfo');
    if (!providers || Object.keys(providers).length === 0) {
        container.innerHTML = '<div style="color: #6c757d; text-align: center;">No providers configured</div>';
        return;
    }

    let html = '<div style="font-family: monospace;">';

    Object.entries(providers).forEach(([name, info]) => {
        const providerType = info.provider_type || 'openai';
        const typeDisplay = providerType === 'anthropic' ?
            '<span style="color: #28a745;">[native]</span>' :
            '<span style="color: #007bff;">[converted]</span>';

        html += `
            <div style="margin-bottom: 15px; padding: 10px; background: white; border-radius: 6px; border: 1px solid #dee2e6;">
                <div style="font-weight: bold; margin-bottom: 5px;">
                    ${name} ${typeDisplay}
                </div>
                <div style="color: #666; font-size: 0.85em;">
                    Type: ${providerType}<br>
                    Base URL: ${info.base_url}<br>
                    Models: ${Object.values(info.models).flat().length} available
                </div>
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;
}

function startAutoRefresh() {
    stopAutoRefresh(); // Clear any existing interval
    autoRefreshInterval = setInterval(async () => {
        if (baseUrl) {
            try {
                await fetchConfig();
                await loadHealthData();
                if (currentTab === 'history') {
                    await loadNewHistoryMessages();
                } else if (currentTab === 'summary') {
                    await loadSummaryData();
                }
            } catch (error) {
                console.error('Auto-refresh failed:', error);
            }
        }
    }, 3000);
}

function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
}

function switchTab(tabName) {
    // Update active tab button
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');

    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });

    // Show selected tab content
    document.getElementById(tabName + '-tab').classList.add('active');
    currentTab = tabName;

    // Load data for the selected tab if connected
    if (baseUrl) {
        if (tabName === 'history') {
            loadHistoryData();
        } else if (tabName === 'summary') {
            loadSummaryData();
        }
    }
}

async function loadHistoryData() {
    try {
        const response = await fetch(`${baseUrl}/api/history?limit=100`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        const data = await response.json();

        messageHistory = data.data.messages;
        if (messageHistory.length > 0) {
            lastMessageId = Math.max(...messageHistory.map(m => m.id));
        }
        updateHistoryDisplay();

    } catch (error) {
        console.error('Failed to load history data:', error);
        document.getElementById('messageList').innerHTML =
            '<div style="text-align: center; padding: 30px; color: #dc3545;">Failed to load message history</div>';
    }
}

async function loadNewHistoryMessages() {
    try {
        const response = await fetch(`${baseUrl}/api/history?limit=20`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        const data = await response.json();

        const allMessages = data.data.messages;
        const newMessages = allMessages.filter(msg => msg.id > lastMessageId);

        // Check for status updates in existing messages
        let hasStatusUpdates = false;
        if (messageHistory.length > 0) {
            for (let i = 0; i < messageHistory.length; i++) {
                const currentMsg = messageHistory[i];
                const updatedMsg = allMessages.find(msg => msg.id === currentMsg.id);

                if (updatedMsg && (
                    updatedMsg.status !== currentMsg.status ||
                    updatedMsg.total_tokens !== currentMsg.total_tokens ||
                    updatedMsg.response_length !== currentMsg.response_length
                )) {
                    messageHistory[i] = updatedMsg;
                    hasStatusUpdates = true;

                    // Update the specific message element in the DOM
                    updateMessageStatus(i, updatedMsg); // i is passed but not used in the function
                }
            }
        }

        // Handle new messages
        if (newMessages.length > 0) {
            // Add new messages to the beginning of the array
            messageHistory = [...newMessages, ...messageHistory];

            // Keep only the most recent 20 messages to avoid memory issues
            if (messageHistory.length > 20) {
                messageHistory = messageHistory.slice(0, 20);

                // Clean up expanded state for removed messages
                const remainingIds = new Set(messageHistory.map(m => m.id));
                expandedMessageIds = new Set([...expandedMessageIds].filter(id => remainingIds.has(id)));

                // Clear currentlyViewingContent if the message was removed
                if (currentlyViewingContent && !remainingIds.has(currentlyViewingContent.messageId)) {
                    currentlyViewingContent = null;
                }
            }

            // Update the last message ID
            lastMessageId = Math.max(...messageHistory.map(m => m.id));

            // Use smart update instead of full rebuild
            appendNewMessages(newMessages);
        } else if (hasStatusUpdates) {
            // If no new messages but we have status updates, use smart updates
            console.log('Status updates detected, using smart update');
            updateExistingMessages();
        }

    } catch (error) {
        console.error('Failed to load new history messages:', error);
    }
}

function updateHistoryDisplay() {
    const messageList = document.getElementById('messageList');

    if (messageHistory.length === 0) {
        messageList.innerHTML =
            '<div style="text-align: center; padding: 30px; color: #6c757d;">No messages found</div>';
        return;
    }

    let htmlContent = '';
    messageHistory.forEach((message, index) => {
        const timestamp = new Date(message.timestamp).toLocaleString();
        const requestLength = message.request_length || 0;
        const responseLength = message.response_length || 0;
        const statusBadge = message.status === 'completed' ?
            '<span style="color: #28a745;">✓</span>' :
            message.status === 'partial' ?
                '<span style="color: #ffc107;">⚠</span>' :
                '<span style="color: #ffc107;">⏳</span>';

        const stopReasonBadge = getStopReasonBadge(message);
        const messageTypeInfo = getMessageTypeInfo(message);

        // Check if this message should be expanded
        const isExpanded = expandedMessageIds.has(message.id);
        const expandedClass = isExpanded ? ' expanded' : '';

        htmlContent += `
                    <div class="message-item" data-index="${index}" data-message-id="${message.id}">
                        <div class="message-click-box" style="width: 40em;" onclick="toggleMessageContent('${message.id}')">
                            <div class="message-header">
                                <span class="message-model">${message.model_name} → ${message.actual_model} ${statusBadge}${stopReasonBadge}</span>
                                <span class="message-time">${timestamp}</span>
                            </div>
                            <div class="message-details">
                                Request: ${requestLength} chars | Response: ${responseLength} chars
                                ${message.is_streaming ? ' | Streaming' : ''}
                                ${messageTypeInfo}
                            </div>
                            <div class="message-tokens">
                                ${message.total_tokens > 0 ?
                `<span class="token-info">📊 Input: ${message.input_tokens} | Output: ${message.output_tokens} | Total: ${message.total_tokens}</span>` :
                '<span class="token-info-empty">📊 Token usage not available</span>'
            }
                            </div>
                        </div>
                        <div id="message-content-${message.id}" class="message-content${expandedClass}">
                            <div class="json-toggle">
                                <button onclick="showJsonContent('${message.id}', 'request', event);" class="active">Request</button>
                                <button onclick="showJsonContent('${message.id}', 'openai_request', event);" >OpenAiRequest</button>
                                <button onclick="showJsonContent('${message.id}', 'response', event);">Response</button>
                            </div>
                            <div id="json-content-${message.id}" class="json-viewer"></div>
                        </div>
                    </div>
                `;
    });

    messageList.innerHTML = htmlContent;

    // Restore expanded state and content after DOM update
    restoreExpandedMessageStates();
}

function toggleMessageContent(messageId) {
    // Find the message in the history by its ID
    const message = messageHistory.find(m => m.id.toString() === messageId.toString());
    if (!message) return;

    const contentEl = document.getElementById(`message-content-${messageId}`);
    const isExpanded = contentEl && contentEl.classList.contains('expanded');

    if (isExpanded) {
        // Close this message
        expandedMessageIds.delete(parseInt(messageId));
        currentlyViewingContent = null;
        if (contentEl) {
            contentEl.classList.remove('expanded');
        }
    } else {
        // Close all other expanded messages
        expandedMessageIds.clear();
        document.querySelectorAll('.message-content.expanded').forEach(el => {
            el.classList.remove('expanded');
        });

        // Open this message
        expandedMessageIds.add(parseInt(messageId));
        currentlyViewingContent = { messageId, contentType: 'request' };
        if (contentEl) {
            contentEl.classList.add('expanded');
            showJsonContent(messageId, 'request');
        }
    }
}

function showJsonContent(messageId, type, event) {
    // Find the message in the history by its ID
    const message = messageHistory.find(m => m.id.toString() === messageId.toString());
    if (!message) return;

    const jsonContentEl = document.getElementById(`json-content-${messageId}`);
    const buttons = document.querySelectorAll(`#message-content-${messageId} .json-toggle button`);

    // Update active button
    buttons.forEach(btn => btn.classList.remove('active'));
    if (event && event.target) {
        event.target.classList.add('active');
    } else {
        // When called programmatically, find the correct button
        const targetButton = Array.from(buttons).find(btn =>
            btn.textContent.toLowerCase() === type.toLowerCase()
        );
        if (targetButton) {
            targetButton.classList.add('active');
        }
    }

    // Update tracking state
    if (currentlyViewingContent && currentlyViewingContent.messageId === messageId) {
        currentlyViewingContent.contentType = type;
    }

    // Show the requested content
    var content = ""
    if (type === 'request' ) {
        content =  message.request_data;
    }  else if (type === 'openai_request') {
        content = message.openai_request;
    } else {
        content = message.response_data;
    }
    if (jsonContentEl) {
        jsonContentEl.textContent = JSON.stringify(content, null, 2);
    }
}

function appendNewMessages(newMessages) {
    const messageList = document.getElementById('messageList');

    // Sort new messages by ID descending (newest first)
    newMessages.sort((a, b) => b.id - a.id);

    // Create HTML for new messages
    let newHtml = '';
    newMessages.forEach((message) => {
        const timestamp = new Date(message.timestamp).toLocaleString();
        const requestLength = message.request_length || 0;
        const responseLength = message.response_length || 0;
        const statusBadge = message.status === 'completed' ?
            '<span style="color: #28a745;">✓</span>' :
            message.status === 'partial' ?
                '<span style="color: #ffc107;">⚠</span>' :
                '<span style="color: #ffc107;">⏳</span>';

        // Find the current index in the full messageHistory array
        const index = messageHistory.findIndex(m => m.id === message.id);

        const stopReasonBadge = getStopReasonBadge(message);
        const messageTypeInfo = getMessageTypeInfo(message);

        newHtml += `
                    <div class="message-item" data-index="${index}" data-message-id="${message.id}">
                        <div class="message-click-box" style="width: 40em;" onclick="toggleMessageContent('${message.id}')">
                        <div class="message-header">
                            <span class="message-model">${message.model_name} → ${message.actual_model} ${statusBadge}${stopReasonBadge}</span>
                            <span class="message-time">${timestamp}</span>
                        </div>
                        <div class="message-details">
                            Request: ${requestLength} chars | Response: ${responseLength} chars
                            ${message.is_streaming ? ' | Streaming' : ''}
                            ${messageTypeInfo}
                        </div>
                        <div class="message-tokens">
                            ${message.total_tokens > 0 ?
                `<span class="token-info">📊 Input: ${message.input_tokens} | Output: ${message.output_tokens} | Total: ${message.total_tokens}</span>` :
                '<span class="token-info-empty">📊 Token usage not available</span>'
            }
                        </div>
                        </div>
                        <div id="message-content-${message.id}" class="message-content">
                            <div class="json-toggle">
                                <button onclick="showJsonContent('${message.id}', 'request', event);" class="active">Request</button>
                                <button onclick="showJsonContent('${message.id}', 'openai_request', event);" >OpenAI Request</button>
                                <button onclick="showJsonContent('${message.id}', 'response', event);">Response</button>
                            </div>
                            <div id="json-content-${message.id}" class="json-viewer"></div>
                        </div>
                    </div>
                `;
    });

    // Check if this is the first load (empty list)
    if (messageList.innerHTML.includes('Loading message history') ||
        messageList.innerHTML.includes('No messages found') ||
        messageList.innerHTML.includes('Failed to load')) {
        // First load - replace everything
        updateHistoryDisplay();
    } else {
        // Append new messages at the top
        messageList.insertAdjacentHTML('afterbegin', newHtml);

        // Add a subtle notification for new messages
        if (newMessages.length > 0) {
            showNewMessageNotification(newMessages.length);
        }
    }
}

function updateMessageStatus(index, updatedMessage) {
    // Find the message element by message ID
    const messageId = updatedMessage.id;
    const messageElement = document.querySelector(`.message-item[data-message-id="${messageId}"]`);

    if (messageElement) {
        // Update status badge and stop reason badge
        const modelSpan = messageElement.querySelector('.message-model');
        if (modelSpan) {
            const statusBadge = updatedMessage.status === 'completed' ?
                '<span style="color: #28a745;">✓</span>' :
                updatedMessage.status === 'partial' ?
                    '<span style="color: #ffc107;">⚠</span>' :
                    '<span style="color: #ffc107;">⏳</span>';

            const stopReasonBadge = getStopReasonBadge(updatedMessage);

            modelSpan.innerHTML = `${updatedMessage.model_name} → ${updatedMessage.actual_model} ${statusBadge}${stopReasonBadge}`;
        }

        // Update message details
        const detailsDiv = messageElement.querySelector('.message-details');
        if (detailsDiv) {
            const requestLength = updatedMessage.request_length || 0;
            const responseLength = updatedMessage.response_length || 0;
            const messageTypeInfo = getMessageTypeInfo(updatedMessage);

            detailsDiv.innerHTML = `
                        Request: ${requestLength} chars | Response: ${responseLength} chars
                        ${updatedMessage.is_streaming ? ' | Streaming' : ''}
                        ${messageTypeInfo}
                    `;
        }

        // Update token information
        const tokensDiv = messageElement.querySelector('.message-tokens');
        if (tokensDiv) {
            tokensDiv.innerHTML = updatedMessage.total_tokens > 0 ?
                `<span class="token-info">📊 Input: ${updatedMessage.input_tokens} | Output: ${updatedMessage.output_tokens} | Total: ${updatedMessage.total_tokens}</span>` :
                '<span class="token-info-empty">📊 Token usage not available</span>';
        }

        // Add a subtle animation to indicate the update
        messageElement.style.animation = 'none';
        messageElement.offsetHeight; // Trigger reflow
        messageElement.style.animation = 'statusUpdate 0.5s ease-out';
    }
}

function getTitle(message) {
    const content = message.response_data?.content;
    if (content && content.includes("isNewTopic")) {
        // content may be json surrounding with ```json{real conten}```
        // should strip code block
        // Strip any surrounding code block markup
        const stripped = content.replace(/```json\s*([\s\S]*?)\s*```/g, '$1').trim();

        try {
            const contentObj = JSON.parse(stripped);
            if (contentObj && contentObj["title"]) {
                return contentObj["title"]
            }
        } catch (e) {
            console.warn("Failed to parse content as {} JSON as title:", content, e);
            return null;
        }
    }
    return null;
}
function getStopReasonBadge(message) {
    // Get stop reason from response data
    const stopReason = message.response_data?.stop_reason;
    if (!stopReason) return '';

    const badgeConfig = {
        'end_turn': { icon: '🎯', label: 'Normal', class: 'stop-reason-end-turn' },
        'title': { icon: '', label: 'Title', class: 'stop-reason-end-turn' },
        'max_tokens': { icon: '📏', label: 'Max Tokens', class: 'stop-reason-max-tokens' },
        'tool_use': { icon: '🔧', label: 'Tool Use', class: 'stop-reason-tool-use' },
        'error': { icon: '❌', label: 'Error', class: 'stop-reason-error' }
    };

    let config = badgeConfig[stopReason] || { icon: '❓', label: 'Unknown', class: 'stop-reason-error' };
    const title = getTitle(message)
    if (title) {
        config = { icon: '🎯', label: 'New Topic', class: 'stop-reason-title' };
    }



    return `<span class="stop-reason-badge ${config.class}" title="Stop reason: ${config.label}">
                ${config.icon} ${config.label}
            </span>`;
}


function getMessageTypeInfo(message) {
    const stopReason = message.response_data?.stop_reason;
    if (!stopReason) return '';

    const typeDescriptions = {
        'end_turn': 'Conversation completed naturally',
        'max_tokens': 'Response reached maximum token limit',
        'tool_use': 'Response included function/tool calls',
        'error': 'Request encountered an error'
    };

    const description = typeDescriptions[stopReason] || 'Unknown completion type';

    // Extract tool name when stop_reason is tool_use
    var toolInfo = '';
    if (stopReason === 'tool_use' || message.response_data?.tool_calls && Object.keys(message.response_data?.tool_calls).length > 0) {
        const toolCalls = message.response_data.tool_calls;

        let toolName = "null";
        if (toolCalls != null) {
            const firstToolKey = Object.keys(toolCalls)[0];
            if (firstToolKey && toolCalls[firstToolKey]?.name) {
                toolName = toolCalls[firstToolKey].name;
            }
        }
        toolInfo = `<div class="message-type-indicator" style="margin-top: 4px;">
                            <span>Tool:</span>
                            <span style="font-weight: 500; color: #4facfe;">${toolName}</span>
                    </div>`;
    } else if (stopReason === 'end_turn' && message.response_data?.tool_calls) {
        const content = message.response_data.content;

        if (content && content.includes("isNewTopic")) {
            const title = getTitle(message);
            if (title) {
                toolInfo = `<div class="message-type-indicator" style="margin-top: 4px;">
                            <span>Title:</span>
                            <span style="font-weight: 500; color: #FFA500;">${title}</span>
                        </div>`;
            }
        }

    }

    return `<div class="message-type-indicator">
                <span>Type:</span>
                <span>${description}</span>
            </div>${toolInfo}`;
}

function showNewMessageNotification(count) {
    // Create a temporary notification
    const notification = document.createElement('div');
    notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: #4facfe;
                color: white;
                padding: 10px 15px;
                border-radius: 5px;
                z-index: 1000;
                font-size: 14px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            `;
    notification.textContent = `${count} new message${count > 1 ? 's' : ''} added`;

    document.body.appendChild(notification);

    // Remove notification after 3 seconds
    setTimeout(() => {
        document.body.removeChild(notification);
    }, 3000);
}

async function loadSummaryData() {
    try {
        // Get date range values from inputs if they exist
        const startDate = document.getElementById('startDate')?.value || null;
        const endDate = document.getElementById('endDate')?.value || null;

        // Build query string with date parameters if they exist
        let summaryUrl = `${baseUrl}/api/summary`;
        const params = new URLSearchParams();
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);
        if (params.toString()) summaryUrl += `?${params.toString()}`;

        // Fetch both summary and credits data in parallel
        const [summaryResponse, creditsResponse] = await Promise.all([
            fetch(summaryUrl),
            fetch(`${baseUrl}/api/credits`)
        ]);

        if (!summaryResponse.ok) {
            throw new Error(`Summary HTTP ${summaryResponse.status}: ${summaryResponse.statusText}`);
        }
        if (!creditsResponse.ok) {
            console.warn(`Credits fetch failed: ${creditsResponse.status}`);
        }

        const summaryDataJson = await summaryResponse.json();
        let creditsData = null;

        // Only parse credits if response is OK and contains data
        if (creditsResponse.ok) {
            const creditsJson = await creditsResponse.json();
            if (creditsJson.status === 'success' && creditsJson.data) {
                creditsData = creditsJson.data;
            }
        }

        summaryData = summaryDataJson.data;
        updateSummaryDisplay(creditsData);
        updateCurrentFilterDisplay(startDate, endDate);

    } catch (error) {
        console.error('Failed to load summary data:', error);
        document.getElementById('summaryOverview').innerHTML =
            '<div style="text-align: center; padding: 30px; color: #dc3545;">Failed to load usage summary</div>';
    }
}

function updateSummaryDisplay(creditsData = null) {
    if (!summaryData) return;

    const overview = document.getElementById('summaryOverview');
    const modelDetails = document.getElementById('modelDetails');

    // Update overview statistics
    const totals = summaryData.totals;

    let creditsCard = '';
    if (creditsData && creditsData.total !== undefined) {
        const usageAmount = creditsData.usage || 0;
        const totalAmount = creditsData.total || 0;
        const remaining = Math.max(0, totalAmount - usageAmount);
        const usagePercent = totalAmount > 0 ? (usageAmount / totalAmount) * 100 : 0;

        creditsCard = `
                    <div class="overview-card">
                        <h3>Credits</h3>
                        <div class="value">$${usageAmount.toFixed(2)}</div>
                        <div class="label">used of $${totalAmount.toFixed(2)}</div>
                        <div style="margin-top: 10px; background: #e2e8f0; height: 6px; border-radius: 3px; overflow: hidden;">
                            <div style="background: linear-gradient(90deg, #4facfe, #00f2fe); width: ${Math.min(100, usagePercent)}%; height: 100%; border-radius: 3px;"></div>
                        </div>
                        <div style="margin-top: 5px; font-size: 0.7em; color: #28a745;">
                            $${remaining.toFixed(2)} remaining
                        </div>
                    </div>
                `;
    }

    overview.innerHTML = `
                <div class="overview-grid">
                    <div class="overview-card">
                        <h3>Total Requests</h3>
                        <div class="value">${totals.total_requests.toLocaleString()}</div>
                        <div class="label">API calls made</div>
                    </div>
                    <div class="overview-card">
                        <h3>Input Tokens</h3>
                        <div class="value">${totals.total_input_tokens.toLocaleString()}</div>
                        <div class="label">Tokens consumed</div>
                    </div>
                    <div class="overview-card">
                        <h3>Output Tokens</h3>
                        <div class="value">${totals.total_output_tokens.toLocaleString()}</div>
                        <div class="label">Tokens generated</div>
                    </div>
                    <div class="overview-card">
                        <h3>Total Tokens</h3>
                        <div class="value">${totals.total_tokens.toLocaleString()}</div>
                        <div class="label">Combined usage</div>
                    </div>
                    <div class="overview-card">
                        <h3>Success Rate</h3>
                        <div class="value">${totals.overall_success_rate}%</div>
                        <div class="label">${totals.total_completed} completed</div>
                    </div>
                    ${creditsCard}
                </div>
            `;

    // Update model details
    if (summaryData.by_model.length === 0) {
        modelDetails.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">📊</div>
                        <h3>No Usage Data Yet</h3>
                        <p>Make some API requests to see detailed usage statistics by model.</p>
                    </div>
                `;
        return;
    }

    let modelsHtml = '';
    summaryData.by_model.forEach(model => {
        const tokenRatio = model.total_tokens > 0 ?
            ((model.total_input_tokens / model.total_tokens) * 100).toFixed(1) : 0;
        const lastUsed = model.last_request ?
            new Date(model.last_request).toLocaleString() : 'Never';

        modelsHtml += `
                    <div class="model-card">
                        <div class="model-header">
                            <span>${model.model}</span>
                            <span>${model.success_rate}% success</span>
                        </div>
                        <div class="model-body">
                            <div class="model-stats">
                                <div class="stat-item">
                                    <div class="stat-value">${model.request_count}</div>
                                    <div class="stat-label">Requests</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-value">${model.total_input_tokens.toLocaleString()}</div>
                                    <div class="stat-label">Input</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-value">${model.total_output_tokens.toLocaleString()}</div>
                                    <div class="stat-label">Output</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-value">${model.total_tokens.toLocaleString()}</div>
                                    <div class="stat-label">Total</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-value">${model.avg_input_tokens}</div>
                                    <div class="stat-label">Avg Input</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-value">${model.avg_output_tokens}</div>
                                    <div class="stat-label">Avg Output</div>
                                </div>
                            </div>
                            <div class="success-rate">
                                <span>✅ ${model.completed_requests} completed</span>
                                ${model.partial_requests > 0 ? `<span>⚠️ ${model.partial_requests} partial</span>` : ''}
                                ${model.pending_requests > 0 ? `<span>⏳ ${model.pending_requests} pending</span>` : ''}
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${model.success_rate}%"></div>
                            </div>
                            <div style="margin-top: 10px; font-size: 0.8em; color: #718096;">
                                Last used: ${lastUsed}
                            </div>
                        </div>
                    </div>
                `;
    });

    modelDetails.innerHTML = modelsHtml;
}

function restoreExpandedMessageStates() {
    // Restore expanded states and content after DOM rebuild
    if (expandedMessageIds.size === 0) return;

    messageHistory.forEach((message) => {
        if (expandedMessageIds.has(message.id)) {
            const contentEl = document.getElementById(`message-content-${message.id}`);
            if (contentEl && !contentEl.classList.contains('expanded')) {
                contentEl.classList.add('expanded');

                // Restore the correct content tab and JSON data
                if (currentlyViewingContent && currentlyViewingContent.messageId === message.id) {
                    const contentType = currentlyViewingContent.contentType || 'request';
                    showJsonContent(message.id, contentType);
                } else {
                    showJsonContent(message.id, 'request');
                }
            }
        }
    });
}

function updateExistingMessages() {
    // Update each message in the message history
    messageHistory.forEach(message => {
        // Find the message element by message ID
        const messageElement = document.querySelector(`.message-item[data-message-id="${message.id}"]`);
        if (!messageElement) return;

        // Update status badge and stop reason badge
        const modelSpan = messageElement.querySelector('.message-model');
        if (modelSpan) {
            const statusBadge = message.status === 'completed' ?
                '<span style="color: #28a745;">✓</span>' :
                message.status === 'partial' ?
                    '<span style="color: #ffc107;">⚠</span>' :
                    '<span style="color: #ffc107;">⏳</span>';

            const stopReasonBadge = getStopReasonBadge(message);
            modelSpan.innerHTML = `${message.model_name} → ${message.actual_model} ${statusBadge}${stopReasonBadge}`;
        }

        // Update message details
        const detailsDiv = messageElement.querySelector('.message-details');
        if (detailsDiv) {
            const requestLength = message.request_length || 0;
            const responseLength = message.response_length || 0;
            const messageTypeInfo = getMessageTypeInfo(message);

            detailsDiv.innerHTML = `
                        Request: ${requestLength} chars | Response: ${responseLength} chars
                        ${message.is_streaming ? ' | Streaming' : ''}
                        ${messageTypeInfo}
                    `;
        }

        // Update token information
        const tokensDiv = messageElement.querySelector('.message-tokens');
        if (tokensDiv) {
            tokensDiv.innerHTML = message.total_tokens > 0 ?
                `<span class="token-info">📊 Input: ${message.input_tokens} | Output: ${message.output_tokens} | Total: ${message.total_tokens}</span>` :
                '<span class="token-info-empty">📊 Token usage not available</span>';
        }

        // Update JSON content if this message is currently expanded
        if (expandedMessageIds.has(message.id) && currentlyViewingContent && currentlyViewingContent.messageId === message.id) {
            const jsonContentEl = document.getElementById(`json-content-${message.id}`);
            if (jsonContentEl) {
                const contentType = currentlyViewingContent.contentType || 'request';
                const content = contentType === 'request' ? message.request_data : message.response_data;
                jsonContentEl.textContent = JSON.stringify(content, null, 2);
            }
        }
    });
}
function applyDateFilter() {
    const startDate = document.getElementById('startDate').value;
    const endDate = document.getElementById('endDate').value;

    // Update current filter
    currentDateFilter.startDate = startDate || null;
    currentDateFilter.endDate = endDate || null;

    // Reload summary data with new filter
    loadSummaryData();
}

function clearDateFilter() {
    // Clear input fields
    document.getElementById('startDate').value = '';
    document.getElementById('endDate').value = '';

    // Reset current filter
    currentDateFilter.startDate = null;
    currentDateFilter.endDate = null;

    // Reload summary data without filter
    loadSummaryData();
}

function updateCurrentFilterDisplay(startDate, endDate) {
    const filterDisplay = document.getElementById('current-filter');

    if (startDate && endDate) {
        filterDisplay.textContent = `Showing data from ${startDate} to ${endDate}`;
    } else if (startDate) {
        filterDisplay.textContent = `Showing data from ${startDate} onwards`;
    } else if (endDate) {
        filterDisplay.textContent = `Showing data up to ${endDate}`;
    } else {
        filterDisplay.textContent = 'Showing all data';
    }
}

function setDateRange(range) {
    const today = new Date();
    let startDate = null;
    let endDate = null;

    // Helper function to get local date string in YYYY-MM-DD format
    const getLocalDateString = (date) => {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    };

    switch (range) {
        case 'today':
            startDate = getLocalDateString(today);
            endDate = getLocalDateString(today);
            break;

        case 'yesterday':
            const yesterday = new Date(today);
            yesterday.setDate(yesterday.getDate() - 1);
            startDate = getLocalDateString(yesterday);
            endDate = getLocalDateString(yesterday);
            break;

        case 'last7':
            const last7 = new Date(today);
            last7.setDate(last7.getDate() - 6); // 7 days including today
            startDate = getLocalDateString(last7);
            endDate = getLocalDateString(today);
            break;

        case 'last30':
            const last30 = new Date(today);
            last30.setDate(last30.getDate() - 29); // 30 days including today
            startDate = getLocalDateString(last30);
            endDate = getLocalDateString(today);
            break;

        case 'thisMonth':
            startDate = getLocalDateString(new Date(today.getFullYear(), today.getMonth(), 1));
            endDate = getLocalDateString(today);
            break;

        case 'lastMonth':
            const firstDayLastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
            const lastDayLastMonth = new Date(today.getFullYear(), today.getMonth(), 0);
            startDate = getLocalDateString(firstDayLastMonth);
            endDate = getLocalDateString(lastDayLastMonth);
            break;
    }

    // Set date inputs
    document.getElementById('startDate').value = startDate;
    document.getElementById('endDate').value = endDate;

    // Apply the filter
    applyDateFilter();
}

// Export functions
function exportHistoryData() {
    if (window.proxyManager && window.proxyManager.isConnected) {
        window.proxyManager.exportData('history').catch(error => {
            showMessage(`Export failed: ${error.message}`, 'error');
        });
    } else {
        showMessage('Please connect to the proxy first', 'error');
    }
}

function exportSummaryData() {
    if (window.proxyManager && window.proxyManager.isConnected) {
        window.proxyManager.exportData('summary').catch(error => {
            showMessage(`Export failed: ${error.message}`, 'error');
        });
    } else {
        showMessage('Please connect to the proxy first', 'error');
    }
}

function exportConfigData() {
    if (window.proxyManager && window.proxyManager.isConnected) {
        window.proxyManager.exportData('config').catch(error => {
            showMessage(`Export failed: ${error.message}`, 'error');
        });
    } else {
        showMessage('Please connect to the proxy first', 'error');
    }
}

// Dual-mode history navigation functions
function toggleHistoryMode() {
    const toggle = document.getElementById('historyModeToggle');
    historyMode = toggle.checked ? 'datetime' : 'live';

    if (historyMode === 'live') {
        // Switch to live mode
        document.getElementById('liveModeIndicator').style.display = 'flex';
        document.getElementById('dateTimeNavigation').style.display = 'none';
        document.getElementById('liveUpdateIndicator').style.display = 'flex';

        // Start live updates
        startHistoryLiveUpdates();
        clearHistoryFilters();
        loadHistoryData();
    } else {
        // Switch to date/time mode
        document.getElementById('liveModeIndicator').style.display = 'none';
        document.getElementById('dateTimeNavigation').style.display = 'block';
        document.getElementById('liveUpdateIndicator').style.display = 'none';

        // Stop live updates
        stopHistoryLiveUpdates();

        // Load with current filters
        loadHistoryWithFilters();
    }
}

function startHistoryLiveUpdates() {
    if (historyLiveInterval) clearInterval(historyLiveInterval);

    historyLiveInterval = setInterval(() => {
        if (historyMode === 'live' && baseUrl) {
            loadNewHistoryMessages();
        }
    }, 5000); // Check for new messages every 5 seconds
}

function stopHistoryLiveUpdates() {
    if (historyLiveInterval) {
        clearInterval(historyLiveInterval);
        historyLiveInterval = null;
    }
}

function navigateHistoryPrevDay() {
    navigateDateByOffset(-1);
}

function navigateHistoryNextDay() {
    navigateDateByOffset(1);
}

function navigateHistoryPrevHour() {
    navigateHourByOffset(-1);
}

function navigateHistoryNextHour() {
    navigateHourByOffset(1);
}

function navigateDateByOffset(days) {
    const dateInput = document.getElementById('historyDate');
    if (!dateInput.value) {
        dateInput.value = new Date().toISOString().split('T')[0];
    }

    const currentDate = new Date(dateInput.value);
    currentDate.setDate(currentDate.getDate() + days);
    dateInput.value = currentDate.toISOString().split('T')[0];

    historyFilters.date = dateInput.value;
    loadHistoryWithFilters();
}

function navigateHourByOffset(hours) {
    const hourSelect = document.getElementById('historyHour');
    const dateInput = document.getElementById('historyDate');

    if (!dateInput.value) {
        dateInput.value = new Date().toISOString().split('T')[0];
        historyFilters.date = dateInput.value;
    }

    let currentHour = parseInt(hourSelect.value || '0');

    // Handle day boundaries
    if (hours > 0 && currentHour === 23) {
        currentHour = 0;
        navigateDateByOffset(1);
    } else if (hours < 0 && currentHour === 0) {
        currentHour = 23;
        navigateDateByOffset(-1);
    } else {
        currentHour = (currentHour + hours + 24) % 24;
        hourSelect.value = currentHour.toString();
        historyFilters.hour = currentHour;
        loadHistoryWithFilters();
    }
}

function navigateHistoryByDate() {
    const dateInput = document.getElementById('historyDate');
    historyFilters.date = dateInput.value || null;
    loadHistoryWithFilters();
}

function navigateHistoryByHour() {
    const hourSelect = document.getElementById('historyHour');
    historyFilters.hour = hourSelect.value ? parseInt(hourSelect.value) : null;
    loadHistoryWithFilters();
}

function loadTodayHistory() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('historyDate').value = today;
    historyFilters.date = today;
    historyFilters.hour = null;
    document.getElementById('historyHour').value = '';
    loadHistoryWithFilters();
}

function loadYesterdayHistory() {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const yesterdayStr = yesterday.toISOString().split('T')[0];
    document.getElementById('historyDate').value = yesterdayStr;
    historyFilters.date = yesterdayStr;
    historyFilters.hour = null;
    document.getElementById('historyHour').value = '';
    loadHistoryWithFilters();
}

function clearHistoryFilters() {
    historyFilters.date = null;
    historyFilters.hour = null;
    document.getElementById('historyDate').value = '';
    document.getElementById('historyHour').value = '';
    loadHistoryWithFilters();
}

function updateHistoryLimit() {
    const limitSelect = document.getElementById('historyLimit');
    historyFilters.limit = parseInt(limitSelect.value);
    loadHistoryWithFilters();
}

async function loadHistoryWithFilters() {
    if (historyMode !== 'datetime') return;

    try {
        showLoading();
        const params = new URLSearchParams();
        params.append('limit', historyFilters.limit.toString());

        if (historyFilters.date) {
            params.append('date', historyFilters.date);
        }
        if (historyFilters.hour !== null) {
            params.append('hour', historyFilters.hour.toString());
        }

        const response = await fetch(`${baseUrl}/api/history?${params.toString()}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        messageHistory = data.data.messages;
        updateHistoryDisplay();
        updateHistoryFilterDisplay();
    } catch (error) {
        console.error('Error loading history with filters:', error);
        document.getElementById('messageList').innerHTML =
            '<div style="text-align: center; padding: 30px; color: #dc3545;">Failed to load message history</div>';
    }
}

function showLoading() {
    const messageList = document.getElementById('messageList');
    messageList.innerHTML = `
                <div style="text-align: center; padding: 30px; color: #6c757d;">
                    <div class="loading" style="margin-bottom: 20px;"></div>
                    <p>Loading message history...</p>
                </div>
            `;
}

function updateHistoryFilterDisplay() {
    const filterDisplay = document.getElementById('currentHistoryFilter');
    let message = '';

    if (historyFilters.date && historyFilters.hour !== null) {
        message = `Showing messages for ${historyFilters.date} at ${historyFilters.hour.toString().padStart(2, '0')}:00`;
    } else if (historyFilters.date) {
        message = `Showing messages for ${historyFilters.date}`;
    } else if (historyFilters.hour !== null) {
        message = `Showing messages at ${historyFilters.hour.toString().padStart(2, '0')}:00 across all dates`;
    } else {
        message = 'Showing all messages';
    }

    if (historyMode === 'datetime') {
        message += ` (Latest ${historyFilters.limit})`;
    }

    filterDisplay.textContent = message;
}

// Override the original loadHistoryData to support both modes
async function loadHistoryData() {
    const limit = historyFilters.limit;

    try {
        if (historyMode === 'live') {
            // Live mode - load recent messages and enable real-time updates
            const response = await fetch(`${baseUrl}/api/history?limit=${limit}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            messageHistory = data.data.messages;
            if (messageHistory.length > 0) {
                lastMessageId = Math.max(...messageHistory.map(m => m.id));
            }
            updateHistoryDisplay();
            if (isFirstHistoryLoad) {
                startHistoryLiveUpdates();
                isFirstHistoryLoad = false;
            }
        } else {
            // Date-Time mode - use filters
            await loadHistoryWithFilters();
        }
    } catch (error) {
        console.error('Failed to load history data:', error);
        document.getElementById('messageList').innerHTML =
            '<div style="text-align: center; padding: 30px; color: #dc3545;">Failed to load message history</div>';
    }
}

// Override original loadNewHistoryMessages to work only in live mode
async function loadNewHistoryMessages() {
    if (historyMode !== 'live') return;

    try {
        const response = await fetch(`${baseUrl}/api/history?limit=${historyFilters.limit}`);
        if (!response.ok) return;

        const data = await response.json();
        const allMessages = data.data.messages;
        const newMessages = allMessages.filter(msg => msg.id > lastMessageId);

        // Handle new messages in live mode
        if (newMessages.length > 0) {
            messageHistory = [...newMessages, ...messageHistory];

            // Keep only the most recent messages
            if (messageHistory.length > historyFilters.limit) {
                messageHistory = messageHistory.slice(0, historyFilters.limit);
                const remainingIds = new Set(messageHistory.map(m => m.id));
                expandedMessageIds = new Set([...expandedMessageIds].filter(id => remainingIds.has(id)));

                if (currentlyViewingContent && !remainingIds.has(currentlyViewingContent.messageId)) {
                    currentlyViewingContent = null;
                }
            }

            lastMessageId = Math.max(...messageHistory.map(m => m.id));
            updateHistoryDisplay();
            showNewMessageNotification(newMessages.length);
        }
    } catch (error) {
        console.warn('Failed to load new history messages:', error);
    }
}

// Clean up when tab changes
function switchHistoryTab() {
    // Reset state when switching to history tab
    if (currentTab === 'history' && baseUrl) {
        if (isFirstHistoryLoad) {
            loadHistoryData();
        }

        // Set default date to today
        document.getElementById('historyDate').value = new Date().toISOString().split('T')[0];
    }
}

// Update the switchTab function to handle history tab initialization
const originalSwitchTab = switchTab;



function start_app() {
    window.switchTab = function (tabName) {
        originalSwitchTab.call(this, tabName);
        switchHistoryTab();
    };
}
if (typeof module !== 'undefined' && module.exports) {
    //export all functions
    // Get all function names by filtering global scope
    const functionNames = Object.keys(global).filter(key => {
        return typeof global[key] === 'function' &&
            global[key].toString().includes('function');
    });

    // Create exports object dynamically
    const exports = {};
    functionNames.forEach(name => {
        exports[name] = global[name];
    });

    module.exports = exports;
    module.exports.default = exports;
}