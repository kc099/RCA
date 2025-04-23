/**
 * Dashboard Charts Module
 * Provides functions for loading Plotly.js and rendering various chart types
 */

// Expose necessary functions to the global scope
window.DashboardCharts = {
    loadPlotlyLibrary,
    renderDashboard,
    renderChart
};

/**
 * Load Plotly.js library dynamically
 * @returns {Promise} Resolves when Plotly is loaded
 */
function loadPlotlyLibrary() {
    return new Promise((resolve, reject) => {
        // Skip loading if already present
        if (window.Plotly) {
            console.log('[RCA] Plotly already loaded');
            return resolve(window.Plotly);
        }
        
        console.log('[RCA] Loading Plotly.js...');
        const script = document.createElement('script');
        script.src = 'https://cdn.plot.ly/plotly-2.20.0.min.js';
        script.integrity = 'sha384-xWRkgkV5gIlbKU6k0JdHZbJXkIzK4ETBpwB1zYvCZfbx4+on1NCvwYHD7xMQcas';
        script.crossOrigin = 'anonymous';
        script.onload = () => {
            console.log('[RCA] Plotly loaded successfully');
            resolve(window.Plotly);
        };
        script.onerror = (error) => {
            console.error('[RCA] Error loading Plotly:', error);
            reject(new Error('Failed to load Plotly library'));
        };
        document.head.appendChild(script);
    });
}

/**
 * Render a dashboard with multiple charts
 * @param {HTMLElement} container - Container element to render the dashboard in
 * @param {Object} dashboardData - Dashboard configuration data
 */
function renderDashboard(container, dashboardData) {
    // First load Plotly library if not already loaded
    loadPlotlyLibrary().then(() => {
        try {
            console.log('[RCA] Rendering dashboard with data:', dashboardData);
            
            // Create dashboard container
            const dashboardContainer = document.createElement('div');
            dashboardContainer.className = 'dashboard-container';
            dashboardContainer.id = dashboardData.id || `dashboard-${Date.now()}`;
            
            // Add dashboard title
            const titleElement = document.createElement('h2');
            titleElement.className = 'dashboard-title';
            titleElement.textContent = dashboardData.title || 'Dashboard';
            dashboardContainer.appendChild(titleElement);
            
            // Create chart grid
            const chartGrid = document.createElement('div');
            chartGrid.className = 'dashboard-grid';
            dashboardContainer.appendChild(chartGrid);
            
            // Render each chart
            const charts = dashboardData.charts || [];
            if (charts.length > 0) {
                charts.forEach((chartConfig, index) => {
                    // Create chart container
                    const chartContainer = document.createElement('div');
                    chartContainer.className = 'chart-container';
                    chartContainer.id = `chart-${index}-${Date.now()}`;
                    chartGrid.appendChild(chartContainer);
                    
                    try {
                        // Render chart
                        renderChart(chartContainer, chartConfig);
                    } catch (err) {
                        console.error('[RCA] Error rendering chart:', err);
                        chartContainer.innerHTML = `
                            <div class="chart-error">
                                <p>Error rendering chart: ${err.message}</p>
                            </div>
                        `;
                    }
                });
            } else {
                // No charts to show
                const noChartsMessage = document.createElement('div');
                noChartsMessage.className = 'chart-error';
                noChartsMessage.textContent = 'No charts to display';
                dashboardContainer.appendChild(noChartsMessage);
            }
            
            // Add the dashboard to the container
            container.appendChild(dashboardContainer);
            
        } catch (error) {
            console.error('[RCA] Error rendering dashboard:', error);
            container.innerHTML += `
                <div class="dashboard-container">
                    <h2 class="dashboard-title">Dashboard Error</h2>
                    <div class="chart-error">
                        <p>Error rendering dashboard: ${error.message}</p>
                    </div>
                </div>
            `;
        }
    }).catch(error => {
        console.error('[RCA] Error loading Plotly library:', error);
        container.innerHTML += `
            <div class="dashboard-container">
                <h2 class="dashboard-title">Dashboard Error</h2>
                <div class="chart-error">
                    <p>Error loading visualization library: ${error.message}</p>
                </div>
            </div>
        `;
    });
}

/**
 * Render a single chart
 * @param {HTMLElement} container - Container element to render the chart in
 * @param {Object} chartConfig - Chart configuration data
 */
function renderChart(container, chartConfig) {
    if (!window.Plotly) {
        throw new Error('Plotly library not loaded');
    }
    
    if (!chartConfig || !chartConfig.type) {
        throw new Error('Invalid chart configuration');
    }
    
    console.log('[RCA] Rendering chart with config:', chartConfig);
    
    // Create a data object for Plotly
    let data = [];
    let layout = {
        title: chartConfig.title || '',
        margin: { t: 30, l: 50, r: 20, b: 50 },
        xaxis: chartConfig.xaxis || {},
        yaxis: chartConfig.yaxis || {}
    };
    
    // Add appropriate chart type
    switch (chartConfig.type.toLowerCase()) {
        case 'bar':
            data = [{
                type: 'bar',
                x: chartConfig.x || [],
                y: chartConfig.y || [],
                marker: {
                    color: chartConfig.color || 'rgba(55, 128, 191, 0.7)'
                },
                name: chartConfig.name || 'Data'
            }];
            break;
            
        case 'line':
            data = [{
                type: 'scatter',
                mode: 'lines+markers',
                x: chartConfig.x || [],
                y: chartConfig.y || [],
                line: {
                    color: chartConfig.color || 'rgba(55, 128, 191, 0.7)',
                    width: 2
                },
                marker: {
                    size: 6,
                    color: chartConfig.markerColor || 'rgba(55, 128, 191, 1.0)'
                },
                name: chartConfig.name || 'Data'
            }];
            break;
            
        case 'pie':
            data = [{
                type: 'pie',
                labels: chartConfig.labels || [],
                values: chartConfig.values || [],
                textinfo: 'label+percent',
                insidetextorientation: 'radial',
                marker: {
                    colors: chartConfig.colors || null
                }
            }];
            // Override layout for pie charts
            layout = {
                title: chartConfig.title || '',
                margin: { t: 30, l: 20, r: 20, b: 20 },
                showlegend: true,
                legend: {
                    orientation: 'h',
                    y: -0.2
                }
            };
            break;
            
        case 'scatter':
            data = [{
                type: 'scatter',
                mode: 'markers',
                x: chartConfig.x || [],
                y: chartConfig.y || [],
                marker: {
                    size: chartConfig.size || 10,
                    color: chartConfig.color || 'rgba(55, 128, 191, 0.7)',
                    opacity: 0.7
                },
                name: chartConfig.name || 'Data'
            }];
            break;
            
        case 'heatmap':
            data = [{
                type: 'heatmap',
                z: chartConfig.z || [],
                x: chartConfig.x || [],
                y: chartConfig.y || [],
                colorscale: chartConfig.colorscale || 'Viridis'
            }];
            break;
            
        default:
            throw new Error(`Unsupported chart type: ${chartConfig.type}`);
    }
    
    // Merge custom layout if provided
    if (chartConfig.layout && typeof chartConfig.layout === 'object') {
        layout = { ...layout, ...chartConfig.layout };
    }
    
    // Create the chart
    window.Plotly.newPlot(container, data, layout, {
        responsive: true,
        displayModeBar: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['lasso2d', 'select2d']
    });
}
