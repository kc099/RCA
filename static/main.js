/**
 * Main entry point for the RCA application
 * This file serves as a wrapper around the modular core components
 * For backward compatibility, it continues to expose global functions
 */

// Debug mode flag
window.DEBUG_MODE = true;

// Add a debug log helper - enhanced version
function mainLog(message, data = null) {
    if (typeof console !== 'undefined' && console.log) {
        if (data !== null) {
            console.log(`[RCA]`, message, data);
        } else {
            console.log(`[RCA]`, message);
        }
    }
}

// Global task creation lock - kept here for backward compatibility
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

// Initialize application when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log(' Initializing RCA Application...');
    mainLog('DOM content loaded, initializing application using modular architecture');
    
    // Track if we're using the modular architecture or fallback to legacy
    window.USING_MODULAR = false;
    
    // Try to use modular architecture
    if (document.querySelector('script[src*="/static/js/core/main.js"]')) {
        // Scripts are already being loaded by HTML
        window.USING_MODULAR = true;
        
        // Check if modules are available after a short delay
        setTimeout(() => {
            if (window.RCAUI && window.RCATasks && window.RCAEvents && window.RCAUtils) {
                mainLog('All core modules loaded, initializing application');
                // Expose the initialization function that core/main.js will look for
                window.initializeRCA = function() {
                    // Already initialized in core/main.js
                    mainLog('Application initialized by core modules');
                };
            } else {
                mainLog('Core modules not available, falling back to legacy mode');
                window.USING_MODULAR = false;
                initializeLegacy();
            }
        }, 500);
    } else {
        // No modules in HTML, try to load them dynamically
        loadCoreModules().then(() => {
            // Initialize the application through the core main module
            if (window.RCAUI && window.RCATasks && window.RCAEvents && window.RCAUtils) {
                window.USING_MODULAR = true;
                mainLog('All core modules loaded, initializing application');
                
                // Call main initialization function if available
                if (window.initializeRCA) {
                    window.initializeRCA();
                } else {
                    // Fallback initialization
                    window.RCAUI.setupUI();
                    window.RCATasks.setupTaskCreation();
                    
                    // Check user authentication and initialize active task
                    window.RCAUtils.checkAuthentication().then(() => {
                        window.RCATasks.initializeActiveTask();
                    });
                }
            } else {
                mainLog('Error: Some core modules failed to load');
                initializeLegacy();
            }
        }).catch(error => {
            mainLog('Failed to load core modules:', error);
            initializeLegacy();
        });
    }
});

/**
 * Fallback to legacy initialization if modules fail to load
 */
function initializeLegacy() {
    mainLog('Falling back to legacy initialization');
    // Here you would add code to initialize the application using the
    // legacy monolithic approach (if needed)
    alert('Module loading failed. Please check the console for errors.');
}

/**
 * Load all core modules
 */
function loadCoreModules() {
    mainLog('Loading core modules');
    
    return new Promise((resolve, reject) => {
        const modules = [
            '/static/js/core/utils.js',
            '/static/js/core/events.js',
            '/static/js/core/tasks.js',
            '/static/js/core/ui.js',
            '/static/js/core/dashboard-loader.js',
            '/static/js/core/main.js'
        ];
        
        let loadedCount = 0;
        const totalModules = modules.length;
        
        modules.forEach(modulePath => {
            const script = document.createElement('script');
            script.src = modulePath;
            
            script.onload = () => {
                loadedCount++;
                mainLog(`Module loaded (${loadedCount}/${totalModules}): ${modulePath}`);
                
                if (loadedCount === totalModules) {
                    mainLog('All core modules loaded');
                    resolve();
                }
            };
            
            script.onerror = (error) => {
                mainLog(`Error loading module: ${modulePath}`, error);
                reject(new Error(`Failed to load module: ${modulePath}`));
            };
            
            document.head.appendChild(script);
        });
    });
}

// Expose core functions globally for backward compatibility
window.mainLog = mainLog;

// For backward compatibility, provide stubs for commonly used functions
// These will be replaced by the actual implementations once modules are loaded
window.createTask = function(promptText) {
    // Defer to the actual implementation once loaded
    if (window.RCATasks && window.RCATasks.createTask) {
        return window.RCATasks.createTask(promptText);
    } else {
        console.error('Task management module not loaded yet');
        
        // Simple fallback implementation
        fetch('/api/task/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: promptText || document.getElementById('prompt-input')?.value })
        }).then(response => response.json())
        .then(data => {
            console.log('Task created:', data);
            location.reload(); // Simple reload to show the new task
        })
        .catch(error => console.error('Error creating task:', error));
    }
};

// More backward compatibility stubs
window.setupUI = function() {
    if (window.RCAUI && window.RCAUI.setupUI) {
        return window.RCAUI.setupUI();
    } else {
        console.warn('UI module not loaded yet');
    }
};

window.checkAuthentication = function() {
    if (window.RCAUtils && window.RCAUtils.checkAuthentication) {
        return window.RCAUtils.checkAuthentication();
    } else {
        console.warn('Utils module not loaded yet');
        return Promise.resolve(false);
    }
};

// Expose ensureDashboardModulesLoaded globally for backward compatibility
window.ensureDashboardModulesLoaded = function() {
    if (window.ensureDashboardModulesLoaded) {
        return window.ensureDashboardModulesLoaded();
    } else {
        console.warn('Dashboard loader not available');
        return Promise.resolve();
    }
};
