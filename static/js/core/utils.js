/**
 * Core utility functions for the RCA application
 */

// Define the utility functions first
/**
 * Add a debug log helper - enhanced version
 */
function mainLog(message, data = null) {
    if (typeof console !== 'undefined' && console.log) {
        if (data !== null) {
            console.log(`[RCA]`, message, data);
        } else {
            console.log(`[RCA]`, message);
        }
    }
}

/**
 * Ensure a DOM element exists
 */
function ensureExists(selector, timeout = 5000) {
    return new Promise((resolve, reject) => {
        const element = document.querySelector(selector);
        if (element) {
            resolve(element);
            return;
        }

        const startTime = Date.now();
        const interval = setInterval(() => {
            const element = document.querySelector(selector);
            if (element) {
                clearInterval(interval);
                resolve(element);
                return;
            }

            if (Date.now() - startTime > timeout) {
                clearInterval(interval);
                reject(new Error(`Element ${selector} not found within ${timeout}ms`));
            }
        }, 100);
    });
}

/**
 * Auto-scroll an element to the bottom
 */
function autoScroll(element) {
    if (!element) return;
    
    element.scrollTop = element.scrollHeight;
}

/**
 * Get the appropriate icon for an event type
 */
function getEventIcon(eventType) {
    const icons = {
        'message': '💬',
        'step': '🔄',
        'completion': '✅',
        'error': '❌',
        'warning': '⚠️',
        'info': '📝',
        'visualization': '📊',
        'thinking': '🤔',
        'tool': '🛠️',
        'action': '🎬',
        'system': '⚙️'
    };
    
    return icons[eventType] || '📝';
}

/**
 * Get the appropriate label for an event type
 */
function getEventLabel(eventType) {
    const labels = {
        'message': 'Message',
        'step': 'Step',
        'completion': 'Complete',
        'error': 'Error',
        'warning': 'Warning',
        'info': 'Info',
        'visualization': 'Visualization',
        'thinking': 'Thinking',
        'tool': 'Tool',
        'action': 'Action',
        'system': 'System'
    };
    
    return labels[eventType] || 'Info';
}

/**
 * Check if configuration is required
 */
function isConfigRequired() {
    // Logic to check if config is required
    return localStorage.getItem('configRequired') === 'true';
}

/**
 * Check if user is authenticated
 */
function isAuthenticated() {
    // Get token from session storage
    const token = sessionStorage.getItem('authToken');
    
    // Check if token exists and is not expired
    if (!token) {
        return false;
    }
    
    try {
        // Decode the JWT token to check expiration
        const tokenData = JSON.parse(atob(token.split('.')[1]));
        const currentTime = Math.floor(Date.now() / 1000);
        
        // Check if token is expired
        if (tokenData.exp && tokenData.exp < currentTime) {
            // Token is expired
            sessionStorage.removeItem('authToken');
            return false;
        }
        
        return true;
    } catch (error) {
        console.error('Error checking authentication:', error);
        return false;
    }
}

/**
 * Check authentication status and handle accordingly
 */
function checkAuthentication() {
    if (isAuthenticated()) {
        // Set up the username display
        const tokenData = JSON.parse(atob(sessionStorage.getItem('authToken').split('.')[1]));
        const usernameDisplay = document.getElementById('username-display');
        const userAvatar = document.getElementById('user-avatar');
        
        if (usernameDisplay) {
            usernameDisplay.textContent = tokenData.username || 'User';
        }
        
        if (userAvatar) {
            userAvatar.textContent = (tokenData.username || 'U').charAt(0).toUpperCase();
        }
        
        return Promise.resolve(true);
    } else {
        // Redirect to login page if not on login page
        if (!window.location.pathname.includes('login.html')) {
            window.location.href = '/login.html';
        }
        return Promise.resolve(false);
    }
}

/**
 * Extract visualization from content
 */
function extractVisualization(content) {
    // Logic to extract visualization data from content
    if (!content) return null;
    
    try {
        // Implementation details...
        return null;
    } catch (error) {
        mainLog('Error extracting visualization:', error);
        return null;
    }
}

// NOW expose utilities to global scope AFTER all functions are defined
window.RCAUtils = {
    mainLog,
    isConfigRequired,
    isAuthenticated,
    checkAuthentication,
    extractVisualization,
    ensureExists,
    autoScroll,
    getEventIcon,
    getEventLabel
};
