"""Excel Agent for interacting with Excel spreadsheets."""

import logging
from typing import Any, Dict, List, Optional, Union, Tuple

from app.agent.toolcall import ToolCallAgent
from app.tool.excel_tool import ExcelTool
from app.tool.tool_collection import ToolCollection

logger = logging.getLogger(__name__)

EXCEL_AGENT_SYSTEM_PROMPT = """You are an Excel assistant capable of manipulating Excel spreadsheets.
You can perform operations such as:
- Creating, opening, and saving workbooks
- Managing sheets within workbooks
- Updating cells and ranges
- Applying formulas and sorting data
- Retrieving data from cells and ranges
- Searching for specific content within sheets

When working with Excel data, always:
1. Ensure workbooks are opened before attempting operations
2. Properly handle errors and edge cases
3. Provide clear explanations of actions taken
4. Use cell references in A1 notation (e.g., A1, B2, AA10)
"""

class ExcelAgent(ToolCallAgent):
    """Agent specialized for Excel manipulation tasks."""
    
    name: str = "excel_agent"
    description: str = "An agent that can manipulate Excel spreadsheets"
    system_prompt: str = EXCEL_AGENT_SYSTEM_PROMPT
    
    def __init__(self, **kwargs):
        """Initialize the Excel agent with the Excel tool."""
        # Create the Excel tool
        excel_tool = ExcelTool()
        
        # Create a tool collection with the Excel tool
        available_tools = ToolCollection(excel_tool)
        
        # Initialize the agent with the Excel tool
        super().__init__(
            name="excel_agent",
            description="An agent that can manipulate Excel spreadsheets",
            system_prompt=EXCEL_AGENT_SYSTEM_PROMPT,
            available_tools=available_tools,
            **kwargs
        )
        
    async def manipulate_excel(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an Excel action using the Excel tool.
        
        Args:
            action: The Excel action to perform.
            params: Parameters specific to the action.
            
        Returns:
            The result of the Excel operation.
        """
        try:
            # Create a tool call for the Excel tool
            result = await self.available_tools.tools["excel_tool"].execute(
                action=action,
                params=params
            )
            return result
        except Exception as e:
            logger.exception(f"Error executing Excel action {action}: {e}")
            return {"error": f"Error: {str(e)}"}
