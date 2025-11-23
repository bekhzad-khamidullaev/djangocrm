/**
 * Real-time Queue Monitor JavaScript
 * Provides live updates of call queues with WebSocket support
 */

class QueueMonitor {
    constructor(config) {
        this.config = config;
        this.refreshInterval = null;
        this.connectionStatus = 'disconnected';
        this.lastUpdateTime = null;
        this.queuesData = {};
        this.statsData = {};
        
        this.initializeElements();
        this.setupEventListeners();
    }
    
    initializeElements() {
        this.elements = {
            connectionStatus: document.getElementById('connectionStatus'),
            offlineIndicator: document.getElementById('offlineIndicator'),
            refreshIndicator: document.getElementById('refreshIndicator'),
            statsGrid: document.getElementById('statsGrid'),
            queuesContainer: document.getElementById('queuesContainer'),
            autoRefreshToggle: document.getElementById('autoRefresh')
        };
    }
    
    setupEventListeners() {
        // Auto-refresh toggle
        this.elements.autoRefreshToggle.addEventListener('change', (e) => {
            if (e.target.checked) {
                this.startAutoRefresh();
            } else {
                this.stopAutoRefresh();
            }
        });
        
        // Visibility change detection (pause when tab is hidden)
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.stopAutoRefresh();
            } else if (this.elements.autoRefreshToggle.checked) {
                this.startAutoRefresh();
            }
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey || e.metaKey) {
                switch(e.key) {
                    case 'r':
                        e.preventDefault();
                        this.refreshData();
                        break;
                    case 'a':
                        e.preventDefault();
                        this.elements.autoRefreshToggle.click();
                        break;
                }
            }
        });
    }
    
    async start() {
        this.updateConnectionStatus('connecting');
        await this.refreshData();
        
        if (this.elements.autoRefreshToggle.checked) {
            this.startAutoRefresh();
        }
    }
    
    startAutoRefresh() {
        this.stopAutoRefresh(); // Clear any existing interval
        
        this.refreshInterval = setInterval(async () => {
            try {
                await this.refreshData();
            } catch (error) {
                console.error('Auto-refresh failed:', error);
                this.updateConnectionStatus('disconnected');
            }
        }, this.config.refreshInterval);
    }
    
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }
    
    updateConnectionStatus(status) {
        this.connectionStatus = status;
        const statusElement = this.elements.connectionStatus;
        const offlineIndicator = this.elements.offlineIndicator;
        
        statusElement.className = `status-indicator status-${status}`;
        
        switch(status) {
            case 'connected':
                offlineIndicator.style.display = 'none';
                break;
            case 'disconnected':
                offlineIndicator.style.display = 'block';
                break;
            case 'connecting':
                offlineIndicator.style.display = 'none';
                break;
        }
    }
    
    async refreshData() {
        try {
            const [queuesResponse, statsResponse] = await Promise.all([
                fetch(this.config.apiEndpoints.queues),
                fetch(this.config.apiEndpoints.stats)
            ]);
            
            if (!queuesResponse.ok || !statsResponse.ok) {
                throw new Error('API request failed');
            }
            
            const queuesData = await queuesResponse.json();
            const statsData = await statsResponse.json();
            
            this.updateQueues(queuesData);
            this.updateStats(statsData);
            this.updateConnectionStatus('connected');
            this.showRefreshIndicator();
            
            this.lastUpdateTime = new Date();
            
        } catch (error) {
            console.error('Failed to refresh data:', error);
            this.updateConnectionStatus('disconnected');
            throw error;
        }
    }
    
    updateStats(data) {
        this.statsData = data;
        
        const stats = [
            {
                value: data.total_calls || 0,
                label: this.config.translations.totalCalls,
                color: '--primary-color'
            },
            {
                value: this.getTotalWaitingCalls(),
                label: this.config.translations.waitingCalls,
                color: '--warning-color'
            },
            {
                value: this.formatDuration(data.avg_wait_time || 0),
                label: this.config.translations.averageWait,
                color: '--info-color'
            },
            {
                value: this.getActiveAgentsCount(),
                label: this.config.translations.activeAgents,
                color: '--success-color'
            }
        ];
        
        this.elements.statsGrid.innerHTML = stats.map(stat => `
            <div class="stat-card" style="border-left-color: var(${stat.color});">
                <div class="stat-value">${stat.value}</div>
                <div class="stat-label">${stat.label}</div>
            </div>
        `).join('');
    }
    
    updateQueues(data) {
        const queues = data.queues || [];
        this.queuesData = data;
        
        if (queues.length === 0) {
            this.elements.queuesContainer.innerHTML = `
                <div class="empty-queue">
                    <h3>${this.config.translations.noCallsInQueue}</h3>
                </div>
            `;
            return;
        }
        
        this.elements.queuesContainer.innerHTML = queues.map(queue => 
            this.renderQueue(queue)
        ).join('');
    }
    
    renderQueue(queue) {
        const queueStatus = this.getQueueStatus(queue);
        const entries = queue.entries || [];
        
        return `
            <div class="queue-section" data-queue-id="${queue.group_id}">
                <div class="queue-header">
                    <h3 class="queue-title">${queue.group_name}</h3>
                    <span class="queue-status status-${queueStatus.type}">
                        ${queueStatus.label}
                    </span>
                </div>
                <div class="queue-body">
                    ${entries.length > 0 ? 
                        entries.map(entry => this.renderQueueEntry(entry)).join('') :
                        `<div class="empty-queue">
                            <p>${this.config.translations.noCallsInQueue}</p>
                        </div>`
                    }
                </div>
            </div>
        `;
    }
    
    renderQueueEntry(entry) {
        const waitTime = this.formatDuration(entry.wait_time);
        const estimatedWait = entry.estimated_wait ? 
            this.formatDuration(entry.estimated_wait) : '--';
        
        return `
            <div class="queue-entry" data-entry-id="${entry.id}">
                <div class="caller-info">
                    <div class="caller-number">${entry.caller_id}</div>
                    <div class="caller-time">
                        ${this.config.translations.position} ${entry.position} • 
                        Est. ${estimatedWait}
                    </div>
                </div>
                <span class="position-badge">#${entry.position}</span>
                <div class="wait-time">
                    <div class="wait-duration">${waitTime}</div>
                    <div class="wait-label">${this.config.translations.waitTime}</div>
                </div>
            </div>
        `;
    }
    
    getQueueStatus(queue) {
        const utilizationPercent = (queue.current_size / queue.max_queue_size) * 100;
        
        if (utilizationPercent >= 90) {
            return { type: 'overloaded', label: 'Overloaded' };
        } else if (utilizationPercent >= 60) {
            return { type: 'busy', label: 'Busy' };
        } else {
            return { type: 'normal', label: 'Normal' };
        }
    }
    
    getTotalWaitingCalls() {
        if (!this.queuesData.queues) return 0;
        
        return this.queuesData.queues.reduce((total, queue) => {
            return total + (queue.waiting_calls || 0);
        }, 0);
    }
    
    getActiveAgentsCount() {
        // This would need to be provided by the API
        // For now, return a placeholder
        return '--';
    }
    
    formatDuration(seconds) {
        if (!seconds || seconds === 0) return '0s';
        
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        
        if (minutes > 0) {
            return `${minutes}${this.config.translations.minutes} ${remainingSeconds}${this.config.translations.seconds}`;
        } else {
            return `${remainingSeconds}${this.config.translations.seconds}`;
        }
    }
    
    showRefreshIndicator() {
        const indicator = this.elements.refreshIndicator;
        indicator.classList.add('show');
        
        setTimeout(() => {
            indicator.classList.remove('show');
        }, 1500);
    }
    
    // Animation helpers
    highlightNewEntries(newEntries) {
        newEntries.forEach(entry => {
            const element = document.querySelector(`[data-entry-id="${entry.id}"]`);
            if (element) {
                element.classList.add('new');
                setTimeout(() => {
                    element.classList.remove('new');
                }, 2000);
            }
        });
    }
    
    // Export functionality
    exportData() {
        const timestamp = new Date().toISOString().split('T')[0];
        const data = {
            timestamp: new Date().toISOString(),
            stats: this.statsData,
            queues: this.queuesData
        };
        
        const blob = new Blob([JSON.stringify(data, null, 2)], {
            type: 'application/json'
        });
        
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `queue-monitor-${timestamp}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
}

// Global functions for external use
window.refreshData = function() {
    if (window.queueMonitor) {
        window.queueMonitor.refreshData();
    }
};

window.exportData = function() {
    if (window.queueMonitor) {
        window.queueMonitor.exportData();
    }
};

// Initialize the monitor
function initializeQueueMonitor() {
    if (window.QUEUE_MONITOR_CONFIG) {
        window.queueMonitor = new QueueMonitor(window.QUEUE_MONITOR_CONFIG);
        window.queueMonitor.start();
    } else {
        console.error('Queue monitor configuration not found');
    }
}

// WebSocket support (if available)
class WebSocketQueueMonitor extends QueueMonitor {
    constructor(config) {
        super(config);
        this.websocket = null;
        this.reconnectInterval = 5000;
        this.maxReconnectAttempts = 10;
        this.reconnectAttempts = 0;
    }
    
    async start() {
        await super.start();
        this.initializeWebSocket();
    }
    
    initializeWebSocket() {
        if (!window.WebSocket) {
            console.log('WebSocket not supported, falling back to polling');
            return;
        }
        
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/voip/queue/`;
            
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                console.log('WebSocket connected');
                this.reconnectAttempts = 0;
                this.stopAutoRefresh(); // Stop polling when WebSocket is active
            };
            
            this.websocket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };
            
            this.websocket.onclose = () => {
                console.log('WebSocket disconnected');
                this.scheduleReconnect();
            };
            
            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
            
        } catch (error) {
            console.error('Failed to initialize WebSocket:', error);
            this.startAutoRefresh(); // Fall back to polling
        }
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            
            setTimeout(() => {
                this.initializeWebSocket();
            }, this.reconnectInterval);
        } else {
            console.log('Max reconnection attempts reached, falling back to polling');
            this.startAutoRefresh();
        }
    }
    
    handleWebSocketMessage(data) {
        switch(data.type) {
            case 'queue_update':
                this.updateQueues(data.data);
                break;
            case 'stats_update':
                this.updateStats(data.data);
                break;
            case 'new_call':
                this.handleNewCall(data.data);
                break;
            case 'call_answered':
                this.handleCallAnswered(data.data);
                break;
        }
        
        this.showRefreshIndicator();
        this.lastUpdateTime = new Date();
    }
    
    handleNewCall(callData) {
        // Handle new call notification
        this.refreshData(); // For now, just refresh everything
    }
    
    handleCallAnswered(callData) {
        // Handle call answered notification
        this.refreshData(); // For now, just refresh everything
    }
}

// Use WebSocket version if available
window.initializeQueueMonitor = function() {
    if (window.QUEUE_MONITOR_CONFIG) {
        window.queueMonitor = new WebSocketQueueMonitor(window.QUEUE_MONITOR_CONFIG);
        window.queueMonitor.start();
    }
};