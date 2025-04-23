/**
 * Main entry point for the RCA application
 * Orchestrates all the modular components
 */

/**
 * Main initialization function
 */
function initializeRCA() {
    console.log('🚀 Initializing RCA Application from core module...');
    
    // Make sure required modules are available
    if (!window.RCAUtils || !window.RCAEvents || !window.RCATasks || !window.RCAUI) {
        console.error('Required modules are not available. Initialization failed.');
        return false;
    }
    
    // Initialize UI
    if (window.RCAUI.setupUI) {
        window.RCAUI.setupUI();
    }
    
    // Setup task creation
    if (window.RCATasks.setupTaskCreation) {
        window.RCATasks.setupTaskCreation();
    }
    
    // Check user authentication and initialize active task
    if (window.RCAUtils.checkAuthentication) {
        window.RCAUtils.checkAuthentication().then(() => {
            // Initialize active task (if any)
            if (window.RCATasks.initializeActiveTask) {
                window.RCATasks.initializeActiveTask();
            }
        });
    }
    
    // Initialize language settings
    if (window.initializeLanguage) {
        window.initializeLanguage();
    }
    
    // Setup fetch interceptor to add auth tokens
    setupFetchInterceptor();
    
    console.log('✅ RCA Application initialized successfully!');
    return true;
}

/**
 * Setup fetch interceptor to add auth tokens to requests
 */
function setupFetchInterceptor() {
    // Override the original fetch to add auth token
    const originalFetch = window.fetch;
    window.fetch = function(url, options = {}) {
        // Get auth token
        const token = sessionStorage.getItem('authToken');
        
        // Add auth token to headers if available
        if (token) {
            options.headers = options.headers || {};
            options.headers['Authorization'] = `Bearer ${token}`;
        }
        
        // Call original fetch
        return originalFetch(url, options).then(handleUnauthorizedResponse);
    };
}

/**
 * Handle unauthorized responses
 */
function handleUnauthorizedResponse(response) {
    if (response.status === 401) {
        // Clear auth token
        sessionStorage.removeItem('authToken');
        
        // Redirect to login page
        window.location.href = '/login.html';
        
        // Reject the promise
        return Promise.reject(new Error('Unauthorized'));
    }
    
    return response;
}

// Wait for DOM content loaded before trying to initialize
document.addEventListener('DOMContentLoaded', function() {
    // Delay initialization to ensure all modules are loaded
    setTimeout(checkAndInitialize, 500);
});

/**
 * Check if all modules are loaded and initialize if they are
 */
function checkAndInitialize() {
    // Only auto-initialize if the wrapper hasn't already done so
    if (window.USING_MODULAR !== true) {
        console.log('Checking if all modules are loaded...');
        
        // Check if all required modules are available
        if (window.RCAUtils && window.RCAEvents && window.RCATasks && window.RCAUI) {
            console.log('All modules loaded, initializing application...');
            
            // Set flag to indicate we're using the modular architecture
            window.USING_MODULAR = true;
            
            // Initialize the application
            initializeRCA();
        } else {
            console.warn('Not all modules are loaded yet, retrying in 500ms...');
            
            // Retry after a delay
            setTimeout(checkAndInitialize, 500);
        }
    }
}

// Expose the initialization function globally for the wrapper to call
window.initializeRCA = initializeRCA;
