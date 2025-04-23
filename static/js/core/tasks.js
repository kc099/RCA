/**
 * Task management functionality for the RCA application
 */

// Expose task functions to global scope
window.RCATasks = {
    createTask,
    initializeActiveTask,
    handleTaskCreation,
    setupTaskCreation
};

// Global task creation lock
window.TASK_LOCK = {
    isCreating: false,
    lastCreationTime: 0,
    lockTimeoutMs: 5000,
    
    // Acquire the lock
    acquire: function() {
        const now = Date.now();
        
        // Check if lock is already held
        if (this.isCreating) {
            // Check if lock has expired
            if (now - this.lastCreationTime > this.lockTimeoutMs) {
                // Lock has expired, reset it
                this.isCreating = false;
            } else {
                // Lock is still valid
                return false;
            }
        }
        
        // Acquire the lock
        this.isCreating = true;
        this.lastCreationTime = now;
        return true;
    },
    
    // Release the lock
    release: function() {
        this.isCreating = false;
    }
};

/**
 * Function to load active task on page load
 */
function initializeActiveTask() {
    window.RCAUtils.mainLog('Initializing active task');
    
    fetch('/tasks/active')
        .then(response => {
            if (!response.ok) {
                throw new Error(`Failed to get active task: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            window.RCAUtils.mainLog('Active task:', data);
            
            // Check if there's an active task
            if (data && data.id) {
                // Connect to events for this task
                window.RCAEvents.setupSSE(data.id);
                
                // Update task status
                const container = document.getElementById('log-container');
                if (container) {
                    container.dataset.taskId = data.id;
                }
            }
        })
        .catch(error => {
            window.RCAUtils.mainLog('Error getting active task:', error);
        });
}

/**
 * Setup task creation handling
 */
function setupTaskCreation() {
    window.RCAUtils.mainLog('Setting up task creation');
    
    // Get input container
    const inputContainer = document.getElementById('input-container');
    if (!inputContainer) {
        window.RCAUtils.mainLog('Input container not found');
        return;
    }
    
    // Add keypress event listener to input
    const promptInput = inputContainer.querySelector('#prompt-input');
    if (promptInput) {
        promptInput.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                handleTaskCreation();
            }
        });
    }
    
    // Add click event listener to send button
    const sendButton = inputContainer.querySelector('button');
    if (sendButton) {
        sendButton.addEventListener('click', function(event) {
            event.preventDefault();
            handleTaskCreation();
        });
    }
}

/**
 * Consolidated task creation handler
 */
function handleTaskCreation() {
    window.RCAUtils.mainLog('Handling task creation');
    
    // Get prompt input
    const promptInput = document.getElementById('prompt-input');
    if (!promptInput) {
        window.RCAUtils.mainLog('Prompt input not found');
        return;
    }
    
    // Get prompt text
    const promptText = promptInput.value.trim();
    if (!promptText) {
        window.RCAUtils.mainLog('No prompt text provided');
        return;
    }
    
    // Create task
    createTask(promptText);
    
    // Clear input
    promptInput.value = '';
}

/**
 * Make createTask function available globally with prompt parameter
 */
function createTask(promptText = null) {
    window.RCAUtils.mainLog('Creating task with prompt:', promptText);
    
    // Validate authentication
    if (!window.RCAUtils.isAuthenticated()) {
        window.RCAUtils.mainLog('User not authenticated');
        window.location.href = '/login';
        return;
    }
    
    // Get prompt text if not provided
    if (!promptText) {
        const promptInput = document.getElementById('prompt-input');
        if (!promptInput) {
            window.RCAUtils.mainLog('Prompt input not found');
            return;
        }
        
        promptText = promptInput.value.trim();
        if (!promptText) {
            window.RCAUtils.mainLog('No prompt text provided');
            return;
        }
    }
    
    // Acquire task creation lock
    if (!window.TASK_LOCK.acquire()) {
        window.RCAUtils.mainLog('Task creation already in progress');
        return;
    }
    
    // Update UI to indicate task creation
    const sendButton = document.querySelector('#input-container button');
    if (sendButton) {
        sendButton.disabled = true;
        sendButton.textContent = 'Creating...';
    }
    
    // Create task
    fetch('/tasks', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            prompt: promptText
        })
    })
    .then(response => {
        // Release task creation lock
        window.TASK_LOCK.release();
        
        // Reset UI
        if (sendButton) {
            sendButton.disabled = false;
            sendButton.textContent = 'Send';
        }
        
        if (!response.ok) {
            throw new Error(`Error creating task: ${response.status}`);
        }
        
        return response.json();
    })
    .then(data => {
        window.RCAUtils.mainLog('Task created:', data);
        
        // Add debug message to the log container if RCAEvents is available
        const debugContainer = document.getElementById('log-container');
        if (debugContainer && window.RCAEvents && window.RCAEvents.addDebugMessage) {
            window.RCAEvents.addDebugMessage(debugContainer, `Task created. Response: ${JSON.stringify(data)}`);
        }
        
        // Get the task ID from the response (handle different field names)
        const taskId = data.task_id || data.id || '';
        
        if (!taskId) {
            if (debugContainer && window.RCAEvents && window.RCAEvents.addDebugMessage) {
                window.RCAEvents.addDebugMessage(debugContainer, `Error: No task ID found in response`);
            }
            return;
        }
        
        // Create task container if not exists
        const existingContainer = document.getElementById(`task-${taskId}`);
        const logContainer = existingContainer || createTaskContainer(taskId);
        
        if (!existingContainer) {
            // Add the task container to the container element
            const container = document.getElementById('task-container');
            if (container) {
                container.appendChild(logContainer);
                
                // Make sure the container is visible
                container.style.display = 'block';
                
                // Scroll to the bottom of the container
                container.scrollTop = container.scrollHeight;
            } else {
                console.error('Task container element not found');
            }
        }
        
        // Add task ID as a data attribute to the container
        logContainer.dataset.taskId = taskId;
        
        // Add a message about connecting to the stream
        if (window.RCAEvents && window.RCAEvents.addDebugMessage) {
            window.RCAEvents.addDebugMessage(logContainer, `Setting up SSE for task: ${taskId}`);
        }
        
        // Wait a small amount of time to ensure DOM is updated
        setTimeout(() => {
            // Setup SSE for new task
            if (window.RCAEvents && window.RCAEvents.setupSSE) {
                window.RCAEvents.setupSSE(taskId);
            } else {
                window.RCAUtils.mainLog('RCAEvents.setupSSE not available');
            }
        }, 100);
        
        // Clear input
        const promptInput = document.getElementById('prompt-input');
        if (promptInput) {
            promptInput.value = '';
        }
    })
    .catch(error => {
        window.RCAUtils.mainLog('Error creating task:', error);
        
        // Release task creation lock
        window.TASK_LOCK.release();
        
        // Reset UI
        if (sendButton) {
            sendButton.disabled = false;
            sendButton.textContent = 'Send';
        }
        
        // Display error
        alert(`Error creating task: ${error.message}`);
    });
}

// Helper function to create a new task container
function createTaskContainer(taskId) {
    const container = document.createElement('div');
    container.id = `task-${taskId}`;
    container.className = 'task-container';
    return container;
}
