/**
 * Event handling functionality for the RCA application
 */

// Global variables for event handling
let currentEventSource = null;
let processedMessageIds = new Set();
let connectionStatus = {
    isConnected: false,
    lastEventTime: null,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    reconnectDelay: 2000
};

/**
 * Set up event listeners for the event source
 */
function setupEventListeners(eventSource, taskId, container) {
    // Default container if not provided
    container = container || document.getElementById('log-container');
    
    // Connection status variables
    const connectionStatus = {
        isConnected: false,
        reconnectAttempts: 0,
        maxReconnectAttempts: 5,
        reconnectDelay: 2000 // 2 seconds
    };
    
    // Handle successful connection
    eventSource.addEventListener('open', function() {
        if (window.RCAUtils && window.RCAUtils.mainLog) {
            window.RCAUtils.mainLog('Event source connected');
        }
        
        connectionStatus.isConnected = true;
        connectionStatus.reconnectAttempts = 0;
        
        addDebugMessage(container, 'Connection established');
    });
    
    // Register for all possible event types that the server might send
    const eventTypes = [
        'message', 'step', 'think', 'tool', 'result', 'complete', 'error', 
        'status', 'debug', 'connected'
    ];
    
    // Set up a generic handler for all event types
    eventTypes.forEach(eventType => {
        eventSource.addEventListener(eventType, function(event) {
            try {
                if (window.RCAUtils && window.RCAUtils.mainLog) {
                    window.RCAUtils.mainLog(`Received ${eventType} event:`, event.data);
                }
                
                // Skip handling if data is undefined or empty
                if (!event.data) {
                    console.warn(`Empty data for ${eventType} event`);
                    return;
                }
                
                let data;
                try {
                    data = JSON.parse(event.data);
                } catch (parseError) {
                    console.error(`Error parsing ${eventType} event data:`, parseError);
                    
                    // Create a fallback data object if parsing fails
                    data = {
                        type: eventType,
                        content: event.data,
                        id: `fallback-${Date.now()}`,
                        timestamp: new Date().toISOString()
                    };
                }
                
                // Always ensure we have a type property
                data.type = data.type || eventType;
                
                // Add to UI
                addEventMessageToContainer(data, container);
                
                // Special handling for tool results that have visualization data
                if ((data.type === 'result' || data.type === 'tool') && 
                    (data.visualization_type || (data.result && data.result.visualization_type))) {
                    
                    if (window.RCAUtils && window.RCAUtils.mainLog) {
                        window.RCAUtils.mainLog('Detected visualization data:', 
                            data.visualization_type || (data.result && data.result.visualization_type));
                    }
                    
                    // Handle visualization if available
                    if (window.RCAViz && window.RCAViz.renderVisualization) {
                        const lastElement = container.lastElementChild;
                        if (lastElement) {
                            setTimeout(() => {
                                window.RCAViz.renderVisualization(lastElement);
                            }, 100);
                        }
                    }
                    
                    // Handle result events that should go to visualization panel
                    handleToolResultVisualization(data);
                }
                
                // Handle task completion
                if (data.type === 'complete') {
                    if (window.RCAUtils && window.RCAUtils.mainLog) {
                        window.RCAUtils.mainLog('Task completed, closing EventSource connection');
                    }
                    eventSource.close();
                    updateTaskAsComplete(container);
                    
                    // Update task status in container to prevent reconnection
                    container.dataset.status = 'complete';
                }
                
                // Also close connection on error
                if (data.type === 'error') {
                    if (window.RCAUtils && window.RCAUtils.mainLog) {
                        window.RCAUtils.mainLog('Error received, closing EventSource connection');
                    }
                    eventSource.close();
                    
                    // Mark task status to prevent reconnection
                    container.dataset.status = 'failed';
                }
                
            } catch (error) {
                console.error(`Error processing ${eventType} event:`, error);
            }
        });
    });
    
    // Error event handler
    eventSource.addEventListener('error', function(error) {
        if (window.RCAUtils && window.RCAUtils.mainLog) {
            window.RCAUtils.mainLog('Event source connection error:', error);
        }
        
        addDebugMessage(container, 'Connection error occurred');
        
        if (connectionStatus.isConnected) {
            connectionStatus.isConnected = false;
            
            // Check if task is marked as complete or failed
            if (container.dataset.status === 'complete' || container.dataset.status === 'failed') {
                if (window.RCAUtils && window.RCAUtils.mainLog) {
                    window.RCAUtils.mainLog('Task already complete or failed, not reconnecting');
                }
                addDebugMessage(container, 'Not reconnecting to completed task');
                
                // Close the current connection if still open
                if (eventSource && eventSource.readyState !== 2) { // 2 = CLOSED
                    eventSource.close();
                }
                return;
            }
            
            // Store the current reconnect attempts
            const currentAttempts = connectionStatus.reconnectAttempts;
            
            // Try to reconnect if not too many attempts
            if (currentAttempts < connectionStatus.maxReconnectAttempts) {
                connectionStatus.reconnectAttempts++;
                
                setTimeout(() => {
                    if (container.dataset.status === 'complete' || container.dataset.status === 'failed') {
                        if (window.RCAUtils && window.RCAUtils.mainLog) {
                            window.RCAUtils.mainLog('Task completed during reconnect delay, aborting reconnection');
                        }
                        return;
                    }
                    
                    if (window.RCAUtils && window.RCAUtils.mainLog) {
                        window.RCAUtils.mainLog(`Attempting to reconnect (${connectionStatus.reconnectAttempts}/${connectionStatus.maxReconnectAttempts})...`);
                    }
                    
                    addDebugMessage(container, `Reconnect attempt ${connectionStatus.reconnectAttempts}/${connectionStatus.maxReconnectAttempts}`);
                    
                    // Close existing connection
                    if (eventSource && eventSource.readyState !== 2) { // 2 = CLOSED
                        eventSource.close();
                    }
                    
                    // Get task ID from container
                    const taskIdFromContainer = container.dataset.taskId;
                    
                    // Reconnect
                    setupSSE(taskIdFromContainer || taskId);
                }, connectionStatus.reconnectDelay * connectionStatus.reconnectAttempts);
            } else {
                if (window.RCAUtils && window.RCAUtils.mainLog) {
                    window.RCAUtils.mainLog('Max reconnect attempts reached, giving up.');
                }
                
                addDebugMessage(container, 'Max reconnect attempts reached, giving up');
                
                // Mark task as failed to prevent further reconnection attempts
                container.dataset.status = 'failed';
                
                // Add error message to container
                const errorMessage = {
                    type: 'error',
                    content: 'Connection to server lost. Please refresh the page to reconnect.',
                    timestamp: new Date().toISOString()
                };
                
                addEventMessageToContainer(errorMessage, container);
            }
        }
    });
}

/**
 * Handle visualization events
 */
function handleVisualizationEvent(eventData, container) {
    if (!eventData || !container) return;
    
    if (window.RCAUtils && window.RCAUtils.mainLog) {
        window.RCAUtils.mainLog('Handling visualization event:', eventData);
    }
    
    try {
        // Check if this is a visualization event
        if (eventData.type === 'visualization') {
            // Get content to process
            const content = eventData.content || eventData.data || eventData.result || '';
            
            // Ensure dashboard modules are loaded, then process visualization
            window.ensureDashboardModulesLoaded()
                .then(() => {
                    // Check for dashboard data first
                    if (window.DashboardData && window.DashboardData.extractDashboardData) {
                        const dashboardData = window.DashboardData.extractDashboardData(content);
                        if (dashboardData) {
                            if (window.RCAUtils && window.RCAUtils.mainLog) {
                                window.RCAUtils.mainLog('Extracted dashboard data:', dashboardData);
                            }
                            
                            // Get output workspace
                            const outputWorkspace = document.getElementById('output-workspace');
                            if (outputWorkspace) {
                                // Render dashboard
                                if (window.DashboardCharts && window.DashboardCharts.renderDashboard) {
                                    window.DashboardCharts.renderDashboard(outputWorkspace, dashboardData);
                                    return true;
                                }
                            }
                        }
                    }
                    
                    // Check for other visualization types (table data, etc.)
                    if (window.DashboardData && window.DashboardData.extractToolVisualization) {
                        const visualizationData = window.DashboardData.extractToolVisualization(content);
                        if (visualizationData) {
                            if (window.RCAUtils && window.RCAUtils.mainLog) {
                                window.RCAUtils.mainLog('Extracted visualization data:', visualizationData);
                            }
                            
                            // Get output workspace
                            const outputWorkspace = document.getElementById('output-workspace');
                            if (outputWorkspace) {
                                // Render visualization
                                if (window.DashboardCharts && window.DashboardCharts.renderVisualization) {
                                    window.DashboardCharts.renderVisualization(outputWorkspace, visualizationData);
                                }
                            }
                        }
                    }
                })
                .catch(error => {
                    console.error('Error handling visualization:', error);
                });
        } else {
            // Regular event, check the content for potential visualizations
            const content = eventData.content || eventData.data || eventData.result || '';
            
            // Look for dashboard data in regular events too
            window.ensureDashboardModulesLoaded()
                .then(() => {
                    if (window.DashboardData && window.DashboardData.extractDashboardData) {
                        const dashboardData = window.DashboardData.extractDashboardData(content);
                        if (dashboardData) {
                            if (window.RCAUtils && window.RCAUtils.mainLog) {
                                window.RCAUtils.mainLog('Found dashboard data in regular event:', dashboardData);
                            }
                            
                            // Get output workspace
                            const outputWorkspace = document.getElementById('output-workspace');
                            if (outputWorkspace) {
                                // Render dashboard
                                if (window.DashboardCharts && window.DashboardCharts.renderDashboard) {
                                    window.DashboardCharts.renderDashboard(outputWorkspace, dashboardData);
                                }
                            }
                        }
                    }
                })
                .catch(error => {
                    console.error('Error checking for visualizations:', error);
                });
        }
    } catch (error) {
        console.error('Error in handleVisualizationEvent:', error);
    }
}

/**
 * Add an event message to the container
 */
function addEventMessageToContainer(event, container) {
    if (!container || !event) return;
    
    // Debug log the event data to help diagnose issues
    if (window.RCAUtils && window.RCAUtils.mainLog) {
        window.RCAUtils.mainLog('Processing event for display:', event);
    }
    
    // Special handling for tool results with MySQL output
    if (event.type === 'act' && typeof event.content === 'string') {
        // Check if this is a MySQL result event
        if (event.content.includes('mysql_rw') && event.content.includes('executed:')) {
            try {
                // Extract the JSON part
                const jsonMatch = event.content.match(/executed:\s*({.*})/);
                if (jsonMatch && jsonMatch[1]) {
                    const jsonStr = jsonMatch[1].trim();
                    const resultData = JSON.parse(jsonStr);
                    
                    // Create a specialized result message
                    const resultEvent = {
                        type: 'result',
                        content: 'Database query result:',
                        result: resultData,
                        visualization_type: resultData.visualization_type || 'table',
                        id: resultData.id || `mysql-${Date.now()}`,
                        timestamp: event.timestamp || new Date().toISOString()
                    };
                    
                    // Add the result message to display
                    if (window.RCAUtils && window.RCAUtils.mainLog) {
                        window.RCAUtils.mainLog('Extracted MySQL result data:', resultEvent);
                    }
                    
                    // First add the original act message
                    createBasicMessage(event, container);
                    
                    // Then add the result with visualization
                    return createResultMessage(resultEvent, container);
                }
            } catch (error) {
                console.error('Error extracting MySQL result:', error);
            }
        }
    }
    
    // Create message based on event type
    if (event.type === 'result' || (event.result && (event.type === 'tool' || event.type === 'act'))) {
        return createResultMessage(event, container);
    } else {
        return createBasicMessage(event, container);
    }
}

// Create a basic message element
function createBasicMessage(event, container) {
    // Create message element
    const messageElement = document.createElement('div');
    messageElement.className = `event-message ${event.type || 'unknown'}`;
    
    // Create header with type indicator
    const headerElement = document.createElement('div');
    headerElement.className = 'message-header';
    
    // Add icon based on event type
    const iconElement = document.createElement('span');
    iconElement.className = 'message-icon';
    
    // Set icon based on event type
    switch (event.type) {
        case 'step': iconElement.textContent = ''; break;
        case 'think': iconElement.textContent = ''; break;
        case 'tool': iconElement.textContent = ''; break;
        case 'act': iconElement.textContent = ''; break;
        case 'result': iconElement.textContent = ''; break;
        case 'complete': iconElement.textContent = ''; break;
        case 'error': iconElement.textContent = ''; break;
        default: iconElement.textContent = '';
    }
    
    headerElement.appendChild(iconElement);
    
    // Add timestamp if available
    if (event.timestamp) {
        const timestampElement = document.createElement('span');
        timestampElement.className = 'message-timestamp';
        
        // Format timestamp safely
        let formattedTime = '';
        try {
            const date = new Date(event.timestamp);
            // Check if date is valid
            if (!isNaN(date.getTime())) {
                formattedTime = date.toLocaleTimeString();
            }
        } catch (e) {
            console.error('Error formatting timestamp:', e);
        }
        
        // Only add timestamp if it's valid
        if (formattedTime) {
            timestampElement.textContent = formattedTime;
            headerElement.appendChild(timestampElement);
        }
    }
    
    messageElement.appendChild(headerElement);
    
    // Create content element
    const contentElement = document.createElement('div');
    contentElement.className = 'message-content';
    
    // Handle regular text content
    const textElement = document.createElement('div');
    textElement.className = 'text-content';
    
    // Set content from appropriate field
    const content = event.content || event.message || '';
    
    // Use innerHTML to support markdown-like formatting
    if (content.includes('\n')) {
        // Preserve line breaks for multi-line content
        const formattedContent = content
            .split('\n')
            .map(line => line.trim())
            .join('<br>');
        textElement.innerHTML = formattedContent;
    } else {
        textElement.textContent = content;
    }
    
    contentElement.appendChild(textElement);
    messageElement.appendChild(contentElement);
    
    // Add to container
    container.appendChild(messageElement);
    
    // Scroll container to bottom
    container.scrollTop = container.scrollHeight;
    
    return messageElement;
}

// Create a result message with tool output
function createResultMessage(event, container) {
    // Create message element
    const messageElement = document.createElement('div');
    messageElement.className = `event-message ${event.type || 'result'}`;
    
    // Create header with type indicator
    const headerElement = document.createElement('div');
    headerElement.className = 'message-header';
    
    // Add icon
    const iconElement = document.createElement('span');
    iconElement.className = 'message-icon';
    iconElement.textContent = '';
    headerElement.appendChild(iconElement);
    
    // Add timestamp if available
    if (event.timestamp) {
        const timestampElement = document.createElement('span');
        timestampElement.className = 'message-timestamp';
        timestampElement.textContent = new Date(event.timestamp).toLocaleTimeString();
        headerElement.appendChild(timestampElement);
    }
    
    messageElement.appendChild(headerElement);
    
    // Create content element
    const contentElement = document.createElement('div');
    contentElement.className = 'message-content';
    
    // Add title/description
    const titleElement = document.createElement('div');
    titleElement.className = 'result-title';
    titleElement.textContent = event.content || 'Tool Result:';
    contentElement.appendChild(titleElement);
    
    // Create a pre tag for tool output
    const outputElement = document.createElement('pre');
    outputElement.className = 'tool-output';
    
    // Get the result data
    let resultData = event.result;
    let resultOutput = '';
    
    // Normalize result data based on where it might be located
    if (typeof resultData === 'string') {
        resultOutput = resultData;
    } else if (resultData && typeof resultData === 'object') {
        if (resultData.output) {
            resultOutput = resultData.output;
        } else if (event.output) {
            resultOutput = event.output;
        } else {
            resultOutput = JSON.stringify(resultData, null, 2);
        }
    } else if (event.content) {
        resultOutput = event.content;
    } else {
        resultOutput = 'No result data available';
    }
    
    // Set the output content
    outputElement.textContent = resultOutput;
    contentElement.appendChild(outputElement);
    
    // Store visualization info
    const vizType = event.visualization_type || 
                   (resultData && resultData.visualization_type);
    
    if (vizType) {
        messageElement.dataset.visualizationType = vizType;
        messageElement.dataset.visualizationData = JSON.stringify(resultData || event);
        
        // Add visualization container
        const vizContainer = document.createElement('div');
        vizContainer.className = 'visualization-container';
        vizContainer.id = `viz-${(resultData && resultData.id) || event.id || Date.now()}`;
        contentElement.appendChild(vizContainer);
        
        // Log for debugging
        if (window.RCAUtils && window.RCAUtils.mainLog) {
            window.RCAUtils.mainLog(`Visualization container created for type: ${vizType}`);
        }
    }
    
    messageElement.appendChild(contentElement);
    
    // Add to container
    container.appendChild(messageElement);
    
    // Scroll container to bottom
    container.scrollTop = container.scrollHeight;
    
    // If this is a visualization, try to render it
    if (vizType && window.RCAViz && window.RCAViz.renderVisualization) {
        setTimeout(() => {
            try {
                window.RCAViz.renderVisualization(messageElement);
            } catch (error) {
                console.error('Error rendering visualization:', error);
            }
        }, 100);
    }
    
    return messageElement;
}

/**
 * Ensure the step container exists
 */
function ensureStepContainer(container) {
    if (!container) return null;
    
    // Check if step container already exists
    let stepContainer = container.querySelector('.step-container');
    
    // If not, create it
    if (!stepContainer) {
        stepContainer = document.createElement('div');
        stepContainer.className = 'step-container';
        container.appendChild(stepContainer);
    }
    
    return stepContainer;
}

/**
 * Create a step element for an event
 */
function createStepElement(type, content, timestamp) {
    // Create step element
    const stepElement = document.createElement('div');
    stepElement.className = `step ${type}`;
    
    // Create header
    const header = document.createElement('div');
    header.className = 'step-header';
    
    // Add icon
    const icon = document.createElement('span');
    icon.className = 'step-icon';
    
    if (window.RCAUtils && window.RCAUtils.getEventIcon) {
        icon.textContent = window.RCAUtils.getEventIcon(type);
    } else {
        // Fallback icons
        const fallbackIcons = {
            'message': '',
            'step': '',
            'completion': '',
            'error': '',
            'visualization': ''
        };
        icon.textContent = fallbackIcons[type] || '';
    }
    
    header.appendChild(icon);
    
    // Add type
    const typeElement = document.createElement('span');
    typeElement.className = 'step-type';
    
    if (window.RCAUtils && window.RCAUtils.getEventLabel) {
        typeElement.textContent = window.RCAUtils.getEventLabel(type);
    } else {
        // Fallback labels
        const fallbackLabels = {
            'message': 'Message',
            'step': 'Step',
            'completion': 'Complete',
            'error': 'Error',
            'visualization': 'Visualization'
        };
        typeElement.textContent = fallbackLabels[type] || 'Info';
    }
    
    header.appendChild(typeElement);
    
    // Add timestamp
    if (timestamp) {
        const timeElement = document.createElement('span');
        timeElement.className = 'step-time';
        
        // Format timestamp
        let timeText;
        try {
            const date = new Date(timestamp);
            // Check if date is valid
            if (!isNaN(date.getTime())) {
                timeText = date.toLocaleTimeString();
            }
        } catch (e) {
            console.error('Error formatting timestamp:', e);
        }
        
        // Only add timestamp if it's valid
        if (timeText) {
            timeElement.textContent = timeText;
            header.appendChild(timeElement);
        }
    }
    
    stepElement.appendChild(header);
    
    // Create content
    const contentElement = document.createElement('div');
    contentElement.className = 'step-content';
    
    // Process different content types
    if (type === 'visualization') {
        // For visualization, may need special handling
        contentElement.textContent = 'Visualization data';
    } else if (typeof content === 'string') {
        // Format content based on type
        if (content.trim().startsWith('{') || content.trim().startsWith('[')) {
            try {
                // Try to parse as JSON for pretty formatting
                const jsonData = JSON.parse(content);
                const formattedJson = JSON.stringify(jsonData, null, 2);
                const pre = document.createElement('pre');
                pre.className = 'code-block';
                pre.textContent = formattedJson;
                contentElement.appendChild(pre);
            } catch (e) {
                // If not valid JSON, render as plain text
                contentElement.innerHTML = formatContentAsHTML(content);
            }
        } else {
            // Render as plain text with HTML formatting for markdown-like syntax
            contentElement.innerHTML = formatContentAsHTML(content);
        }
    } else if (content && typeof content === 'object') {
        // Handle object content
        try {
            const pre = document.createElement('pre');
            pre.className = 'code-block';
            pre.textContent = JSON.stringify(content, null, 2);
            contentElement.appendChild(pre);
        } catch (e) {
            contentElement.textContent = 'Invalid content';
        }
    } else {
        contentElement.textContent = 'No content';
    }
    
    stepElement.appendChild(contentElement);
    
    return stepElement;
}

/**
 * Format content as HTML with markdown-like syntax
 */
function formatContentAsHTML(content) {
    if (!content) return '';
    
    // Simple markdown-like formatting
    let formatted = content
        // Code blocks
        .replace(/```([^`]+)```/g, '<pre class="code-block">$1</pre>')
        // Inline code
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        // Bold
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        // Italic
        .replace(/\*([^*]+)\*/g, '<em>$1</em>')
        // Line breaks
        .replace(/\n/g, '<br>');
    
    return formatted;
}

/**
 * Set up server-sent events
 */
function setupSSE(taskId) {
    if (!taskId) {
        if (window.RCAUtils && window.RCAUtils.mainLog) {
            window.RCAUtils.mainLog('No task ID provided for setupSSE');
        }
        return null;
    }
    
    if (window.RCAUtils && window.RCAUtils.mainLog) {
        window.RCAUtils.mainLog('Setting up SSE for task:', taskId);
    }
    
    // Get container for this task first - we need it for debug messages
    const container = document.getElementById(`task-${taskId}`) || document.getElementById('log-container');
    if (!container) {
        if (window.RCAUtils && window.RCAUtils.mainLog) {
            window.RCAUtils.mainLog('Container not found for task:', taskId);
        }
        return null;
    }
    
    // Add a debug message before anything else
    addDebugMessage(container, 'Starting EventSource connection...');
    
    // Close existing connection if any
    if (currentEventSource && currentEventSource.readyState !== 2) { // 2 = CLOSED
        currentEventSource.close();
    }
    
    // Check if task is already marked as complete
    const taskStatus = container.dataset.status;
    if (taskStatus === 'complete' || taskStatus === 'failed') {
        if (window.RCAUtils && window.RCAUtils.mainLog) {
            window.RCAUtils.mainLog('Task already completed or failed, not setting up SSE');
        }
        addDebugMessage(container, `Task already in status: ${taskStatus}, not connecting`);
        return null;
    }
    
    try {
        // Get auth token for secure connection
        const authToken = sessionStorage.getItem('authToken') || localStorage.getItem('auth_token');
        
        // Connect to SSE endpoint with auth token
        const sseUrl = `/tasks/${taskId}/events?token=${encodeURIComponent(authToken)}`;
        addDebugMessage(container, `Creating event source with URL: ${sseUrl.substring(0, 30)}...`);
        const eventSource = new EventSource(sseUrl);
        currentEventSource = eventSource;
        
        // Store task ID in container data attribute
        container.dataset.taskId = taskId;
        
        // Set up event listeners
        setupEventListeners(eventSource, taskId, container);
        
        return eventSource;
    } catch (error) {
        console.error('Error setting up SSE:', error);
        addDebugMessage(container, `Error setting up SSE: ${error.message}`);
        return null;
    }
}

/**
 * Update task status in UI
 */
function updateTaskStatus(data, container) {
    // Update progress indicators if present
    const statusElem = container.querySelector('.task-status');
    const progressElem = container.querySelector('.task-progress');
    
    if (statusElem) {
        statusElem.textContent = data.status || 'running';
    }
    
    if (progressElem && data.steps) {
        const percent = Math.min(100, Math.round((data.current_step || 0) / data.steps * 100));
        progressElem.style.width = `${percent}%`;
        progressElem.setAttribute('aria-valuenow', percent);
        progressElem.textContent = `${percent}%`;
    }
    
    // Add status message to container
    addDebugMessage(container, `Task status: ${data.status || 'running'}`);
}

/**
 * Mark task as complete in UI
 */
function updateTaskAsComplete(container) {
    // Update any UI elements to show completion
    const statusElem = container.querySelector('.task-status');
    if (statusElem) {
        statusElem.textContent = 'completed';
        statusElem.classList.add('status-complete');
    }
    
    const progressElem = container.querySelector('.task-progress');
    if (progressElem) {
        progressElem.style.width = '100%';
        progressElem.setAttribute('aria-valuenow', 100);
        progressElem.textContent = '100%';
    }
    
    // Add completion message
    addDebugMessage(container, 'Task completed successfully');
}

/**
 * Helper to add debug messages (only in dev mode)
 */
function addDebugMessage(container, message) {
    // Check if we're in development mode
    const isDev = window.RCA_CONFIG && window.RCA_CONFIG.DEV_MODE === true;
    
    // Only show debug messages in dev mode
    if (!isDev) return;
    
    // Add debug message
    const debugElement = document.createElement('div');
    debugElement.className = 'debug-message';
    debugElement.textContent = message;
    
    // Add to container but don't display by default
    if (container) {
        // Hide debug messages by default
        debugElement.style.display = 'none'; 
        container.appendChild(debugElement);
    }
}

/**
 * Handle result events that should go to visualization panel
 */
function handleToolResultVisualization(event) {
    if (!event || !event.result) return false;
    
    // Check if this is a tool result that should be visualized
    let visualizationType = event.visualization_type || 
                           (event.result && event.result.visualization_type);
    
    // Special handling for dashboard_viz tool results
    // The dashboard_viz tool embeds visualization_type inside the result object
    if (!visualizationType && event.result && typeof event.result === 'string') {
        try {
            // Try to parse JSON string result
            const resultObj = JSON.parse(event.result);
            if (resultObj && resultObj.visualization_type) {
                visualizationType = resultObj.visualization_type;
                
                // Extract the actual chart data from the nested structure
                if (resultObj.output) {
                    event.result = resultObj;
                }
            }
        } catch (e) {
            // Not JSON or couldn't parse, continue with normal processing
        }
    }
    
    if (!visualizationType) return false;
    
    try {
        console.log('Handling visualization for tool result:', visualizationType);
        
        // Get output workspace for visualization panel
        const outputWorkspace = document.getElementById('output-workspace');
        if (!outputWorkspace) return false;
        
        // Extract table content before creating the panel to validate it
        let tableContent = '';
        let isJsonSchema = false;
        let chartData = null;
        
        // Check if this is a chart visualization
        if (visualizationType === 'chart' || visualizationType === 'dashboard') {
            // For charts, we extract the chart configuration
            try {
                if (event.result && typeof event.result === 'object') {
                    if (typeof event.result === 'string') {
                        // If result is a string, try to parse as JSON
                        chartData = JSON.parse(event.result).output;
                    } else if (event.result.output) {
                        // If result already has output field, use that
                        chartData = event.result.output;
                    }
                    
                    // Valid chart data found
                    if (chartData) {
                        console.log('Chart data found:', chartData);
                    }
                }
            } catch (e) {
                console.error('Error parsing chart data:', e);
            }
        } else {
            // For tables, extract the content as before
            if (event.result && event.result.output) {
                tableContent = event.result.output;
                
                // Check if this is a JSON schema result
                if (typeof tableContent === 'string' && tableContent.includes('"COLUMN_NAME"') && 
                    tableContent.includes('"DATA_TYPE"')) {
                    isJsonSchema = true;
                }
            } else if (typeof event.result === 'string') {
                tableContent = event.result;
                
                // Check if this is a JSON schema result
                if (tableContent.includes('"COLUMN_NAME"') && tableContent.includes('"DATA_TYPE"')) {
                    isJsonSchema = true;
                }
            }
        }
        
        // Check if we have valid content - either chart data, ASCII table, or JSON schema
        if ((!tableContent || (!isJsonSchema && !(tableContent.includes('|') && tableContent.includes('+')))) && !chartData) {
            console.log('No valid visualization content found, skipping visualization');
            return false;
        }
        
        // Create a new panel for this visualization
        const panel = document.createElement('div');
        panel.className = 'visualization-panel';
        panel.dataset.id = event.id || `viz-${Date.now()}`;
        
        // Add header with title and controls
        const header = document.createElement('div');
        header.className = 'panel-header';
        
        // Add title
        const title = document.createElement('div');
        title.className = 'panel-title';
        title.textContent = event.content || 'Database Query Result';
        header.appendChild(title);
        
        // Add controls
        const controls = document.createElement('div');
        controls.className = 'panel-controls';
        
        // Add close button
        const closeBtn = document.createElement('button');
        closeBtn.className = 'panel-close';
        closeBtn.innerHTML = '&times;';
        closeBtn.onclick = function() {
            panel.remove();
        };
        controls.appendChild(closeBtn);
        
        header.appendChild(controls);
        panel.appendChild(header);
        
        // Add content area
        const content = document.createElement('div');
        content.className = 'panel-content';
        
        // Handle different visualization types
        if (visualizationType === 'table') {
            const tableWrapper = document.createElement('div');
            tableWrapper.className = 'table-wrapper';
            
            let htmlTable = '';
            
            // Check if this is a JSON schema result
            if (isJsonSchema) {
                htmlTable = convertJsonSchemaToHtml(tableContent);
            } else {
                // Convert ASCII table to HTML
                htmlTable = convertAsciiTableToHtml(tableContent);
            }
            
            tableWrapper.innerHTML = htmlTable;
            content.appendChild(tableWrapper);
        } else if (visualizationType === 'chart' && chartData) {
            // Create chart container
            const chartContainer = document.createElement('div');
            chartContainer.className = 'chart-wrapper';
            chartContainer.style.height = '100%';
            chartContainer.style.width = '100%';
            
            // Add a unique ID for Plotly to target
            const chartId = `chart-${Date.now()}`;
            chartContainer.id = chartId;
            
            content.appendChild(chartContainer);
            
            // Set panel title based on chart title if available
            if (chartData.title && title) {
                title.textContent = chartData.title;
            }
            
            // Initialize the chart after the panel is added to the DOM
            setTimeout(() => {
                createChart(chartId, chartData);
            }, 10);
        } else if (visualizationType === 'dashboard' && chartData) {
            // Create dashboard container with multiple charts
            const dashboardContainer = document.createElement('div');
            dashboardContainer.className = 'dashboard-wrapper';
            
            // Set panel title based on dashboard title if available
            if (chartData.title && title) {
                title.textContent = chartData.title;
            }
            
            // Create container for each chart in the dashboard
            if (chartData.charts && Array.isArray(chartData.charts)) {
                chartData.charts.forEach((chart, index) => {
                    const chartWrapper = document.createElement('div');
                    chartWrapper.className = 'dashboard-chart';
                    chartWrapper.style.height = '300px';
                    chartWrapper.style.marginBottom = '20px';
                    
                    // Add a unique ID for Plotly to target
                    const chartId = `dashboard-chart-${Date.now()}-${index}`;
                    chartWrapper.id = chartId;
                    
                    dashboardContainer.appendChild(chartWrapper);
                    
                    // Initialize the chart after the panel is added to the DOM
                    setTimeout(() => {
                        createChart(chartId, chart);
                    }, 10);
                });
            }
            
            content.appendChild(dashboardContainer);
        }
        
        panel.appendChild(content);
        
        // Add resize handles (8 directions)
        const directions = ['n', 'ne', 'e', 'se', 's', 'sw', 'w', 'nw'];
        directions.forEach(dir => {
            const handle = document.createElement('div');
            handle.className = `resize-handle resize-${dir}`;
            handle.dataset.direction = dir;
            panel.appendChild(handle);
        });
        
        // Add to workspace (panels are absolute positioned by default)
        outputWorkspace.appendChild(panel);
        
        // Position panel in workspace - panels are positioned absolutely for dragging
        const workspaceRect = outputWorkspace.getBoundingClientRect();
        
        // Calculate panel position (initially centered)
        const panelWidth = Math.min(workspaceRect.width * 0.8, 800);
        const panelHeight = Math.min(workspaceRect.height * 0.6, 500);
        
        // Get all existing panels to find a non-overlapping position
        const existingPanels = Array.from(outputWorkspace.querySelectorAll('.visualization-panel'))
            .filter(p => p !== panel);
        
        // Default starting position
        let topPosition = 50;
        let leftPosition = Math.max(20, (workspaceRect.width - panelWidth) / 2);
        
        // If we have existing panels, find a non-overlapping position
        if (existingPanels.length > 0) {
            // Create a grid system for panel placement
            const gridCellSize = 50; // Size of each grid cell
            const occupiedCells = new Set();
            
            // Mark occupied cells for all existing panels
            existingPanels.forEach(existingPanel => {
                const rect = existingPanel.getBoundingClientRect();
                const workspaceTop = workspaceRect.top;
                const workspaceLeft = workspaceRect.left;
                
                // Convert panel position to grid coordinates
                const panelLeft = parseInt(existingPanel.style.left);
                const panelTop = parseInt(existingPanel.style.top);
                const panelRight = panelLeft + rect.width;
                const panelBottom = panelTop + rect.height;
                
                // Mark all cells this panel occupies as taken
                for (let x = Math.floor(panelLeft / gridCellSize); x <= Math.ceil(panelRight / gridCellSize); x++) {
                    for (let y = Math.floor(panelTop / gridCellSize); y <= Math.ceil(panelBottom / gridCellSize); y++) {
                        occupiedCells.add(`${x},${y}`);
                    }
                }
            });
            
            // Find first available position using grid
            let foundPosition = false;
            const maxGridX = Math.floor(workspaceRect.width / gridCellSize);
            const maxGridY = Math.floor(workspaceRect.height / gridCellSize) * 2; // Allow scrolling
            
            // Try to find a suitable position in the grid
            for (let y = 1; y < maxGridY && !foundPosition; y++) {
                for (let x = 0; x < maxGridX && !foundPosition; x++) {
                    // Check if this position and surrounding area is free
                    const gridPosX = x * gridCellSize;
                    const gridPosY = y * gridCellSize;
                    const panelWidthInCells = Math.ceil(panelWidth / gridCellSize);
                    const panelHeightInCells = Math.ceil(panelHeight / gridCellSize);
                    
                    let isPositionFree = true;
                    
                    // Check if any cell in the panel area is occupied
                    for (let checkX = x; checkX < x + panelWidthInCells && isPositionFree; checkX++) {
                        for (let checkY = y; checkY < y + panelHeightInCells && isPositionFree; checkY++) {
                            if (occupiedCells.has(`${checkX},${checkY}`)) {
                                isPositionFree = false;
                            }
                        }
                    }
                    
                    if (isPositionFree) {
                        leftPosition = gridPosX;
                        topPosition = gridPosY;
                        foundPosition = true;
                    }
                }
            }
            
            // If no position found, place below the lowest panel
            if (!foundPosition) {
                // Find the lowest panel
                let lowestBottom = 0;
                existingPanels.forEach(existingPanel => {
                    const panelTop = parseInt(existingPanel.style.top);
                    const panelHeight = existingPanel.getBoundingClientRect().height;
                    const bottom = panelTop + panelHeight;
                    lowestBottom = Math.max(lowestBottom, bottom);
                });
                
                topPosition = lowestBottom + 20;
                leftPosition = 20;
            }
        }
        
        // Set panel dimensions and position
        panel.style.position = 'absolute';
        panel.style.width = `${panelWidth}px`;
        panel.style.height = `${panelHeight}px`;
        panel.style.left = `${leftPosition}px`;
        panel.style.top = `${topPosition}px`;
        panel.style.zIndex = '10';
        
        // Auto-scroll to show new panel if it's below the visible area
        if (topPosition + panelHeight > outputWorkspace.clientHeight) {
            outputWorkspace.scrollTop = topPosition - 20;
        }
        
        // Setup dragging
        setupDraggablePanel(panel, header);
        
        // Setup resizing
        setupResizablePanel(panel);
        
        // Bring panel to front when clicked
        panel.addEventListener('mousedown', function() {
            const allPanels = outputWorkspace.querySelectorAll('.visualization-panel');
            allPanels.forEach(p => p.style.zIndex = '10');
            panel.style.zIndex = '100';
        });
        
        return true;
    } catch (error) {
        console.error('Error creating visualization panel:', error);
        return false;
    }
}

/**
 * Setup draggable behavior for visualization panel - more fluid implementation
 */
function setupDraggablePanel(panel, dragHandle) {
    if (!panel || !dragHandle) return;
    
    let isDragging = false;
    let offsetX, offsetY;
    
    // Mouse events for desktop
    dragHandle.addEventListener('mousedown', startDrag);
    document.addEventListener('mousemove', drag);
    document.addEventListener('mouseup', stopDrag);
    
    // Touch events for mobile
    dragHandle.addEventListener('touchstart', handleTouchStart);
    document.addEventListener('touchmove', handleTouchMove);
    document.addEventListener('touchend', handleTouchEnd);
    
    function startDrag(e) {
        // Don't start drag if clicked on a button
        if (e.target.closest('.panel-close')) {
            return;
        }
        
        // Prevent text selection during drag
        e.preventDefault();
        e.stopPropagation();
        
        // Calculate offset - these values are crucial for smooth dragging
        const rect = panel.getBoundingClientRect();
        offsetX = e.clientX - rect.left;
        offsetY = e.clientY - rect.top;
        
        // Bring panel to front
        const workspace = document.getElementById('output-workspace');
        const allPanels = workspace.querySelectorAll('.visualization-panel');
        allPanels.forEach(p => p.style.zIndex = '10');
        panel.style.zIndex = '100';
        
        isDragging = true;
        panel.classList.add('dragging');
    }
    
    function drag(e) {
        if (!isDragging) return;
        
        // Get workspace for boundaries
        const workspace = document.getElementById('output-workspace');
        const workspaceRect = workspace.getBoundingClientRect();
        
        // Calculate new position relative to workspace
        const x = e.clientX - workspaceRect.left - offsetX;
        const y = e.clientY - workspaceRect.top - offsetY;
        
        // Update position directly
        panel.style.left = `${x}px`;
        panel.style.top = `${y}px`;
        
        // Ensure workspace scrolls if panel is moved to the edges
        const scrollMargin = 50;
        
        // Handle scrolling down
        if (e.clientY > workspaceRect.bottom - scrollMargin) {
            workspace.scrollTop += 10;
        }
        
        // Handle scrolling up
        if (e.clientY < workspaceRect.top + scrollMargin) {
            workspace.scrollTop -= 10;
        }
    }
    
    function stopDrag() {
        if (!isDragging) return;
        isDragging = false;
        panel.classList.remove('dragging');
    }
    
    // Touch event handlers
    function handleTouchStart(e) {
        if (e.touches.length === 1) {
            const touch = e.touches[0];
            const mouseEvent = new MouseEvent('mousedown', {
                clientX: touch.clientX,
                clientY: touch.clientY
            });
            startDrag(mouseEvent);
        }
    }
    
    function handleTouchMove(e) {
        if (isDragging && e.touches.length === 1) {
            const touch = e.touches[0];
            const mouseEvent = new MouseEvent('mousemove', {
                clientX: touch.clientX,
                clientY: touch.clientY
            });
            drag(mouseEvent);
        }
    }
    
    function handleTouchEnd() {
        stopDrag();
    }
}

/**
 * Setup resizable behavior for visualization panel with 8 resize handles
 */
function setupResizablePanel(panel) {
    if (!panel) return;
    
    const handles = panel.querySelectorAll('.resize-handle');
    if (!handles.length) return;
    
    handles.forEach(handle => {
        handle.addEventListener('mousedown', startResize);
        handle.addEventListener('touchstart', handleTouchStart);
    });
    
    document.addEventListener('mousemove', resize);
    document.addEventListener('mouseup', stopResize);
    document.addEventListener('touchmove', handleTouchMove);
    document.addEventListener('touchend', handleTouchEnd);
    
    let isResizing = false;
    let currentHandle = null;
    let startX, startY, startWidth, startHeight, startLeft, startTop;
    
    function startResize(e) {
        e.preventDefault();
        e.stopPropagation();
        
        // Bring panel to front
        const workspace = document.getElementById('output-workspace');
        const allPanels = workspace.querySelectorAll('.visualization-panel');
        allPanels.forEach(p => p.style.zIndex = '10');
        panel.style.zIndex = '100';
        
        isResizing = true;
        currentHandle = e.target;
        panel.classList.add('resizing');
        
        // Save starting dimensions and position
        startWidth = panel.offsetWidth;
        startHeight = panel.offsetHeight;
        startLeft = panel.offsetLeft;
        startTop = panel.offsetTop;
        startX = e.clientX;
        startY = e.clientY;
    }
    
    function resize(e) {
        if (!isResizing) return;
        
        const direction = currentHandle.dataset.direction;
        const deltaX = e.clientX - startX;
        const deltaY = e.clientY - startY;
        
        // Handle different resize directions
        if (direction.includes('e')) {
            // East - resize width
            panel.style.width = `${Math.max(200, startWidth + deltaX)}px`;
        }
        if (direction.includes('w')) {
            // West - resize width and reposition
            const newWidth = Math.max(200, startWidth - deltaX);
            const newLeft = startLeft + (startWidth - newWidth);
            panel.style.width = `${newWidth}px`;
            panel.style.left = `${newLeft}px`;
        }
        if (direction.includes('s')) {
            // South - resize height
            panel.style.height = `${Math.max(150, startHeight + deltaY)}px`;
        }
        if (direction.includes('n')) {
            // North - resize height and reposition
            const newHeight = Math.max(150, startHeight - deltaY);
            const newTop = startTop + (startHeight - newHeight);
            panel.style.height = `${newHeight}px`;
            panel.style.top = `${newTop}px`;
        }
        
        // Ensure workspace scrolls if resizing to the edges
        const workspace = document.getElementById('output-workspace');
        const workspaceRect = workspace.getBoundingClientRect();
        const scrollMargin = 50;
        
        // Handle scrolling down
        if (e.clientY > workspaceRect.bottom - scrollMargin) {
            workspace.scrollTop += 10;
        }
        
        // Handle scrolling up
        if (e.clientY < workspaceRect.top + scrollMargin) {
            workspace.scrollTop -= 10;
        }
    }
    
    function stopResize() {
        if (!isResizing) return;
        
        isResizing = false;
        panel.classList.remove('resizing');
        currentHandle = null;
    }
    
    // Touch event handlers
    function handleTouchStart(e) {
        if (e.touches.length === 1) {
            const touch = e.touches[0];
            const mouseEvent = new MouseEvent('mousedown', {
                clientX: touch.clientX,
                clientY: touch.clientY
            });
            startResize(mouseEvent);
        }
    }
    
    function handleTouchMove(e) {
        if (isResizing && e.touches.length === 1) {
            const touch = e.touches[0];
            const mouseEvent = new MouseEvent('mousemove', {
                clientX: touch.clientX,
                clientY: touch.clientY
            });
            resize(mouseEvent);
        }
    }
    
    function handleTouchEnd() {
        stopResize();
    }
}

/**
 * Convert ASCII table to HTML
 */
function convertAsciiTableToHtml(asciiTable) {
    if (!asciiTable) return '';
    
    try {
        const lines = asciiTable.split('\n');
        let html = '<table class="data-table">';
        
        // Check for header row
        if (lines.length > 2 && lines[1].startsWith('+')) {
            // Extract header row
            const headerRow = lines[2].trim().split('|')
                .filter(cell => cell.trim() !== '')
                .map(cell => cell.trim());
            
            // Add header row
            html += '<thead><tr>';
            headerRow.forEach(cell => {
                html += `<th>${cell}</th>`;
            });
            html += '</tr></thead>';
        }
        
        // Extract data rows
        const dataRows = lines.slice(3).filter(line => line.startsWith('|'));
        
        // Add data rows
        html += '<tbody>';
        dataRows.forEach(row => {
            const cells = row.trim().split('|')
                .filter(cell => cell.trim() !== '')
                .map(cell => cell.trim());
            
            html += '<tr>';
            cells.forEach(cell => {
                html += `<td>${cell}</td>`;
            });
            html += '</tr>';
        });
        html += '</tbody>';
        
        html += '</table>';
        return html;
    } catch (error) {
        console.error('Error converting ASCII table to HTML:', error);
        return `<pre>${asciiTable}</pre>`;
    }
}

/**
 * Convert JSON schema to HTML table
 */
function convertJsonSchemaToHtml(jsonString) {
    try {
        // Try to parse the JSON string
        let data = [];
        
        try {
            // First try parsing it directly
            data = JSON.parse(jsonString);
        } catch (e) {
            // If direct parsing fails, try to extract JSON from the string
            // This handles cases where the JSON is embedded in a larger output
            const jsonMatch = jsonString.match(/\{\"output\"\s*:\s*\"(.*)\"\s*,\s*\"id\"/);
            
            if (jsonMatch && jsonMatch[1]) {
                // We need to handle escaped JSON strings
                const extractedJson = jsonMatch[1]
                    .replace(/\\n/g, '\n')
                    .replace(/\\"/g, '"')
                    .replace(/\\\\/g, '\\');
                
                // Parse the cleaned JSON
                data = JSON.parse(extractedJson);
            }
        }
        
        // Ensure we have an array of objects
        if (!Array.isArray(data)) {
            console.error('Invalid JSON schema format, expected array');
            return '<div class="error">Invalid schema format</div>';
        }
        
        if (data.length === 0) {
            return '<div class="empty-result">No columns found</div>';
        }
        
        // Get all possible headers from all objects
        const headers = Array.from(new Set(
            data.flatMap(obj => Object.keys(obj))
        ));
        
        // Create HTML table
        let html = '<table class="data-table schema-table">';
        
        // Add header row
        html += '<thead><tr>';
        headers.forEach(header => {
            html += `<th>${header}</th>`;
        });
        html += '</tr></thead>';
        
        // Add data rows
        html += '<tbody>';
        data.forEach(row => {
            html += '<tr>';
            headers.forEach(header => {
                const value = row[header] !== undefined ? row[header] : '';
                html += `<td>${value}</td>`;
            });
            html += '</tr>';
        });
        html += '</tbody>';
        
        html += '</table>';
        return html;
    } catch (error) {
        console.error('Error converting JSON schema to HTML:', error);
        return `<div class="error">Error converting schema: ${error.message}</div>`;
    }
}

/**
 * Create a chart using Plotly.js
 */
function createChart(containerId, chartConfig) {
    // Ensure Plotly.js is loaded
    if (!window.Plotly) {
        console.error('Plotly.js is not loaded. Cannot create chart.');
        
        // Check if we need to load Plotly
        const plotlyScript = document.getElementById('plotly-script');
        if (!plotlyScript) {
            // Add Plotly.js from CDN if not loaded
            const script = document.createElement('script');
            script.id = 'plotly-script';
            script.src = 'https://cdn.plot.ly/plotly-2.16.1.min.js';
            script.onload = function() {
                // Try creating the chart again once Plotly is loaded
                setTimeout(() => createChart(containerId, chartConfig), 100);
            };
            document.head.appendChild(script);
        }
        return;
    }
    
    try {
        const container = document.getElementById(containerId);
        if (!container) {
            console.error(`Chart container with id ${containerId} not found.`);
            return;
        }
        
        const chartType = chartConfig.type || 'scatter';
        let traces = [];
        let layout = {
            title: chartConfig.title || '',
            margin: { t: 40, r: 10, l: 60, b: 60 },
            xaxis: chartConfig.xaxis || { title: 'X Axis' },
            yaxis: chartConfig.yaxis || { title: 'Y Axis' },
            plot_bgcolor: '#ffffff',
            paper_bgcolor: '#ffffff',
            font: { family: 'Arial, sans-serif' }
        };
        
        // Create appropriate traces based on chart type
        switch (chartType) {
            case 'bar':
                traces.push({
                    x: chartConfig.x || [],
                    y: chartConfig.y || [],
                    type: 'bar',
                    marker: {
                        color: chartConfig.color || '#1f77b4',
                        line: {
                            color: '#333',
                            width: 1
                        }
                    }
                });
                break;
                
            case 'line':
                traces.push({
                    x: chartConfig.x || [],
                    y: chartConfig.y || [],
                    type: 'scatter',
                    mode: 'lines+markers',
                    line: {
                        color: chartConfig.color || '#1f77b4',
                        width: 2
                    },
                    marker: {
                        size: 6,
                        color: chartConfig.color || '#1f77b4'
                    }
                });
                break;
                
            case 'pie':
                traces.push({
                    labels: chartConfig.labels || [],
                    values: chartConfig.values || [],
                    type: 'pie',
                    marker: {
                        colors: chartConfig.colors || [
                            '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                            '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
                        ]
                    }
                });
                
                // Pie charts need a different layout
                layout = {
                    title: chartConfig.title || '',
                    margin: { t: 40, r: 10, l: 10, b: 10 },
                    plot_bgcolor: '#ffffff',
                    paper_bgcolor: '#ffffff',
                    font: { family: 'Arial, sans-serif' }
                };
                break;
                
            case 'scatter':
                traces.push({
                    x: chartConfig.x || [],
                    y: chartConfig.y || [],
                    type: 'scatter',
                    mode: 'markers',
                    marker: {
                        size: 10,
                        color: chartConfig.color || '#1f77b4',
                        opacity: 0.7,
                        line: {
                            color: '#333',
                            width: 1
                        }
                    }
                });
                break;
                
            default:
                // Default to a line chart
                traces.push({
                    x: chartConfig.x || [],
                    y: chartConfig.y || [],
                    type: 'scatter',
                    mode: 'lines+markers'
                });
        }
        
        // Create the plot
        Plotly.newPlot(containerId, traces, layout, {
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['sendDataToCloud', 'autoScale2d', 'resetScale2d']
        });
        
        // Handle responsive resizing
        window.addEventListener('resize', function() {
            Plotly.Plots.resize(containerId);
        });
        
    } catch (error) {
        console.error('Error creating chart:', error);
    }
}

/**
 * Expose event functions to global scope AFTER all functions are defined
 */
window.RCAEvents = {
    setupEventListeners,
    handleEventData: handleVisualizationEvent, // Alias for backward compatibility
    addEventMessageToContainer,
    handleVisualizationEvent,
    ensureStepContainer,
    createStepElement,
    setupSSE,
    updateTaskStatus,
    updateTaskAsComplete,
    addDebugMessage,
    handleToolResultVisualization
};
