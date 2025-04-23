/**
 * UI functionality for the RCA application
 */

// Expose UI functions to global scope
window.RCAUI = {
    setupUI,
    setupStyles,
    showConfigModal,
    saveConfig,
    fillConfigForm,
    showFullImage
};

/**
 * Setup UI components and event handlers
 */
function setupUI() {
    console.log('Setting up UI components');
    
    // Initialize UI elements
    setupConfigButton();
    setupPanelResizing();
    setupUserMenu();
    
    // Check configuration status
    checkConfigStatus();
}

/**
 * Set up configuration button
 */
function setupConfigButton() {
    console.log('Setting up config button');
    const configButton = document.getElementById('config-button');
    if (!configButton) {
        console.error('Config button not found');
        return;
    }
    
    const configModal = document.getElementById('config-modal');
    if (!configModal) {
        console.error('Config modal not found');
        return;
    }
    
    // Setup config button click handler
    configButton.addEventListener('click', function() {
        console.log('Config button clicked');
        configModal.style.display = 'block';
        checkConfigStatus().then(config => {
            showConfigModal(config);
        });
    });
    
    // Setup close button
    const closeButton = configModal.querySelector('.close-modal');
    if (closeButton) {
        closeButton.addEventListener('click', function() {
            configModal.style.display = 'none';
        });
    }
    
    // Setup cancel button
    const cancelButton = document.getElementById('cancel-config-btn');
    if (cancelButton) {
        cancelButton.addEventListener('click', function() {
            configModal.style.display = 'none';
        });
    }
    
    // Setup save button
    const saveButton = document.getElementById('save-config-btn');
    if (saveButton) {
        saveButton.addEventListener('click', saveConfig);
    }
    
    // Close modal when clicking outside
    window.addEventListener('click', function(event) {
        if (event.target === configModal) {
            configModal.style.display = 'none';
        }
    });
}

/**
 * Set up panel resizing
 */
function setupPanelResizing() {
    const resizeHandle = document.getElementById('panel-resize-handle');
    if (!resizeHandle) return;
    
    const chatPanel = document.getElementById('chat-panel');
    if (!chatPanel) return;
    
    let isResizing = false;
    let startX = 0;
    let startWidth = 0;
    
    // Start resize on mousedown
    resizeHandle.addEventListener('mousedown', function(e) {
        isResizing = true;
        startX = e.clientX;
        startWidth = chatPanel.offsetWidth;
        
        // Add resizing class
        document.body.classList.add('resizing');
    });
    
    // Stop resize on mouseup
    document.addEventListener('mouseup', function() {
        if (isResizing) {
            isResizing = false;
            document.body.classList.remove('resizing');
        }
    });
    
    // Resize on mousemove
    document.addEventListener('mousemove', function(e) {
        if (!isResizing) return;
        
        // Calculate delta
        const delta = e.clientX - startX;
        
        // Update width
        const newWidth = startWidth + delta;
        
        // Apply constraints
        const minWidth = 250;
        const maxWidth = window.innerWidth * 0.8;
        
        if (newWidth >= minWidth && newWidth <= maxWidth) {
            chatPanel.style.width = newWidth + 'px';
        }
    });
    
    // Handle window resize
    window.addEventListener('resize', function() {
        // Ensure chat panel width is within constraints
        const maxWidth = window.innerWidth * 0.8;
        if (chatPanel.offsetWidth > maxWidth) {
            chatPanel.style.width = maxWidth + 'px';
        }
    });
}

/**
 * Setup user menu dropdown
 */
function setupUserMenu() {
    console.log('Setting up user menu');
    const userMenu = document.getElementById('user-menu');
    if (!userMenu) {
        console.error('User menu not found');
        return;
    }
    
    const userProfile = userMenu.querySelector('.user-profile');
    if (!userProfile) {
        console.error('User profile not found');
        return;
    }
    
    const dropdown = userMenu.querySelector('.user-menu-dropdown');
    if (!dropdown) {
        console.error('User dropdown not found');
        return;
    }
    
    // Toggle dropdown on click
    userProfile.addEventListener('click', function(e) {
        console.log('User profile clicked, toggling dropdown');
        dropdown.classList.toggle('active');
        
        // Force dropdown to be visible for debugging
        if (!dropdown.classList.contains('active')) {
            dropdown.classList.add('active');
        }
        
        // Add explicit styling to ensure it's visible
        dropdown.style.display = 'block';
        dropdown.style.visibility = 'visible';
        dropdown.style.opacity = '1';
        dropdown.style.zIndex = '1000';
        
        // Stop event propagation
        e.stopPropagation();
    });
    
    // Close dropdown when clicking outside
    document.addEventListener('click', function(event) {
        if (!userMenu.contains(event.target)) {
            dropdown.classList.remove('active');
            
            // Reset explicit styling
            dropdown.style.display = '';
            dropdown.style.visibility = '';
            dropdown.style.opacity = '';
            dropdown.style.zIndex = '';
        }
    });
    
    // Setup logout button
    const logoutButton = dropdown.querySelector('.logout');
    if (logoutButton) {
        logoutButton.addEventListener('click', function() {
            console.log('Logout clicked');
            // Clear auth token
            sessionStorage.removeItem('authToken');
            
            // Redirect to login page
            window.location.href = '/login.html';
        });
    }
}

/**
 * Check configuration status
 */
function checkConfigStatus() {
    return fetch('/api/config/status')
        .then(response => {
            if (!response.ok) {
                throw new Error(`Failed to get config status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Config status:', data);
            
            // Check if config is required
            if (data.configRequired) {
                // Store in localStorage
                localStorage.setItem('configRequired', 'true');
                
                // Show config modal
                showConfigModal(data.config || {});
            } else {
                // Clear flag from localStorage
                localStorage.removeItem('configRequired');
                
                // Check if server field is present, if not, set defaults
                if (data.config && !data.config.server) {
                    data.config.server = {
                        host: 'localhost',
                        port: 5172
                    };
                    
                    // Log notification about using default server config
                    console.log('Server configuration missing, using defaults:', data.config.server);
                }
            }
            
            return data.config || {};
        })
        .catch(error => {
            console.log('Error checking config status:', error);
            return {};
        });
}

/**
 * Show configuration modal
 */
function showConfigModal(config) {
    console.log('Showing config modal with config:', config);
    
    // Get config modal
    const configModal = document.getElementById('config-modal');
    if (!configModal) return;
    
    // Fill form with current config
    fillConfigForm(config);
    
    // Show modal
    configModal.style.display = 'block';
}

/**
 * Fill config form with values
 */
function fillConfigForm(config) {
    console.log('Filling config form with:', config);
    
    if (!config) return;
    
    // Helper function to set input value
    function setInputValue(id, value) {
        const input = document.getElementById(id);
        if (input && value !== undefined && value !== null) {
            input.value = value;
        }
    }
    
    // LLM config
    if (config.llm) {
        setInputValue('llm-model', config.llm.model);
        setInputValue('llm-base-url', config.llm.base_url);
        setInputValue('llm-api-key', config.llm.api_key);
        setInputValue('llm-max-tokens', config.llm.max_tokens);
        setInputValue('llm-temperature', config.llm.temperature);
    }
    
    // Server config
    if (config.server) {
        setInputValue('server-host', config.server.host);
        setInputValue('server-port', config.server.port);
    }
}

/**
 * Save configuration
 */
function saveConfig() {
    console.log('Saving config');
    
    // Get form data
    const formData = collectFormData();
    
    // Get error container
    const errorContainer = document.getElementById('config-error');
    if (errorContainer) {
        errorContainer.textContent = '';
    }
    
    // Validate form data
    let hasError = false;
    
    // Check required fields
    const requiredFields = [
        { id: 'llm-model', label: 'Model Name' },
        { id: 'llm-base-url', label: 'API Base URL' },
        { id: 'llm-api-key', label: 'API Key' },
        { id: 'server-host', label: 'Host' },
        { id: 'server-port', label: 'Port' }
    ];
    
    for (const field of requiredFields) {
        const input = document.getElementById(field.id);
        if (!input || !input.value.trim()) {
            if (errorContainer) {
                errorContainer.textContent = `${field.label} is required`;
            }
            hasError = true;
            break;
        }
    }
    
    if (hasError) return;
    
    // Save config
    fetch('/api/config/save', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Failed to save config: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Config saved:', data);
        
        // Hide modal
        const configModal = document.getElementById('config-modal');
        if (configModal) {
            configModal.style.display = 'none';
        }
        
        // Reload page if needed
        if (data.reload) {
            window.location.reload();
        }
        
        // Update config status
        localStorage.removeItem('configRequired');
    })
    .catch(error => {
        console.log('Error saving config:', error);
        
        // Display error
        if (errorContainer) {
            errorContainer.textContent = `Error saving config: ${error.message}`;
        }
    });
}

/**
 * Collect form data
 */
function collectFormData() {
    const data = {
        llm: {
            model: document.getElementById('llm-model')?.value.trim(),
            base_url: document.getElementById('llm-base-url')?.value.trim(),
            api_key: document.getElementById('llm-api-key')?.value,
            max_tokens: parseInt(document.getElementById('llm-max-tokens')?.value || '0'),
            temperature: parseFloat(document.getElementById('llm-temperature')?.value || '0')
        },
        server: {
            host: document.getElementById('server-host')?.value.trim(),
            port: parseInt(document.getElementById('server-port')?.value || '0')
        }
    };
    
    return data;
}

/**
 * Display full screen image
 */
function showFullImage(imageSrc) {
    console.log('Showing full image:', imageSrc);
    
    // Create overlay
    const overlay = document.createElement('div');
    overlay.className = 'image-overlay';
    
    // Create image
    const image = document.createElement('img');
    image.src = imageSrc;
    image.alt = 'Full size image';
    
    // Create close button
    const closeButton = document.createElement('button');
    closeButton.className = 'close-button';
    closeButton.innerHTML = '&times;';
    closeButton.addEventListener('click', function() {
        document.body.removeChild(overlay);
    });
    
    // Add elements to overlay
    overlay.appendChild(closeButton);
    overlay.appendChild(image);
    
    // Add overlay to body
    document.body.appendChild(overlay);
    
    // Close on click outside image
    overlay.addEventListener('click', function(event) {
        if (event.target === overlay) {
            document.body.removeChild(overlay);
        }
    });
}

/**
 * Setup default styles
 */
function setupStyles() {
    // Add overlay styles if not already present
    if (!document.getElementById('rca-dynamic-styles')) {
        const styleElement = document.createElement('style');
        styleElement.id = 'rca-dynamic-styles';
        styleElement.textContent = `
            .image-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0, 0, 0, 0.8);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 1000;
            }
            
            .image-overlay img {
                max-width: 90%;
                max-height: 90%;
                border: 2px solid white;
            }
            
            .image-overlay .close-button {
                position: absolute;
                top: 20px;
                right: 20px;
                background: white;
                border: none;
                border-radius: 50%;
                width: 30px;
                height: 30px;
                font-size: 20px;
                line-height: 1;
                cursor: pointer;
            }
            
            body.resizing {
                cursor: col-resize;
                user-select: none;
            }
        `;
        document.head.appendChild(styleElement);
    }
}
