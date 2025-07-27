class ProxyManager {
    constructor() {
        this.baseUrl = '';
        this.websocket = null;
        this.isConnected = false;
        this.retryCount = 0;
        this.maxRetries = 5;
    }

    // Enhanced connection with retry logic
    async connectWithRetry(port) {
        this.baseUrl = `http://localhost:${port}`;
        
        const connect = async () => {
            try {
                const response = await fetch(`${this.baseUrl}/health`);
                if (response.ok) {
                    this.isConnected = true;
                    this.retryCount = 0;
                    this.setupWebSocket();
                    return true;
                } else {
                    throw new Error(`Health check failed: ${response.status}`);
                }
            } catch (error) {
                console.warn(`Connection attempt ${this.retryCount + 1} failed:`, error);
                this.retryCount++;
                
                if (this.retryCount < this.maxRetries) {
                    // Exponential backoff: 1s, 2s, 4s, 8s, 16s
                    const delay = Math.pow(2, this.retryCount) * 1000;
                    await new Promise(resolve => setTimeout(resolve, delay));
                    return connect();
                } else {
                    throw new Error(`Failed to connect after ${this.maxRetries} attempts`);
                }
            }
        };
        
        return connect();
    }

    // WebSocket connection for real-time updates
    setupWebSocket() {
        if (this.websocket) {
            this.websocket.close();
        }
        
        // Update UI to show connecting status
        this.updateWebSocketStatus('connecting');
        
        const wsPort = new URL(this.baseUrl).port;
        this.websocket = new WebSocket(`ws://localhost:${wsPort}/ws`);
        
        this.websocket.onopen = () => {
            console.log('WebSocket connected for real-time updates');
            this.updateWebSocketStatus('connected');
            this.showNotification('Real-time updates connected', 'success');
        };
        
        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };
        
        this.websocket.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateWebSocketStatus('disconnected');
            this.showNotification('Real-time updates disconnected', 'info');
            
            // Attempt to reconnect after 5 seconds
            setTimeout(() => {
                if (this.isConnected) {
                    this.setupWebSocket();
                }
            }, 5000);
        };
        
        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateWebSocketStatus('disconnected');
            this.showNotification('Real-time updates error', 'error');
        };
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'model_update':
                this.updateModelStatus(data.payload);
                break;
            case 'health_update':
                this.updateHealthStatus(data.payload);
                break;
            case 'history_update':
                this.updateMessageHistory(data.payload);
                break;
            default:
                console.log('Unknown WebSocket message type:', data.type);
        }
    }

    // Update WebSocket status indicator in UI
    updateWebSocketStatus(status) {
        const wsStatusElement = document.getElementById('websocketStatus');
        const wsStatusIndicator = document.getElementById('websocketStatusIndicator');
        
        if (wsStatusElement && wsStatusIndicator) {
            wsStatusElement.className = `websocket-status ${status}`;
            wsStatusIndicator.textContent = status.charAt(0).toUpperCase() + status.slice(1);
            
            switch (status) {
                case 'connected':
                    wsStatusElement.textContent = 'WS Connected';
                    break;
                case 'disconnected':
                    wsStatusElement.textContent = 'WS Disconnected';
                    break;
                case 'connecting':
                    wsStatusElement.textContent = 'WS Connecting';
                    break;
            }
        }
    }

    // Update performance indicators
    updatePerformanceIndicators(requestCount, avgResponseTime) {
        const requestCountElement = document.getElementById('requestCount');
        const avgResponseTimeElement = document.getElementById('avgResponseTime');
        const perfIndicator = document.getElementById('performanceIndicator');
        
        if (requestCountElement && avgResponseTimeElement && perfIndicator) {
            requestCountElement.textContent = requestCount;
            avgResponseTimeElement.textContent = `${avgResponseTime}ms`;
            perfIndicator.classList.add('visible');
        }
    }

    // Show notification
    showNotification(message, type = 'info', duration = 3000) {
        const container = document.getElementById('notificationContainer');
        if (!container) return;
        
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        container.appendChild(notification);
        
        // Trigger reflow and show
        notification.offsetHeight;
        notification.classList.add('show');
        
        // Auto remove after duration
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, duration);
    }

    updateModelStatus(payload) {
        // Update model status in the UI
        const modelElement = document.getElementById(`${payload.model_type}_${payload.model_name}`);
        if (modelElement) {
            modelElement.checked = true;
            // Trigger change event to update the UI
            modelElement.dispatchEvent(new Event('change'));
        }
    }

    updateHealthStatus(payload) {
        // Update health indicators in the UI
        const healthElement = document.getElementById('healthStatus');
        if (healthElement) {
            // This would call the existing updateHealthDisplay function
            if (typeof updateHealthDisplay === 'function') {
                updateHealthDisplay(payload);
            }
        }
    }

    updateMessageHistory(payload) {
        // Update message history with new data
        if (typeof appendNewMessages === 'function') {
            appendNewMessages([payload]);
        }
    }

    // Enhanced logging with different levels
    log(level, message) {
        const timestamp = new Date().toISOString();
        const logEntry = `[${timestamp}] ${level.toUpperCase()}: ${message}`;
        
        // Add to browser console
        switch (level) {
            case 'error':
                console.error(logEntry);
                break;
            case 'warn':
                console.warn(logEntry);
                break;
            case 'info':
                console.info(logEntry);
                break;
            default:
                console.log(logEntry);
        }
        
        // Add to UI logs if element exists
        const logsContent = document.getElementById('logsContent');
        if (logsContent) {
            const logDiv = document.createElement('div');
            logDiv.className = 'log-entry';
            logDiv.innerHTML = `<span class="log-timestamp">[${new Date().toLocaleTimeString()}]</span> ${message}`;
            
            // Add level-specific styling
            if (level === 'error') {
                logDiv.style.borderLeftColor = '#dc3545';
                logDiv.style.backgroundColor = 'rgba(220, 53, 69, 0.1)';
            } else if (level === 'warn') {
                logDiv.style.borderLeftColor = '#ffc107';
                logDiv.style.backgroundColor = 'rgba(255, 193, 7, 0.1)';
            } else if (level === 'info') {
                logDiv.style.borderLeftColor = '#17a2b8';
                logDiv.style.backgroundColor = 'rgba(23, 162, 184, 0.1)';
            }
            
            logsContent.appendChild(logDiv);
            logsContent.scrollTop = logsContent.scrollHeight;
        }
    }

    // Export data functionality
    async exportData(dataType, format = 'json') {
        try {
            // Show export progress
            this.showExportProgress(true);
            
            let data;
            let filename;
            
            // Helper function to get local date string in YYYY-MM-DD format
            const getLocalDateString = () => {
                const date = new Date();
                const year = date.getFullYear();
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const day = String(date.getDate()).padStart(2, '0');
                return `${year}-${month}-${day}`;
            };
            
            switch (dataType) {
                case 'history':
                    const historyResponse = await fetch(`${this.baseUrl}/api/history?limit=1000`);
                    data = await historyResponse.json();
                    filename = `proxy-history-${getLocalDateString()}.${format}`;
                    break;
                    
                case 'summary':
                    const summaryResponse = await fetch(`${this.baseUrl}/api/summary`);
                    data = await summaryResponse.json();
                    filename = `proxy-summary-${getLocalDateString()}.${format}`;
                    break;
                    
                case 'config':
                    const configResponse = await fetch(`${this.baseUrl}/api/config/get`);
                    data = await configResponse.json();
                    filename = `proxy-config-${getLocalDateString()}.${format}`;
                    break;
                    
                default:
                    throw new Error(`Unsupported data type: ${dataType}`);
            }
            
            if (format === 'csv') {
                const csvContent = this.convertToCSV(data);
                this.downloadFile(csvContent, filename, 'text/csv');
            } else {
                const jsonContent = JSON.stringify(data, null, 2);
                this.downloadFile(jsonContent, filename, 'application/json');
            }
            
            // Hide export progress
            this.showExportProgress(false);
            
            this.log('info', `Exported ${dataType} data as ${format.toUpperCase()}`);
            this.showNotification(`Exported ${dataType} data successfully`, 'success');
        } catch (error) {
            // Hide export progress
            this.showExportProgress(false);
            
            this.log('error', `Failed to export ${dataType} data: ${error.message}`);
            this.showNotification(`Export failed: ${error.message}`, 'error');
            throw error;
        }
    }

    // Show/hide export progress indicator
    showExportProgress(show) {
        const exportButtons = document.querySelectorAll('[id^="export"]');
        const progressIndicator = document.querySelector('.export-progress');
        
        exportButtons.forEach(button => {
            if (show) {
                button.disabled = true;
                button.classList.add('disabled');
            } else {
                button.disabled = false;
                button.classList.remove('disabled');
            }
        });
        
        if (progressIndicator) {
            if (show) {
                progressIndicator.classList.add('visible');
            } else {
                progressIndicator.classList.remove('visible');
            }
        }
    }

    convertToCSV(objArray) {
        // Simple CSV conversion - can be enhanced based on specific data structure
        const array = typeof objArray !== 'object' ? JSON.parse(objArray) : objArray;
        let str = '';
        
        // Add headers (assuming first object has all keys)
        if (array.data && array.data.length > 0) {
            const headers = Object.keys(array.data[0]);
            str += headers.join(',') + '\n';
            
            // Add data rows
            for (let i = 0; i < array.data.length; i++) {
                let line = '';
                for (let index in headers) {
                    if (line !== '') line += ',';
                    line += `"${array.data[i][headers[index]]}"`;
                }
                str += line + '\n';
            }
        }
        
        return str;
    }

    downloadFile(content, filename, contentType) {
        const blob = new Blob([content], { type: contentType });
        const url = window.URL.createObjectURL(blob);
        
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.style.display = 'none';
        
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        window.URL.revokeObjectURL(url);
    }

    // Bulk model operations
    async updateMultipleModels(modelUpdates) {
        try {
            const results = [];
            
            for (const [modelType, modelName] of Object.entries(modelUpdates)) {
                try {
                    const response = await fetch(`${this.baseUrl}/api/config/update`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ [modelType]: modelName })
                    });
                    
                    if (!response.ok) {
                        throw new Error(`Failed to update ${modelType}: ${response.statusText}`);
                    }
                    
                    const result = await response.json();
                    results.push({ modelType, modelName, success: true, result });
                    this.log('info', `Updated ${modelType} to ${modelName}`);
                    
                } catch (error) {
                    results.push({ modelType, modelName, success: false, error: error.message });
                    this.log('error', `Failed to update ${modelType}: ${error.message}`);
                }
            }
            
            return results;
        } catch (error) {
            this.log('error', `Bulk model update failed: ${error.message}`);
            throw error;
        }
    }

    // Performance monitoring
    monitorPerformance() {
        let requestCount = 0;
        let totalResponseTime = 0;
        
        // Monitor API response times
        const originalFetch = window.fetch;
        window.fetch = async (...args) => {
            const start = performance.now();
            try {
                const response = await originalFetch(...args);
                const end = performance.now();
                const duration = end - start;
                
                // Update performance metrics
                requestCount++;
                totalResponseTime += duration;
                const avgResponseTime = Math.round(totalResponseTime / requestCount);
                
                // Update UI indicators
                this.updatePerformanceIndicators(requestCount, avgResponseTime);
                
                // Log slow requests (>1000ms)
                if (duration > 1000) {
                    this.log('warn', `Slow request: ${args[0]} took ${duration.toFixed(2)}ms`);
                }
                
                return response;
            } catch (error) {
                const end = performance.now();
                const duration = end - start;
                this.log('error', `Request failed: ${args[0]} took ${duration.toFixed(2)}ms - ${error.message}`);
                throw error;
            }
        };
    }

    // Cleanup resources
    disconnect() {
        this.isConnected = false;
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
        
        // Update UI indicators
        this.updateWebSocketStatus('disconnected');
        
        // Hide performance indicator
        const perfIndicator = document.getElementById('performanceIndicator');
        if (perfIndicator) {
            perfIndicator.classList.remove('visible');
        }
    }
}

// Utility functions
const utils = {
    // Format bytes to human-readable format
    formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    },

    // Format time duration
    formatDuration(ms) {
        const seconds = Math.floor(ms / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        
        if (hours > 0) {
            return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
        } else if (minutes > 0) {
            return `${minutes}m ${seconds % 60}s`;
        } else {
            return `${seconds}s`;
        }
    },

    // Debounce function to limit rate of execution
    debounce(func, wait, immediate) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                timeout = null;
                if (!immediate) func.apply(this, args);
            };
            const callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func.apply(this, args);
        };
    },

    // Generate UUID
    generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }
};

// Initialize the proxy manager when the page loads
document.addEventListener('DOMContentLoaded', () => {
    // Make ProxyManager globally available
    window.proxyManager = new ProxyManager();
    
    // Start performance monitoring
    window.proxyManager.monitorPerformance();
    
    // Add event listeners for export buttons if they exist
    const exportHistoryBtn = document.getElementById('exportHistory');
    if (exportHistoryBtn) {
        exportHistoryBtn.addEventListener('click', () => {
            window.proxyManager.exportData('history');
        });
    }
    
    const exportSummaryBtn = document.getElementById('exportSummary');
    if (exportSummaryBtn) {
        exportSummaryBtn.addEventListener('click', () => {
            window.proxyManager.exportData('summary');
        });
    }
    
    const exportConfigBtn = document.getElementById('exportConfig');
    if (exportConfigBtn) {
        exportConfigBtn.addEventListener('click', () => {
            window.proxyManager.exportData('config');
        });
    }
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ProxyManager, utils };
}