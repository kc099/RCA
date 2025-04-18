let currentEventSource = null;
let exampleApiKey = '';
// Store output items that will be displayed in the visualization panel
let outputItems = [];

function checkConfigStatus() {
    fetch('/config/status')
    .then(response => response.json())
    .then(data => {
        const inputContainer = document.getElementById('input-container');
        if (data.status === 'missing') {
            showConfigModal(data.example_config);
            inputContainer.classList.add('disabled');
        } else if (data.status === 'no_example') {
            alert('Error: Missing configuration example file! Please ensure that the config/config.example.toml file exists.');
            inputContainer.classList.add('disabled');
        } else {
            inputContainer.classList.remove('disabled');
        }
    })
    .catch(error => {
        console.error('Configuration check failed:', error);
        document.getElementById('input-container').classList.add('disabled');
    });
}

// Display configuration pop-up and fill in sample configurations
function showConfigModal(config) {
    const configModal = document.getElementById('config-modal');
    if (!configModal) return;

    configModal.classList.add('active');

    if (config) {
        fillConfigForm(config);
    }

    const closeBtn = configModal.querySelector('.close-modal');
    const cancelBtn = document.getElementById('cancel-config-btn');

    function closeConfigModal() {
        configModal.classList.remove('active');
        document.getElementById('config-error').textContent = '';
        document.querySelectorAll('.form-group.error').forEach(group => {
            group.classList.remove('error');
        });
    }

    if (closeBtn) {
        closeBtn.onclick = closeConfigModal;
    }

    if (cancelBtn) {
        cancelBtn.onclick = closeConfigModal;
    }

    const saveButton = document.getElementById('save-config-btn');
    if (saveButton) {
        saveButton.onclick = saveConfig;
    }
}

// Use example configuration to fill in the form
function fillConfigForm(exampleConfig) {
    if (exampleConfig.llm) {
        const llm = exampleConfig.llm;

        setInputValue('llm-model', llm.model);
        setInputValue('llm-base-url', llm.base_url);
        setInputValue('llm-api-key', llm.api_key);

        exampleApiKey = llm.api_key || '';

        setInputValue('llm-max-tokens', llm.max_tokens);
        setInputValue('llm-temperature', llm.temperature);
    }

    if (exampleConfig.server) {
        setInputValue('server-host', exampleConfig.server.host);
        setInputValue('server-port', exampleConfig.server.port);
    }
}

function setInputValue(id, value) {
    const input = document.getElementById(id);
    if (input && value !== undefined) {
        input.value = value;
    }
}

function saveConfig() {
    const configData = collectFormData();

    const requiredFields = [
        { id: 'llm-model', name: 'Model Name' },
        { id: 'llm-base-url', name: 'API Base URL' },
        { id: 'llm-api-key', name: 'API Key' },
        { id: 'server-host', name: 'Server Host' },
        { id: 'server-port', name: 'Server Port' }
    ];

    let missingFields = [];
    requiredFields.forEach(field => {
        if (!document.getElementById(field.id).value.trim()) {
            missingFields.push(field.name);
        }
    });

    if (missingFields.length > 0) {
        document.getElementById('config-error').textContent =
            `Please fill in the necessary configuration information: ${missingFields.join(', ')}`;
        return;
    }

    // Check if the API key is the same as the example configuration
    const apiKey = document.getElementById('llm-api-key').value.trim();
    if (apiKey === exampleApiKey && exampleApiKey.includes('sk-')) {
        document.getElementById('config-error').textContent =
            `Please enter your own API key`;
        document.getElementById('llm-api-key').parentElement.classList.add('error');
        return;
    } else {
        document.getElementById('llm-api-key').parentElement.classList.remove('error');
    }

    fetch('/config/save', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(configData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            document.getElementById('config-modal').classList.remove('active');
            document.getElementById('input-container').classList.remove('disabled');
            alert('Configuration saved successfully! The application will use the new configuration on next startup.');
            window.location.reload();
        } else {
            document.getElementById('config-error').textContent =
                `Save failed: ${data.message}`;
        }
    })
    .catch(error => {
        document.getElementById('config-error').textContent =
            `Request error: ${error.message}`;
    });
}

// Collect form data
function collectFormData() {
    const configData = {
        llm: {
            model: document.getElementById('llm-model').value,
            base_url: document.getElementById('llm-base-url').value,
            api_key: document.getElementById('llm-api-key').value
        },
        server: {
            host: document.getElementById('server-host').value,
            port: parseInt(document.getElementById('server-port').value || '5172')
        }
    };

    const maxTokens = document.getElementById('llm-max-tokens').value;
    if (maxTokens) {
        configData.llm.max_tokens = parseInt(maxTokens);
    }

    const temperature = document.getElementById('llm-temperature').value;
    if (temperature) {
        configData.llm.temperature = parseFloat(temperature);
    }

    return configData;
}

function createTask() {
    const promptInput = document.getElementById('prompt-input');
    const prompt = promptInput.value.trim();

    if (!prompt) {
        alert("Please enter a valid prompt");
        promptInput.focus();
        return;
    }

    if (currentEventSource) {
        currentEventSource.close();
        currentEventSource = null;
    }

    const container = document.getElementById('task-container');
    container.innerHTML = '<div class="loading">Initializing task...</div>';

    fetch('/tasks', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ prompt })
    })
    .then(response => response.json())
    .then(data => {
        // Server returns { task_id: "..." } instead of { id: "..." }
        const taskId = data.task_id || data.id;
        
        if (taskId) {
            setupSSE(taskId);
            promptInput.value = '';
        } else {
            throw new Error('Invalid task response: missing task ID');
        }
    })
    .catch(error => {
        console.error('Error creating task:', error);
        container.innerHTML = `<div class="error">Error creating task: ${error.message}</div>`;
    });
}

// Event Source to handle real-time updates
function setupSSE(taskId) {
    if (!taskId) {
        console.error('Invalid task ID provided to setupSSE:', taskId);
        const container = document.getElementById('task-container');
        container.innerHTML = '<div class="error">Error: Invalid task ID</div>';
        return;
    }

    if (currentEventSource) {
        currentEventSource.close();
    }

    currentEventSource = new EventSource(`/tasks/${taskId}/events`);
    
    const container = document.getElementById('task-container');
    const stepContainer = ensureStepContainer(container);
    
    currentEventSource.onopen = function() {
        console.log(`Connected to event stream for task ${taskId}`);
    };
    
    currentEventSource.onerror = function(error) {
        console.error('EventSource error:', error);
        if (currentEventSource.readyState === EventSource.CLOSED) {
            console.log('Connection was closed');
        }
        
        // Handle error case
        const errorElement = createStepElement('error', 'Error connecting to event stream. Please try again.', new Date().toLocaleTimeString());
        stepContainer.appendChild(errorElement);
        
        // Close the connection on error
        if (currentEventSource) {
            currentEventSource.close();
            currentEventSource = null;
        }
    };
    
    // Initialize the log counter for this task
    let lastId = 0;
    
    // Helper function to safely parse JSON
    function safeJsonParse(data) {
        try {
            return JSON.parse(data);
        } catch (e) {
            console.error('JSON Parse error:', e, 'Data:', data);
            return { content: 'Error parsing response data', id: ++lastId, timestamp: new Date().toISOString() };
        }
    }
    
    // Handle different event types
    currentEventSource.addEventListener('step', function(event) {
        const data = safeJsonParse(event.data);
        lastId = data.id || ++lastId;
        
        // Check if this step contains a visualization
        const visualizationData = extractVisualization(data.content);
        if (visualizationData) {
            addVisualizationItem(visualizationData);
        }
        
        // Format the step content - removing any extracted visualization if needed
        const formattedContent = formatStepContent(data, 'step');
        const stepElement = createStepElement('step', formattedContent, data.timestamp || new Date().toLocaleTimeString());
        stepContainer.appendChild(stepElement);
        
        autoScroll(container);
    });
    
    currentEventSource.addEventListener('log', function(event) {
        const data = safeJsonParse(event.data);
        const formattedContent = formatStepContent(data, 'log');
        const logElement = createStepElement('log', formattedContent, data.timestamp || new Date().toLocaleTimeString());
        stepContainer.appendChild(logElement);
        
        autoScroll(container);
    });
    
    currentEventSource.addEventListener('think', function(event) {
        const data = safeJsonParse(event.data);
        const formattedContent = formatStepContent(data, 'think');
        const thinkElement = createStepElement('think', formattedContent, data.timestamp || new Date().toLocaleTimeString());
        stepContainer.appendChild(thinkElement);
        
        autoScroll(container);
    });
    
    currentEventSource.addEventListener('tool', function(event) {
        const data = safeJsonParse(event.data);
        
        // Check if the tool content contains a table or visualization
        const visualizationData = extractVisualization(data.content);
        if (visualizationData) {
            addVisualizationItem(visualizationData);
        }
        
        const formattedContent = formatStepContent(data, 'tool');
        const toolElement = createStepElement('tool', formattedContent, data.timestamp || new Date().toLocaleTimeString());
        stepContainer.appendChild(toolElement);
        
        autoScroll(container);
    });
    
    currentEventSource.addEventListener('result', function(event) {
        const data = safeJsonParse(event.data);
        
        // Check if the result contains a table or visualization
        const visualizationData = extractVisualization(data.content);
        if (visualizationData) {
            addVisualizationItem(visualizationData);
        }
        
        const formattedContent = formatStepContent(data, 'result');
        const resultElement = createStepElement('result', formattedContent, data.timestamp || new Date().toLocaleTimeString());
        stepContainer.appendChild(resultElement);
        
        autoScroll(container);
    });
    
    currentEventSource.addEventListener('error', function(event) {
        const data = safeJsonParse(event.data);
        const errorElement = createStepElement('error', formatStepContent(data, 'error'), data.timestamp || new Date().toLocaleTimeString());
        stepContainer.appendChild(errorElement);
        
        autoScroll(container);
    });
    
    currentEventSource.addEventListener('complete', function(event) {
        const data = safeJsonParse(event.data);
        const completeElement = createStepElement('success', formatStepContent(data, 'complete'), data.timestamp || new Date().toLocaleTimeString());
        stepContainer.appendChild(completeElement);
        
        autoScroll(container);
        
        if (currentEventSource) {
            currentEventSource.close();
            currentEventSource = null;
        }
        
        // Refresh the task list to show the updated status
        loadHistory();
    });
    
    currentEventSource.addEventListener('ping', function() {
        // Just to keep the connection alive, no UI update needed
    });
}

// Extract tables and other visualizations from content
function extractVisualization(content) {
    if (!content) return null;
    
    // Check for markdown tables
    const tableRegex = /\|[\s\S]*?\|\n[\s\S]*?\|[\s\S]*?(\n\n|\n$|$)/g;
    const tableMatches = content.match(tableRegex);
    
    if (tableMatches && tableMatches.length > 0) {
        // Parse the first table found
        const tableData = parseMarkdownTable(tableMatches[0]);
        if (tableData && tableData.headers && tableData.rows && tableData.rows.length > 0) {
            // Remove the table from the content for chat display
            const cleanedContent = content.replace(tableMatches[0], '');
            
            return {
                type: 'table',
                title: 'Generated Table',
                content: tableData,
                originalMarkdown: tableMatches[0],
                cleanedContent: cleanedContent
            };
        }
    }
    
    // TODO: Add support for other visualizations like charts, images, etc.
    
    return null;
}

// Parse a markdown table into structured data
function parseMarkdownTable(markdownTable) {
    if (!markdownTable) return null;
    
    const lines = markdownTable.trim().split('\n');
    if (lines.length < 3) return null; // Need at least header, separator, and one data row
    
    // Parse headers (first row)
    const headerLine = lines[0];
    const headers = headerLine.split('|')
        .map(h => h.trim())
        .filter(h => h.length > 0);
    
    // Skip the separator line (line[1])
    
    // Parse data rows
    const rows = [];
    for (let i = 2; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line || !line.includes('|')) continue;
        
        const cells = line.split('|')
            .map(c => c.trim())
            .filter((c, idx) => idx > 0 && idx <= headers.length);
        
        if (cells.length > 0) {
            const row = {};
            headers.forEach((header, index) => {
                row[header] = cells[index] || '';
            });
            rows.push(row);
        }
    }
    
    return { headers, rows };
}

// Add a visualization item to the output workspace
function addVisualizationItem(data) {
    const id = Date.now();
    const position = { x: 50, y: 50 };
    const size = { width: 400, height: data.type === 'table' ? 300 : 250 };
    
    const item = {
        id,
        type: data.type,
        title: data.title || 'Visualization',
        content: data.content,
        position,
        size
    };
    
    outputItems.push(item);
    renderVisualizationItems();
}

// Render all visualization items in the output workspace
function renderVisualizationItems() {
    const workspace = document.getElementById('output-workspace');
    if (!workspace) return;
    
    // Clear the empty message if there are items
    if (outputItems.length > 0) {
        workspace.innerHTML = '';
    } else {
        workspace.innerHTML = `
            <div class="empty-output">
                <p>No visualizations or data to display</p>
                <p>Use the chat to get started</p>
            </div>
        `;
        return;
    }
    
    // Render each visualization item
    outputItems.forEach(item => {
        const itemElement = document.createElement('div');
        itemElement.className = 'draggable-item';
        itemElement.id = `item-${item.id}`;
        itemElement.style.left = `${item.position.x}px`;
        itemElement.style.top = `${item.position.y}px`;
        itemElement.style.width = `${item.size.width}px`;
        itemElement.style.height = `${item.size.height}px`;
        
        // Create the item header
        const header = document.createElement('div');
        header.className = 'item-header';
        header.innerHTML = `
            <div class="item-title">${item.title}</div>
            <button class="item-close" onclick="removeVisualizationItem(${item.id})">×</button>
        `;
        
        // Create the content container
        const content = document.createElement('div');
        content.className = 'item-content';
        
        // Render different content based on type
        if (item.type === 'table') {
            content.appendChild(createTableElement(item.content));
        } else if (item.type === 'image') {
            const img = document.createElement('img');
            img.src = item.content;
            img.alt = item.title;
            content.appendChild(img);
        } else {
            content.textContent = item.content;
        }
        
        // Add resize handle
        const resizeHandle = document.createElement('div');
        resizeHandle.className = 'resize-handle';
        
        // Append all elements
        itemElement.appendChild(header);
        itemElement.appendChild(content);
        itemElement.appendChild(resizeHandle);
        workspace.appendChild(itemElement);
        
        // Setup drag and resize functionality
        setupDraggableItem(itemElement, item.id);
    });
}

// Create HTML table from the structured data
function createTableElement(tableData) {
    const table = document.createElement('table');
    table.className = 'data-table';
    
    // Create table header
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    
    tableData.headers.forEach(header => {
        const th = document.createElement('th');
        th.textContent = header;
        headerRow.appendChild(th);
    });
    
    thead.appendChild(headerRow);
    table.appendChild(thead);
    
    // Create table body
    const tbody = document.createElement('tbody');
    
    tableData.rows.forEach(row => {
        const tr = document.createElement('tr');
        
        tableData.headers.forEach(header => {
            const td = document.createElement('td');
            td.textContent = row[header] || '';
            tr.appendChild(td);
        });
        
        tbody.appendChild(tr);
    });
    
    table.appendChild(tbody);
    return table;
}

// Setup drag functionality for a visualization item
function setupDraggableItem(element, itemId) {
    let isDragging = false;
    let isResizing = false;
    let dragOffset = { x: 0, y: 0 };
    
    const header = element.querySelector('.item-header');
    const resizeHandle = element.querySelector('.resize-handle');
    const workspace = document.getElementById('output-workspace');
    
    // Drag functionality
    header.addEventListener('mousedown', function(e) {
        isDragging = true;
        element.classList.add('dragging');
        
        const rect = element.getBoundingClientRect();
        const workspaceRect = workspace.getBoundingClientRect();
        
        dragOffset = {
            x: e.clientX - (rect.left - workspaceRect.left),
            y: e.clientY - (rect.top - workspaceRect.top)
        };
        
        e.preventDefault();
    });
    
    // Resize functionality
    resizeHandle.addEventListener('mousedown', function(e) {
        isResizing = true;
        element.classList.add('resizing');
        e.stopPropagation();
        e.preventDefault();
    });
    
    // Mouse move handler for both dragging and resizing
    document.addEventListener('mousemove', function(e) {
        if (isDragging) {
            const workspaceRect = workspace.getBoundingClientRect();
            const newX = e.clientX - workspaceRect.left - dragOffset.x;
            const newY = e.clientY - workspaceRect.top - dragOffset.y;
            
            // Update position with bounds checking
            const boundedX = Math.max(0, Math.min(newX, workspaceRect.width - element.offsetWidth));
            const boundedY = Math.max(0, Math.min(newY, workspaceRect.height - element.offsetHeight));
            
            element.style.left = `${boundedX}px`;
            element.style.top = `${boundedY}px`;
            
            // Update the item in our data structure
            const itemIndex = outputItems.findIndex(item => item.id === itemId);
            if (itemIndex !== -1) {
                outputItems[itemIndex].position = { x: boundedX, y: boundedY };
            }
        } else if (isResizing) {
            const workspaceRect = workspace.getBoundingClientRect();
            const itemRect = element.getBoundingClientRect();
            
            const newWidth = e.clientX - itemRect.left;
            const newHeight = e.clientY - itemRect.top;
            
            // Minimum size constraints
            const width = Math.max(200, newWidth);
            const height = Math.max(150, newHeight);
            
            element.style.width = `${width}px`;
            element.style.height = `${height}px`;
            
            // Update the item in our data structure
            const itemIndex = outputItems.findIndex(item => item.id === itemId);
            if (itemIndex !== -1) {
                outputItems[itemIndex].size = { width, height };
            }
        }
    });
    
    // Mouse up handler to stop dragging/resizing
    document.addEventListener('mouseup', function() {
        if (isDragging || isResizing) {
            isDragging = false;
            isResizing = false;
            element.classList.remove('dragging', 'resizing');
        }
    });
}

// Remove a visualization item
function removeVisualizationItem(id) {
    outputItems = outputItems.filter(item => item.id !== id);
    renderVisualizationItems();
}

// Format the content based on event type
function formatStepContent(data, eventType) {
    // Handle null or undefined data case
    if (!data) {
        return "No data received";
    }
    
    // If this data has visualization extracted, use the cleaned content
    if (data.cleanedContent) {
        return data.cleanedContent;
    }
    
    // Handle cases where content might be missing
    return data.content || data.message || data.result || "No content available";
}

function ensureStepContainer(container) {
    let stepContainer = container.querySelector('.step-container');
    if (!stepContainer) {
        container.innerHTML = '<div class="step-container"></div>';
        stepContainer = container.querySelector('.step-container');
    }
    return stepContainer;
}

function createStepElement(type, content, timestamp) {
    const step = document.createElement('div');

    // Executing step
    const stepRegex = /Executing step (\d+)\/(\d+)/;
    if (type === 'log' && stepRegex.test(content)) {
        const match = content.match(stepRegex);
        const currentStep = parseInt(match[1]);
        const totalSteps = parseInt(match[2]);

        step.className = 'step-divider';
        step.innerHTML = `
            <div class="step-circle">${currentStep}</div>
            <div class="step-line"></div>
            <div class="step-info">${currentStep}/${totalSteps}</div>
        `;
    } else if (type === 'act') {
        // Check if it contains information about file saving
        const saveRegex = /Content successfully saved to (.+)/;
        const match = content.match(saveRegex);

        step.className = `step-item ${type}`;

        if (match && match[1]) {
            const filePath = match[1].trim();
            const fileName = filePath.split('/').pop();
            const fileExtension = fileName.split('.').pop().toLowerCase();

            // Handling different types of files
            let fileInteractionHtml = '';

            if (['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp'].includes(fileExtension)) {
                fileInteractionHtml = `
                    <div class="file-interaction image-preview">
                        <img src="${filePath}" alt="${fileName}" class="preview-image" onclick="showFullImage('${filePath}')">
                        <a href="/download?file_path=${filePath}" download="${fileName}" class="download-link">⬇️ 下载图片</a>
                    </div>
                `;
            } else if (['mp3', 'wav', 'ogg'].includes(fileExtension)) {
                fileInteractionHtml = `
                    <div class="file-interaction audio-player">
                        <audio controls src="${filePath}"></audio>
                        <a href="/download?file_path=${filePath}" download="${fileName}" class="download-link">⬇️ 下载音频</a>
                    </div>
                `;
            } else if (['html', 'js', 'py'].includes(fileExtension)) {
                fileInteractionHtml = `
                    <div class="file-interaction code-file">
                        <button onclick="simulateRunPython('${filePath}')" class="run-button">▶️ 模拟运行</button>
                        <a href="/download?file_path=${filePath}" download="${fileName}" class="download-link">⬇️ 下载文件</a>
                    </div>
                `;
            } else {
                fileInteractionHtml = `
                    <div class="file-interaction">
                        <a href="/download?file_path=${filePath}" download="${fileName}" class="download-link">⬇️ 下载文件: ${fileName}</a>
                    </div>
                `;
            }

            step.innerHTML = `
                <div class="log-line">
                    <span class="log-prefix">${getEventIcon(type)} [${timestamp}] ${getEventLabel(type)}:</span>
                    <pre>${content}</pre>
                    ${fileInteractionHtml}
                </div>
            `;
        } else {
            step.innerHTML = `
                <div class="log-line">
                    <span class="log-prefix">${getEventIcon(type)} [${timestamp}] ${getEventLabel(type)}:</span>
                    <pre>${content}</pre>
                </div>
            `;
        }
    } else {
        step.className = `step-item ${type}`;
        step.innerHTML = `
            <div class="log-line">
                <span class="log-prefix">${getEventIcon(type)} [${timestamp}] ${getEventLabel(type)}:</span>
                <pre>${content}</pre>
            </div>
        `;
    }
    return step;
}

function autoScroll(element) {
    requestAnimationFrame(() => {
        element.scrollTo({
            top: element.scrollHeight,
            behavior: 'smooth'
        });
    });
    setTimeout(() => {
        element.scrollTop = element.scrollHeight;
    }, 100);
}

function getEventIcon(eventType) {
    const icons = {
        'think': '🤔',
        'tool': '🛠️',
        'act': '🚀',
        'result': '🏁',
        'error': '❌',
        'complete': '✅',
        'log': '📝',
        'run': '⚙️'
    };
    return icons[eventType] || 'ℹ️';
}

function getEventLabel(eventType) {
    const labels = {
        'think': 'Thinking',
        'tool': 'Using Tool',
        'act': 'Action',
        'result': 'Result',
        'error': 'Error',
        'complete': 'Complete',
        'log': 'Log',
        'run': 'Running'
    };
    return labels[eventType] || 'Info';
}

function updateTaskStatus(task) {
    const statusBar = document.getElementById('status-bar');
    if (!statusBar) return;

    if (task.status === 'completed') {
        statusBar.innerHTML = `<span class="status-complete">✅ Task completed</span>`;

        if (currentEventSource) {
            currentEventSource.close();
            currentEventSource = null;
        }
    } else if (task.status === 'failed') {
        statusBar.innerHTML = `<span class="status-error">❌ Task failed: ${task.error || 'Unknown error'}</span>`;

        if (currentEventSource) {
            currentEventSource.close();
            currentEventSource = null;
        }
    } else {
        statusBar.innerHTML = `<span class="status-running">⚙️ Task running: ${task.status}</span>`;
    }
}

// Display full screen image
function showFullImage(imageSrc) {
    const modal = document.getElementById('image-modal');
    if (!modal) {
        const modalDiv = document.createElement('div');
        modalDiv.id = 'image-modal';
        modalDiv.className = 'image-modal';
        modalDiv.innerHTML = `
            <span class="close-modal">&times;</span>
            <img src="${imageSrc}" class="modal-content" id="full-image">
        `;
        document.body.appendChild(modalDiv);

        const closeBtn = modalDiv.querySelector('.close-modal');
        closeBtn.addEventListener('click', () => {
            modalDiv.classList.remove('active');
        });

        modalDiv.addEventListener('click', (e) => {
            if (e.target === modalDiv) {
                modalDiv.classList.remove('active');
            }
        });

        setTimeout(() => modalDiv.classList.add('active'), 10);
    } else {
        document.getElementById('full-image').src = imageSrc;
        modal.classList.add('active');
    }
}

// Simulate running Python files
function simulateRunPython(filePath) {
    let modal = document.getElementById('python-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'python-modal';
        modal.className = 'python-modal';
        modal.innerHTML = `
            <div class="python-console">
                <div class="close-modal">&times;</div>
                <div class="python-output">Loading Python file contents...</div>
            </div>
        `;
        document.body.appendChild(modal);

        const closeBtn = modal.querySelector('.close-modal');
        closeBtn.addEventListener('click', () => {
            modal.classList.remove('active');
        });
    }

    modal.classList.add('active');

    // Load Python file content
    fetch(filePath)
        .then(response => response.text())
        .then(code => {
            const outputDiv = modal.querySelector('.python-output');
            outputDiv.innerHTML = '';

            const codeElement = document.createElement('pre');
            codeElement.textContent = code;
            codeElement.style.marginBottom = '20px';
            codeElement.style.padding = '10px';
            codeElement.style.borderBottom = '1px solid #444';
            outputDiv.appendChild(codeElement);

            // Add simulation run results
            const resultElement = document.createElement('div');
            resultElement.innerHTML = `
                <div style="color: #4CAF50; margin-top: 10px; margin-bottom: 10px;">
                    > Simulated operation output:</div>
                <pre style="color: #f8f8f8;">
#This is the result of Python code simulation run
#The actual operational results may vary

# Running ${filePath.split('/').pop()}...
print("Hello from Python Simulated environment!")

# Code execution completed
</pre>
            `;
            outputDiv.appendChild(resultElement);
        })
        .catch(error => {
            console.error('Error loading Python file:', error);
            const outputDiv = modal.querySelector('.python-output');
            outputDiv.innerHTML = `Error loading file: ${error.message}`;
        });
}

function loadHistory() {
    fetch('/tasks')
    .then(response => {
        if (!response.ok) {
            return response.text().then(text => {
                throw new Error(`request failure: ${response.status} - ${text.substring(0, 100)}`);
            });
        }
        return response.json();
    })
    .then(tasks => {
        const listContainer = document.getElementById('task-list');
        listContainer.innerHTML = tasks.map(task => `
            <div class="task-card" data-task-id="${task.id}">
                <div>${task.prompt}</div>
                <div class="task-meta">
                    ${new Date(task.created_at).toLocaleString()} -
                    <span class="status status-${task.status ? task.status.toLowerCase() : 'unknown'}">
                        ${task.status || 'Unknown state'}
                    </span>
                </div>
            </div>
        `).join('');
    })
    .catch(error => {
        console.error('Failed to load history records:', error);
        const listContainer = document.getElementById('task-list');
        listContainer.innerHTML = `<div class="error">Load Fail: ${error.message}</div>`;
    });
}

// Panel resize functionality
function initializePanelResize() {
    const chatPanel = document.getElementById('chat-panel');
    const resizeHandle = document.getElementById('panel-resize-handle');
    const contentContainer = document.querySelector('.content-container');
    
    if (!chatPanel || !resizeHandle || !contentContainer) return;
    
    let isResizing = false;
    let startX, startWidth;
    
    // Initialize resize handle position
    resizeHandle.style.left = `${chatPanel.offsetWidth}px`;
    
    // When user presses mouse button on the resize handle
    resizeHandle.addEventListener('mousedown', function(e) {
        isResizing = true;
        startX = e.clientX;
        startWidth = chatPanel.offsetWidth;
        
        resizeHandle.classList.add('resizing');
        contentContainer.classList.add('resizing');
        
        e.preventDefault();
    });
    
    // When user moves the mouse after pressing the resize handle
    document.addEventListener('mousemove', function(e) {
        if (!isResizing) return;
        
        // Calculate new width
        const containerWidth = contentContainer.offsetWidth;
        const newWidth = startWidth + (e.clientX - startX);
        
        // Apply constraints: min-width 250px, max-width 50% of container
        const minWidth = 250;
        const maxWidth = containerWidth * 0.5;
        
        let appliedWidth = Math.max(minWidth, Math.min(newWidth, maxWidth));
        
        // Update chat panel width
        chatPanel.style.width = `${appliedWidth}px`;
        
        // Update resize handle position
        resizeHandle.style.left = `${appliedWidth}px`;
    });
    
    // When user releases the mouse button
    document.addEventListener('mouseup', function() {
        if (isResizing) {
            isResizing = false;
            resizeHandle.classList.remove('resizing');
            contentContainer.classList.remove('resizing');
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    // Check configuration status on startup
    checkConfigStatus();

    // Load task history
    loadHistory();

    // Setup language selector
    const languageSelect = document.getElementById('language-select');
    if (languageSelect) {
        languageSelect.addEventListener('change', function() {
            setLanguage(this.value);
        });
    }

    // Setup configuration button event
    const configButton = document.getElementById('config-button');
    if (configButton) {
        configButton.addEventListener('click', function() {
            fetch('/config/status')
                .then(response => response.json())
                .then(data => {
                    showConfigModal(data.example_config);
                })
                .catch(error => {
                    console.error('Config status check failed:', error);
                });
        });
    }

    // Initialize task history click events
    const taskList = document.getElementById('task-list');
    if (taskList) {
        taskList.addEventListener('click', function(event) {
            const taskCard = event.target.closest('.task-card');
            if (taskCard) {
                const taskId = taskCard.dataset.taskId;
                if (taskId) {
                    setupSSE(taskId);
                    
                    // Highlight the selected task
                    document.querySelectorAll('.task-card').forEach(card => {
                        card.classList.remove('active');
                    });
                    taskCard.classList.add('active');
                }
            }
        });
    }

    // Initialize panel resize functionality
    initializePanelResize();
});

function isConfigRequired() {
    return false;
}
