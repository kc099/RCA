/**
 * Dashboard visualization loader for the RCA application
 * Provides dynamic loading of dashboard visualization modules
 */

// Expose dashboard loader functions to global scope
window.ensureDashboardModulesLoaded = ensureDashboardModulesLoaded;

/**
 * Check if dashboard modules are available and load them if not
 */
function ensureDashboardModulesLoaded() {
    // Create a promise that resolves when all dashboard modules are loaded
    return new Promise((resolve, reject) => {
        // Check if all required dashboard modules are loaded
        if (window.DashboardCharts && window.DashboardData) {
            window.RCAUtils.mainLog('Dashboard modules already loaded');
            resolve();
            return;
        }

        // Count of loaded modules
        let loadedCount = 0;
        const requiredCount = 3; // We need three modules

        // Function to check if all modules are loaded
        const checkAllLoaded = () => {
            loadedCount++;
            if (loadedCount === requiredCount) {
                window.RCAUtils.mainLog('All dashboard modules loaded');
                resolve();
            }
        };

        // Load CSS
        const cssLink = document.createElement('link');
        cssLink.rel = 'stylesheet';
        cssLink.href = '/static/js/dashboard.css';
        cssLink.onload = checkAllLoaded;
        cssLink.onerror = () => reject(new Error('Failed to load dashboard CSS'));
        document.head.appendChild(cssLink);

        // Load data module
        const dataScript = document.createElement('script');
        dataScript.src = '/static/js/dashboard-data.js';
        dataScript.onload = checkAllLoaded;
        dataScript.onerror = () => reject(new Error('Failed to load dashboard data module'));
        document.head.appendChild(dataScript);

        // Load charts module
        const chartsScript = document.createElement('script');
        chartsScript.src = '/static/js/dashboard-charts.js';
        chartsScript.onload = checkAllLoaded;
        chartsScript.onerror = () => reject(new Error('Failed to load dashboard charts module'));
        document.head.appendChild(chartsScript);
    });
}
