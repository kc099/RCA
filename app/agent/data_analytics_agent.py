"""
Data Analytics Agent Module

This module provides a specialized agent focused solely on data analytics tasks,
with content moderation to filter out non-analytics requests.
"""

from typing import Optional, List

from pydantic import Field

from app.agent.manus import Manus
from app.filter.data_analytics_filter import DataAnalyticsFilter
from app.logger import logger
from app.schema import AgentState
from app.tool import ToolCollection
from app.tool.python_execute import PythonExecute
from app.tool.excel_tool import ExcelTool
from app.tool.str_replace_editor import StrReplaceEditor
from app.tool.terminate import Terminate


class DataAnalyticsAgent(Manus):
    """
    A specialized agent focused exclusively on data analytics tasks.
    
    This agent extends Manus but includes a moderation layer to ensure
    only data analytics related queries are processed.
    """

    name: str = "DataAnalyticsAgent"
    description: str = "An agent specialized in data analytics tasks only"
    
    # Add a data analytics filter
    filter: DataAnalyticsFilter = Field(default_factory=DataAnalyticsFilter)
    
    # Override the system prompt to focus on analytics
    system_prompt: str = (
        "You are DataAnalyticsAgent, a specialized AI assistant focused exclusively on data analytics tasks. "
        "You can help users analyze data, create visualizations, perform statistical analysis, "
        "clean and transform datasets, and derive insights from numerical information. "
        "You should decline non-analytics related requests politely, explaining that you're "
        "specialized in data analytics tasks."
    )
    
    # Override available tools to include only data analytics relevant tools
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            PythonExecute(), ExcelTool(), StrReplaceEditor(), Terminate()
        )
    )
    
    # Customized prompt for specialized data analytics focus
    next_step_prompt: str = (
        "Based on the data analytics request, determine the appropriate next steps. "
        "Consider which analytical techniques or tools would be most suitable for "
        "processing the data and extracting meaningful insights."
    )
    
    # Track whether the current request is analytics-related
    _is_analytics_request: bool = False
    
    # Custom filter keywords
    custom_analytics_keywords: Optional[List[str]] = None
    custom_non_analytics_keywords: Optional[List[str]] = None
    filter_threshold: float = 0.6
    
    def __init__(self, **data):
        """Initialize the DataAnalyticsAgent with custom settings."""
        super().__init__(**data)
        
        # Initialize filter with custom keywords if provided
        custom_analytics = data.get("custom_analytics_keywords", self.custom_analytics_keywords)
        custom_non_analytics = data.get("custom_non_analytics_keywords", self.custom_non_analytics_keywords)
        threshold = data.get("filter_threshold", self.filter_threshold)
        
        self.filter = DataAnalyticsFilter(
            custom_analytics_keywords=custom_analytics,
            custom_non_analytics_keywords=custom_non_analytics,
            threshold=threshold
        )
        
    async def run(self, request: Optional[str] = None) -> str:
        """
        Execute the agent's main loop with content moderation.
        
        Args:
            request: Optional initial user request to process.
            
        Returns:
            A string summarizing the execution results or rejection message.
        """
        if not request:
            return "No request provided."
        
        # Check if the request is analytics-related
        is_analytics, analysis = self.filter.is_data_analytics_query(request)
        self._is_analytics_request = is_analytics
        
        # Log the analysis results
        logger.info(f"Request analysis: {analysis}")
        
        if not is_analytics:
            # Generate rejection message
            rejection_message = self.filter.get_rejection_message(request, analysis)
            
            # Add messages to memory for context
            self.update_memory("user", request)
            self.update_memory("assistant", rejection_message)
            
            # Return rejection message directly
            return rejection_message
        
        # If request is analytics-related, proceed with normal execution
        return await super().run(request)
    
    async def think(self) -> bool:
        """
        Process current state and decide next actions with analytics focus.
        
        Returns:
            Boolean indicating if action should be taken
        """
        # If the current request isn't analytics-related, skip normal processing
        if not self._is_analytics_request:
            self.state = AgentState.FINISHED
            return False
        
        # Call the parent think method for normal processing
        return await super().think()
