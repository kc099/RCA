/**
 * Dashboard Initialization Module
 * Integrates dashboard visualization into the main application
 */

// Initialize dashboard functionality when the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('[RCA] Initializing dashboard visualization module');
    
    // Add event handler for visualization events
    window.handleDashboardVisualization = function(eventData, container) {
        if (!eventData || !container) return false;
        
        // Try to extract visualization data
        const content = eventData.content || eventData.data || eventData.result || '';
        
        // Check for dashboard data first
        const dashboardData = window.DashboardData.extractDashboardData(content);
        if (dashboardData) {
            console.log('[RCA] Extracted dashboard data:', dashboardData);
            
            // Get output workspace
            const outputWorkspace = document.getElementById('output-workspace');
            if (outputWorkspace) {
                // Clear empty state if present
                if (outputWorkspace.querySelector('.empty-output')) {
                    outputWorkspace.innerHTML = '';
                }
                
                // Render dashboard
                window.DashboardCharts.renderDashboard(outputWorkspace, dashboardData);
                return true; // Indicate that we handled the visualization
            }
        }
        
        // Check for tabular visualization
        const visualizationData = window.DashboardData.extractToolVisualization(content);
        if (visualizationData && visualizationData.type === 'table') {
            console.log('[RCA] Extracted table visualization data');
            
            // Get output workspace
            const outputWorkspace = document.getElementById('output-workspace');
            if (outputWorkspace) {
                // Clear empty state if present
                if (outputWorkspace.querySelector('.empty-output')) {
                    outputWorkspace.innerHTML = '';
                }
                
                // Render table (assuming a renderTable function exists or using existing functionality)
                if (typeof window.renderTable === 'function') {
                    window.renderTable(outputWorkspace, visualizationData);
                    return true;
                }
            }
        }
        
        return false; // Indicate that we didn't handle any visualization
    };
    
    // Setup dashboard CSS
    const linkElement = document.createElement('link');
    linkElement.rel = 'stylesheet';
    linkElement.href = '/static/js/dashboard.css';
    document.head.appendChild(linkElement);
    
    console.log('[RCA] Dashboard visualization module initialized');
});
