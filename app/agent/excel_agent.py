"""Excel Agent for interacting with Excel spreadsheets."""

import logging
from typing import Any, Dict, List, Optional, Union, Tuple

from pydantic import Field

from app.agent.browser import BrowserAgent
from app.logger import logger
from app.prompt.excel import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.schema import Message, ToolChoice
from app.tool.excel_tool import ExcelTool
from app.tool.terminate import Terminate
from app.tool.tool_collection import ToolCollection


class ExcelAgent(BrowserAgent):
    """Agent specialized for Excel manipulation tasks.
    
    This agent extends BrowserAgent with Excel-specific capabilities
    to manipulate Excel workbooks, sheets, and cells.
    """
    
    name: str = "excel_agent"
    description: str = "An agent that can manipulate Excel spreadsheets"
    
    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT
    
    max_observe: int = 10000
    max_steps: int = 20
    
    # Configure the available tools
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            ExcelTool(), 
            Terminate()
        )
    )
    
    # Use Auto for tool choice to allow both tool usage and free-form responses
    tool_choices: ToolChoice = ToolChoice.AUTO
    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])
    
    async def _handle_special_tool(self, name: str, result: Any, **kwargs):
        """Handle special tools like terminate."""
        if not self._is_special_tool(name):
            return
        else:
            # Clean up any resources if needed
            await super()._handle_special_tool(name, result, **kwargs)
    
    async def get_excel_state(self) -> Optional[Dict[str, Any]]:
        """Get the current Excel state for context in next steps."""
        excel_tool = self.available_tools.get_tool(ExcelTool().name)
        if not excel_tool:
            return None
            
        try:
            # You could implement state tracking here if needed
            return {
                "status": "active",
                "tool_name": excel_tool.name
            }
        except Exception as e:
            logger.error(f"Error getting Excel state: {e}")
            return None
    
    async def think(self) -> bool:
        """Process current state and decide next actions using tools."""
        # Get Excel state for context
        excel_state = await self.get_excel_state()
        
        # Add Excel state to the context if available
        if excel_state:
            context_msg = Message.system_message(
                f"Current Excel state: {excel_state}"
            )
            self.messages.append(context_msg)
            
        # Use the parent class's think method to handle the rest
        return await super().think()
    
    async def execute_excel_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an Excel action using the Excel tool.
        
        Args:
            action: The Excel action to perform.
            params: Parameters specific to the action.
            
        Returns:
            The result of the Excel operation.
        """
        try:
            excel_tool = self.available_tools.get_tool(ExcelTool().name)
            if not excel_tool:
                return {"error": "Excel tool not available"}
                
            # Execute the action
            result = await excel_tool.execute(action=action, params=params)
            return result
        except Exception as e:
            logger.exception(f"Error executing Excel action {action}: {e}")
            return {"error": f"Error: {str(e)}"}
