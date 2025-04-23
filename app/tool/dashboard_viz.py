"""Dashboard visualization tool for RCA.

This tool creates visualizations like charts and dashboards from various data sources.
It integrates with Plotly and provides output that can be rendered in the visualization panel.
"""

import json
import csv
import os
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from app.tool.base import BaseTool, ToolResult
from app.logger import logger


class DashboardVizTool(BaseTool):
    """Tool for creating dashboard visualizations from data."""

    name: str = "dashboard_viz"
    description: str = "Create visualizations like charts and dashboards from data sources."
    
    # Default chart configuration
    _default_colors = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"
    ]
    
    def __init__(self):
        """Initialize the dashboard visualization tool."""
        super().__init__(
            name="dashboard_viz",
            description="Create visualizations like charts and dashboards from data sources."
        )
        
        # Define parameters schema
        self.parameters = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "The visualization action to perform",
                    "enum": [
                        "create_chart", "create_dashboard", "create_bar_chart", 
                        "create_line_chart", "create_pie_chart", "create_scatter_plot",
                        "visualize_json", "visualize_csv"
                    ]
                },
                "title": {
                    "type": "string",
                    "description": "Title for the visualization"
                },
                "data": {
                    "oneOf": [
                        {"type": "string", "description": "JSON or CSV data to visualize (as a string)"},
                        {"type": "array", "description": "Data as a list of objects"},
                        {"type": "object", "description": "Data as a single object"}
                    ],
                    "description": "Data to visualize (as a string, list, or object)"
                },
                "data_file": {
                    "type": "string",
                    "description": "Path to a JSON or CSV file containing data to visualize"
                },
                "chart_type": {
                    "type": "string",
                    "description": "Type of chart to create",
                    "enum": ["bar", "line", "pie", "scatter", "heatmap"]
                },
                "x_axis": {
                    "type": "string",
                    "description": "Field name to use for the x-axis"
                },
                "y_axis": {
                    "type": "string",
                    "description": "Field name to use for the y-axis"
                },
                "category_field": {
                    "type": "string",
                    "description": "Field name to use for data categorization"
                },
                "value_field": {
                    "type": "string",
                    "description": "Field name to use for numeric values"
                },
                "charts": {
                    "type": "array",
                    "description": "List of chart configurations for a dashboard",
                    "items": {
                        "type": "object"
                    }
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the visualization action with the given parameters.
        
        Args:
            action: The visualization action to perform.
            Other parameters depend on the specific action.
            
        Returns:
            Dict with visualization data or error message.
        """
        try:
            action = kwargs.get("action")
            if not action:
                return ToolResult(error="Missing required parameter: action").dict()
            
            # Handle different visualization actions
            if action == "create_chart":
                return await self._create_chart(**kwargs)
            elif action == "create_dashboard":
                return await self._create_dashboard(**kwargs)
            elif action == "create_bar_chart":
                return await self._create_bar_chart(**kwargs)
            elif action == "create_line_chart":
                return await self._create_line_chart(**kwargs)
            elif action == "create_pie_chart":
                return await self._create_pie_chart(**kwargs)
            elif action == "create_scatter_plot":
                return await self._create_scatter_plot(**kwargs)
            elif action == "visualize_json":
                return await self._visualize_json(**kwargs)
            elif action == "visualize_csv":
                return await self._visualize_csv(**kwargs)
            else:
                return ToolResult(error=f"Unknown action: {action}").dict()
        except Exception as e:
            logger.exception(f"Error executing dashboard visualization action: {e}")
            return ToolResult(error=f"Error executing visualization: {str(e)}").dict()
    
    async def _create_chart(self, **kwargs) -> Dict[str, Any]:
        """Create a single chart based on the provided parameters."""
        try:
            # Get chart parameters
            chart_type = kwargs.get("chart_type")
            if not chart_type:
                return ToolResult(error="Missing required parameter: chart_type").dict()
            
            title = kwargs.get("title", f"{chart_type.capitalize()} Chart")
            
            # Get data from either direct data or file
            data = await self._get_data(kwargs)
            if not data:
                return ToolResult(error="No data provided. Use either 'data' or 'data_file' parameter.").dict()
            
            # Create chart configuration based on type
            chart_config = {
                "type": chart_type,
                "title": title
            }
            
            # Handle different chart types
            if chart_type in ["bar", "line", "scatter"]:
                x_axis = kwargs.get("x_axis")
                y_axis = kwargs.get("y_axis")
                
                if not x_axis or not y_axis:
                    # Auto-detect fields if not specified
                    if len(data) > 0 and isinstance(data[0], dict):
                        fields = list(data[0].keys())
                        
                        # Try to find suitable fields for x and y axes
                        numeric_fields = []
                        non_numeric_fields = []
                        
                        for field in fields:
                            # Check the first non-null value to determine field type
                            field_value = next((item.get(field) for item in data if item.get(field) is not None), None)
                            if field_value is not None and (isinstance(field_value, (int, float)) or 
                                                          (isinstance(field_value, str) and field_value.replace('.', '', 1).isdigit())):
                                numeric_fields.append(field)
                            else:
                                non_numeric_fields.append(field)
                        
                        if not x_axis and non_numeric_fields:
                            x_axis = non_numeric_fields[0]
                        
                        if not y_axis and numeric_fields:
                            y_axis = numeric_fields[0]
                    
                    if not x_axis or not y_axis:
                        return ToolResult(error="Missing required parameters: x_axis and y_axis").dict()
                
                # Extract x and y values
                chart_config["x"] = [item.get(x_axis) for item in data]
                chart_config["y"] = [item.get(y_axis) for item in data]
                chart_config["xaxis"] = {"title": x_axis}
                chart_config["yaxis"] = {"title": y_axis}
                
            elif chart_type == "pie":
                category_field = kwargs.get("category_field")
                value_field = kwargs.get("value_field")
                
                if not category_field or not value_field:
                    # Auto-detect fields if not specified
                    if len(data) > 0 and isinstance(data[0], dict):
                        fields = list(data[0].keys())
                        
                        # Try to find suitable fields for categories and values
                        numeric_fields = []
                        non_numeric_fields = []
                        
                        for field in fields:
                            # Check the first non-null value to determine field type
                            field_value = next((item.get(field) for item in data if item.get(field) is not None), None)
                            if field_value is not None and (isinstance(field_value, (int, float)) or 
                                                          (isinstance(field_value, str) and field_value.replace('.', '', 1).isdigit())):
                                numeric_fields.append(field)
                            else:
                                non_numeric_fields.append(field)
                        
                        if not category_field and non_numeric_fields:
                            category_field = non_numeric_fields[0]
                        
                        if not value_field and numeric_fields:
                            value_field = numeric_fields[0]
                    
                    if not category_field or not value_field:
                        return ToolResult(error="Missing required parameters: category_field and value_field").dict()
                
                # Extract labels and values
                chart_config["labels"] = [item.get(category_field) for item in data]
                chart_config["values"] = [item.get(value_field) for item in data]
            
            # Create the result - using ToolResult to ensure consistent format with visualization_type
            result = ToolResult(
                output=chart_config,
                visualization_type="chart"
            ).dict()
            
            return result
        except Exception as e:
            logger.exception(f"Error creating chart: {e}")
            return ToolResult(error=f"Error creating chart: {str(e)}").dict()
    
    async def _create_dashboard(self, **kwargs) -> Dict[str, Any]:
        """Create a dashboard with multiple charts."""
        try:
            title = kwargs.get("title", "Dashboard")
            
            # Get chart configurations 
            charts = kwargs.get("charts", [])
            
            if not charts:
                # If no charts are specified, try to auto-generate from data
                data = await self._get_data(kwargs)
                if not data:
                    return ToolResult(error="No data provided and no chart configurations specified.").dict()
                
                # Auto-generate appropriate charts based on data
                charts = await self._auto_generate_charts(data, title)
                
                if not charts:
                    return ToolResult(error="Could not auto-generate charts from the provided data.").dict()
            
            # Create dashboard configuration
            dashboard_config = {
                "title": title,
                "charts": charts
            }
            
            # Return the result
            result = ToolResult(
                output=dashboard_config,
                visualization_type="dashboard"
            ).dict()
            
            return result
        except Exception as e:
            logger.exception(f"Error creating dashboard: {e}")
            return ToolResult(error=f"Error creating dashboard: {str(e)}").dict()
    
    async def _create_bar_chart(self, **kwargs) -> Dict[str, Any]:
        """Create a bar chart."""
        kwargs["chart_type"] = "bar"
        return await self._create_chart(**kwargs)
    
    async def _create_line_chart(self, **kwargs) -> Dict[str, Any]:
        """Create a line chart."""
        kwargs["chart_type"] = "line"
        return await self._create_chart(**kwargs)
    
    async def _create_pie_chart(self, **kwargs) -> Dict[str, Any]:
        """Create a pie chart."""
        kwargs["chart_type"] = "pie"
        return await self._create_chart(**kwargs)
    
    async def _create_scatter_plot(self, **kwargs) -> Dict[str, Any]:
        """Create a scatter plot."""
        kwargs["chart_type"] = "scatter"
        return await self._create_chart(**kwargs)
    
    async def _visualize_json(self, **kwargs) -> Dict[str, Any]:
        """Create visualizations from JSON data."""
        try:
            title = kwargs.get("title", "JSON Visualization")
            
            # Get data from either direct data or file
            data = await self._get_data(kwargs)
            if not data:
                return ToolResult(error="No data provided. Use either 'data' or 'data_file' parameter.").dict()
            
            # Auto-generate appropriate charts based on data
            charts = await self._auto_generate_charts(data, title)
            
            if not charts:
                return ToolResult(error="Could not generate visualizations from the provided JSON data.").dict()
            
            # Create result
            result = ToolResult(
                output={
                    "title": title,
                    "charts": charts
                },
                visualization_type="dashboard"
            ).dict()
            
            return result
        except Exception as e:
            logger.exception(f"Error visualizing JSON: {e}")
            return ToolResult(error=f"Error visualizing JSON: {str(e)}").dict()
    
    async def _visualize_csv(self, **kwargs) -> Dict[str, Any]:
        """Create visualizations from CSV data."""
        try:
            title = kwargs.get("title", "CSV Visualization")
            
            # Get data 
            data = await self._get_data(kwargs)
            if not data:
                return ToolResult(error="No data provided. Use either 'data' or 'data_file' parameter.").dict()
            
            # Convert any string numeric values to actual numbers
            data = self._convert_numeric_values(data)
            
            # Auto-generate appropriate charts based on data
            charts = await self._auto_generate_charts(data, title)
            
            if not charts:
                return ToolResult(error="Could not generate visualizations from the provided CSV data.").dict()
            
            # Create result
            result = ToolResult(
                output={
                    "title": title,
                    "charts": charts
                },
                visualization_type="dashboard"
            ).dict()
            
            return result
        except Exception as e:
            logger.exception(f"Error visualizing CSV: {e}")
            return ToolResult(error=f"Error visualizing CSV: {str(e)}").dict()
    
    async def _get_data(self, kwargs) -> List[Dict]:
        """Get data from provided parameters, either direct data or from a file."""
        try:
            data_input = kwargs.get("data")
            data_file = kwargs.get("data_file")
            
            if data_input:
                # First check if it's already a Python object (list or dict)
                if isinstance(data_input, list):
                    return data_input
                elif isinstance(data_input, dict):
                    return [data_input]
                
                # Otherwise, treat it as a string and try to parse
                try:
                    data = json.loads(data_input)
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        # If data is a dictionary, wrap it in a list
                        return [data]
                except json.JSONDecodeError:
                    # Try parsing as CSV
                    try:
                        reader = csv.DictReader(data_input.splitlines())
                        data = list(reader)
                        return self._convert_numeric_values(data)
                    except Exception as csv_error:
                        logger.error(f"Error parsing data as CSV: {csv_error}")
                        return []
            
            elif data_file:
                if os.path.exists(data_file):
                    # Detect file type by extension
                    if data_file.lower().endswith('.json'):
                        with open(data_file, 'r') as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                return data
                            elif isinstance(data, dict):
                                return [data]
                    elif data_file.lower().endswith('.csv'):
                        with open(data_file, 'r') as f:
                            reader = csv.DictReader(f)
                            data = list(reader)
                            return self._convert_numeric_values(data)
                else:
                    logger.error(f"Data file not found: {data_file}")
            
            return []
        except Exception as e:
            logger.exception(f"Error getting data: {e}")
            return []
    
    def _convert_numeric_values(self, data: List[Dict]) -> List[Dict]:
        """Convert string numeric values to actual numbers."""
        result = []
        for item in data:
            converted_item = {}
            for key, value in item.items():
                if isinstance(value, str):
                    # Try to convert to number if it looks like one
                    if value.replace('.', '', 1).isdigit():
                        try:
                            if '.' in value:
                                converted_item[key] = float(value)
                            else:
                                converted_item[key] = int(value)
                            continue
                        except ValueError:
                            pass
                converted_item[key] = value
            result.append(converted_item)
        return result
    
    async def _auto_generate_charts(self, data: List[Dict], title: str) -> List[Dict]:
        """Auto-generate appropriate charts based on the data structure."""
        if not data or not isinstance(data, list) or not isinstance(data[0], dict):
            return []
        
        charts = []
        fields = list(data[0].keys())
        
        # Determine field types
        numeric_fields = []
        non_numeric_fields = []
        
        for field in fields:
            # Check the first non-null value to determine field type
            field_value = next((item.get(field) for item in data if item.get(field) is not None), None)
            if field_value is not None and (isinstance(field_value, (int, float)) or 
                                          (isinstance(field_value, str) and field_value.replace('.', '', 1).isdigit())):
                numeric_fields.append(field)
            else:
                non_numeric_fields.append(field)
        
        # If we have both numeric and non-numeric fields, create meaningful charts
        if numeric_fields and non_numeric_fields:
            # Create one bar chart for each category-value combination
            for category_field in non_numeric_fields[:2]:  # Limit to first 2 category fields
                for value_field in numeric_fields[:3]:  # Limit to first 3 numeric fields
                    chart = {
                        "type": "bar",
                        "title": f"{category_field} vs {value_field}",
                        "x": [item.get(category_field) for item in data],
                        "y": [item.get(value_field) for item in data],
                        "xaxis": {"title": category_field},
                        "yaxis": {"title": value_field}
                    }
                    charts.append(chart)
            
            # Create one pie chart if we have suitable fields
            if len(charts) > 0 and len(numeric_fields) > 0 and len(non_numeric_fields) > 0:
                category_field = non_numeric_fields[0]
                value_field = numeric_fields[0]
                
                # Create a dictionary to aggregate values by category
                aggregated = {}
                for item in data:
                    category = item.get(category_field)
                    value = item.get(value_field)
                    if category is not None and value is not None:
                        category_str = str(category)
                        if category_str in aggregated:
                            aggregated[category_str] += float(value) if isinstance(value, str) else value
                        else:
                            aggregated[category_str] = float(value) if isinstance(value, str) else value
                
                # Create pie chart
                if aggregated:
                    chart = {
                        "type": "pie",
                        "title": f"Distribution of {value_field} by {category_field}",
                        "labels": list(aggregated.keys()),
                        "values": list(aggregated.values())
                    }
                    charts.append(chart)
        
        # If only numeric fields are present, create scatter plots between pairs
        elif len(numeric_fields) >= 2:
            # Create scatter plots between pairs of numeric fields
            for i in range(min(len(numeric_fields) - 1, 2)):  # Limit to first 2 pairs
                x_field = numeric_fields[i]
                y_field = numeric_fields[i + 1]
                
                chart = {
                    "type": "scatter",
                    "title": f"{x_field} vs {y_field}",
                    "x": [item.get(x_field) for item in data],
                    "y": [item.get(y_field) for item in data],
                    "xaxis": {"title": x_field},
                    "yaxis": {"title": y_field}
                }
                charts.append(chart)
        
        # Create a line chart if there's a field that might be a date/time and a numeric field
        date_fields = [field for field in fields if any(date_hint in field.lower() 
                                                    for date_hint in ["date", "time", "day", "month", "year"])]
        if date_fields and numeric_fields:
            date_field = date_fields[0]
            value_field = numeric_fields[0]
            
            chart = {
                "type": "line",
                "title": f"{value_field} over {date_field}",
                "x": [item.get(date_field) for item in data],
                "y": [item.get(value_field) for item in data],
                "xaxis": {"title": date_field},
                "yaxis": {"title": value_field}
            }
            charts.append(chart)
            
        return charts
