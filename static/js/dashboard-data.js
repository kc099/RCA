/**
 * Dashboard Data Processing Module
 * Provides functions for extracting and processing data for visualizations
 */

// Expose necessary functions to the global scope
window.DashboardData = {
    extractDashboardData,
    extractToolVisualization,
    convertMySQLOutputToMarkdown,
    parseMarkdownTable
};

/**
 * Extract dashboard visualization data from tool output
 * @param {string} content - The content to parse for dashboard data
 * @returns {Object|null} Dashboard data object or null if none found
 */
function extractDashboardData(content) {
    if (!content) return null;
    
    try {
        console.log('[RCA] Attempting to extract dashboard data');
        
        // Look for dashboard data pattern in tool output
        const jsonMatch = content.match(/Observed output of cmd.*?executed:\s*(\{.*?\})/s);
        if (jsonMatch) {
            const jsonStr = jsonMatch[1];
            try {
                const toolData = JSON.parse(jsonStr);
                
                // Check if this is dashboard data
                if (toolData.output && toolData.visualization_type === 'dashboard') {
                    console.log('[RCA] Found dashboard data in tool output');
                    
                    // If output is a string, try to parse it as JSON
                    let dashboardData;
                    if (typeof toolData.output === 'string') {
                        try {
                            dashboardData = JSON.parse(toolData.output);
                        } catch (e) {
                            console.error('[RCA] Error parsing dashboard data:', e);
                            return null;
                        }
                    } else if (typeof toolData.output === 'object') {
                        dashboardData = toolData.output;
                    }
                    
                    if (dashboardData) {
                        return {
                            type: 'dashboard',
                            title: dashboardData.title || 'Dashboard',
                            charts: dashboardData.charts || [],
                            id: toolData.id || `dashboard-${Date.now()}`
                        };
                    }
                }
                
                // Check if this is a chart that should be turned into a dashboard
                else if (toolData.output && toolData.visualization_type === 'chart') {
                    console.log('[RCA] Found chart data in tool output');
                    
                    // Parse chart data
                    let chartData;
                    if (typeof toolData.output === 'string') {
                        try {
                            chartData = JSON.parse(toolData.output);
                        } catch (e) {
                            console.error('[RCA] Error parsing chart data:', e);
                            return null;
                        }
                    } else if (typeof toolData.output === 'object') {
                        chartData = toolData.output;
                    }
                    
                    if (chartData && chartData.type) {
                        // Create a single-chart dashboard
                        return {
                            type: 'dashboard',
                            title: chartData.title || 'Chart',
                            charts: [chartData],
                            id: toolData.id || `chart-${Date.now()}`
                        };
                    }
                }
                
                // Check if we can create a chart from table data
                else if (toolData.output && typeof toolData.output === 'string' && 
                         toolData.output.trim().startsWith('[') && 
                         !toolData.visualization_type) {
                    console.log('[RCA] Found JSON array data, checking if suitable for chart');
                    
                    try {
                        const jsonArray = JSON.parse(toolData.output);
                        
                        // Check if this is an array of objects with numeric data
                        if (Array.isArray(jsonArray) && jsonArray.length > 0 && 
                            typeof jsonArray[0] === 'object') {
                            
                            // Get all keys from the first object
                            const keys = Object.keys(jsonArray[0]);
                            
                            // Try to find numeric columns for charting
                            const numericColumns = keys.filter(key => {
                                // Check if at least 80% of values are numeric
                                const numericCount = jsonArray.reduce((count, item) => {
                                    const val = item[key];
                                    // Check if value is a number or can be parsed as a number
                                    return count + ((!isNaN(val) || !isNaN(parseFloat(val))) ? 1 : 0);
                                }, 0);
                                
                                return (numericCount / jsonArray.length) >= 0.8;
                            });
                            
                            // Find potential category columns (non-numeric)
                            const categoryColumns = keys.filter(key => !numericColumns.includes(key));
                            
                            // If we have both numeric and category columns, we can create a chart
                            if (numericColumns.length > 0 && categoryColumns.length > 0) {
                                console.log('[RCA] Data suitable for charting', { 
                                    numericColumns, 
                                    categoryColumns 
                                });
                                
                                // Choose the first category column for x-axis
                                const xAxis = categoryColumns[0];
                                
                                // Create charts for each numeric column
                                const charts = numericColumns.map(numCol => {
                                    return {
                                        type: 'bar',  // Default to bar chart
                                        title: `${xAxis} vs ${numCol}`,
                                        x: jsonArray.map(item => item[xAxis]),
                                        y: jsonArray.map(item => {
                                            const val = item[numCol];
                                            return isNaN(val) ? parseFloat(val) : val;
                                        }),
                                        xaxis: { title: xAxis },
                                        yaxis: { title: numCol }
                                    };
                                });
                                
                                return {
                                    type: 'dashboard',
                                    title: 'Auto-generated Charts',
                                    charts: charts,
                                    id: toolData.id || `auto-chart-${Date.now()}`
                                };
                            }
                        }
                    } catch (e) {
                        console.error('[RCA] Error analyzing JSON data for charts:', e);
                    }
                }
            } catch (e) {
                console.error('[RCA] Error parsing JSON from tool output:', e);
            }
        }
    } catch (error) {
        console.error('[RCA] Error extracting dashboard data:', error);
    }
    
    return null;
}

/**
 * Extract table visualization from tool output
 * @param {string} content - The content to parse for table data
 * @returns {Object|null} Table data object or null if none found
 */
function extractToolVisualization(content) {
    if (!content) return null;
    
    try {
        console.log('[RCA] Attempting to extract visualization from content');
        
        // Try different extraction methods
        
        // Method 1: Direct JSON pattern in tool output
        const jsonMatch = content.match(/Observed output of cmd.*?executed:\s*(\{.*?\})/s);
        if (jsonMatch) {
            const jsonStr = jsonMatch[1];
            console.log('[RCA] Found JSON in tool output');
            try {
                const toolData = JSON.parse(jsonStr);
                
                // Check if this has visualization data
                if (toolData.output) {
                    // For MySQL tables or other tabular data
                    if (toolData.visualization_type === 'table' || 
                       (toolData.output.includes('+-') && toolData.output.includes('-+') && toolData.output.includes('|'))) {
                        
                        console.log('[RCA] Detected MySQL table format in output');
                        const markdownTable = convertMySQLOutputToMarkdown(toolData.output);
                        if (markdownTable) {
                            const parsedTable = parseMarkdownTable(markdownTable);
                            if (parsedTable && parsedTable.headers && parsedTable.rows.length > 0) {
                                console.log('[RCA] Successfully parsed table data');
                                return {
                                    type: 'table',
                                    title: 'Query Result',
                                    content: parsedTable,
                                    id: toolData.id || null,
                                    originalMarkdown: markdownTable,
                                    toolOutput: toolData.output
                                };
                            }
                        }
                    }
                    
                    // Check if this is a JSON array that can be rendered as a table
                    else if (typeof toolData.output === 'string' && toolData.output.trim().startsWith('[')) {
                        try {
                            const jsonArray = JSON.parse(toolData.output);
                            if (Array.isArray(jsonArray) && jsonArray.length > 0 && typeof jsonArray[0] === 'object') {
                                console.log('[RCA] Found JSON array data, converting to table');
                                
                                // Extract headers from the first object's keys
                                const headers = Object.keys(jsonArray[0]);
                                
                                // Convert array of objects to rows
                                const rows = jsonArray.map(item => {
                                    return headers.map(key => {
                                        const val = item[key];
                                        if (val === null || val === undefined) return '';
                                        return val.toString();
                                    });
                                });
                                
                                return {
                                    type: 'table',
                                    title: toolData.title || 'Data',
                                    content: { headers, rows },
                                    id: toolData.id || `json-table-${Date.now()}`,
                                    sourceData: jsonArray
                                };
                            }
                        } catch (e) {
                            console.error('[RCA] Error parsing JSON data:', e);
                        }
                    }
                }
            } catch (e) {
                console.error('[RCA] Error parsing JSON from tool output:', e);
            }
        }
        
        // Method 2: Look for MySQL output format directly
        if (content.includes('+---') && content.includes('|')) {
            const tableLines = content.split('\n').filter(line => 
                line.includes('|') || line.includes('+---'));
            
            if (tableLines.length > 2) {
                const tableText = tableLines.join('\n');
                console.log('[RCA] Found MySQL table format directly');
                
                const markdownTable = convertMySQLOutputToMarkdown(tableText);
                if (markdownTable) {
                    const parsedTable = parseMarkdownTable(markdownTable);
                    if (parsedTable && parsedTable.headers && parsedTable.rows.length > 0) {
                        return {
                            type: 'table',
                            title: 'Query Result',
                            content: parsedTable,
                            id: `direct-table-${Date.now()}`,
                            originalMarkdown: markdownTable,
                            toolOutput: tableText
                        };
                    }
                }
            }
        }
        
        // Method 3: Look for Step content with mysql_rw execution
        const stepMatch = content.match(/Step \d+: Observed output of cmd `mysql_rw` executed:\s*(\{.*?\})/s);
        if (stepMatch) {
            const jsonStr = stepMatch[1];
            console.log('[RCA] Found mysql_rw output in step content');
            
            try {
                const toolData = JSON.parse(jsonStr);
                if (toolData.output && (toolData.output.includes('+-') || toolData.output.includes('|'))) {
                    const markdownTable = convertMySQLOutputToMarkdown(toolData.output);
                    if (markdownTable) {
                        const parsedTable = parseMarkdownTable(markdownTable);
                        if (parsedTable && parsedTable.headers && parsedTable.rows.length > 0) {
                            console.log('[RCA] Successfully parsed step table data');
                            return {
                                type: 'table',
                                title: 'Query Result',
                                content: parsedTable,
                                id: toolData.id || `step-table-${Date.now()}`,
                                originalMarkdown: markdownTable,
                                toolOutput: toolData.output
                            };
                        }
                    }
                }
            } catch (e) {
                console.error('[RCA] Error parsing JSON from step output:', e);
            }
        }
    } catch (error) {
        console.error('[RCA] Error extracting tool visualization:', error);
    }
    
    return null;
}

/**
 * Convert MySQL output to markdown table format
 * @param {string} mysqlOutput - The MySQL output to convert
 * @returns {string|null} Markdown table or null if conversion fails
 */
function convertMySQLOutputToMarkdown(mysqlOutput) {
    try {
        if (!mysqlOutput) return null;
        
        // Split the MySQL output into lines
        let lines = mysqlOutput.split('\n');
        
        // Filter out empty lines and keep only rows with data or separator lines
        lines = lines.filter(line => line.trim().length > 0);
        
        if (lines.length < 3) {
            console.log('[RCA] Not enough lines for a valid table');
            return null; // Not enough lines for a valid table
        }
        
        // Initialize markdown table lines
        const markdownLines = [];
        
        // Process header line (second line, after the top border)
        const headerLine = lines.find(line => line.includes('|') && !line.includes('+-'));
        if (!headerLine) {
            console.log('[RCA] No header line found in MySQL output');
            return null;
        }
        
        // Extract headers from the header line
        const headers = headerLine.split('|')
            .map(h => h.trim())
            .filter(h => h.length > 0);
        
        if (headers.length === 0) {
            console.log('[RCA] No valid headers found');
            return null;
        }
        
        // Add headers to markdown
        markdownLines.push(`| ${headers.join(' | ')} |`);
        
        // Add separator line
        markdownLines.push(`| ${headers.map(() => '---').join(' | ')} |`);
        
        // Process data rows (all lines that have | but are not headers or separator lines)
        const dataLines = lines.filter(line => 
            line.includes('|') && 
            !line.includes('+-') && 
            line !== headerLine
        );
        
        // Add data rows to markdown
        dataLines.forEach(line => {
            const cells = line.split('|')
                .map(c => c.trim())
                .filter(c => c.length > 0);
            
            if (cells.length > 0) {
                markdownLines.push(`| ${cells.join(' | ')} |`);
            }
        });
        
        // Make sure we have at least one data row
        if (markdownLines.length < 3) {
            console.log('[RCA] No data rows found');
            return null;
        }
        
        return markdownLines.join('\n');
    } catch (error) {
        console.error('[RCA] Error converting MySQL output to markdown:', error);
        return null;
    }
}

/**
 * Parse markdown table into structured data
 * @param {string} markdownTable - The markdown table to parse
 * @returns {Object|null} Parsed table data object or null if parsing fails
 */
function parseMarkdownTable(markdownTable) {
    if (!markdownTable) return null;
    
    try {
        const lines = markdownTable.trim().split('\n');
        if (lines.length < 3) return null; // Need at least header, separator, and one data row
        
        // Parse headers (first row)
        const headerLine = lines[0];
        const headers = headerLine.split('|')
            .map(h => h.trim())
            .filter(h => h.length > 0);
        
        if (headers.length === 0) return null;
        
        // Skip the separator line (line[1])
        
        // Parse data rows
        const rows = [];
        for (let i = 2; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line || !line.includes('|')) continue;
            
            const cells = line.split('|')
                .map(c => c.trim())
                .filter(c => c.length > 0);
            
            if (cells.length > 0) {
                rows.push(cells);
            }
        }
        
        return { headers, rows };
    } catch (error) {
        console.error('[RCA] Error parsing markdown table:', error);
        return null;
    }
}
